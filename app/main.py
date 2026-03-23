import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.core.config import settings
from app.core.db_init import init_db
from app.routers import (
    address,
    auth,
    chat_webhook,
    report,
    ticket_admin,
    ticket_messages,
    ticket_reference,
    tickets,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=settings.APP_NAME, version="1.0.0", routes=app.routes)
    schema["components"]["securitySchemes"] = {
        "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
    }
    for path in schema.get("paths", {}).values():
        for operation in path.values():
            if "chat-webhook" in operation.get("tags", []):
                continue
            operation["security"] = [{"bearerAuth": []}]
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok"}


app.include_router(auth.router, prefix="/api")
app.include_router(ticket_reference.router, prefix="/api")
app.include_router(tickets.router, prefix="/api")
app.include_router(ticket_messages.router, prefix="/api")
app.include_router(chat_webhook.router, prefix="/api")
app.include_router(ticket_admin.router, prefix="/api")
app.include_router(address.router, prefix="/api")
app.include_router(report.router, prefix="/api")
