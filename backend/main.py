"""FastAPI app factory. Run: uvicorn backend.main:app --reload --port 8000"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import build_router
from backend.container import Container


def create_app() -> FastAPI:
    container = Container()
    app = FastAPI(title="Signal Scout", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(build_router(container))
    return app


app = create_app()
