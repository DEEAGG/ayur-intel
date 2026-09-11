"""AYUR-INTEL — Phase 3A Grounded Knowledge Synthesis Engine.

Synthesizes retrieved evidence records into structured, grounded AI explanations
for Classical Ayurvedic Literature, PMC Research Papers, and FSSAI Regulations.

Architecture:
  Retrieved Evidence (DB)
         ↓
  Deterministic Evidence Fingerprint
         ↓
  GET (0 Gemini Calls) -> Persisted Validated Synthesis
         ↓ (or on explicit POST generate)
  Source-Specific Bounded Gemini Prompt
         ↓
  Post-Gemini Deterministic Validation (Grounding Status)
         ↓
  Persisted Knowledge Synthesis
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from api.core.config import settings
from api.models.models import (
    KnowledgeEvidence,
    KnowledgeFinding,
    KnowledgeSynthesis,
    Source,
)

logger = logging.getLogger("ayur_intel.knowledge_synthesis_service")


# ---------------------------------------------------------------------------
# Helpers & Fingerprinting
# ---------------------------------------------------------------------------

def compute_evidence_fingerprint(evidence_records: List[Dict[str, Any]]) -> str:
    """Compute a deterministic SHA256 fingerprint for a set of evidence records."""
    tokens = []
    for ev in sorted(evidence_records, key=lambda x: str(x.get("id", ""))):
        ev_id = str(ev.get("id", ""))
        c_hash = str(ev.get("content_hash", ""))
        loc = str(ev.get("evidence_locator", ""))
        tokens.append(f"{ev_id}:{c_hash}:{loc}")
    payload = "|".join(tokens)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def detect_source_category(source_type: str, document_identifier: str) -> str:
    """Classify source category as CLASSICAL, SCIENTIFIC, or REGULATORY."""
    st_upper = (source_type or "").upper()
    doc_upper = (document_identifier or "").upper()

    if "CLASSICAL" in st_upper or "TK" in st_upper or "NIIMH" in doc_upper or "CHARAKA" in doc_upper or "SUSHRUTA" in doc_upper:
        return "CLASSICAL"
    elif "SCIENTIFIC" in st_upper or "PMC" in doc_upper or "ARTICLE" in st_upper:
        return "SCIENTIFIC"
    elif "REGULATORY" in st_upper or "FSSAI" in doc_upper or "GOV" in st_upper:
        return "REGULATORY"
    return "CLASSICAL"


# ---------------------------------------------------------------------------
# Source-Specific Schema Specifications
# ---------------------------------------------------------------------------

REQUIRED_SECTIONS = {
    "CLASSICAL": [
        "summary_60s",
        "traditional_context",
        "key_concepts",
        "what_the_text_indicates",
        "why_it_matters_for_product_research",
        "source_context",
        "limitations",
        "evidence_references",
    ],
    "SCIENTIFIC": [
        "summary_60s",
        "research_question",
        "study_type",
        "study_context",
        "key_findings",
        "why_it_matters",
        "important_limitations",
        "product_research_relevance",
        "evidence_references",
    ],
    "REGULATORY": [
        "summary_60s",
        "regulatory_context",
        "key_requirements",
        "who_or_what_it_applies_to",
        "product_developer_implications",
        "important_restrictions",
        "version_and_date_context",
        "limitations",
        "evidence_references",
    ],
}


# ---------------------------------------------------------------------------
# Grounded Knowledge Synthesis Service
# ---------------------------------------------------------------------------

class KnowledgeSynthesisService:
    """Grounded AI synthesis engine for Knowledge Hub evidence."""

    @classmethod
    def gather_document_evidence(
        cls, db: Session, document_identifier: str
    ) -> Tuple[List[Dict[str, Any]], Optional[Source], str]:
        """Fetch all evidence units associated with a document_identifier using robust multi-stage matching."""
        doc_str = str(document_identifier).strip()

        # Stage 1: Exact matches on source_identifier, public_id, or title
        evidence_rows = (
            db.query(KnowledgeEvidence)
            .filter(
                (KnowledgeEvidence.source_identifier == doc_str)
                | (KnowledgeEvidence.public_id == doc_str)
                | (KnowledgeEvidence.title == doc_str)
            )
            .all()
        )

        # Stage 2: Substring matches on evidence_locator, title, or source_identifier
        if not evidence_rows:
            evidence_rows = (
                db.query(KnowledgeEvidence)
                .filter(
                    (KnowledgeEvidence.evidence_locator.like(f"%{doc_str}%"))
                    | (KnowledgeEvidence.title.like(f"%{doc_str}%"))
                    | (KnowledgeEvidence.source_identifier.like(f"%{doc_str}%"))
                )
                .all()
            )

        # Stage 3: Match via KnowledgeFinding title or public_id
        if not evidence_rows:
            finding = (
                db.query(KnowledgeFinding)
                .filter(
                    (KnowledgeFinding.public_id == doc_str)
                    | (KnowledgeFinding.title == doc_str)
                    | (KnowledgeFinding.evidence_locator.like(f"%{doc_str}%"))
                )
                .first()
            )
            if finding and hasattr(finding, "evidence_records") and finding.evidence_records:
                evidence_rows = finding.evidence_records

        evidence_list = []
        source_obj = None

        for ev in evidence_rows:
            if not source_obj and ev.source:
                source_obj = ev.source
            evidence_list.append({
                "id": ev.public_id,
                "title": ev.title or "Evidence Record",
                "source_identifier": ev.source_identifier or ev.public_id,
                "evidence_locator": ev.evidence_locator or "",
                "excerpt": ev.excerpt or "",
                "confidence": ev.confidence or "HIGH",
                "publication_date": ev.publication_date or "",
                "retrieval_date": ev.retrieval_date or "",
                "source_version": ev.source_version or "",
                "license_note": ev.license_note or "",
                "content_hash": ev.content_hash or "",
                "official_url": ev.source.url if ev.source else "",
            })

        source_type = source_obj.source_type if source_obj else "TRADITIONAL_KNOWLEDGE"
        category = detect_source_category(source_type, doc_str)
        return evidence_list, source_obj, category


    @classmethod
    def get_synthesis(
        cls, db: Session, document_identifier: str
    ) -> Dict[str, Any]:
        """GET-First Persistence Lifecycle. NEVER calls Gemini implicitly on GET.

        Returns persisted synthesis if valid & current; otherwise returns structured fallback.
        """
        evidence_list, source_obj, category = cls.gather_document_evidence(db, document_identifier)
        current_fp = compute_evidence_fingerprint(evidence_list) if evidence_list else ""

        syn_record = (
            db.query(KnowledgeSynthesis)
            .filter(KnowledgeSynthesis.document_identifier == document_identifier)
            .order_by(KnowledgeSynthesis.updated_at.desc())
            .first()
        )

        if syn_record:
            is_stale = syn_record.evidence_fingerprint != current_fp
            if is_stale and not syn_record.is_stale:
                syn_record.is_stale = True
                db.add(syn_record)
                db.commit()

            sections = {}
            if syn_record.structured_sections_json:
                try:
                    sections = json.loads(syn_record.structured_sections_json)
                except Exception:
                    sections = {}

            evidence_ids = []
            if syn_record.evidence_ids_json:
                try:
                    evidence_ids = json.loads(syn_record.evidence_ids_json)
                except Exception:
                    evidence_ids = []

            return {
                "id": syn_record.public_id,
                "document_identifier": syn_record.document_identifier,
                "source_type": syn_record.source_type,
                "category": category,
                "title": syn_record.title,
                "summary_60s": syn_record.summary_60s,
                "structured_sections": sections,
                "evidence_ids": evidence_ids,
                "evidence_fingerprint": syn_record.evidence_fingerprint,
                "grounding_status": syn_record.grounding_status,
                "validation_notes": syn_record.validation_notes,
                "is_stale": is_stale,
                "model_used": syn_record.model_used,
                "generated_at": syn_record.generated_at.isoformat() if syn_record.generated_at else "",
                "evidence_items": evidence_list,
                "ai_available": True,
            }

        # No persisted synthesis exists -> return structured evidence fallback (0 Gemini calls)
        return cls._build_evidence_fallback(document_identifier, category, evidence_list, source_obj)

    @classmethod
    def _build_evidence_fallback(
        cls,
        document_identifier: str,
        category: str,
        evidence_list: List[Dict[str, Any]],
        source_obj: Optional[Source],
        validation_notes: str = "AI synthesis unavailable. Raw source evidence preserved.",
    ) -> Dict[str, Any]:
        """Structured raw evidence fallback when AI synthesis has not been explicitly generated."""
        now_str = datetime.now(timezone.utc).isoformat()
        evidence_ids = [e["id"] for e in evidence_list]
        fingerprint = compute_evidence_fingerprint(evidence_list) if evidence_list else ""

        first_title = evidence_list[0]["title"] if evidence_list else f"Document {document_identifier}"
        fallback_sections = {
            "summary_60s": f"AI synthesis is currently unavailable for {document_identifier}. Source evidence and official links remain accessible.",
            "source_context": f"Authority: {source_obj.authority if source_obj else 'Official Authority'}. Document: {document_identifier}.",
            "evidence_references": evidence_ids,
        }

        return {
            "id": None,
            "document_identifier": document_identifier,
            "source_type": source_obj.source_type if source_obj else category,
            "category": category,
            "title": first_title,
            "summary_60s": fallback_sections["summary_60s"],
            "structured_sections": fallback_sections,
            "evidence_ids": evidence_ids,
            "evidence_fingerprint": fingerprint,
            "grounding_status": "UNAVAILABLE",
            "validation_notes": validation_notes,
            "is_stale": False,
            "model_used": None,
            "generated_at": now_str,
            "evidence_items": evidence_list,
            "ai_available": False,
        }

    @classmethod
    def generate_synthesis(
        cls,
        db: Session,
        document_identifier: str,
        force_regenerate: bool = False,
    ) -> Dict[str, Any]:
        """Explicit POST generation endpoint. Calls Gemini only when explicitly triggered."""
        evidence_list, source_obj, category = cls.gather_document_evidence(db, document_identifier)
        if not evidence_list:
            return cls._build_evidence_fallback(document_identifier, category, [], source_obj)

        current_fp = compute_evidence_fingerprint(evidence_list)

        # Check existing synthesis unless force_regenerate is True
        if not force_regenerate:
            existing = (
                db.query(KnowledgeSynthesis)
                .filter(
                    KnowledgeSynthesis.document_identifier == document_identifier,
                    KnowledgeSynthesis.evidence_fingerprint == current_fp,
                    KnowledgeSynthesis.is_stale == False,
                )
                .first()
            )
            if existing and existing.grounding_status in ("GROUNDED", "PARTIALLY_GROUNDED"):
                return cls.get_synthesis(db, document_identifier)

        # Execute Gemini synthesis
        api_key = (
            os.getenv("GEMINI_API_KEY")
            or settings.GEMINI_API_KEY
            or settings.AYURINTEL_GEMINI_API_KEY
        )

        if not api_key:
            logger.info("Gemini API key not configured — returning raw evidence fallback.")
            return cls._build_evidence_fallback(document_identifier, category, evidence_list, source_obj)

        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)

            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config={"response_mime_type": "application/json"}
            )

            prompt = cls._build_source_prompt(category, document_identifier, evidence_list, source_obj)
            logger.info("Calling Gemini API (%s) for Knowledge Synthesis (%s)...", model_name, document_identifier)
            response = model.generate_content(prompt)

            raw_text = response.text.strip() if response and response.text else ""
            if not raw_text:
                raise ValueError("Empty response received from Gemini API.")

            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

            parsed_json = json.loads(raw_text)

            # Post-Gemini Validation
            validated_data, grounding_status, val_notes = cls.validate_synthesis_output(
                parsed_json, evidence_list, category
            )

            # Persist synthesis
            now_utc = datetime.now(timezone.utc)
            first_title = evidence_list[0]["title"] if evidence_list else f"Synthesis for {document_identifier}"
            summary_60s = validated_data.get("summary_60s", "")

            # Upsert into knowledge_syntheses
            existing_syn = (
                db.query(KnowledgeSynthesis)
                .filter(KnowledgeSynthesis.document_identifier == document_identifier)
                .first()
            )

            if not existing_syn:
                existing_syn = KnowledgeSynthesis(
                    source_id=source_obj.id if source_obj else None,
                    source_type=category,
                    document_identifier=document_identifier,
                )

            existing_syn.evidence_fingerprint = current_fp
            existing_syn.evidence_ids_json = json.dumps([e["id"] for e in evidence_list])
            existing_syn.title = first_title
            existing_syn.summary_60s = summary_60s
            existing_syn.structured_sections_json = json.dumps(validated_data)
            existing_syn.grounding_status = grounding_status
            existing_syn.validation_notes = val_notes
            existing_syn.is_stale = False
            existing_syn.model_used = model_name
            existing_syn.generated_at = now_utc

            db.add(existing_syn)
            db.commit()
            db.refresh(existing_syn)

            logger.info("Successfully generated and persisted synthesis for %s (Status: %s)", document_identifier, grounding_status)
            return cls.get_synthesis(db, document_identifier)

        except Exception as e:
            logger.warning("Gemini synthesis call failed (%s) — returning raw evidence fallback.", str(e))
            return cls._build_evidence_fallback(
                document_identifier, category, evidence_list, source_obj,
                validation_notes=f"Gemini synthesis failed: {str(e)}"
            )

    @classmethod
    def _build_source_prompt(
        cls,
        category: str,
        document_identifier: str,
        evidence_list: List[Dict[str, Any]],
        source_obj: Optional[Source],
    ) -> str:
        """Construct source-specific prompt for Gemini grounding."""
        evidence_formatted = json.dumps(evidence_list, indent=2)

        if category == "CLASSICAL":
            return f"""You are an expert Classical Ayurvedic Literature Research Analyst.
