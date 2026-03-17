# models.py — complete version
from pydantic import BaseModel
from typing import List, Optional

class TutorResponse(BaseModel):
    explanation: str
    summary:     str
    quiz:        List[str]
    lang:        str
    audio:       Optional[str] = None
    audio_error: Optional[str] = None