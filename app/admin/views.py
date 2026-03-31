from fastapi import HTTPException
from sqladmin import ModelView
from starlette.requests import Request

from app.core.permissions import (
    ADDRESS_MANAGE,
    ADMIN_ACCESS,
    ROLES_READ,
    TICKETS_DELETE,
    TICKETS_READ_ALL,
    TICKETS_UPDATE_STATUS,
    USERS_CREATE,
    USERS_DELETE,
    USERS_READ,
    USERS_UPDATE,
)
from app.models import (
    Address,
    AuditLog,
    Chat,
    ChatParticipant,
    District,
    Message,
    MessageFile,
    Permission,
    Role,
    RolePermission,
    Street,
    TelegramLinkCode,
    Ticket,
    TicketFile,
    TicketStatus,
    Uprava,
    User,
)
from app.services.audit import write_audit_log


class RBACModelView(ModelView):
    required_permission: str | None = None
    create_permission: str | None = None
    edit_permission: str | None = None
    delete_permission: str | None = None
    can_view_details = True

    def _permission_codes(self, request: Request) -> set[str]:
        return set(request.session.get("admin_permissions", []))

    def _has_permission(self, request: Request, permission_code: str | None) -> bool:
        if permission_code is None:
            return True
        return permission_code in self._permission_codes(request)

    def _current_admin_user(self, request: Request) -> User | None:
        admin_user = getattr(request.state, "admin_user", None)
        if admin_user is not None:
            return admin_user

        admin_user_id = request.session.get("admin_user_id")
        admin_email = request.session.get("admin_email")
        if admin_user_id is None and admin_email is None:
            return None

        return User(
            id=admin_user_id or 0,
            email=admin_email or "",
            name="",
            surname="",
            hash_pass="",
            role_id=0,
            is_activated=True,
        )

    async def _log_action(
        self,
        request: Request,
        action_type: str,
        *,
        entity_id: str | None = None,
        details: dict | None = None,
    ) -> None:
        await write_audit_log(
            action_type=action_type,
            user=self._current_admin_user(request),
            entity_type=self.model.__name__,
            entity_id=entity_id,
            details=details,
        )

    def is_accessible(self, request: Request) -> bool:
        return self._has_permission(request, self.required_permission)

    def is_visible(self, request: Request) -> bool:
        return self.is_accessible(request)

    async def insert_model(self, request: Request, data: dict):
        if not self._has_permission(request, self.create_permission):
            raise HTTPException(status_code=403, detail="Недостаточно прав для создания записей")
        result = await super().insert_model(request, data)
        entity_id = getattr(result, "id", None)
        await self._log_action(
            request,
            "ADMIN_CREATE",
            entity_id=str(entity_id) if entity_id is not None else None,
            details={"fields": sorted(data.keys())},
        )
        return result

    async def update_model(self, request: Request, pk: str, data: dict):
        if not self._has_permission(request, self.edit_permission):
            raise HTTPException(status_code=403, detail="Недостаточно прав для редактирования записей")
        result = await super().update_model(request, pk, data)
        await self._log_action(
            request,
            "ADMIN_UPDATE",
            entity_id=pk,
            details={"fields": sorted(data.keys())},
        )
        return result

    async def delete_model(self, request: Request, pk: str):
        if not self._has_permission(request, self.delete_permission):
            raise HTTPException(status_code=403, detail="Недостаточно прав для удаления записей")
        result = await super().delete_model(request, pk)
        await self._log_action(request, "ADMIN_DELETE", entity_id=pk)
        return result


class ReadOnlyAdmin(RBACModelView):
    can_create = False
    can_edit = False
    can_delete = False


class ManagedAdmin(RBACModelView):
    required_permission = ADMIN_ACCESS
    create_permission = ADMIN_ACCESS
    edit_permission = ADMIN_ACCESS
    delete_permission = ADMIN_ACCESS
    can_create = True
    can_edit = True
    can_delete = True


class UserAdmin(RBACModelView, model=User):
    name = "Users"
    name_plural = "Users"
    icon = "fa-solid fa-users"
    required_permission = USERS_READ
    create_permission = USERS_CREATE
    edit_permission = USERS_UPDATE
    delete_permission = USERS_DELETE
    can_create = False
    can_delete = True
    can_edit = True

    column_list = [User.id, User.email, User.surname, User.name, User.role_id, User.uprava_id, User.position, User.is_activated, User.created_at]
    column_searchable_list = [User.email, User.name, User.surname]
    column_sortable_list = [User.id, User.email, User.created_at]
    form_columns = [User.email, User.name, User.surname, User.father_name, User.role, User.is_activated, User.uprava, User.position, User.tg_chat_id]


