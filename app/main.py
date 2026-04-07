"""FastAPI entrypoint for tests and ASGI servers."""
from app.api.app import create_app

app = create_app()
