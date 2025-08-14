from pydantic import BaseModel, Field
from typing import Optional, List

class MemoryIn(BaseModel):
    text: str = Field(..., min_length=1)

class MemoryPatch(BaseModel):
    text: Optional[str] = Field(None, min_length=1)

class TaskIn(BaseModel):
    title: str = Field(..., min_length=1)
    due: Optional[str] = None  # ISO datetime string

class TaskPatch(BaseModel):
    title: Optional[str] = Field(None, min_length=1)
    due: Optional[str] = None  # ISO datetime string
    done: Optional[bool] = None

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

class TranscriptionResponse(BaseModel):
    text: str