from collections import Counter
from datetime import datetime, timezone
import pandas as pd
import pytest
from fastapi import HTTPException, status
from backend.models.companies_transcripts import Company, EarningCallTranscript
from backend.services.InternalSchemas.resolver import ResolverResponse
from backend.services.fetch_transcripts import create_get_company, fetch_transcripts, persist_transcripts

def _build_transcript_payload(
    fiscal_year=2024,
    fiscal_quarter=4,
    raw_text="Microsoft discussed AI strategy and cloud growth. Azure and Github are very important blah blah..",
    content_hash="msft-2024-q4-hash",
):
    now = datetime.now(timezone.utc)
    return {
        "source": "defeatbeta_api",
        "source_url": "https://finance.yahoo.com/quote/MSFT/earnings-calls/",
        "fiscal_year": fiscal_year,
        "fiscal_quarter": fiscal_quarter,
        "fetched_at": now,
        "preprocessed_at": now,
        "raw_text": raw_text,
        "para_structured_text": [
            {"paragraph_number": 1, "content": raw_text, "speaker": "Satya Nadela"}
        ],
        "org_data": {
            "org_unique_count": 0,
            "org_freq_count_sorted": [],
        },
        "document_meta_data": {"char_count": len(raw_text), "word_count": 5, "sentence_count": 1},
        "content_hash": content_hash,
    }

def test_transcript_persisted(test_session, mock_transcript):
    loaded = (
        test_session.query(EarningCallTranscript)
        .filter(EarningCallTranscript.id == mock_transcript.id)
        .one()
    )

    assert loaded.fiscal_year == 2025
    assert loaded.fiscal_quarter == 3
    assert loaded.parent_company.ticker == "MSFT"
    assert loaded.parent_company.name == "Microsoft"

def test_reuse_company_when_exists(test_session, mock_company):
    resolved = ResolverResponse(
        name="Microsoft Corporation",
        ticker="MSFT",
        exchCode="US",
        securityType="Common Stock",
        marketSector="Equity",
    )
    company = create_get_company(resolved, test_session)
    assert company.id == mock_company.id
    assert test_session.query(Company).count() == 1


def test_fetch_transcripts_not_found(monkeypatch):
    #mimic a blank datafame sent from Openfigi API 
    import backend.services.fetch_transcripts as ft
    class DummyTranscripts:
        def get_transcripts_list(self):
            return pd.DataFrame([{"year": 2025, "quarter": 3}])
        #empty data frame - this should trigger 404
        def get_transcript(self, year, quarter):
            return pd.DataFrame()  

    class DummyTicker:
        def __init__(self, tick):
            self.tick = tick
        def earning_call_transcripts(self):
            return DummyTranscripts()
        
    #to mimic Ticker("MSFT").earning_call_transcripts()
    monkeypatch.setattr(ft, "Ticker", DummyTicker)

    with pytest.raises(HTTPException) as exc:
        fetch_transcripts("MSFT", 2025, 3)

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    assert "Transcript not found" in exc.value.detail

def test_duplicate_transcript_conflict(test_session, mock_transcript):
    #build a conflicting transcript payload with a previously loaded transcript
    #supply its same year, and quarter
    #thr transcripts must be unique

    payload = _build_transcript_payload(
        fiscal_year=mock_transcript.fiscal_year,
        fiscal_quarter=mock_transcript.fiscal_quarter,
        content_hash="different-hash-but-same-period",
    )

    with pytest.raises(HTTPException) as exc:
        persist_transcripts(
            test_session,
            company_id=mock_transcript.company_id,
            transcript_payload=payload,
            org_counts=Counter(),
        )

    assert exc.value.status_code == status.HTTP_409_CONFLICT
    assert "Transcript already exists" in exc.value.detail