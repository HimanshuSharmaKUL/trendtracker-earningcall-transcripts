

from datetime import datetime, timezone
import uuid

from backend.models.companies_transcripts import EarningCallTranscript
from backend.services.chunking import chunk_paras


def _build_transcript(company_id, para_structured_text, raw_text):
    now = datetime.now(timezone.utc)
    return EarningCallTranscript(
        id=uuid.uuid4(),
        company_id=company_id,
        source="test",
        source_url="https://imagine-dragons.com",
        fiscal_year=2024,
        fiscal_quarter=4,
        fetched_at=now,
        preprocessed_at=now,
        updated_at=now,
        raw_text=raw_text,
        para_structured_text=para_structured_text,
        org_data={"org_unique_count": 0, "org_freq_count_sorted": []},
        document_meta_data={"char_count": len(raw_text), "word_count": 0, "sentence_count": 0},
        content_hash=uuid.uuid4().hex,
    )

def test_chunk_hash_uniqueness(mock_company):
    #Same company, same transcript, same content, but different chunk index (determined by para_number)
    paras = [
        {"paragraph_number": 1, "content": "Same text for both paras.", "speaker": "CEO"},
        {"paragraph_number": 2, "content": "Same text for both paras.", "speaker": "CFO"},
    ]
    transcript = _build_transcript(
        mock_company.id,
        para_structured_text=paras,
        raw_text="Same text for both paras.",
    )

    chunks = chunk_paras(transcript, chunk_size=200)
    hashes = [c.chunk_hash for c in chunks]

    assert len(hashes) == 2
    assert len(set(hashes)) == 2  # unique because chunk_index changes