Synthesize the following retrieved classical evidence records for document '{document_identifier}'.

CRITICAL CLASSICAL GROUNDING RULES:
1. Classical text is TRADITIONAL textual context, NOT modern clinical evidence.
2. NEVER claim a classical mention proves medical or clinical efficacy.
3. NEVER fabricate Sanskrit verses or English/Hindi translations.
4. If verified translation is unavailable, state so conservatively.
5. All statements MUST be grounded in the provided evidence.

REQUIRED JSON FIELDS:
- "summary_60s": Executive 60-second classical overview.
- "traditional_context": Historical and traditional framework described in text.
- "key_concepts": Major Ayurvedic concepts (e.g. Sthana, Chapter, Tridosha, Dravya, Rasayana).
- "what_the_text_indicates": Objective textual indications as stated.
- "why_it_matters_for_product_research": Relevance for modern product development.
- "source_context": Classical hierarchy provenance (Samhita, Sthana, Chapter, Verse).
- "limitations": Traditional textual limitations.
- "evidence_references": Array of valid evidence IDs used from input.

RETRIEVED EVIDENCE BOUNDED CONTEXT:
{evidence_formatted}
"""

        elif category == "SCIENTIFIC":
            return f"""You are a Biomedical Evidence Synthesis Specialist.
Synthesize the following PMC research evidence records for document '{document_identifier}'.

