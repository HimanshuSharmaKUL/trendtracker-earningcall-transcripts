#route to perform question and answer with the stored transcripts
#entry point of RAG system

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.RequestSchemas.qa import RAGRequest
from backend.ResponseSchemas.qa import RAGResponse
from backend.config.database import get_session
from backend.services.qna import ask_ques_svc

qna_router = APIRouter(
    prefix="/qna",
    tags=["QnA"],
    responses={
        404: {"description": "Not Found"}
    }
)

@qna_router.post('/ask', status_code=status.HTTP_201_CREATED, response_model=RAGResponse)
def ask_question(ask: RAGRequest, session: Session = Depends(get_session)):
    return ask_ques_svc(ask, session)