class TicketAdmin(RBACModelView, model=Ticket):
    name = "Tickets"
    name_plural = "Tickets"
    icon = "fa-solid fa-ticket"
    required_permission = TICKETS_READ_ALL
    edit_permission = TICKETS_UPDATE_STATUS
    delete_permission = TICKETS_DELETE
    can_create = False
    can_delete = True
    can_edit = True

    column_list = [Ticket.id, Ticket.title, Ticket.user_id, Ticket.address_id, Ticket.status_id, Ticket.opened_at, Ticket.closed_at, Ticket.is_closed]
    column_searchable_list = [Ticket.title, Ticket.description]
    column_sortable_list = [Ticket.id, Ticket.opened_at, Ticket.closed_at]
    form_columns = [Ticket.title, Ticket.description, Ticket.address, Ticket.status, Ticket.creator, Ticket.is_closed, Ticket.closed_at]


class AddressAdmin(ManagedAdmin, model=Address):
    name = "Addresses"
    name_plural = "Addresses"
    icon = "fa-solid fa-location-dot"
    required_permission = ADDRESS_MANAGE
    create_permission = ADDRESS_MANAGE
    edit_permission = ADDRESS_MANAGE
    delete_permission = ADDRESS_MANAGE

    column_list = [Address.id, Address.street_id, Address.house_number]
    column_searchable_list = [Address.house_number]
    column_sortable_list = [Address.id, Address.street_id, Address.house_number]
    form_columns = [Address.street, Address.house_number]


class UpravaAdmin(ManagedAdmin, model=Uprava):
    name = "Upravas"
    name_plural = "Upravas"
    icon = "fa-solid fa-building"
    required_permission = ADDRESS_MANAGE
    create_permission = ADDRESS_MANAGE
    edit_permission = ADDRESS_MANAGE
    delete_permission = ADDRESS_MANAGE

    column_list = [Uprava.id, Uprava.name]
    column_searchable_list = [Uprava.name]
    column_sortable_list = [Uprava.id, Uprava.name]
    form_columns = [Uprava.name]


class DistrictAdmin(ManagedAdmin, model=District):
    name = "Districts"
    name_plural = "Districts"
    icon = "fa-solid fa-map"
    required_permission = ADDRESS_MANAGE
    create_permission = ADDRESS_MANAGE
    edit_permission = ADDRESS_MANAGE
    delete_permission = ADDRESS_MANAGE

    column_list = [District.id, District.name, District.uprava_id]
    column_searchable_list = [District.name]
    column_sortable_list = [District.id, District.name, District.uprava_id]
    form_columns = [District.uprava, District.name]


class StreetAdmin(ManagedAdmin, model=Street):
    name = "Streets"
    name_plural = "Streets"
    icon = "fa-solid fa-road"
    required_permission = ADDRESS_MANAGE
    create_permission = ADDRESS_MANAGE
    edit_permission = ADDRESS_MANAGE
    delete_permission = ADDRESS_MANAGE

    column_list = [Street.id, Street.name, Street.district_id]
    column_searchable_list = [Street.name]
    column_sortable_list = [Street.id, Street.name, Street.district_id]
    form_columns = [Street.district, Street.name]


class ChatAdmin(ManagedAdmin, model=Chat):
    name = "Chats"
    name_plural = "Chats"
    icon = "fa-solid fa-comments"
    can_create = False

    column_list = [Chat.id, Chat.ticket_id]
    column_sortable_list = [Chat.id, Chat.ticket_id]
    form_columns = [Chat.ticket]


class ChatParticipantAdmin(ManagedAdmin, model=ChatParticipant):
    name = "Chat Participants"
    name_plural = "Chat Participants"
    icon = "fa-solid fa-user-group"

    column_list = [ChatParticipant.chat_id, ChatParticipant.user_id, ChatParticipant.role_in_chat, ChatParticipant.joined_at]
    column_sortable_list = [ChatParticipant.chat_id, ChatParticipant.user_id, ChatParticipant.joined_at]
    form_columns = [ChatParticipant.chat, ChatParticipant.user, ChatParticipant.role_in_chat]


class MessageAdmin(ManagedAdmin, model=Message):
    name = "Messages"
    name_plural = "Messages"
    icon = "fa-solid fa-envelope"

    column_list = [Message.id, Message.chat_id, Message.sender_user_id, Message.text, Message.sent_at]
    column_searchable_list = [Message.text]
    column_sortable_list = [Message.id, Message.chat_id, Message.sent_at]
    form_columns = [Message.chat, Message.sender, Message.text]