CRITICAL SCIENTIFIC GROUNDING RULES:
1. Do NOT convert "Study observed X" into "Ingredient is proven to treat Y".
2. Preserve study design, uncertainty, sample size limitations, and observational nature.
3. NEVER invent study sample sizes or methodology.
4. All statements MUST be grounded in the provided evidence.

REQUIRED JSON FIELDS:
- "summary_60s": Executive 60-second research summary.
- "research_question": Primary objective or hypothesis studied.
- "study_type": Study model (e.g. In vitro, In vivo, Clinical trial, Systematic review).
- "study_context": Research design and publication context.
- "key_findings": Core experimental observations.
- "why_it_matters": Significance for botanical/phytochemical research.
- "important_limitations": Methodological and clinical limitations.
- "product_research_relevance": Implications for formulation and R&D.
- "evidence_references": Array of valid evidence IDs used from input.

RETRIEVED EVIDENCE BOUNDED CONTEXT:
{evidence_formatted}
"""

        else:  # REGULATORY
            return f"""You are an AYUSH and Food Safety Regulatory Compliance Analyst.
Synthesize the following official regulatory evidence records for document '{document_identifier}'.

CRITICAL REGULATORY GROUNDING RULES:
1. NEVER provide unsupported legal opinions or guarantee regulatory compliance.
2. Preserve document date, notification version, and official authority context.
3. All statements MUST be grounded in the provided regulatory text.

