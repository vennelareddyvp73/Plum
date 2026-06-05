from datetime import date, datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import extract, func

from app.db.models import Member, Claim, Document, Decision


# --- Members ---

def get_member(db: Session, member_id: str) -> Optional[Member]:
    return db.query(Member).filter(Member.id == member_id).first()


def get_all_members(db: Session) -> List[Member]:
    return db.query(Member).all()


# --- Claims ---

def create_claim(db: Session, claim_id: str, member_id: str, treatment_date: str,
                 claimed_amount: float) -> Claim:
    claim = Claim(
        id=claim_id,
        member_id=member_id,
        treatment_date=date.fromisoformat(treatment_date),
        claimed_amount=claimed_amount,
        status="PENDING",
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


def get_claim(db: Session, claim_id: str) -> Optional[Claim]:
    return db.query(Claim).filter(Claim.id == claim_id).first()


def get_claim_with_decision(db: Session, claim_id: str) -> Optional[dict]:
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        return None
    result = {
        "claim_id": claim.id,
        "member_id": claim.member_id,
        "treatment_date": str(claim.treatment_date),
        "claimed_amount": claim.claimed_amount,
        "approved_amount": claim.approved_amount,
        "category_approved_amounts": claim.category_approved_amounts,
        "category_claimed_amounts": claim.category_claimed_amounts,
        "category_balances": get_category_balances(db, claim.member_id, str(claim.treatment_date)),
        "status": claim.status,
        "submission_date": str(claim.submission_date),
        "flagged_for_review": claim.flagged_for_review,
        "documents": [
            {
                "doc_type": d.doc_type,
                "extraction_confidence": d.extraction_confidence,
                "extracted_data": d.extracted_json,
            }
            for d in claim.documents
        ],
        "decision": None,
    }
    if claim.decision:
        d = claim.decision
        result["decision"] = {
            "decision": d.decision,
            "claimed_amount": d.claimed_amount,
            "approved_amount": d.approved_amount,
            "deductions": d.deductions,
            "rejection_reasons": d.rejection_reasons,
            "violation_reasoning": d.violation_reasoning,
            "fraud_flags": d.fraud_flags,
            "medical_necessity_verdict": d.medical_necessity_verdict,
            "confidence_score": d.confidence_score,
            "notes": d.notes,
            "next_steps": d.next_steps,
            "requires_manual_review": d.requires_manual_review,
            "manual_review_reasons": d.manual_review_reasons,
        }
    return result


def get_member_claims(db: Session, member_id: str) -> List[dict]:
    claims = db.query(Claim).filter(Claim.member_id == member_id)\
        .order_by(Claim.created_at.desc()).all()
    return [
        {
            "claim_id": c.id,
            "treatment_date": str(c.treatment_date),
            "claimed_amount": c.claimed_amount,
            "approved_amount": c.approved_amount,
            "status": c.status,
            "submission_date": str(c.submission_date),
        }
        for c in claims
    ]


def update_claim_status(db: Session, claim_id: str, status: str,
                        approved_amount: float,
                        category_approved_amounts: Optional[dict] = None,
                        category_claimed_amounts: Optional[dict] = None,
                        claimed_amount: Optional[float] = None) -> None:
    update_data = {"status": status, "approved_amount": approved_amount}
    if category_approved_amounts is not None:
        update_data["category_approved_amounts"] = category_approved_amounts
    if category_claimed_amounts is not None:
        update_data["category_claimed_amounts"] = category_claimed_amounts
    if claimed_amount is not None:
        update_data["claimed_amount"] = claimed_amount
    db.query(Claim).filter(Claim.id == claim_id).update(update_data)
    db.commit()


def flag_for_review(db: Session, claim_id: str, notes: str = "") -> None:
    db.query(Claim).filter(Claim.id == claim_id).update(
        {"flagged_for_review": True, "review_notes": notes, "status": "MANUAL_REVIEW"}
    )
    db.commit()


def get_ytd_approved(db: Session, member_id: str, treatment_date: str) -> float:
    tx_date = date.fromisoformat(treatment_date)
    result = db.query(func.coalesce(func.sum(Claim.approved_amount), 0)).filter(
        Claim.member_id == member_id,
        Claim.status.in_(["APPROVED", "PARTIAL"]),
        extract("year", Claim.treatment_date) == tx_date.year,
    ).scalar()
    return float(result)


def get_ytd_category_approved(db: Session, member_id: str, treatment_date: str) -> dict:
    tx_date = date.fromisoformat(treatment_date)
    claims = db.query(Claim).filter(
        Claim.member_id == member_id,
        Claim.status.in_(["APPROVED", "PARTIAL"]),
        extract("year", Claim.treatment_date) == tx_date.year,
    ).all()
    
    ytd = {
        "consultation": 0.0, "diagnostic": 0.0, "pharmacy": 0.0,
        "dental": 0.0, "dental_routine": 0.0, "dental_procedure": 0.0, "vision": 0.0,
        "alternative": 0.0, "procedure": 0.0, "other": 0.0,
    }
    for c in claims:
        if c.category_approved_amounts:
            for cat, amt in c.category_approved_amounts.items():
                if cat in ytd:
                    ytd[cat] += float(amt)
    return ytd


def get_category_balances(db: Session, member_id: str, treatment_date: str) -> dict:
    ytd_spent = get_ytd_category_approved(db, member_id, treatment_date)
    from app.config import POLICY
    limits = {
        "consultation": POLICY["coverage_details"]["consultation_fees"]["sub_limit"],
        "pharmacy":     POLICY["coverage_details"]["pharmacy"]["sub_limit"],
        "diagnostic":   POLICY["coverage_details"]["diagnostic_tests"]["sub_limit"],
        "dental_routine":   POLICY["coverage_details"]["dental"]["routine_checkup_limit"],
        "dental_procedure": POLICY["coverage_details"]["dental"]["sub_limit"],
        "vision":       POLICY["coverage_details"]["vision"]["sub_limit"],
        "alternative":  POLICY["coverage_details"]["alternative_medicine"]["sub_limit"],
    }
    balances = {}
    for cat, limit in limits.items():
        spent = ytd_spent.get(cat, 0.0)
        balances[cat] = {
            "limit": limit,
            "spent": spent,
            "remaining": max(limit - spent, 0.0)
        }
    return balances


def get_same_day_claims_count(db: Session, member_id: str, treatment_date: str) -> int:
    tx_date = date.fromisoformat(treatment_date)
    return db.query(Claim).filter(
        Claim.member_id == member_id,
        Claim.treatment_date == tx_date,
    ).count()


def get_existing_bill_numbers(db: Session, member_id: str) -> List[str]:
    docs = db.query(Document).join(Claim).filter(
        Claim.member_id == member_id,
        Claim.status != "REJECTED"
    ).all()
    bill_numbers = []
    for doc in docs:
        if doc.extracted_json:
            bn = doc.extracted_json.get("bill_number")
            if bn:
                bill_numbers.append(bn)
    return bill_numbers


def get_bill_number_counts(db: Session, member_id: str) -> dict:
    docs = db.query(Document).join(Claim).filter(Claim.member_id == member_id).all()
    counts = {}
    for doc in docs:
        if doc.extracted_json:
            bn = doc.extracted_json.get("bill_number")
            if bn:
                counts[bn] = counts.get(bn, 0) + 1
    return counts



# --- Documents ---

def create_document(db: Session, claim_id: str, doc_type: str, file_path: str,
                    extracted_json: Optional[dict],
                    extraction_confidence: Optional[float],
                    ocr_text: Optional[str] = None) -> Document:
    doc = Document(
        claim_id=claim_id,
        doc_type=doc_type,
        file_path=file_path,
        ocr_text=ocr_text,        # populated for text-mode claims, None for vision-mode
        extracted_json=extracted_json,
        extraction_confidence=extraction_confidence,
    )
    db.add(doc)
    db.commit()
    return doc


# --- Decisions ---

def create_decision(db: Session, claim_id: str, decision_data: dict) -> Decision:
    decision = Decision(
        claim_id=claim_id,
        decision=decision_data["decision"],
        claimed_amount=decision_data["claimed_amount"],
        approved_amount=decision_data["approved_amount"],
        deductions=decision_data.get("deductions", []),
        rejection_reasons=decision_data.get("rejection_reasons", []),
        violation_reasoning=decision_data.get("violation_reasoning", []),
        fraud_flags=decision_data.get("fraud_flags", []),
        medical_necessity_verdict=decision_data.get("medical_necessity_verdict"),
        confidence_score=decision_data.get("confidence_score", 0.9),
        notes=decision_data.get("notes", ""),
        next_steps=decision_data.get("next_steps", ""),
        requires_manual_review=decision_data.get("requires_manual_review", False),
        manual_review_reasons=decision_data.get("manual_review_reasons", []),
    )
    db.add(decision)
    db.commit()
    return decision