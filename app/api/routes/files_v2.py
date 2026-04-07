"""File browsing endpoints for v2 runtime."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field


router = APIRouter(prefix="/files", tags=["files-v2"])


class FileEntry(BaseModel):
    name: str
    path: str
    type: str
    size: int | None = None


class FileTreeResponse(BaseModel):
    path: str
    entries: list[FileEntry]
    truncated: bool = False


class FileReadResponse(BaseModel):
    path: str
    content: str | None = None
    truncated: bool = False
    binary: bool = False


class FileUploadResponse(BaseModel):
    path: str
    relative_path: str


def _root() -> Path:
    return Path(os.getenv("LANGLY_FILE_ROOT", Path.cwd())).resolve()


def _resolve_path(path: str | None) -> Path:
    root = _root()
    raw = path or "."
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    if candidate != root and root not in candidate.parents:
        raise HTTPException(status_code=400, detail="path outside allowed root")
    return candidate


@router.get("/tree", response_model=FileTreeResponse)
def list_tree(path: str | None = None, max_entries: int = 200) -> FileTreeResponse:
    target = _resolve_path(path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="path not found")
    if target.is_file():
        raise HTTPException(status_code=400, detail="path is a file")
    entries: list[FileEntry] = []
    for item in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        rel = item.relative_to(_root())
        entry = FileEntry(
            name=item.name,
            path=str(rel),
            type="dir" if item.is_dir() else "file",
            size=item.stat().st_size if item.is_file() else None,
        )
        entries.append(entry)
        if len(entries) >= max_entries:
            break
    truncated = len(entries) >= max_entries
    rel_target = str(target.relative_to(_root()))
    return FileTreeResponse(path=rel_target or ".", entries=entries, truncated=truncated)


@router.get("/read", response_model=FileReadResponse)
def read_file(
    path: str,
    max_bytes: int = Query(default=20000, ge=1000, le=200000),
) -> FileReadResponse:
    target = _resolve_path(path)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    data = target.read_bytes()
    truncated = False
    if len(data) > max_bytes:
        data = data[:max_bytes]
        truncated = True
    if b"\x00" in data:
        return FileReadResponse(path=str(target.relative_to(_root())), binary=True, truncated=truncated)
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError:
        content = data.decode("utf-8", errors="replace")
    return FileReadResponse(path=str(target.relative_to(_root())), content=content, truncated=truncated)


@router.post("/upload", response_model=FileUploadResponse)
def upload_file(file: UploadFile = File(...)) -> FileUploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="missing filename")
    root = _root()
    upload_dir = Path(os.getenv("LANGLY_UPLOAD_DIR", "uploads"))
    if not upload_dir.is_absolute():
        upload_dir = root / upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename).name
    target = upload_dir / safe_name
    with target.open("wb") as handle:
        handle.write(file.file.read())
    rel = target.relative_to(root)
    return FileUploadResponse(path=str(target), relative_path=str(rel))
