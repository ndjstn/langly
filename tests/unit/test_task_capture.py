from __future__ import annotations

from app.harness.task_capture import TaskCapture, TaskTemplateEngine


def test_task_capture_extracts_bullets() -> None:
    response = """\
- First task\n- Second task\n1. Third task\n"""
    capture = TaskCapture()
    tasks = capture.extract(response)
    assert len(tasks) == 3
    assert tasks[0].description == "First task"


def test_task_templates_heuristics() -> None:
    engine = TaskTemplateEngine()
    result = engine.suggest("Please read /tmp/file.txt", {"intent": "plan"})
    names = [template.name for template in result.templates]
    assert "read_file" in names
