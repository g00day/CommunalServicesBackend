from fastapi import HTTPException
from sqladmin import ModelView
from starlette.requests import Request

from app.core.permissions import (
    ADDRESS_MANAGE,
    ROLES_MANAGE,
    ROLES_READ,
    TICKETS_READ_ALL,
    TICKETS_UPDATE_STATUS,
    USERS_READ,
    USERS_UPDATE,
)
from app.models import Address, District, Permission, Role, Street, Ticket, Uprava, User


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

    def is_accessible(self, request: Request) -> bool:
        return self._has_permission(request, self.required_permission)

    def is_visible(self, request: Request) -> bool:
        return self.is_accessible(request)

    async def insert_model(self, request: Request, data: dict):
        if not self._has_permission(request, self.create_permission):
            raise HTTPException(status_code=403, detail="Недостаточно прав для создания записей")
        return await super().insert_model(request, data)

    async def update_model(self, request: Request, pk: str, data: dict):
        if not self._has_permission(request, self.edit_permission):
            raise HTTPException(status_code=403, detail="Недостаточно прав для редактирования записей")
        return await super().update_model(request, pk, data)

    async def delete_model(self, request: Request, pk: str):
        if not self._has_permission(request, self.delete_permission):
            raise HTTPException(status_code=403, detail="Недостаточно прав для удаления записей")
        return await super().delete_model(request, pk)


class UserAdmin(RBACModelView, model=User):
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-users"
    required_permission = USERS_READ
    edit_permission = USERS_UPDATE
    can_create = False
    can_delete = False

    column_list = [
        User.id,
        User.email,
        User.surname,
        User.name,
        User.role_id,
        User.is_activated,
        User.created_at,
    ]
    column_searchable_list = [User.email, User.name, User.surname]
    column_sortable_list = [User.id, User.email, User.created_at]
    form_columns = [
        User.email,
        User.name,
        User.surname,
        User.father_name,
        User.role,
        User.is_activated,
        User.uprava,
        User.position,
        User.tg_chat_id,
    ]


class TicketAdmin(RBACModelView, model=Ticket):
    name = "Ticket"
    name_plural = "Tickets"
    icon = "fa-solid fa-ticket"
    required_permission = TICKETS_READ_ALL
    edit_permission = TICKETS_UPDATE_STATUS
    can_create = False
    can_delete = False

    column_list = [
        Ticket.id,
        Ticket.title,
        Ticket.status_id,
        Ticket.user_id,
        Ticket.address_id,
        Ticket.opened_at,
        Ticket.is_closed,
    ]
    column_searchable_list = [Ticket.title, Ticket.description]
    column_sortable_list = [Ticket.id, Ticket.opened_at]
    form_columns = [
        Ticket.title,
        Ticket.description,
        Ticket.address,
        Ticket.status,
        Ticket.creator,
        Ticket.is_closed,
        Ticket.closed_at,
    ]


class RoleAdmin(RBACModelView, model=Role):
    name = "Role"
    name_plural = "Roles"
    icon = "fa-solid fa-user-shield"
    required_permission = ROLES_READ
    edit_permission = ROLES_MANAGE
    can_create = False
    can_delete = False

    column_list = [Role.id, Role.name]
    form_columns = [Role.name, Role.permissions]


class PermissionAdmin(RBACModelView, model=Permission):
    name = "Permission"
    name_plural = "Permissions"
    icon = "fa-solid fa-key"
    required_permission = ROLES_READ
    can_create = False
    can_edit = False
    can_delete = False

    column_list = [Permission.id, Permission.code, Permission.name, Permission.description]
    column_searchable_list = [Permission.code, Permission.name]
    column_sortable_list = [Permission.id, Permission.code]


class AddressAdmin(RBACModelView, model=Address):
    name = "Address"
    name_plural = "Addresses"
    icon = "fa-solid fa-location-dot"
    required_permission = ADDRESS_MANAGE
    create_permission = ADDRESS_MANAGE
    edit_permission = ADDRESS_MANAGE
    delete_permission = ADDRESS_MANAGE
    
    column_list = [Address.id, Address.street_id, Address.house_number]


class UpravaAdmin(RBACModelView, model=Uprava):
    name = "Uprava"
    name_plural = "Upravas"
    icon = "fa-solid fa-building"
    required_permission = ADDRESS_MANAGE
    create_permission = ADDRESS_MANAGE
    edit_permission = ADDRESS_MANAGE
    delete_permission = ADDRESS_MANAGE
    
    column_list = [Uprava.id, Uprava.name]


class DistrictAdmin(RBACModelView, model=District):
    name = "District"
    name_plural = "Districts"
    icon = "fa-solid fa-map"
    required_permission = ADDRESS_MANAGE
    create_permission = ADDRESS_MANAGE
    edit_permission = ADDRESS_MANAGE
    delete_permission = ADDRESS_MANAGE

    column_list = [District.id, District.name, District.uprava_id]

class StreetAdmin(RBACModelView, model=Street):
    name = "Street"
    name_plural = "Streets"
    icon = "fa-solid fa-road"
    required_permission = ADDRESS_MANAGE
    create_permission = ADDRESS_MANAGE
    edit_permission = ADDRESS_MANAGE
    delete_permission = ADDRESS_MANAGE
    
    column_list = [Street.id, Street.name, Street.district_id]

