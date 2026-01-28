#route to perform full text search over transcript content


from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.RequestSchemas.search import QueryRequest
from backend.ResponseSchemas.search import QueryResponse
from backend.config.database import get_session
from backend.services.search import search_transcripts_svc


search_router = APIRouter(
    prefix="/search",
    tags=["Search"],
    responses={
        404: {"description": "Not Found"}
    },  # default response - eg: if a route path is not defined then 404 will be thrown
)


@search_router.post("/query", status_code=status.HTTP_201_CREATED, response_model=QueryResponse)
def search_transcript(req: QueryRequest, session: Session = Depends(get_session)):
    return search_transcripts_svc(req, session)


