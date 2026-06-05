import os
import shutil
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db import crud
from app.pipeline.graph import pipeline, PipelineState

router = APIRouter(prefix="/api/claims", tags=["claims"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

_ALLOWED_MIME = {
    "image/jpeg", "image/png", "image/tiff", "image/bmp",
    "image/jpg", "application/pdf",
}


def _save_upload(upload: UploadFile, dest: str) -> str:
    ext = upload.filename.rsplit(".", 1)[-1] if "." in (upload.filename or "") else "jpg"
    path = f"{dest}.{ext}"
    with open(path, "wb") as f:
        shutil.copyfileobj(upload.file, f)
    return path


@router.post("/submit")
async def submit_claim(
    member_id:      str           = Form(...),
    treatment_date: str           = Form(...),
    claim_amount:   Optional[float] = Form(0.0),
    prescription:   Optional[UploadFile] = File(None),
    pharmacy_bill:  Optional[UploadFile] = File(None),
    diagnosis_test: Optional[UploadFile] = File(None),
    medical_bill:   Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    uploads = {
        "prescription":   prescription,
        "pharmacy_bill":  pharmacy_bill,
        "diagnosis_test": diagnosis_test,
        "medical_bill":   medical_bill,
    }

    claim_id  = f"CLM_{uuid.uuid4().hex[:8].upper()}"
    claim_dir = os.path.join(UPLOAD_DIR, claim_id)
    os.makedirs(claim_dir, exist_ok=True)

    files: dict[str, str] = {}
    for doc_type, upload in uploads.items():
        if not upload or not upload.filename:
            continue
        if upload.content_type not in _ALLOWED_MIME:
            raise HTTPException(400, f"Unsupported file type for {doc_type}: {upload.content_type}")
        files[doc_type] = _save_upload(upload, os.path.join(claim_dir, doc_type))

    if not files:
        raise HTTPException(400, "At least one document is required.")

    # Load DB context for rules engine and check if member exists
    member_row  = crud.get_member(db, member_id)
    if not member_row:
        raise HTTPException(status_code=400, detail=f"Member ID '{member_id}' does not exist.")

    # Persist claim skeleton
    crud.create_claim(db, claim_id=claim_id, member_id=member_id,
                      treatment_date=treatment_date, claimed_amount=claim_amount)

    member_dict = None
    if member_row:
        member_dict = {
            "id":                member_row.id,
            "name":              member_row.name,
            "gender":            member_row.gender,
            "age":               member_row.age,
            "is_active":         member_row.is_active,
            "policy_start_date": str(member_row.policy_start_date) if member_row.policy_start_date else None,
            "policy_end_date":   str(member_row.policy_end_date)   if member_row.policy_end_date   else None,
            "join_date":         str(member_row.join_date)         if member_row.join_date         else None,
        }

    initial: PipelineState = {
        "claim_id":                 claim_id,
        "member_id":                member_id,
        "treatment_date":           treatment_date,
        "claim_amount":             claim_amount,
        "files":                    files,       # vision mode
        "ocr_texts":                {},          # empty → extract_node uses files
        "member":                   member_dict,
        "ytd_approved":             crud.get_ytd_approved(db, member_id, treatment_date),
        "ytd_category_approved":    crud.get_ytd_category_approved(db, member_id, treatment_date),
        "previous_claims_same_day": crud.get_same_day_claims_count(db, member_id, treatment_date),
        "existing_bill_numbers":    crud.get_existing_bill_numbers(db, member_id),
        "bill_number_counts":       crud.get_bill_number_counts(db, member_id),
        "prescription":             None,
        "pharmacy_bill":            None,
        "diagnosis_test":           None,
        "medical_bill":             None,
        "aggregated_claim":         None,
        "violations":               [],
        "violation_details":        [],
        "copay_info":               {},
        "decision":                 None,
        "error":                    None,
    }

    result        = pipeline.invoke(initial)
    decision_data = result["decision"]

    # Persist each extracted document — stores structured fields in DB
    for doc_type, file_path in files.items():
        extracted = result.get(doc_type)
        crud.create_document(
            db,
            claim_id=claim_id,
            doc_type=doc_type,
            file_path=file_path,
            extracted_json=extracted,
            extraction_confidence=extracted.get("extraction_confidence") if extracted else None,
        )

    # Persist decision with all fields
    crud.create_decision(db, claim_id=claim_id, decision_data=decision_data)
    crud.update_claim_status(
        db, claim_id=claim_id,
        status=decision_data["decision"],
        approved_amount=decision_data["approved_amount"],
        category_approved_amounts=decision_data.get("category_approved_amounts"),
        category_claimed_amounts=decision_data.get("category_claimed_amounts"),
        claimed_amount=decision_data.get("claimed_amount"),
    )

    return {
        "claim_id": claim_id,
        "decision": decision_data,
        "documents": [
            {
                "doc_type": doc_type,
                "extraction_confidence": result.get(doc_type).get("extraction_confidence") if result.get(doc_type) else None,
                "extracted_data": result.get(doc_type)
            }
            for doc_type in files
            if result.get(doc_type)
        ]
    }


@router.get("/dashboard-stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    from sqlalchemy import func
    from app.db.models import Claim
    
    total_approved = db.query(func.coalesce(func.sum(Claim.approved_amount), 0.0)).filter(
        Claim.status.in_(["APPROVED", "PARTIAL"])
    ).scalar()
    
    count_approved = db.query(Claim).filter(Claim.status == "APPROVED").count()
    count_partial = db.query(Claim).filter(Claim.status == "PARTIAL").count()
    count_rejected = db.query(Claim).filter(Claim.status == "REJECTED").count()
    count_review = db.query(Claim).filter(Claim.status == "MANUAL_REVIEW").count()
    count_pending = db.query(Claim).filter(Claim.status == "PENDING").count()
    total_claims = db.query(Claim).count()
    
    recent_claims = db.query(Claim).order_by(Claim.created_at.desc()).limit(5).all()
    recent_list = []
    for c in recent_claims:
        recent_list.append({
            "claim_id": c.id,
            "member_id": c.member_id,
            "member_name": c.member.name if c.member else "Unknown",
            "treatment_date": str(c.treatment_date),
            "claimed_amount": c.claimed_amount,
            "approved_amount": c.approved_amount,
            "status": c.status,
            "submission_date": str(c.submission_date)
        })
        
    return {
        "total_approved_amount": float(total_approved),
        "count_approved": count_approved,
        "count_partially_approved": count_partial,
        "count_rejected": count_rejected,
        "count_manual_review": count_review,
        "count_pending": count_pending,
        "total_claims": total_claims,
        "recent_claims": recent_list,
    }


@router.get("/{claim_id}")
def get_claim(claim_id: str, db: Session = Depends(get_db)):
    data = crud.get_claim_with_decision(db, claim_id)
    if not data:
        raise HTTPException(404, "Claim not found.")
    return data


@router.get("")
def list_claims(member_id: str, db: Session = Depends(get_db)):
    return crud.get_member_claims(db, member_id)


@router.post("/{claim_id}/appeal")
def appeal_claim(claim_id: str, notes: str = "", db: Session = Depends(get_db)):
    claim = crud.get_claim(db, claim_id)
    if not claim:
        raise HTTPException(404, "Claim not found.")
    crud.flag_for_review(db, claim_id, notes)
    return {"message": "Claim flagged for manual review.", "claim_id": claim_id}