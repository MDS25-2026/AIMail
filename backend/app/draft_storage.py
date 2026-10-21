"""How a draft's grounding, review and receipt are stored and shown: one shape for replies and new emails.

The reply path (app/dashboard.py) and Compose (app/compose.py) store the agent's answer the same way, so
the dashboard reads a new email's sources, review reasons and privacy receipt with the reply's components.
"""

from app.contracts import ContextChunk, EgressRecord
from app.db.models import ModelEgress


def source_records(chunks: list[ContextChunk]) -> list[dict]:
    return [
        {"label": chunk["source_title"] or "Policy", "chunkId": str(chunk["chunk_id"]),
         "excerpt": chunk["content"], "score": round(chunk["similarity_score"], 3)}
        for chunk in chunks
    ]


def rag_context_of(sources: list[dict] | None) -> str:
    """The policy passages a draft was grounded on, rebuilt from what generation stored."""
    return "\n\n".join(f"[{source.get('label', 'Policy')}] {source.get('excerpt', '')}" for source in sources or [])


def review_columns(reviewed: dict) -> dict:
    """The critic's verdict on a draft, stored the same way for a generated and a refined one."""
    confidence = reviewed.get("confidence")
    return {
        "critic_confidence": None if confidence is None else float(confidence),
        # Stored so a rescued draft is distinguishable from a first-pass success.
        "critic_attempts": int(reviewed.get("attempts") or 0),
        "critic_checks": {
            "grounding_ok": reviewed.get("grounding_ok"),
            "pii_clean": reviewed.get("pii_clean"),
            "tone_match": reviewed.get("tone_match"),
            "completeness": reviewed.get("completeness"),
            "pii_findings": reviewed.get("pii_findings") or [],
            "review_reasons": reviewed.get("review_reasons") or [],
            "review_codes": reviewed.get("review_codes") or [],
            # Which models answered and how many retries it took; outcomes and ms, no content.
            "model_calls": reviewed.get("model_calls") or [],
            "prompt_version": reviewed.get("prompt_version") or "",
        },
        "needs_human_review": bool(reviewed.get("needs_human_review")),
    }


def egress_view(row: ModelEgress) -> EgressRecord:
    return EgressRecord(purpose=row.purpose, provider=row.provider, chars=row.chars, hidden=row.hidden or {},
                        caught=row.caught, at=row.created_at.isoformat() if row.created_at else "")
