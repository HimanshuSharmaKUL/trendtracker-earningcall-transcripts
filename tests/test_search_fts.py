from backend.RequestSchemas.search import QueryRequest
from backend.services.search import search_transcripts_svc

from datetime import datetime, timezone

from backend.models.companies_transcripts import EarningCallTranscript
from backend.RequestSchemas.search import QueryRequest
from backend.services.search import search_transcripts_svc


def _insert_transcript(test_session, company_id, raw_text, year, quarter, content_hash):
    now = datetime.now(timezone.utc)
    transcript = EarningCallTranscript(
        company_id=company_id,
        source="test",
        source_url="https://some-fancy-url.com",
        fiscal_year=year,
        fiscal_quarter=quarter,
        fetched_at=now,
        preprocessed_at=now,
        updated_at=now,
        raw_text=raw_text,
        para_structured_text=[
            {"paragraph_number": 1, "content": raw_text, "speaker": "Mahatma Gandhi"}
        ],
        org_data={"org_unique_count": 0, "org_freq_count_sorted": []},
        document_meta_data={"char_count": len(raw_text), "word_count": 0, "sentence_count": 0},
        content_hash=content_hash,
    )
    test_session.add(transcript)
    test_session.flush()
    return transcript

def test_search_finds_mock_transcript(test_session, mock_transcript):
    req = QueryRequest(
        query="cloud revenue",
        company_id=mock_transcript.company_id,
        fiscal_year=2025,
        fiscal_quarter=3,
    )
    response = search_transcripts_svc(req, test_session)
    assert response.total == 1
    assert response.hits[0].transcript_id == mock_transcript.id

def test_search_rank_order(test_session, mock_company):
    #transcript with low number of occurance of mock search term "cloud revenue"
    t_low = _insert_transcript(
        test_session,
        mock_company.id,
        raw_text="Cloud revenue grew this quarter.",
        year=2024,
        quarter=4,
        content_hash="rank-low",
    )
    #artificially repeated term occurrences to drive higher rank in full text search in postgresql
    t_high = _insert_transcript(
        test_session,
        mock_company.id,
        raw_text="Cloud revenue cloud revenue cloud revenue drove results.",
        year=2024,
        quarter=3, #differnt quarter
        content_hash="rank-high",
    )
    
    req = QueryRequest(query="cloud revenue", company_id=mock_company.id)
    response = search_transcripts_svc(req, test_session)

    assert response.total == 2
    assert response.hits[0].rank >= response.hits[1].rank
    assert response.hits[0].transcript_id == t_high.id
    assert response.hits[1].transcript_id == t_low.id

def test_search_no_hits_returns_empty(test_session, mock_company):
    _insert_transcript(
        test_session,
        mock_company.id,
        raw_text="Cloud revenue grew this quarter.",
        year=2024,
        quarter=4,
        content_hash="no-hit",
    )

    req = QueryRequest(query="blockchain audit", company_id=mock_company.id)
    response = search_transcripts_svc(req, test_session)
    #should return 0
    assert response.total == 0
    assert response.hits == []