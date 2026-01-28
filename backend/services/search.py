#after performing of search we want to return ranked transcript hits with snippets
import sqlalchemy as sa
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.RequestSchemas.search import QueryRequest
from backend.ResponseSchemas.search import QueryResponse, TranscriptHit
from backend.models.companies_transcripts import EarningCallTranscript


def search_transcripts_svc(req: QueryRequest, session: Session):
    ts_query = func.websearch_to_tsquery("english", req.query)

    base_q = (
        session.query(
            EarningCallTranscript.id.label("transcript_id"),
            EarningCallTranscript.company_id,
            EarningCallTranscript.fiscal_year,
            EarningCallTranscript.fiscal_quarter,
            func.ts_rank_cd(EarningCallTranscript.raw_text_fts, ts_query).label("rank"), 
            func.ts_headline("english",
                            EarningCallTranscript.raw_text,
                            ts_query,
                            "StartSel=<mark>, StopSel=</mark>, MaxFragments=2, "
                            "MinWords=10, MaxWords=35, FragmentDelimiter=' … '"
                        ).label("snippet"),
        ).filter(EarningCallTranscript.raw_text_fts.op("@@")(ts_query))
    )

    if req.company_id:
        base_q = base_q.filter(EarningCallTranscript.company_id == req.company_id)
    if req.fiscal_year:
        base_q = base_q.filter(EarningCallTranscript.fiscal_year == req.fiscal_year)
    if req.fiscal_quarter:
        base_q = base_q.filter(EarningCallTranscript.fiscal_quarter == req.fiscal_quarter)

    total = base_q.count()

    rows = (base_q.order_by(sa.desc("rank"))
              .offset(req.offset)
              .limit(req.limit)
              .all()
              )

    hits = [TranscriptHit(
            transcript_id=r.transcript_id,
            company_id=r.company_id,
            fiscal_year=r.fiscal_year,
            fiscal_quarter=r.fiscal_quarter,
            rank=r.rank,
            snippet=r.snippet,
            ) for r in rows]

    return QueryResponse(total=total, hits=hits)
