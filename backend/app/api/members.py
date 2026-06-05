"""Member-level endpoints: stats, policy info."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date

from app.db.database import get_db
from app.db import crud
from app.config import POLICY

router = APIRouter(prefix="/api", tags=["members"])


@router.get("/members/{member_id}/stats")
def member_stats(member_id: str, treatment_date: str = None, db: Session = Depends(get_db)):
    """
    Returns a member's claims summary, remaining coverage limits, and category balances.
    Accepts an optional treatment_date query parameter.
    """
    member = crud.get_member(db, member_id)
    if not member:
        raise HTTPException(404, "Member not found.")

    tx_date_str = treatment_date or str(date.today())
    try:
        tx_date = date.fromisoformat(tx_date_str)
        year = tx_date.year
    except ValueError:
        raise HTTPException(400, "Invalid treatment_date format. Must be YYYY-MM-DD.")

    ytd_approved = crud.get_ytd_approved(db, member_id, tx_date_str)
    category_balances = crud.get_category_balances(db, member_id, tx_date_str)
    claims = crud.get_member_claims(db, member_id)
    annual_limit = POLICY["coverage_details"]["annual_limit"]

    approved_claims = sum(1 for c in claims if c["status"] == "APPROVED")

    return {
        "member_id":         member.id,
        "member_name":       member.name,
        "age":               member.age,
        "gender":            member.gender,
        "policy_start_date": str(member.policy_start_date) if member.policy_start_date else None,
        "policy_end_date":   str(member.policy_end_date) if member.policy_end_date else None,
        "policy_year":       year,
        "is_active":         member.is_active,
        "join_date":         str(member.join_date) if member.join_date else None,
        "ytd_approved":      ytd_approved,
        "annual_limit":      annual_limit,
        "remaining_limit":   max(annual_limit - ytd_approved, 0),
        "total_claims":      len(claims),
        "approved_claims":   approved_claims,
        "category_balances": category_balances,
        "sub_limits": {
            "consultation": POLICY["coverage_details"]["consultation_fees"]["sub_limit"],
            "pharmacy":     POLICY["coverage_details"]["pharmacy"]["sub_limit"],
            "diagnostics":  POLICY["coverage_details"]["diagnostic_tests"]["sub_limit"],
            "dental_routine":   POLICY["coverage_details"]["dental"]["routine_checkup_limit"],
            "dental_procedure": POLICY["coverage_details"]["dental"]["sub_limit"],
            "vision":       POLICY["coverage_details"]["vision"]["sub_limit"],
            "alternative":  POLICY["coverage_details"]["alternative_medicine"]["sub_limit"],
        },
    }


@router.get("/policy")
def get_policy():
    """Returns the full policy configuration."""
    return POLICY


@router.get("/members")
def list_members(db: Session = Depends(get_db)):
    """Returns all seeded test members."""
    members = crud.get_all_members(db)
    return [
        {
            "id":        m.id,
            "name":      m.name,
            "is_active": m.is_active,
            "join_date": str(m.join_date) if m.join_date else None,
        }
        for m in members
    ]