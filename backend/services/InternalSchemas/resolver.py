from pydantic import BaseModel

class ResolverResponse(BaseModel):
    name: str
    ticker: str
    exchCode: str
    securityType: str
    marketSector: str
    