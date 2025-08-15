from pydantic import BaseModel, Field
from typing import Optional, List

class MemoryIn(BaseModel):
    text: str = Field(..., min_length=1)

class MemoryPatch(BaseModel):
    text: Optional[str] = Field(None, min_length=1)

class TaskIn(BaseModel):
    title: str = Field(..., min_length=1)
    due: Optional[str] = None  # ISO datetime string
    rrule: Optional[str] = None  # RFC 5545 RRULE string
    priority: Optional[str] = Field(None, regex="^(low|medium|high)$")  # Priority level

class TaskPatch(BaseModel):
    title: Optional[str] = Field(None, min_length=1)
    due: Optional[str] = None  # ISO datetime string
    done: Optional[bool] = None
    rrule: Optional[str] = None  # RFC 5545 RRULE string
    priority: Optional[str] = Field(None, regex="^(low|medium|high)$")  # Priority level

class CaptureIn(BaseModel):
    text: str = Field(..., min_length=1)

class Memory(BaseModel):
    id: int
    text: str
    created: str
    tags: List[str]

class Task(BaseModel):
    id: int
    title: str
    due: Optional[str]
    done: bool
    created: str
    tags: List[str]
    notified_at: Optional[str] = None
    rrule: Optional[str] = None
    priority: Optional[str] = None

class TranscriptionResponse(BaseModel):
    text: str