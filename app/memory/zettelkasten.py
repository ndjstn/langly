"""Simple file-backed Zettelkasten store."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


@dataclass
class ZkNote:
    note_id: str
    title: str
    body: str
    tags: list[str]
    links: list[str]
    created_at: str
    updated_at: str
    path: str


class ZettelkastenStore:
    def __init__(self, root: Path | None = None) -> None:
        if root is None:
            root = Path("zettelkasten")
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def list_notes(self) -> list[ZkNote]:
        notes: list[ZkNote] = []
        for meta_path in sorted(self.root.glob("*.json")):
            note = self._load_note(meta_path)
            if note:
                notes.append(note)
        notes.sort(key=lambda note: note.updated_at, reverse=True)
        return notes

    def read_note(self, note_id: str) -> ZkNote | None:
        meta_path = self._meta_path(note_id)
        if not meta_path.exists():
            return None
        return self._load_note(meta_path)

    def create_note(
        self,
        title: str,
        body: str,
        tags: Iterable[str] | None = None,
        links: Iterable[str] | None = None,
    ) -> ZkNote:
        note_id = self._build_id(title)
        created_at = datetime.now(timezone.utc).isoformat()
        meta = {
            "id": note_id,
            "title": title,
            "tags": list(tags or []),
            "links": list(links or []),
            "created_at": created_at,
            "updated_at": created_at,
        }
        meta_path = self._meta_path(note_id)
        body_path = self._body_path(note_id)
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        body_path.write_text(body, encoding="utf-8")
        return self._load_note(meta_path)  # type: ignore[return-value]

    def search(self, query: str) -> list[ZkNote]:
        query_lower = query.lower()
        matches: list[ZkNote] = []
        for note in self.list_notes():
            if (
                query_lower in note.title.lower()
                or query_lower in note.body.lower()
                or any(query_lower in tag.lower() for tag in note.tags)
            ):
                matches.append(note)
        return matches

    def _build_id(self, title: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"{timestamp}-{slug or 'note'}"

    def _meta_path(self, note_id: str) -> Path:
        return self.root / f"{note_id}.json"

    def _body_path(self, note_id: str) -> Path:
        return self.root / f"{note_id}.md"

    def _load_note(self, meta_path: Path) -> ZkNote | None:
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        note_id = meta.get("id") or meta_path.stem
        body_path = self._body_path(note_id)
        body = body_path.read_text(encoding="utf-8") if body_path.exists() else ""
        return ZkNote(
            note_id=note_id,
            title=meta.get("title", note_id),
            body=body,
            tags=list(meta.get("tags") or []),
            links=list(meta.get("links") or []),
            created_at=meta.get("created_at", ""),
            updated_at=meta.get("updated_at", ""),
            path=str(body_path),
        )