REQUIRED JSON FIELDS:
- "summary_60s": Executive 60-second regulatory summary.
- "regulatory_context": Authority, Gazette date, and scope.
- "key_requirements": Core mandatory statutory standards.
- "who_or_what_it_applies_to": Target food business operators or product categories.
- "product_developer_implications": Practical compliance steps for product developers.
- "important_restrictions": Prohibitions and statutory warnings.
- "version_and_date_context": Gazette notification date and version relationships.
- "limitations": Legal disclaimer and regulatory boundaries.
- "evidence_references": Array of valid evidence IDs used from input.

RETRIEVED EVIDENCE BOUNDED CONTEXT:
{evidence_formatted}
"""

    @classmethod
    def validate_synthesis_output(
        cls,
        parsed_json: Dict[str, Any],
        evidence_list: List[Dict[str, Any]],
        category: str,
    ) -> Tuple[Dict[str, Any], str, str]:
        """Validate Gemini output against ground-truth evidence IDs and required sections."""
        valid_ev_ids = {e["id"] for e in evidence_list}
        required_keys = REQUIRED_SECTIONS.get(category, REQUIRED_SECTIONS["CLASSICAL"])

        validation_notes = []
        missing_keys = [k for k in required_keys if k not in parsed_json]
        if missing_keys:
            validation_notes.append(f"Missing required keys: {', '.join(missing_keys)}")

        ref_ids = parsed_json.get("evidence_references", [])
        if isinstance(ref_ids, str):
            ref_ids = [ref_ids]

        invalid_refs = [r for r in ref_ids if r not in valid_ev_ids]
        if invalid_refs:
            validation_notes.append(f"Invalid/hallucinated evidence IDs rejected: {', '.join(invalid_refs)}")

        # Filter evidence_references to include ONLY valid evidence IDs
        sanitized_refs = [r for r in ref_ids if r in valid_ev_ids]
        if not sanitized_refs and evidence_list:
            sanitized_refs = [evidence_list[0]["id"]]

        parsed_json["evidence_references"] = sanitized_refs

        if invalid_refs or missing_keys:
            if sanitized_refs and len(missing_keys) <= 2:
                grounding_status = "PARTIALLY_GROUNDED"
            else:
                grounding_status = "FAILED_VALIDATION"
        else:
            grounding_status = "GROUNDED"

        val_notes_str = "; ".join(validation_notes) if validation_notes else "All evidence references and required sections validated cleanly."
        return parsed_json, grounding_status, val_notes_str

    @classmethod
    def get_product_source_analysis(
        cls, db: Session, source_name: str, case_id: str
    ) -> Dict[str, Any]:
        """GET-First Product-Specific Source Analysis (0 Gemini calls)."""
        doc_id = f"SOURCE_ANALYSIS_{source_name.upper()}_{case_id}"
        return cls.get_synthesis(db, doc_id)

    @classmethod
    def generate_product_source_analysis(
        cls, db: Session, source_name: str, case_id: str, force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """Explicit POST generation endpoint for Product-Specific Grounded Source Analysis."""
        import hashlib
        from api.models.models import ProductCase, Source, KnowledgeEvidence, KnowledgeSynthesis
        doc_id = f"SOURCE_ANALYSIS_{source_name.upper()}_{case_id}"

        p_case = db.query(ProductCase).filter(
            (ProductCase.public_id == case_id) | (ProductCase.id == case_id)
        ).first()

        if not p_case:
            return {
                "id": None,
                "document_identifier": doc_id,
                "has_synthesis": False,
                "summary_60s": "Product Case not found.",
                "ai_available": False,
                "structured_sections": {},
                "evidence_items": [],
            }

        src_obj = db.query(Source).filter(Source.name == source_name.upper()).first()
        evidence_query = db.query(KnowledgeEvidence)
        if src_obj:
            evidence_query = evidence_query.filter(KnowledgeEvidence.source_id == src_obj.id)

        evidence_rows = evidence_query.all()
        evidence_list = []
        for ev in evidence_rows:
            evidence_list.append({
                "id": ev.public_id,
                "title": ev.title or "Evidence Record",
                "source_identifier": ev.source_identifier or ev.public_id,
                "evidence_locator": ev.evidence_locator or "",
                "excerpt": ev.excerpt or "",
                "confidence": ev.confidence or "HIGH",
            })

        if not evidence_list:
            evidence_list, _, _ = cls.gather_document_evidence(db, source_name)

        current_fp = compute_evidence_fingerprint(evidence_list) if evidence_list else ""
        prod_data_str = f"{p_case.name}|{p_case.ingredients}|{p_case.intended_use}"
        combined_fp = hashlib.sha256(f"{prod_data_str}|{current_fp}".encode("utf-8")).hexdigest()

        if not force_regenerate:
            existing = (
                db.query(KnowledgeSynthesis)
                .filter(
                    KnowledgeSynthesis.document_identifier == doc_id,
                    KnowledgeSynthesis.evidence_fingerprint == combined_fp,
                    KnowledgeSynthesis.is_stale == False,
                )
                .first()
            )
            if existing and existing.grounding_status in ("GROUNDED", "PARTIALLY_GROUNDED"):
                return cls.get_synthesis(db, doc_id)

        api_key = (
            os.getenv("GEMINI_API_KEY")
            or settings.GEMINI_API_KEY
            or settings.AYURINTEL_GEMINI_API_KEY
        )
        if not api_key:
            return cls._build_evidence_fallback(doc_id, "CLASSICAL", evidence_list, src_obj, validation_notes="Gemini API key not configured")

        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name=model_name, generation_config={"response_mime_type": "application/json"})

            prompt = f"""You are an Expert AYUSH Phytomedicine & Regulatory Analyst.
