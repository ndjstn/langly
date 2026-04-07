"""Auto tool runner for harness."""
from __future__ import annotations

import asyncio
import ast
import base64
import io
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Literal

import httpx
from pydantic import BaseModel


class ToolResult(BaseModel):
    name: str
    status: Literal["ok", "error", "skipped"]
    output: Any | None = None
    stdout: str | None = None
    stderr: str | None = None
    attempts: int = 1
    retries: int = 0
    cached: bool = False
    duration_ms: float = 0.0


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 0
    backoff_ms: int = 200

    def run(self, name: str, fn: Callable[[], ToolResult]) -> ToolResult:
        attempts = 0
        last: ToolResult | None = None
        while attempts <= self.max_retries:
            attempts += 1
            result = fn()
            result.attempts = attempts
            result.retries = self.max_retries
            last = result
            if result.status == "ok":
                return result
            if attempts <= self.max_retries:
                time.sleep((self.backoff_ms * attempts) / 1000)
        return last or ToolResult(name=name, status="error", attempts=attempts, retries=self.max_retries)


@dataclass(frozen=True)
class HarnessToolContext:
    message: str
    scope: dict[str, Any] | None
    cwd: Path


class ToolRunner:
    def __init__(self, name: str, retry_policy: RetryPolicy) -> None:
        self.name = name
        self.retry_policy = retry_policy

    def execute(self, context: HarnessToolContext) -> list[ToolResult]:
        return [self.retry_policy.run(self.name, lambda: self.run(context))]

    def run(self, context: HarnessToolContext) -> ToolResult:
        raise NotImplementedError


class MultiToolRunner(ToolRunner):
    def __init__(self, name: str, runners: Iterable[ToolRunner]) -> None:
        super().__init__(name, RetryPolicy())
        self.runners = list(runners)

    def execute(self, context: HarnessToolContext) -> list[ToolResult]:
        results: list[ToolResult] = []
        for runner in self.runners:
            results.extend(runner.execute(context))
        return results


class JJToolRunner(ToolRunner):
    def __init__(self, runners: Iterable[ToolRunner]) -> None:
        super().__init__("jj", RetryPolicy())
        self.runners = list(runners)

    def execute(self, context: HarnessToolContext) -> list[ToolResult]:
        if not (context.cwd / ".jj").exists():
            return [
                ToolResult(
                    name="jj",
                    status="skipped",
                    stderr="jj repo not initialized (run jj git init)",
                )
            ]
        results: list[ToolResult] = []
        for runner in self.runners:
            results.extend(runner.execute(context))
        return results


