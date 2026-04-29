import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from sqladmin import Admin
from starlette.middleware.sessions import SessionMiddleware

from app.admin.auth import AdminAuth
from app.admin.views import (
    AddressAdmin,
    AuditLogAdmin,
    ChatAdmin,
    ChatParticipantAdmin,
    DistrictAdmin,
    MessageAdmin,
    MessageFileAdmin,
    PermissionAdmin,
    RoleAdmin,
    RolePermissionAdmin,
    StreetAdmin,
    TelegramLinkCodeAdmin,
    TicketAdmin,
    TicketFileAdmin,
    TicketStatusAdmin,
    UpravaAdmin,
    UserAdmin,
)
from app.core.config import settings
from app.core.address_seed import seed_addresses_if_empty
from app.core.database import engine
from app.core.db_init import init_db
from app.routers import (
    ai,
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
    await seed_addresses_if_empty(engine)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(SessionMiddleware, secret_key=settings.JWT_SECRET)


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
    return {"status": "работает"}


app.include_router(auth.router, prefix="/api")
app.include_router(ticket_reference.router, prefix="/api")
app.include_router(tickets.router, prefix="/api")
app.include_router(ticket_messages.router, prefix="/api")
app.include_router(chat_webhook.router, prefix="/api")
app.include_router(ticket_admin.router, prefix="/api")
app.include_router(address.router, prefix="/api")
app.include_router(report.router, prefix="/api")
app.include_router(ai.router, prefix="/api")

authentication_backend = AdminAuth(secret_key=settings.JWT_SECRET)
admin = Admin(app=app, engine=engine, authentication_backend=authentication_backend)

admin.add_view(UserAdmin)
admin.add_view(AuditLogAdmin)
admin.add_view(TicketAdmin)
admin.add_view(AddressAdmin)
admin.add_view(UpravaAdmin)
admin.add_view(DistrictAdmin)
admin.add_view(StreetAdmin)
admin.add_view(ChatAdmin)
admin.add_view(ChatParticipantAdmin)
admin.add_view(MessageAdmin)
admin.add_view(MessageFileAdmin)
admin.add_view(TicketFileAdmin)
admin.add_view(TelegramLinkCodeAdmin)
admin.add_view(TicketStatusAdmin)
admin.add_view(RoleAdmin)
admin.add_view(PermissionAdmin)
admin.add_view(RolePermissionAdmin)
