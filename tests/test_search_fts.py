from backend.RequestSchemas.search import QueryRequest
from backend.services.search import search_transcripts_svc


def test_search_finds_microsoft_transcript(test_session, mock_transcript):
    req = QueryRequest(
        query="cloud revenue",
        company_id=mock_transcript.company_id,
        fiscal_year=2025,
        fiscal_quarter=3,
    )

    response = search_transcripts_svc(req, test_session)

    assert response.total == 1
    assert response.hits[0].transcript_id == mock_transcript.id
