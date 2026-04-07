"""Zettelkasten note endpoints for v2 runtime."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.memory.zettelkasten import ZettelkastenStore


router = APIRouter(prefix="/notes", tags=["notes-v2"])


class NoteCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    body: str = Field("", max_length=200000)
    tags: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)


class NoteSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)


class NoteOut(BaseModel):
    id: str
    title: str
    body: str
    tags: list[str]
    links: list[str]
    created_at: str
    updated_at: str
    path: str


def _store() -> ZettelkastenStore:
    root = Path(os.getenv("LANGLY_ZK_DIR", "zettelkasten"))
    return ZettelkastenStore(root=root)


@router.get("", response_model=list[NoteOut])
def list_notes() -> list[NoteOut]:
    store = _store()
    return [NoteOut(**_note_to_dict(note)) for note in store.list_notes()]


@router.get("/{note_id}", response_model=NoteOut)
def read_note(note_id: str) -> NoteOut:
    store = _store()
    note = store.read_note(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="note not found")
    return NoteOut(**_note_to_dict(note))


@router.post("", response_model=NoteOut)
def create_note(payload: NoteCreateRequest) -> NoteOut:
    store = _store()
    note = store.create_note(
        title=payload.title,
        body=payload.body,
        tags=payload.tags,
        links=payload.links,
    )
    return NoteOut(**_note_to_dict(note))


@router.post("/search", response_model=list[NoteOut])
def search_notes(payload: NoteSearchRequest) -> list[NoteOut]:
    store = _store()
    return [NoteOut(**_note_to_dict(note)) for note in store.search(payload.query)]


def _note_to_dict(note) -> dict[str, object]:
    return {
        "id": note.note_id,
        "title": note.title,
        "body": note.body,
        "tags": note.tags,
        "links": note.links,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
        "path": note.path,
    }
