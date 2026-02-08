from typing import Optional, Literal
from pydantic import BaseModel

class CloseTicketPayload(BaseModel):
    ticket_id: str
    resolution_type: Literal['Resolved Successfully', 'Not Applicable']
    notes: Optional[str] = None
    add_to_knowledge_base: bool

class CloseTicketResponse(BaseModel):
    status: str
    message: str