class MessageFileAdmin(ManagedAdmin, model=MessageFile):
    name = "Message Files"
    name_plural = "Message Files"
    icon = "fa-solid fa-file-lines"

    column_list = [MessageFile.id, MessageFile.message_id, MessageFile.file_name, MessageFile.mime_type, MessageFile.uploaded_at]
    column_searchable_list = [MessageFile.file_name, MessageFile.original_name]
    column_sortable_list = [MessageFile.id, MessageFile.message_id, MessageFile.uploaded_at]
    form_columns = [MessageFile.message, MessageFile.original_name, MessageFile.file_path, MessageFile.file_url, MessageFile.file_name, MessageFile.mime_type]


class TicketFileAdmin(ManagedAdmin, model=TicketFile):
    name = "Ticket Files"
    name_plural = "Ticket Files"
    icon = "fa-solid fa-paperclip"

    column_list = [TicketFile.id, TicketFile.ticket_id, TicketFile.file_name, TicketFile.mime_type, TicketFile.uploaded_at]
    column_searchable_list = [TicketFile.file_name, TicketFile.original_name]
    column_sortable_list = [TicketFile.id, TicketFile.ticket_id, TicketFile.uploaded_at]
    form_columns = [TicketFile.ticket, TicketFile.original_name, TicketFile.file_path, TicketFile.file_url, TicketFile.file_name, TicketFile.mime_type]


class TelegramLinkCodeAdmin(ManagedAdmin, model=TelegramLinkCode):
    name = "Telegram Codes"
    name_plural = "Telegram Codes"
    icon = "fa-brands fa-telegram"
    can_create = False

    column_list = [TelegramLinkCode.id, TelegramLinkCode.user_id, TelegramLinkCode.code, TelegramLinkCode.expires_at, TelegramLinkCode.consumed_at, TelegramLinkCode.created_at]
    column_sortable_list = [TelegramLinkCode.id, TelegramLinkCode.user_id, TelegramLinkCode.expires_at, TelegramLinkCode.created_at]
    form_columns = [TelegramLinkCode.user, TelegramLinkCode.code, TelegramLinkCode.expires_at, TelegramLinkCode.consumed_at]


class TicketStatusAdmin(ReadOnlyAdmin, model=TicketStatus):
    name = "Ticket Statuses"
    name_plural = "Ticket Statuses"
    icon = "fa-solid fa-list-check"
    required_permission = ADMIN_ACCESS

    column_list = [TicketStatus.id, TicketStatus.code, TicketStatus.name]
    column_searchable_list = [TicketStatus.code, TicketStatus.name]
    column_sortable_list = [TicketStatus.id, TicketStatus.code, TicketStatus.name]


class RoleAdmin(ReadOnlyAdmin, model=Role):
    name = "Roles"
    name_plural = "Roles"
    icon = "fa-solid fa-user-shield"
    required_permission = ROLES_READ

    column_list = [Role.id, Role.name]
    form_columns = [Role.name, Role.permissions]


class PermissionAdmin(ReadOnlyAdmin, model=Permission):
    name = "Permissions"
    name_plural = "Permissions"
    icon = "fa-solid fa-key"
    required_permission = ROLES_READ

    column_list = [Permission.id, Permission.code, Permission.name, Permission.description]
    column_searchable_list = [Permission.code, Permission.name]
    column_sortable_list = [Permission.id, Permission.code]


class RolePermissionAdmin(ReadOnlyAdmin, model=RolePermission):
    name = "Role Permissions"
    name_plural = "Role Permissions"
    icon = "fa-solid fa-link"
    required_permission = ROLES_READ

    column_list = [RolePermission.role_id, RolePermission.permission_id]
    column_sortable_list = [RolePermission.role_id, RolePermission.permission_id]


class AuditLogAdmin(ReadOnlyAdmin, model=AuditLog):
    name = "Audit Logs"
    name_plural = "Audit Logs"
    icon = "fa-solid fa-clipboard-list"
    required_permission = ADMIN_ACCESS

    column_list = [
        AuditLog.id,
        AuditLog.created_at,
        AuditLog.user_email,
        AuditLog.action_type,
        AuditLog.entity_type,
        AuditLog.entity_id,
        AuditLog.details,
    ]
    column_searchable_list = [AuditLog.user_email, AuditLog.action_type, AuditLog.entity_type, AuditLog.details]
    column_sortable_list = [AuditLog.id, AuditLog.created_at, AuditLog.action_type]
