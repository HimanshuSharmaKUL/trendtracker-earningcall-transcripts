from collections import Counter
from datetime import UTC, datetime, timezone
import hashlib
import re
import json

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from defeatbeta_api.client import duckdb_conf, duckdb_client
from defeatbeta_api.utils.util import validate_memory_limit
from defeatbeta_api.data.ticker import Ticker
import pandas as pd
import spacy

from backend.RequestSchemas.ingestion import IngestRequest
from backend.config.config import get_settings
from backend.models.companies_transcripts import Company, EarningCallTranscript, TranscriptOrgEntity
from backend.services.InternalSchemas.resolver import ResolverResponse

settings = get_settings()

def no_cache_settings(self):
    return [
        "INSTALL httpfs",
        "LOAD httpfs",
        f"SET GLOBAL http_keep_alive = {self.http_keep_alive}",
        f"SET GLOBAL http_timeout = {self.http_timeout}",
        f"SET GLOBAL http_retries = {self.http_retries}",
        f"SET GLOBAL http_retry_backoff = {self.http_retry_backoff}",
        f"SET GLOBAL http_retry_wait_ms = {self.http_retry_wait_ms}",
        f"SET GLOBAL memory_limit = '{validate_memory_limit(self.memory_limit)}'",
        f"SET GLOBAL threads = {self.threads}",
        f"SET GLOBAL parquet_metadata_cache = {self.parquet_metadata_cache}",
    ]


duckdb_conf.Configuration.get_duckdb_settings = no_cache_settings
duckdb_client.DuckDBClient._validate_httpfs_cache = lambda self: None

def _normalise_tick(tick: str) -> str:
    return tick.strip().upper()

_SUFFIXES = {"inc", "inc.", "corp", "corp.", "ltd", "ltd.", "llc", "plc", "co", "co."}
def _normalize_org_name(s: str) -> str:
    x = s.strip().lower()
    x = re.sub(r"^[^\w]+|[^\w]+$", "", x)      #trim punctuation ends
    x = re.sub(r"\s+", " ", x)                #collapse spaces
    parts = x.split(" ")
    #removes trailing corporate suffixes
    while parts and parts[-1] in _SUFFIXES:
        parts.pop()
    return " ".join(parts)

def create_get_company(resolved, session):
    company_exist = (session.query(Company).filter(Company.ticker==resolved.ticker).first())
    if company_exist:
        # raise HTTPException(status_code=400, detail="Email already exists.")
        return company_exist
    
    company = Company(
        name=resolved.name,
        ticker=_normalise_tick(resolved.ticker),
        exchange_code=resolved.exchCode,
        security_type=resolved.securityType,
        market_sector=resolved.marketSector,
        created_at = datetime.now(timezone.utc) 
    )
    session.add(company)
    session.commit()
    session.refresh(company)

    return company
    
def fetch_transcripts(tick: str, year: int, quarter: int):
    "Fetch, Preprocess - extract named-entities: ORG, organisations, extract meta data, and Persist the transcript and the meta data"
    try:
        ticker = Ticker(tick)
        transcripts = ticker.earning_call_transcripts()
        transcripts_list_df = transcripts.get_transcripts_list()
        required_transcript_df = transcripts.get_transcript(year, quarter) #returns a dataframe
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,detail="Failed to fetch transcripts from Defeatbeta_API.") from e
    
    if required_transcript_df is None or required_transcript_df.empty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transcript not found.")


    # required_transcript = required_transcript_df.to_dict(orient="records") #convert it into a list of dicts to store in our db
    return required_transcript_df

def _normalize_org(name: str) -> str:
    return name.strip().lower()

