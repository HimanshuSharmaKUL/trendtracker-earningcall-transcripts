from pydantic import BaseModel, Field

class IngestRequest(BaseModel):
    company_name_query: str = Field(min_length=1)
    security_type: str = Field(default="Common Stock")
    exchange_code: str = Field(default="US")
    year: int = Field(ge=2006, le=2026)
    quarter: int = Field(ge=1, le=4)