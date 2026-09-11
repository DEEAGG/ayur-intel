"""AYUR-INTEL — Knowledge Evidence Ingestion Service (Phase 2).

Provides idempotent, provenance-preserving evidence ingestion into the database:
- Reuses existing tables: Source, KnowledgeFinding, KnowledgeEvidence
- Computes and checks content_hash to eliminate duplicates
- Maintains strict 100% ground-truth provenance
- Zero Gemini calls (0 AI calls during ingestion)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from api.models.models import (
    KnowledgeEvidence,
    KnowledgeFinding,
    ProductCase,
    Source,
    User,
)
from api.services.source_adapter import SourceResult

logger = logging.getLogger("ayur_intel.knowledge_ingestion_service")


class KnowledgeIngestionService:
    """Idempotent ingestion service for knowledge findings and evidence."""

    @staticmethod
    def get_or_create_source(
        db: Session,
        name: str,
        authority: str,
        jurisdiction: str,
        source_type: str,
        url: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Source:
        """Get an existing Source or create one idempotently."""
        source = db.query(Source).filter(Source.name == name).first()
        if not source:
            source = Source(
                name=name,
                authority=authority,
                jurisdiction=jurisdiction,
                source_type=source_type,
                url=url,
                description=description,
                is_configured=True,
                is_active=True,
            )
            db.add(source)
            db.commit()
            db.refresh(source)
        return source

    @classmethod
    def ingest_results(
        cls,
        db: Session,
        user_id: int,
        results: List[SourceResult],
        product_case_id: Optional[int] = None,
    ) -> Dict[str, int]:
        """Ingest a list of SourceResults into DB idempotently.

        Returns:
            Dict with counts: {"sources_touched": int, "findings_created": int, "evidence_created": int, "duplicates_skipped": int}
        """
        now_utc = datetime.now(timezone.utc)
        retrieval_date_str = now_utc.strftime("%Y-%m-%d")

        findings_created = 0
        evidence_created = 0
        duplicates_skipped = 0
        sources_touched_map: Dict[str, Source] = {}

        for res in results:
            src_name = res.source_name or "GENERIC_SOURCE"
            if src_name not in sources_touched_map:
                source_obj = cls.get_or_create_source(
                    db=db,
                    name=src_name,
                    authority=res.source_authority or "Official Authority",
                    jurisdiction=res.jurisdiction or "GLOBAL",
                    source_type=res.category or "SCIENTIFIC",
                    url=res.source_url,
                )
                source_obj.last_retrieved_at = now_utc
                db.add(source_obj)
                sources_touched_map[src_name] = source_obj

            source_obj = sources_touched_map[src_name]

            c_hash = res.content_hash or f"{src_name}_{res.source_identifier}_{res.evidence_locator}"

            # Check if evidence with same content_hash already exists
            existing_ev = db.query(KnowledgeEvidence).filter(
                KnowledgeEvidence.content_hash == c_hash
            ).first()

            if existing_ev:
                duplicates_skipped += 1
                logger.debug("Skipped duplicate evidence (hash=%s)", c_hash)
                continue

            # Check or create finding
            finding = db.query(KnowledgeFinding).filter(
                KnowledgeFinding.owner_id == user_id,
                KnowledgeFinding.title == res.title,
                KnowledgeFinding.source_name == src_name,
            ).first()

            if not finding:
                finding = KnowledgeFinding(
                    owner_id=user_id,
                    product_case_id=product_case_id,
                    source_id=source_obj.id,
                    title=res.title,
                    summary=res.summary or res.title,
                    category=res.category or "GENERAL",
                    plant_name=res.plant_name,
                    botanical_name=res.botanical_name,
                    traditional_name=res.traditional_name,
                    confidence=res.confidence or "HIGH",
                    relevance=res.relevance or "HIGH",
                    evidence_locator=res.evidence_locator,
                    evidence_excerpt=res.excerpt,
                    publication_date=res.publication_date,
                    retrieval_date=res.retrieval_date or retrieval_date_str,
                    jurisdiction=res.jurisdiction,
                    source_name=src_name,
                    source_authority=res.source_authority,
                    limitations=res.limitations,
                    status="RETRIEVED",
                )
                db.add(finding)
                db.flush()
                findings_created += 1

            # Create evidence unit
            evidence = KnowledgeEvidence(
                finding_id=finding.id,
                source_id=source_obj.id,
                title=res.title,
                source_identifier=res.source_identifier or res.source_url,
                evidence_locator=res.evidence_locator,
                excerpt=res.excerpt,
                confidence=res.confidence or "HIGH",
                publication_date=res.publication_date,
                retrieval_date=res.retrieval_date or retrieval_date_str,
                source_version=res.source_version,
                license_note=res.license_note,
                content_hash=c_hash,
            )
            db.add(evidence)
            evidence_created += 1

        db.commit()

        return {
            "sources_touched": len(sources_touched_map),
            "findings_created": findings_created,
            "evidence_created": evidence_created,
            "duplicates_skipped": duplicates_skipped,
        }