def preprocess_transcripts(transcript_df):
    
    if transcript_df is None or transcript_df.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript data is empty.",
        )
    
    parts = []
    for row in transcript_df.iterrows():
        parts.append(row[1]['content'])

    raw_text = " ".join(parts)

    nlp = spacy.load(settings.SPACY_MODEL) #expensive loading
    doc = nlp(raw_text)

    orgs  = [ent.text for ent in doc.ents if ent.label_ == "ORG"]
    #people also
    org_counts = Counter(_normalize_org(o) for o in orgs if o.strip())

    content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

    document_meta_data = {
            "char_count": len(raw_text),
            "word_count": len([t for t in doc if not t.is_space]),
            "sentence_count": len(list(doc.sents)),
        }
    org_data = {
        "org_unique_count": len(org_counts),
        "org_freq_count_sorted": [{"name":name, "count":count} for name, count in org_counts.most_common()]
    }
    
    return {
        "raw_text": raw_text,
        "para_structured_text": transcript_df.to_dict(orient="records"), #convert df into a list of dicts to store in our db
        "content_hash": content_hash,
        "org_data" : org_data,
        "document_meta_data": document_meta_data,
        "org_counts_raw": org_counts,
    }

def persist_transcripts(session, company_id, transcript_payload, org_counts):

    transcript_exist = session.query(EarningCallTranscript).filter(
        EarningCallTranscript.company_id==company_id,
        EarningCallTranscript.fiscal_year==transcript_payload.get('fiscal_year'),
        EarningCallTranscript.fiscal_quarter==transcript_payload.get('fiscal_quarter')
        ).first()
    
    if transcript_exist:
        #return transcript_exist #raise  raise 409 conflict when a transcript already exists
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,detail="Transcript already exists.")

    transcript = EarningCallTranscript(
        company_id= company_id,
        source= transcript_payload.get('source'),
        source_url= transcript_payload.get("source_url"),
        fiscal_year= transcript_payload.get("fiscal_year"),
        fiscal_quarter= transcript_payload.get("fiscal_quarter"),
        fetched_at= transcript_payload.get("fetched_at"),
        preprocessed_at= transcript_payload.get("preprocessed_at"),
        updated_at= datetime.now(timezone.utc),
        raw_text= transcript_payload.get("raw_text"),
        para_structured_text = transcript_payload.get("para_structured_text"),
        org_data = transcript_payload.get('org_data'),
        document_meta_data = transcript_payload.get('document_meta_data'),
        content_hash = transcript_payload.get('content_hash'),
    )
    
    session.add(transcript)
    # session.commit()
    # session.refresh(transcript)
    session.flush()

    for org_norm, count in org_counts.most_common():
        org_entity = TranscriptOrgEntity(
            transcript_id = transcript.id,
            org_name = org_norm,
            mention_count = count,
            created_at = datetime.now(timezone.utc)
        )

        session.add(org_entity)
    
    session.commit()
    return transcript


    

def store_transcripts(resolved : ResolverResponse, inputRequest: IngestRequest, session: Session):
    company = create_get_company(resolved, session)
    transcript_df = fetch_transcripts(tick=resolved.ticker, year=inputRequest.year, quarter=inputRequest.quarter)
    fetched_at = datetime.now(timezone.utc)
    preprocess_response = preprocess_transcripts(transcript_df)
    preprocessed_at = datetime.now(timezone.utc)

    #preparing payload for persistance
    transcript_payload = {
        # "tick": resolved.ticker, 
        "source": "defeatbeta_api",
        "source_url": f"https://finance.yahoo.com/quote/{resolved.ticker}/earnings-calls/",
        "fiscal_year": inputRequest.year,
        "fiscal_quarter": inputRequest.quarter,
        "fetched_at": fetched_at,
        "preprocessed_at": preprocessed_at,
        "raw_text": preprocess_response["raw_text"],
        "para_structured_text": preprocess_response["para_structured_text"],
        "org_data" : preprocess_response['org_data'],
        "document_meta_data": preprocess_response['document_meta_data'],
        "content_hash": preprocess_response["content_hash"],
        
    }
    
    transcript = persist_transcripts(session, company_id=company.id, transcript_payload=transcript_payload, org_counts=preprocess_response.get("org_counts_raw"))
    
    return {
        'company_id': company.id,
        'company_ticker':company.ticker,
        'company_name':company.name,
        'inserted_transcript_id': transcript.id,
        'year': transcript.fiscal_year,
        'quarter': transcript.fiscal_quarter
    }








