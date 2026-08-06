from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, HttpUrl

class HearingData(BaseModel):
    google_event_id: str
    process_number: str
    client_external_id: str
    starts_at: datetime
    timezone: str
    mode: Literal["online", "presencial", "hibrida"]
    
    # Usando Optional para campos que podem ser None (conforme o contrato)
    public_link: Optional[HttpUrl] = None
    public_location: Optional[str] = None
    witness_instruction: Optional[str] = None
    public_note: Optional[str] = None