Analyze the following retrieved evidence records from source '{source_name}' specifically for product '{p_case.name}'.

PRODUCT DATA CONTEXT:
- Product Name: {p_case.name}
- Stage: {p_case.stage}
- Ingredients: {p_case.ingredients}
- Intended Use: {p_case.intended_use}
- Form: {p_case.form}

STRICT GROUNDING & SAFETY RULES:
1. ONLY reference evidence records provided below.
2. For classical sources: state TRADITIONAL TEXTUAL CONTEXT clearly. NEVER claim traditional mention proves clinical efficacy.
3. For regulatory sources (FSSAI): highlight relevant provisions. NEVER guarantee regulatory approval.
4. For PMC sources: note scientific study findings and preserve study limitations.
5. All statements MUST be grounded in the provided evidence.

REQUIRED JSON OUTPUT FIELDS:
- "summary_60s": Executive 60-second summary of what this source contains relevant to product '{p_case.name}'.
- "relevant_ingredients": List of product ingredients matched in source evidence.
- "source_findings": Specific findings from source relevant to formulation.
- "what_you_should_read": Recommended passages or documents to inspect.
- "limitations": Statutory/scientific grounding limitations.
- "evidence_references": Array of valid evidence IDs used from input.

RETRIEVED EVIDENCE BOUNDED CONTEXT FOR SOURCE '{source_name}':
{json.dumps(evidence_list, indent=2)}
"""
            logger.info("Calling Gemini API (%s) for Product-Source Analysis (%s)...", model_name, doc_id)
            response = model.generate_content(prompt)
            raw_text = response.text.strip() if response and response.text else ""
            if raw_text.startswith("```json"): raw_text = raw_text[7:]
            if raw_text.startswith("```"): raw_text = raw_text[3:]
            if raw_text.endswith("```"): raw_text = raw_text[:-3]
            parsed_json = json.loads(raw_text.strip())

            validated_data, grounding_status, val_notes = cls.validate_synthesis_output(parsed_json, evidence_list, "CLASSICAL")
            now_utc = datetime.now(timezone.utc)

            syn_rec = db.query(KnowledgeSynthesis).filter(KnowledgeSynthesis.document_identifier == doc_id).first()
            if not syn_rec:
                syn_rec = KnowledgeSynthesis(source_id=src_obj.id if src_obj else None, source_type=source_name, document_identifier=doc_id)

            syn_rec.evidence_fingerprint = combined_fp
            syn_rec.evidence_ids_json = json.dumps([e["id"] for e in evidence_list])
            syn_rec.title = f"Product-Grounded Analysis: {p_case.name} x {source_name}"
            syn_rec.summary_60s = validated_data.get("summary_60s", "")
            syn_rec.structured_sections_json = json.dumps(validated_data)
            syn_rec.grounding_status = grounding_status
            syn_rec.validation_notes = val_notes
            syn_rec.is_stale = False
            syn_rec.model_used = model_name
            syn_rec.generated_at = now_utc

            db.add(syn_rec)
            db.commit()
            return cls.get_synthesis(db, doc_id)
        except Exception as e:
            logger.warning("Product-Source analysis failed: %s", e)
            return cls._build_evidence_fallback(doc_id, "CLASSICAL", evidence_list, src_obj, validation_notes=f"Analysis failed: {str(e)}")
