"""
Text-based claim submission — skips OCR, accepts raw document text directly.
Useful for testing and demonstration without needing real scanned documents.

POST /api/claims/test-submit
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db import crud
from app.pipeline.graph import pipeline, PipelineState

router = APIRouter(prefix="/api/claims", tags=["claims"])


class TextClaimRequest(BaseModel):
    member_id: str
    treatment_date: str
    claim_amount: Optional[float] = 0.0
    prescription_text:   Optional[str] = None
    pharmacy_bill_text:  Optional[str] = None
    diagnosis_test_text: Optional[str] = None
    medical_bill_text:   Optional[str] = None


@router.post("/test-submit")
def test_submit(req: TextClaimRequest, db: Session = Depends(get_db)):
    """
    Submit a claim using raw text instead of image files.
    The text is passed directly to the LLM extraction step, bypassing OCR.
    Runs the same pipeline as the regular submit endpoint.
    """
    claim_id = f"TST_{uuid.uuid4().hex[:8].upper()}"

    # Map text inputs to the ocr_texts dict (bypasses the OCR node)
    ocr_texts = {}
    text_map = {
        "prescription":   req.prescription_text,
        "pharmacy_bill":  req.pharmacy_bill_text,
        "diagnosis_test": req.diagnosis_test_text,
        "medical_bill":   req.medical_bill_text,
    }
    for doc_type, text in text_map.items():
        if text and text.strip():
            ocr_texts[doc_type] = text.strip()

    if not ocr_texts:
        from fastapi import HTTPException
        raise HTTPException(400, "At least one document text field is required.")

    member_row = crud.get_member(db, req.member_id)
    if not member_row:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Member ID '{req.member_id}' does not exist.")

    crud.create_claim(db, claim_id=claim_id, member_id=req.member_id,
                      treatment_date=req.treatment_date, claimed_amount=req.claim_amount)


    member_dict = None
    if member_row:
        member_dict = {
            "id":               member_row.id,
            "name":             member_row.name,
            "gender":           member_row.gender,
            "age":              member_row.age,
            "is_active":        member_row.is_active,
            "policy_start_date": str(member_row.policy_start_date) if member_row.policy_start_date else None,
            "policy_end_date":   str(member_row.policy_end_date)   if member_row.policy_end_date   else None,
            "join_date":         str(member_row.join_date)         if member_row.join_date         else None,
        }

    initial: PipelineState = {
        "claim_id":                  claim_id,
        "member_id":                 req.member_id,
        "treatment_date":            req.treatment_date,
        "claim_amount":              req.claim_amount,
        "files":                     {},
        "ocr_texts":                 ocr_texts,
        "member":                    member_dict,
        "ytd_approved":              crud.get_ytd_approved(db, req.member_id, req.treatment_date),
        "ytd_category_approved":     crud.get_ytd_category_approved(db, req.member_id, req.treatment_date),
        "previous_claims_same_day":  crud.get_same_day_claims_count(db, req.member_id, req.treatment_date),
        "existing_bill_numbers":     crud.get_existing_bill_numbers(db, req.member_id),
        "bill_number_counts":        crud.get_bill_number_counts(db, req.member_id),
        "prescription":              None,
        "pharmacy_bill":             None,
        "diagnosis_test":            None,
        "medical_bill":              None,
        "aggregated_claim":          None,
        "violations":                [],
        "violation_details":         [],
        "copay_info":                {},
        "decision":                  None,
        "error":                     None,
    }

    result = pipeline.invoke(initial)
    decision_data = result["decision"]

    for doc_type in ocr_texts:
        extracted = result.get(doc_type)
        crud.create_document(
            db,
            claim_id=claim_id,
            doc_type=doc_type,
            file_path="",
            extracted_json=extracted,
            extraction_confidence=extracted.get("extraction_confidence") if extracted else None,
            ocr_text=ocr_texts[doc_type],   # store the input text for test-mode claims
        )

    crud.create_decision(db, claim_id=claim_id, decision_data=decision_data)
    crud.update_claim_status(db, claim_id=claim_id,
                             status=decision_data["decision"],
                             approved_amount=decision_data["approved_amount"],
                             category_approved_amounts=decision_data.get("category_approved_amounts"),
                             category_claimed_amounts=decision_data.get("category_claimed_amounts"),
                             claimed_amount=decision_data.get("claimed_amount"))

    return {"claim_id": claim_id, "decision": decision_data}