from pydantic import BaseModel


class TicketStatusStatOut(BaseModel):
    status: str
    count: int


class TicketAddressStatOut(BaseModel):
    address_id: int
    count: int


class TicketReportOut(BaseModel):
    total_tickets: int
    open_tickets: int
    closed_tickets: int
    average_resolution_hours: float | None
    by_status: list[TicketStatusStatOut]
    by_address: list[TicketAddressStatOut]
