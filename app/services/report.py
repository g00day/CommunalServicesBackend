from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import REPORTS_READ, has_permission
from app.models import Ticket, User
from app.schemas import TicketAddressStatOut, TicketReportOut, TicketStatusStatOut


def _normalize_filter_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


async def get_ticket_report_service(
    db: AsyncSession,
    current_user: User,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> TicketReportOut:
    if not has_permission(current_user, REPORTS_READ):
        raise HTTPException(status_code=403, detail="Отчеты доступны только сотруднику с соответствующим правом")

    date_from = _normalize_filter_datetime(date_from)
    date_to = _normalize_filter_datetime(date_to)

    query = select(Ticket).order_by(Ticket.opened_at.desc())
    if date_from is not None:
        query = query.where(Ticket.opened_at >= date_from)
    if date_to is not None:
        query = query.where(Ticket.opened_at <= date_to)

    result = await db.execute(query)
    tickets = result.scalars().all()

    total_tickets = len(tickets)
    open_tickets = sum(not item.is_closed for item in tickets)
    closed_tickets = sum(item.is_closed for item in tickets)

    status_map: dict[str, int] = {}
    address_map: dict[int, int] = {}
    resolution_hours: list[float] = []

    for ticket in tickets:
        status_map[ticket.status.code] = status_map.get(ticket.status.code, 0) + 1
        address_map[ticket.address_id] = address_map.get(ticket.address_id, 0) + 1

        if ticket.closed_at is not None:
            delta = ticket.closed_at - ticket.opened_at
            resolution_hours.append(round(delta.total_seconds() / 3600, 2))

    average_resolution_hours = None
    if resolution_hours:
        average_resolution_hours = round(sum(resolution_hours) / len(resolution_hours), 2)

    by_status = [
        TicketStatusStatOut(status=status_name, count=count)
        for status_name, count in sorted(status_map.items(), key=lambda item: item[0])
    ]
    by_address = [
        TicketAddressStatOut(address_id=address_id, count=count)
        for address_id, count in sorted(address_map.items(), key=lambda item: (-item[1], item[0]))
    ]

    return TicketReportOut(
        total_tickets=total_tickets,
        open_tickets=open_tickets,
        closed_tickets=closed_tickets,
        average_resolution_hours=average_resolution_hours,
        by_status=by_status,
        by_address=by_address,
    )
