from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, status
from PIL import Image, UnidentifiedImageError

from app.database import ReadOnlyDatabase
from app.graph import GroundedAgent
from app.ollama import OllamaClient
from app.schemas import AskRequest, AskResponse, VisionRequest, VisionResponse


DATABASE_URL = os.getenv(
    "AGENT_DATABASE_URL",
    "postgresql://safesite_agent:safesite_agent_dev_password@postgres:5432/safesite",
)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
OLLAMA_TEXT_MODEL = os.getenv("OLLAMA_TEXT_MODEL", "llama3.2:latest")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "qwen2.5vl:3b")
DATA_ROOT = Path(os.getenv("SAFESITE_DATA_ROOT", "/data"))


def create_app(
    database: Any | None = None,
    ollama: Any | None = None,
    data_root: Path | None = None,
) -> FastAPI:
    selected_database = database or ReadOnlyDatabase(DATABASE_URL)
    selected_ollama = ollama or OllamaClient(OLLAMA_URL, OLLAMA_TEXT_MODEL, OLLAMA_VISION_MODEL)
    selected_data_root = data_root or DATA_ROOT
    agent = GroundedAgent(selected_database.execute, selected_ollama.answer)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await selected_database.open()
        yield
        await selected_database.close()

    application = FastAPI(
        title="SafeSite Grounded Agent",
        description="Read-only natural-language access to SafeSite violation analytics.",
        version="1.0.0",
        lifespan=lifespan,
    )

    @application.get("/health")
    async def health() -> dict[str, Any]:
        database_health = await selected_database.health()
        try:
            models = await selected_ollama.available_models()
            ollama_health = {
                "reachable": True,
                "text_model_available": OLLAMA_TEXT_MODEL in models,
                "vision_model_available": OLLAMA_VISION_MODEL in models,
                "models": models,
            }
        except RuntimeError as error:
            ollama_health = {"reachable": False, "error": str(error)}
        return {"status": "healthy", "database": database_health, "ollama": ollama_health}

    @application.post("/ask", response_model=AskResponse)
    async def ask(payload: AskRequest) -> AskResponse:
        result = await agent.ask(payload.question)
        plan = result.get("plan")
        if result["status"] == "rejected":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=result["answer"])
        return AskResponse(
            status=result["status"],
            intent=plan.intent if plan else None,
            sql=plan.sql if plan else None,
            parameters=plan.parameters if plan else [],
            rows=result.get("rows", []),
            answer=result["answer"],
            answer_provider=result["answer_provider"],
        )

    @application.post("/vision/describe", response_model=VisionResponse)
    async def describe(payload: VisionRequest) -> VisionResponse:
        requested = Path(payload.image_path)
        candidate = requested if requested.is_absolute() else selected_data_root / requested
        resolved_root = selected_data_root.resolve()
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail="Image not found") from error
        if resolved_root != resolved and resolved_root not in resolved.parents:
            raise HTTPException(status_code=403, detail="Image must be inside the SafeSite data root")
        if resolved.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            raise HTTPException(status_code=422, detail="Only JPEG and PNG evidence is supported")
        try:
            with Image.open(resolved) as image:
                image.verify()
        except (OSError, UnidentifiedImageError) as error:
            raise HTTPException(status_code=422, detail="Evidence is not a valid image") from error
        try:
            description = await selected_ollama.describe_image(resolved)
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        return VisionResponse(status="described", model=OLLAMA_VISION_MODEL, description=description)

    return application


app = create_app()
