from typing import Literal, Optional
from pydantic import BaseModel

class SuggestedAction(BaseModel):
    id: str
    type: Literal['script', 'response', 'action']
    confidence_score: float
    title: str
    description: str
    content: str
    source: str
    adapted_summary: Optional[str] = None