class CommandToolRunner(ToolRunner):
    def __init__(
        self,
        name: str,
        command_fn: Callable[[HarnessToolContext], list[str]],
        retry_policy: RetryPolicy,
        *,
        timeout: int = 30,
        cwd_fn: Callable[[HarnessToolContext], Path] | None = None,
    ) -> None:
        super().__init__(name, retry_policy)
        self.command_fn = command_fn
        self.timeout = timeout
        self.cwd_fn = cwd_fn

    def run(self, context: HarnessToolContext) -> ToolResult:
        start = time.time()
        cmd = self.command_fn(context)
        cwd = self.cwd_fn(context) if self.cwd_fn else None
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            duration_ms = (time.time() - start) * 1000
            status = "ok" if proc.returncode == 0 else "error"
            return ToolResult(
                name=" ".join(cmd),
                status=status,
                stdout=proc.stdout.strip(),
                stderr=proc.stderr.strip(),
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = (time.time() - start) * 1000
            return ToolResult(
                name=" ".join(cmd),
                status="error",
                stderr=str(exc),
                duration_ms=duration_ms,
            )


class LintToolRunner(ToolRunner):
    def __init__(self, retry_policy: RetryPolicy) -> None:
        super().__init__("lint", retry_policy)

    def run(self, context: HarnessToolContext) -> ToolResult:
        start = time.time()
        commands: list[list[str]] = []
        if shutil.which("uv"):
            commands.append(["uv", "run", "ruff", "check", "app", "tests"])
        if shutil.which("ruff"):
            commands.append(["ruff", "check", "app", "tests"])
        if shutil.which("python"):
            commands.append(["python", "-m", "ruff", "check", "app", "tests"])
        if not commands:
            return ToolResult(
                name="lint",
                status="error",
                stderr="ruff not available (install ruff or uv)",
                duration_ms=(time.time() - start) * 1000,
            )
        last_error = None
        for cmd in commands:
            proc = subprocess.run(
                cmd,
                cwd=str(context.cwd),
                capture_output=True,
                text=True,
                timeout=60,
            )
            duration_ms = (time.time() - start) * 1000
            if proc.returncode == 0:
                return ToolResult(
                    name="lint",
                    status="ok",
                    stdout=proc.stdout.strip(),
                    stderr=proc.stderr.strip(),
                    duration_ms=duration_ms,
                )
            last_error = proc.stderr.strip() or proc.stdout.strip()
            if last_error and "stub-ld" in last_error.lower():
                continue
        return ToolResult(
            name="lint",
            status="error",
            stderr=last_error or "ruff failed",
            duration_ms=(time.time() - start) * 1000,
        )


class GreptileToolRunner(ToolRunner):
    def __init__(self, greptile_dir: Path, retry_policy: RetryPolicy) -> None:
        super().__init__("greptile", retry_policy)
        self.greptile_dir = greptile_dir

    def run(self, context: HarnessToolContext) -> ToolResult:
        start = time.time()
        if not self.greptile_dir.exists():
            return ToolResult(
                name="greptile",
                status="error",
                stderr=f"greptile dir not found: {self.greptile_dir}",
            )
        try:
            tools = self._greptile_rpc({"jsonrpc": "2.0", "method": "tools/list"})
            tool_list = tools.get("result", {}).get("tools", tools.get("result", tools.get("tools", [])))
            selected = None
            for candidate in ("query_codebase", "search_code", "explain_code"):
                if any(t.get("name") == candidate for t in tool_list if isinstance(t, dict)):
                    selected = candidate
                    break
            output = {"tools": tool_list}
            if selected:
                args = {"query": context.message}
                response = self._greptile_rpc(
                    {
                        "jsonrpc": "2.0",
                        "method": "tools/call",
                        "params": {"name": selected, "arguments": args},
                    }
                )
                output["call"] = response.get("result", response)
            duration_ms = (time.time() - start) * 1000
            return ToolResult(
                name="greptile",
                status="ok",
                output=output,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = (time.time() - start) * 1000
            return ToolResult(
                name="greptile",
                status="error",
                stderr=str(exc),
                duration_ms=duration_ms,
            )

    def _greptile_rpc(self, payload: dict[str, Any]) -> dict[str, Any]:
        proc = subprocess.run(
            ["pnpm", "mcp:server"],
            cwd=str(self.greptile_dir),
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "greptile rpc failed")
        for line in reversed(proc.stdout.strip().splitlines()):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        raise RuntimeError("greptile rpc returned no json")


class TaskwarriorToolRunner(ToolRunner):
    def __init__(self, retry_policy: RetryPolicy) -> None:
        super().__init__("taskwarrior", retry_policy)

    def run(self, context: HarnessToolContext) -> ToolResult:
        start = time.time()
        if shutil.which("task") is None:
            return ToolResult(
                name="taskwarrior",
                status="error",
                stderr="taskwarrior not installed (task command not found)",
            )
        try:
            proc = subprocess.run(
                ["task", "rc.json.array=1", "rc.json.depends=1", "export"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            duration_ms = (time.time() - start) * 1000
            if proc.returncode != 0:
                return ToolResult(
                    name="taskwarrior",
                    status="error",
                    stdout=proc.stdout.strip(),
                    stderr=proc.stderr.strip(),
                    duration_ms=duration_ms,
                )
            raw = proc.stdout.strip() or "[]"
            try:
                tasks = json.loads(raw)
            except json.JSONDecodeError as exc:
                return ToolResult(
                    name="taskwarrior",
                    status="error",
                    stderr=f"task export parse failed: {exc}",
                    duration_ms=duration_ms,
                )
            if not isinstance(tasks, list):
                tasks = []
            summary: dict[str, int] = {}
            view: list[dict[str, Any]] = []
            fields = (
                "id",
                "uuid",
                "description",
                "status",
                "project",
                "priority",
                "due",
                "entry",
                "modified",
                "tags",
            )
            for task in tasks:
                if not isinstance(task, dict):
                    continue
                status = str(task.get("status", "unknown"))
                summary[status] = summary.get(status, 0) + 1
                view.append({k: task.get(k) for k in fields if task.get(k) is not None})
            view.sort(
                key=lambda item: item.get("modified") or item.get("entry") or "",
                reverse=True,
            )
            output = {
                "summary": summary,
                "count": len(tasks),
                "tasks": view[:100],
            }
            return ToolResult(
                name="taskwarrior",
                status="ok",
                output=output,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = (time.time() - start) * 1000
            return ToolResult(
                name="taskwarrior",
                status="error",
                stderr=str(exc),
                duration_ms=duration_ms,
            )


class MCPBrowserToolRunner(ToolRunner):
    def __init__(self, endpoint: str, retry_policy: RetryPolicy, *, name: str = "browser") -> None:
        super().__init__(name, retry_policy)
        self.endpoint = endpoint

    def run(self, context: HarnessToolContext) -> ToolResult:
        start = time.time()
        try:
            tool_list = self._rpc({"jsonrpc": "2.0", "method": "tools/list"})
            tools = tool_list.get("result", {}).get("tools", tool_list.get("tools", []))
            output: dict[str, Any] = {"tools": tools}

            script = self._load_script(context.message, tools)
            calls: list[dict[str, Any]] = []
            for action in script:
                result = self._rpc(
                    {
                        "jsonrpc": "2.0",
                        "method": "tools/call",
                        "params": {"name": action["name"], "arguments": action.get("arguments", {})},
                    }
                )
                calls.append({"name": action["name"], "result": result.get("result", result)})
            if calls:
                output["calls"] = calls
                vision = self._maybe_run_vision(calls)
                if vision:
                    output["vision"] = vision

            duration_ms = (time.time() - start) * 1000
            return ToolResult(name="browser", status="ok", output=output, duration_ms=duration_ms)
        except Exception as exc:
            duration_ms = (time.time() - start) * 1000
            return ToolResult(
                name="browser",
                status="error",
                stderr=str(exc),
                duration_ms=duration_ms,
            )

    def _rpc(self, payload: dict[str, Any]) -> dict[str, Any]:
        proc = subprocess.run(
            [
                "curl",
                "-sS",
                "-X",
                "POST",
                "-H",
                "Content-Type: application/json",
                "-d",
                json.dumps(payload),
                self.endpoint,
            ],
            capture_output=True,
            text=True,
            timeout=int(os.getenv("LANGLY_MCP_BROWSER_TIMEOUT_SEC", "30")),
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "browser rpc failed")
        raw = proc.stdout.strip() or "{}"
        return json.loads(raw)

    def _load_script(self, message: str, tools: Any) -> list[dict[str, Any]]:
        script_raw = os.getenv("LANGLY_MCP_BROWSER_SCRIPT", "").strip()
        if script_raw:
            try:
                script = json.loads(script_raw)
                return self._render_script(script, message)
            except json.JSONDecodeError:
                return []
        auto = os.getenv("LANGLY_MCP_BROWSER_AUTO", "false").lower() == "true"
        if not auto:
            return []
        return self._build_auto_script(message, tools)

    def _build_auto_script(self, message: str, tools: Any) -> list[dict[str, Any]]:
        url = _extract_first_url(message)
        if not url:
            return []
        tool_names = [tool.get("name") for tool in tools if isinstance(tool, dict)]
        nav_tool = next((name for name in tool_names if name and "navigate" in name), None)
        snap_tool = next(
            (name for name in tool_names if name and ("snapshot" in name or "screenshot" in name)),
            None,
        )
        script: list[dict[str, Any]] = []
        if nav_tool:
            script.append({"name": nav_tool, "arguments": {"url": url}})
        if snap_tool:
            script.append({"name": snap_tool, "arguments": {}})
        return script

    def _render_script(self, script: Any, message: str) -> list[dict[str, Any]]:
        if not isinstance(script, list):
            return []
        url = _extract_first_url(message)
        rendered: list[dict[str, Any]] = []
        for action in script:
            if not isinstance(action, dict) or "name" not in action:
                continue
            args = action.get("arguments", {})
            if isinstance(args, dict):
                args = {k: _replace_placeholders(v, url) for k, v in args.items()}
            rendered.append({"name": action["name"], "arguments": args})
        return rendered

    def _maybe_run_vision(self, calls: list[dict[str, Any]]) -> dict[str, Any] | None:
        cmd_template = os.getenv("LANGLY_VISION_PIPELINE_CMD", "").strip()
        if not cmd_template:
            return None
        images = _extract_image_paths(calls)
        if not images:
            return {"status": "skipped", "reason": "no_images_detected"}
        image = images[0]
        cmd = cmd_template.replace("{{image}}", image)
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=int(os.getenv("LANGLY_VISION_TIMEOUT_SEC", "30")),
            )
            return {
                "status": "ok" if proc.returncode == 0 else "error",
                "image": image,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
            }
        except Exception as exc:
            return {"status": "error", "image": image, "stderr": str(exc)}


class MCPTaskwarriorToolRunner(ToolRunner):
    def __init__(self, endpoint: str, retry_policy: RetryPolicy) -> None:
        super().__init__("taskwarrior_mcp", retry_policy)
        self.endpoint = endpoint

    def run(self, context: HarnessToolContext) -> ToolResult:
        start = time.time()
        try:
            tool_list = self._rpc({"jsonrpc": "2.0", "method": "tools/list"})
            tools = tool_list.get("result", {}).get("tools", tool_list.get("tools", []))
            output: dict[str, Any] = {"tools": tools}
            script = self._load_script(context.message, tools)
            calls: list[dict[str, Any]] = []
            for action in script:
                result = self._rpc(
                    {
                        "jsonrpc": "2.0",
                        "method": "tools/call",
                        "params": {"name": action["name"], "arguments": action.get("arguments", {})},
                    }
                )
                calls.append({"name": action["name"], "result": result.get("result", result)})
            if calls:
                output["calls"] = calls
            duration_ms = (time.time() - start) * 1000
            return ToolResult(name="taskwarrior_mcp", status="ok", output=output, duration_ms=duration_ms)
        except Exception as exc:
            duration_ms = (time.time() - start) * 1000
            return ToolResult(
                name="taskwarrior_mcp",
                status="error",
                stderr=str(exc),
                duration_ms=duration_ms,
            )

    def _rpc(self, payload: dict[str, Any]) -> dict[str, Any]:
        proc = subprocess.run(
            [
                "curl",
                "-sS",
                "-X",
                "POST",
                "-H",
                "Content-Type: application/json",
                "-d",
                json.dumps(payload),
                self.endpoint,
            ],
            capture_output=True,
            text=True,
            timeout=int(os.getenv("LANGLY_MCP_TASK_TIMEOUT_SEC", "30")),
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "taskwarrior mcp rpc failed")
        raw = proc.stdout.strip() or "{}"
        return json.loads(raw)

    def _load_script(self, message: str, tools: Any) -> list[dict[str, Any]]:
        script_raw = os.getenv("LANGLY_MCP_TASK_SCRIPT", "").strip()
        if script_raw:
            try:
                script = json.loads(script_raw)
                return script if isinstance(script, list) else []
            except json.JSONDecodeError:
                return []
        auto = os.getenv("LANGLY_MCP_TASK_AUTO", "false").lower() == "true"
        if not auto:
            return []
        tool_names = [tool.get("name") for tool in tools if isinstance(tool, dict)]
        list_tool = next((name for name in tool_names if name and "list" in name), None)
        if not list_tool:
            return []
        return [{"name": list_tool, "arguments": {}}]


class PreflightToolRunner(ToolRunner):
    def __init__(self, retry_policy: RetryPolicy) -> None:
        super().__init__("preflight", retry_policy)

    def run(self, context: HarnessToolContext) -> ToolResult:
        start = time.time()
        paths = _extract_paths(context.message)
        results: list[dict[str, Any]] = []
        for path in paths:
            info: dict[str, Any] = {"path": path}
            p = Path(path).expanduser()
            info["exists"] = p.exists()
            info["is_file"] = p.is_file()
            info["is_dir"] = p.is_dir()
            info["suffix"] = p.suffix
            info["readable"] = os.access(p, os.R_OK)
            if p.exists() and p.is_file():
                try:
                    info["size"] = p.stat().st_size
                    if p.suffix.lower() == ".py":
                        info["python_symbols"] = _scan_python_symbols(p)
                    if shutil.which("file"):
                        proc = subprocess.run(["file", "-b", str(p)], capture_output=True, text=True, timeout=5)
                        if proc.returncode == 0:
                            info["file_type"] = proc.stdout.strip()
                except Exception as exc:
                    info["error"] = str(exc)
            results.append(info)
        duration_ms = (time.time() - start) * 1000
        return ToolResult(name="preflight", status="ok", output={"files": results}, duration_ms=duration_ms)


class FileReadToolRunner(ToolRunner):
    def __init__(self, retry_policy: RetryPolicy) -> None:
        super().__init__("file_read", retry_policy)
        self.max_bytes = int(os.getenv("LANGLY_FILE_READ_MAX_BYTES", "20000"))
        self.max_files = int(os.getenv("LANGLY_FILE_READ_MAX_FILES", "2"))

    def run(self, context: HarnessToolContext) -> ToolResult:
        start = time.time()
        paths = _extract_paths(context.message)
        results: list[dict[str, Any]] = []
        for path in paths[: self.max_files]:
            p = Path(path).expanduser()
            if not p.exists() or not p.is_file():
                results.append({"path": path, "error": "file not found"})
                continue
            try:
                data = p.read_bytes()
                truncated = False
                if len(data) > self.max_bytes:
                    data = data[: self.max_bytes]
                    truncated = True
                if b"\x00" in data:
                    results.append({"path": str(p), "binary": True, "truncated": truncated})
                    continue
                text = data.decode("utf-8", errors="replace")
                results.append(
                    {
                        "path": str(p),
                        "truncated": truncated,
                        "lines": text.count("\n") + 1,
                        "content": text,
                    }
                )
            except Exception as exc:
                results.append({"path": str(p), "error": str(exc)})
        duration_ms = (time.time() - start) * 1000
        status = "ok" if results else "skipped"
        return ToolResult(name="file_read", status=status, output={"files": results}, duration_ms=duration_ms)


class VisionToolRunner(ToolRunner):
    def __init__(self, retry_policy: RetryPolicy) -> None:
        super().__init__("vision", retry_policy)
        self.model = os.getenv("LANGLY_VISION_MODEL", "granite3.2-vision:latest").strip()
        self.prompt = os.getenv(
            "LANGLY_VISION_PROMPT",
            "Describe the image, extract any text, and summarize key details.",
        )
        self.host = os.getenv("LANGLY_VISION_HOST", os.getenv("LANGLY_OLLAMA_HOST", "http://localhost:11434"))

    def run(self, context: HarnessToolContext) -> ToolResult:
        start = time.time()
        images = _extract_image_paths_from_message(context.message)
        if not images:
            return ToolResult(
                name="vision",
                status="skipped",
                stderr="no image paths found in message",
                duration_ms=(time.time() - start) * 1000,
            )
        if not self.model:
            return ToolResult(
                name="vision",
                status="error",
                stderr="LANGLY_VISION_MODEL is not set",
                duration_ms=(time.time() - start) * 1000,
            )
        outputs: list[dict[str, Any]] = []
        for image_path in images[: int(os.getenv("LANGLY_VISION_MAX_IMAGES", "2"))]:
            path = Path(image_path).expanduser()
            if not path.exists() or not path.is_file():
                outputs.append({"path": image_path, "error": "file not found"})
                continue
            try:
                data = path.read_bytes()
                encoded = base64.b64encode(data).decode("utf-8")
                payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": self.prompt}],
                    "images": [encoded],
                    "stream": False,
                }
                with httpx.Client(base_url=self.host, timeout=60) as client:
                    resp = client.post("/api/chat", json=payload)
                    resp.raise_for_status()
                    result = resp.json()
                outputs.append(
                    {
                        "path": str(path),
                        "response": result.get("message", {}).get("content", ""),
                        "model": self.model,
                    }
                )
            except Exception as exc:
                outputs.append({"path": str(path), "error": str(exc)})
        duration_ms = (time.time() - start) * 1000
        status = "ok" if any("response" in item for item in outputs) else "error"
        return ToolResult(
            name="vision",
            status=status,
            output={"results": outputs, "model": self.model},
            duration_ms=duration_ms,
        )


class VisionPipelineToolRunner(ToolRunner):
    def __init__(self, retry_policy: RetryPolicy) -> None:
        super().__init__("vision_pipeline", retry_policy)
        self.model = os.getenv("LANGLY_VISION_PIPELINE_MODEL", "yolov8n.pt").strip()
        self.seg_model = os.getenv("LANGLY_VISION_SEGMENT_MODEL", "").strip()
        self.confidence = float(os.getenv("LANGLY_VISION_CONFIDENCE", "0.25"))
        self.max_images = int(os.getenv("LANGLY_VISION_MAX_IMAGES", "2"))
        self.max_objects = int(os.getenv("LANGLY_VISION_MAX_OBJECTS", "25"))
        self._detector = None
        self._segmenter = None

    def _load_model(self, model_name: str):
        from ultralytics import YOLO

        return YOLO(model_name)

    def _get_detector(self):
        if self._detector is None:
            self._detector = self._load_model(self.model)
        return self._detector

    def _get_segmenter(self):
        if not self.seg_model:
            return None
        if self._segmenter is None:
            self._segmenter = self._load_model(self.seg_model)
        return self._segmenter

    def run(self, context: HarnessToolContext) -> ToolResult:
        start = time.time()
        images = _extract_image_paths_from_message(context.message)
        if not images:
            return ToolResult(
                name="vision_pipeline",
                status="skipped",
                stderr="no image paths found in message",
                duration_ms=(time.time() - start) * 1000,
            )
        try:
            import numpy as np  # noqa: F401
            from PIL import Image
        except Exception:
            Image = None  # type: ignore[assignment]

        try:
            detector = self._get_detector()
            segmenter = self._get_segmenter()
        except Exception as exc:
            duration_ms = (time.time() - start) * 1000
            return ToolResult(
                name="vision_pipeline",
                status="error",
                stderr=f"vision pipeline requires ultralytics (pip install ultralytics): {exc}",
                duration_ms=duration_ms,
            )

        results_payload: list[dict[str, Any]] = []
        for image_path in images[: self.max_images]:
            path = Path(image_path).expanduser()
            if not path.exists() or not path.is_file():
                results_payload.append({"path": image_path, "error": "file not found"})
                continue
            try:
                detections = detector.predict(
                    source=str(path),
                    conf=self.confidence,
                    verbose=False,
                )
                result = detections[0]
                names = result.names or {}
                objects: list[dict[str, Any]] = []
                if result.boxes is not None:
                    for box in result.boxes[: self.max_objects]:
                        xyxy = box.xyxy[0].tolist() if box.xyxy is not None else []
                        cls_idx = int(box.cls[0]) if box.cls is not None else -1
                        label = names.get(cls_idx, str(cls_idx))
                        conf = float(box.conf[0]) if box.conf is not None else 0.0
                        objects.append(
                            {
                                "label": label,
                                "confidence": conf,
                                "box": [round(x, 2) for x in xyxy],
                            }
                        )

                mask_count = 0
                if result.masks is not None:
                    mask_count = len(result.masks)
                if segmenter:
                    seg_results = segmenter.predict(
                        source=str(path),
                        conf=self.confidence,
                        verbose=False,
                    )
                    seg = seg_results[0]
                    if seg.masks is not None:
                        mask_count = max(mask_count, len(seg.masks))

                annotated_b64 = None
                annotated_mime = None
                if Image is not None:
                    annotated = result.plot()
                    if hasattr(annotated, "shape") and annotated.shape[-1] == 3:
                        annotated = annotated[..., ::-1]
                    buffer = io.BytesIO()
                    Image.fromarray(annotated).save(buffer, format="PNG")
                    annotated_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
                    annotated_mime = "image/png"

                results_payload.append(
                    {
                        "path": str(path),
                        "objects": objects,
                        "object_count": len(objects),
                        "mask_count": mask_count,
                        "annotated_image": annotated_b64,
                        "annotated_mime": annotated_mime,
                    }
                )
            except Exception as exc:
                results_payload.append({"path": str(path), "error": str(exc)})

        duration_ms = (time.time() - start) * 1000
        status = "ok" if any("objects" in item for item in results_payload) else "error"
        return ToolResult(
            name="vision_pipeline",
            status=status,
            output={
                "model": self.model,
                "segment_model": self.seg_model or None,
                "confidence": self.confidence,
                "results": results_payload,
            },
            duration_ms=duration_ms,
        )


class MermaidToolRunner(ToolRunner):
    def __init__(self, retry_policy: RetryPolicy) -> None:
        super().__init__("mermaid", retry_policy)

    def run(self, context: HarnessToolContext) -> ToolResult:
        start = time.time()
        keywords = _extract_keywords(context.message)
        nodes = ["U[User]", "R[Request]"]
        edges = ["U --> R"]
        for idx, keyword in enumerate(keywords, start=1):
            nodes.append(f"K{idx}[{keyword}]")
            edges.append(f"R --> K{idx}")
        graph = "\n".join(["graph TD", *nodes, *edges])
        duration_ms = (time.time() - start) * 1000
        return ToolResult(
            name="mermaid",
            status="ok",
            output={"graph": graph, "keywords": keywords},
            duration_ms=duration_ms,
        )


def _extract_keywords(message: str) -> list[str]:
    if not message:
        return []
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", message)
    stopwords = {
        "the", "and", "for", "with", "that", "this", "from", "you", "your", "are",
        "how", "what", "why", "who", "when", "where", "should", "could", "would",
        "into", "about", "have", "has", "had", "will", "can", "our", "we", "us",
        "they", "them", "their", "is", "it", "of", "to", "in", "on", "at",
        "by", "as", "be", "or", "if", "an", "a", "it", "its",
    }
    keywords: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        lower = token.lower()
        if lower in stopwords or lower in seen:
            continue
        seen.add(lower)
        keywords.append(token)
        if len(keywords) >= 6:
            break
    if not keywords:
        return ["scope", "tools", "response"]
    return keywords


def _extract_first_url(message: str) -> str | None:
    match = re.search(r"(https?://[^\s)]+)", message or "", re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip(".,)")


def _replace_placeholders(value: Any, url: str | None) -> Any:
    if not isinstance(value, str):
        return value
    if url is None:
        return value
    return value.replace("{{url}}", url)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolRunner] = {}

    def register(self, tool: ToolRunner) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolRunner | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools.keys())


class AutoToolRunner:
    def __init__(self) -> None:
        self.greptile_dir = Path(os.getenv("LANGLY_GREPTILE_DIR", "~/Desktop/greptile")).expanduser()
        self.auto_tools = [
            t.strip()
            for t in os.getenv(
                "LANGLY_AUTO_TOOLS",
                "greptile,lint,jj,taskwarrior,preflight,file_read,mermaid,vision,vision_pipeline",
            ).split(",")
            if t.strip()
        ]
        self.retry_default = int(os.getenv("LANGLY_TOOL_RETRY_DEFAULT", "0"))
        self.retry_backoff_ms = int(os.getenv("LANGLY_TOOL_RETRY_BACKOFF_MS", "200"))
        self.retry_overrides = {
            "greptile": int(os.getenv("LANGLY_TOOL_RETRY_GREPTILE", "2")),
            "lint": int(os.getenv("LANGLY_TOOL_RETRY_LINT", "1")),
            "jj": int(os.getenv("LANGLY_TOOL_RETRY_JJ", "0")),
            "taskwarrior": int(os.getenv("LANGLY_TOOL_RETRY_TASKWARRIOR", "0")),
            "browser": int(os.getenv("LANGLY_TOOL_RETRY_BROWSER", "0")),
            "playwright": int(os.getenv("LANGLY_TOOL_RETRY_PLAYWRIGHT", "0")),
            "chrome_devtools": int(os.getenv("LANGLY_TOOL_RETRY_CHROME_DEVTOOLS", "0")),
            "taskwarrior_mcp": int(os.getenv("LANGLY_TOOL_RETRY_TASK_MCP", "0")),
            "preflight": int(os.getenv("LANGLY_TOOL_RETRY_PREFLIGHT", "0")),
            "file_read": int(os.getenv("LANGLY_TOOL_RETRY_FILE_READ", "0")),
            "mermaid": int(os.getenv("LANGLY_TOOL_RETRY_MERMAID", "0")),
            "vision": int(os.getenv("LANGLY_TOOL_RETRY_VISION", "0")),
            "vision_pipeline": int(os.getenv("LANGLY_TOOL_RETRY_VISION_PIPELINE", "0")),
        }
        self.cache_ttl = int(os.getenv("LANGLY_TOOL_CACHE_TTL_SEC", "30"))
        self.cache_max = int(os.getenv("LANGLY_TOOL_CACHE_MAX", "64"))
        self.cache_enabled = os.getenv("LANGLY_TOOL_CACHE_ENABLED", "true").lower() == "true"
        self._cache: dict[str, tuple[float, list[ToolResult]]] = {}
        self.concurrency = int(os.getenv("LANGLY_TOOL_CONCURRENCY", "4"))
        self.registry = self._build_registry()

    def apply_reconfiguration(
        self,
        *,
        disabled_tools: Iterable[str] | None = None,
        retry_overrides: dict[str, int] | None = None,
    ) -> None:
        if disabled_tools:
            disabled = {tool for tool in disabled_tools}
            self.auto_tools = [tool for tool in self.auto_tools if tool not in disabled]
        if retry_overrides:
            self.retry_overrides.update(retry_overrides)
        self.registry = self._build_registry()

    def _policy_for(self, name: str) -> RetryPolicy:
        return RetryPolicy(
            max_retries=self.retry_overrides.get(name, self.retry_default),
            backoff_ms=self.retry_backoff_ms,
        )

    def _build_registry(self) -> ToolRegistry:
        registry = ToolRegistry()

        registry.register(GreptileToolRunner(self.greptile_dir, self._policy_for("greptile")))

        registry.register(LintToolRunner(self._policy_for("lint")))

        jj_status = CommandToolRunner(
            "jj status",
            command_fn=lambda _ctx: ["jj", "status"],
            retry_policy=self._policy_for("jj"),
            timeout=15,
            cwd_fn=lambda ctx: ctx.cwd,
        )
        jj_diff = CommandToolRunner(
            "jj diff --stat",
            command_fn=lambda _ctx: ["jj", "diff", "--stat"],
            retry_policy=self._policy_for("jj"),
            timeout=15,
            cwd_fn=lambda ctx: ctx.cwd,
        )
        registry.register(JJToolRunner([jj_status, jj_diff]))

        registry.register(TaskwarriorToolRunner(self._policy_for("taskwarrior")))

        task_mcp_url = os.getenv("LANGLY_MCP_TASK_URL")
        if task_mcp_url:
            registry.register(MCPTaskwarriorToolRunner(task_mcp_url, self._policy_for("taskwarrior_mcp")))

        registry.register(PreflightToolRunner(self._policy_for("preflight")))

        registry.register(FileReadToolRunner(self._policy_for("file_read")))

        registry.register(VisionToolRunner(self._policy_for("vision")))

        registry.register(VisionPipelineToolRunner(self._policy_for("vision_pipeline")))

        browser_url = os.getenv("LANGLY_MCP_BROWSER_URL")
        if browser_url:
            registry.register(MCPBrowserToolRunner(browser_url, self._policy_for("browser"), name="browser"))

        playwright_url = os.getenv("LANGLY_MCP_PLAYWRIGHT_URL")
        if playwright_url:
            registry.register(MCPBrowserToolRunner(playwright_url, self._policy_for("playwright"), name="playwright"))

        chrome_url = os.getenv("LANGLY_MCP_CHROME_URL")
        if chrome_url:
            registry.register(MCPBrowserToolRunner(chrome_url, self._policy_for("chrome_devtools"), name="chrome_devtools"))

        registry.register(MermaidToolRunner(self._policy_for("mermaid")))

        return registry

    async def run(
        self,
        message: str,
        scope: dict[str, Any] | None = None,
        *,
        observer: Callable[[str, str, ToolResult | None], None] | None = None,
    ) -> list[ToolResult]:
        context = HarnessToolContext(message=message, scope=scope, cwd=Path.cwd())
        cache_key = self._cache_key(message, scope)
        if self.cache_enabled:
            cached = self._cache_get(cache_key)
            if cached is not None:
                for tool_result in cached:
                    tool_result.cached = True
                return cached

        results: list[ToolResult] = []
        semaphore = asyncio.Semaphore(self.concurrency)

        async def _run_tool(tool_name: str, runner: ToolRunner | None) -> list[ToolResult]:
            if observer:
                observer("start", tool_name, None)
            if runner is None:
                skipped = ToolResult(
                    name=tool_name,
                    status="skipped",
                    stderr="tool not registered",
                )
                if observer:
                    observer("done", tool_name, skipped)
                return [skipped]
            async with semaphore:
                tool_results = await asyncio.to_thread(runner.execute, context)
            if observer:
                for tool_result in tool_results:
                    observer("done", tool_name, tool_result)
            return tool_results

        tasks = [
            _run_tool(tool_name, self.registry.get(tool_name))
            for tool_name in self.auto_tools
        ]
        for batch in await asyncio.gather(*tasks):
            results.extend(batch)

        if self.cache_enabled:
            self._cache_set(cache_key, results)
        return results

    def _cache_key(self, message: str, scope: dict[str, Any] | None) -> str:
        payload = {
            "message": message,
            "scope": scope,
            "tools": self.auto_tools,
            "retry": self.retry_overrides,
        }
        return json.dumps(payload, sort_keys=True, default=str)

    def _cache_get(self, key: str) -> list[ToolResult] | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        created_at, results = entry
        if time.time() - created_at > self.cache_ttl:
            self._cache.pop(key, None)
            return None
        return [result.model_copy() for result in results]

    def _cache_set(self, key: str, results: list[ToolResult]) -> None:
        if len(self._cache) >= self.cache_max:
            oldest_key = next(iter(self._cache.keys()), None)
            if oldest_key:
                self._cache.pop(oldest_key, None)
        self._cache[key] = (time.time(), [result.model_copy() for result in results])


def _extract_image_paths(payload: Any) -> list[str]:
    results: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in {"filePath", "filename", "path"} and isinstance(value, str):
                if value.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    results.append(value)
            results.extend(_extract_image_paths(value))
    elif isinstance(payload, list):
        for item in payload:
            results.extend(_extract_image_paths(item))
    return results


def _extract_paths(message: str) -> list[str]:
    if not message:
        return []
    matches = re.findall(r"(?:\.?/[^\s'\"\n]+)", message)
    return [m.strip(".,)") for m in matches]


def _extract_image_paths_from_message(message: str) -> list[str]:
    if not message:
        return []
    candidates: list[str] = []
    attach_split = re.split(r"attachments:\s*", message, flags=re.IGNORECASE, maxsplit=1)
    if len(attach_split) > 1:
        for line in attach_split[1].splitlines():
            cleaned = line.strip().strip("`")
            if cleaned:
                candidates.append(cleaned)
    candidates.extend(
        re.findall(
            r"([\w./~-]+\.(?:png|jpe?g|webp|bmp|gif))",
            message,
            flags=re.IGNORECASE,
        )
    )
    candidates.extend(_extract_paths(message))
    images: list[str] = []
    seen: set[str] = set()
    for path in candidates:
        lower = path.lower()
        if not lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")):
            continue
        if path in seen:
            continue
        seen.add(path)
        images.append(path)
    return images


def _scan_python_symbols(path: Path) -> dict[str, list[str]]:
    try:
        source = path.read_text(encoding="utf-8")
    except Exception:
        return {}
    try:
        tree = ast.parse(source)
    except Exception:
        return {}
    classes: list[str] = []
    functions: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.FunctionDef):
            functions.append(node.name)
    return {"classes": classes[:50], "functions": functions[:50]}
