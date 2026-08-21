from datetime import datetime
from typing import Literal

from pydantic import BaseModel, HttpUrl


class HearingData(BaseModel):
    google_event_id: str
    process_number: str
    client_external_id: str
    starts_at: datetime
    timezone: str
    mode: Literal["online", "presencial", "hibrida"]
    
    # Usando Optional para campos que podem ser nulos
    public_link: HttpUrl | None = None
    public_location: str | None = None
    witness_instruction: str | None = None
    public_note: str | None = None