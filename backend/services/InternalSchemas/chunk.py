from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel


class Chunk(BaseModel):
    transcript_id: UUID
    company_id: UUID
    chunk_id: UUID #unique chunk id with signature of chunk text, transcript id and chunk 
    chunk_hash: str
    chunk_index: int
    chunk_data: Dict[str, Any]