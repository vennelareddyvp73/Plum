"""
LangGraph pipeline: Extract → Aggregate → Rules → Decision

Two paths after rules:
  - violations found  → violation_llm_node  (explains violations, PARTIAL or REJECTED)
  - all rules passed  → adjudication_llm_node (checks medical necessity + fraud)

Two extraction modes (handled inside extract_node):
  - Vision mode  (files dict populated):    image/PDF → vision LLM → structured JSON
  - Text mode    (ocr_texts dict populated): raw text  → text LLM  → structured JSON

CHANGE: claim_amount is now clamped to actual bill totals in aggregate_node.
        Users cannot claim more than the sum of uploaded bills.
        The "unsupported_claim_amount" deduction has been removed from both LLM nodes
        since it can no longer trigger after upstream clamping.
"""
import logging
from typing import TypedDict, Optional, Dict, Any, List

from langgraph.graph import StateGraph, END

from app.services.extractor import extract_document_from_image, extract_document
from app.services.aggregator import aggregate
from app.services.rules_engine import run_rules, SUB_LIMITS, PER_CLAIM_LIMIT, ANNUAL_LIMIT
from app.services.adjudicator import explain_violations, run_final_adjudication

logger = logging.getLogger(__name__)

_COSMETIC_KW = {"whitening", "bleaching", "cosmetic", "aesthetic", "lasik",
                "liposuction", "botox", "filler", "teeth whitening"}


class PipelineState(TypedDict):
    claim_id:       str
    member_id:      str
    treatment_date: str
    claim_amount:   float

    # Vision mode: doc_type → file path on disk
    files: Dict[str, str]

    # Text mode: doc_type → raw text (used by /test-submit, bypasses vision)
    ocr_texts: Dict[str, str]

    # DB context injected before pipeline runs
    member:                     Optional[Dict]
    ytd_approved:               float
    ytd_category_approved:      Dict[str, float]
    previous_claims_same_day:   int
    existing_bill_numbers:      List[str]
    bill_number_counts:         Optional[Dict[str, int]]

    # Extracted document JSONs (one per doc type)
    prescription:   Optional[Dict]
    pharmacy_bill:  Optional[Dict]
    diagnosis_test: Optional[Dict]
    medical_bill:   Optional[Dict]

    aggregated_claim:  Optional[Dict]
    violations:        List[str]
    violation_details: List[Dict]
    copay_info:        Dict[str, float]
    decision:          Optional[Dict]
    error:             Optional[str]


# ── Nodes ─────────────────────────────────────────────────────────────────────

def extract_node(state: PipelineState) -> dict:
    """
    Single node handling both extraction modes:
    - Vision mode : file_path → vision LLM  (real document uploads)
    - Text mode   : raw text  → text LLM    (test-submit endpoint)
    """
    extracted: Dict[str, Optional[Dict]] = {
        "prescription": None, "pharmacy_bill": None,
        "diagnosis_test": None, "medical_bill": None,
    }

    if state.get("files"):
        for doc_type, file_path in state["files"].items():
            try:
                extracted[doc_type] = extract_document_from_image(doc_type, file_path)
            except Exception as e:
                logger.error(f"[extract] vision failed for {doc_type}: {e}")
                extracted[doc_type] = None

    elif state.get("ocr_texts"):
        for doc_type, text in state["ocr_texts"].items():
            if not text or not text.strip():
                continue
            try:
                extracted[doc_type] = extract_document(doc_type, text)
            except Exception as e:
                logger.error(f"[extract] text failed for {doc_type}: {e}")
                extracted[doc_type] = None

    return extracted


def aggregate_node(state: PipelineState) -> dict:
    claim = aggregate(
        prescription=state.get("prescription"),
        pharmacy_bill=state.get("pharmacy_bill"),
        diagnosis_test=state.get("diagnosis_test"),
        medical_bill=state.get("medical_bill"),
        member_id=state["member_id"],
        treatment_date=state["treatment_date"],
        claim_amount=state["claim_amount"],
    )

    # ── Override claim_amount with actual bill totals ──────────────────────────────
    # Claimed amount is auto-calculated as the sum of uploaded bills.
    # If bill_total is 0 (all docs failed extraction), fall back to raw_claimed
    # so rules_node can fire missing-document violations naturally.
    bill_total = sum(
        float(v) for v in claim.get("amounts_by_category", {}).values()
    )
    raw_claimed = float(claim.get("total_claimed_amount", 0.0))

    if bill_total > 0:
        logger.info(
            f"[aggregate] claim_id={state.get('claim_id')} setting "
            f"total_claimed_amount from ₹{raw_claimed:,.2f} → ₹{bill_total:,.2f}"
        )
        claim["total_claimed_amount"]    = round(bill_total, 2)
        claim["claim_amount_clamped"]    = True          # audit flag
        claim["original_claimed_amount"] = raw_claimed   # preserved for records

    return {"aggregated_claim": claim}


def rules_node(state: PipelineState) -> dict:
    from datetime import datetime
    claim_id = state.get("claim_id", "")
    today_val = None
    if claim_id.startswith("TST_"):
        tx_date_str = state["aggregated_claim"].get("treatment_date", "")
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                today_val = datetime.strptime(tx_date_str, fmt).date()
                break
            except ValueError:
                continue

    violations, details, copay = run_rules(
        claim=state["aggregated_claim"],
        member=state["member"],
        ytd_approved=state["ytd_approved"],
        previous_claims_same_day=state["previous_claims_same_day"],
        existing_bill_numbers=state["existing_bill_numbers"],
        today=today_val,
        ytd_category_approved=state.get("ytd_category_approved"),
        bill_number_counts=state.get("bill_number_counts"),
    )
    return {"violations": violations, "violation_details": details, "copay_info": copay}


def _route(state: PipelineState) -> str:
    return "violation_path" if state["violations"] else "adjudication_path"


def _cashless_info(claim: dict, copay_info: dict, approved: float, decision_type: str) -> dict:
    """
    Determine cashless eligibility and network discount amount.
    Cashless is auto-approved when:
      - Hospital is a network hospital
      - Decision is APPROVED or PARTIAL
      - Approved amount is within the instant_approval_limit (₹5,000 per policy)
    """
    from app.config import POLICY
    instant_limit = POLICY.get("cashless_facilities", {}).get("instant_approval_limit", 5000)
    is_network = claim.get("is_network_hospital", False)
    nd_amount = copay_info.get("network_discount", 0.0) or 0.0
    cashless = (
        is_network
        and decision_type in ("APPROVED", "PARTIAL")
        and approved <= instant_limit
    )
    return {
        "cashless_approved":       cashless if is_network else None,
        "network_discount_amount": round(nd_amount, 2) if nd_amount > 0 else None,
    }


def violation_llm_node(state: PipelineState) -> dict:
    """
    Rule violations found.
    LLM provides human-readable explanations.
    Decision: PARTIAL (soft violations only) or REJECTED (any hard violation).

    NOTE: "unsupported_claim_amount" deduction removed — claim is already clamped
    to bill totals in aggregate_node so this case can no longer occur.
    """
    claim = state["aggregated_claim"]
    total = float(claim["total_claimed_amount"])
    codes = set(state["violations"])

    reasoning = explain_violations(claim, state["violation_details"])

    manual_review_codes = {"SUSPICIOUS_PATTERN", "EXCESSIVE_REENTRIES"}
    soft_codes = {"COSMETIC_PROCEDURE", "SUB_LIMIT_EXCEEDED", "PER_CLAIM_EXCEEDED", "ANNUAL_LIMIT_EXCEEDED"}
    review_codes = codes & manual_review_codes
    hard_codes = codes - soft_codes - manual_review_codes

    deductions = []
    category_approved = {cat: float(val) for cat, val in claim.get("amounts_by_category", {}).items()}

    # Deduct uncovered categories (e.g. procedure, other)
    COVERED_CATEGORIES = {"consultation", "pharmacy", "diagnostic", "dental_routine", "dental_procedure", "vision", "alternative"}
    for cat in list(category_approved.keys()):
        if cat not in COVERED_CATEGORIES:
            cat_amt = category_approved[cat]
            if cat_amt > 0:
                category_approved[cat] = 0.0
                deductions.append({
                    "type":        "uncovered_category",
                    "description": f"Category '{cat}' is not covered under this OPD policy.",
                    "amount":      cat_amt,
                })

    if review_codes:
        category_approved_mr = {cat: float(val) for cat, val in claim.get("amounts_by_category", {}).items()}
        return {"decision": {
            "claim_id":                  state["claim_id"],
            "decision":                  "MANUAL_REVIEW",
            "claimed_amount":            total,
            "category_claimed_amounts":  {cat: float(val) for cat, val in claim.get("amounts_by_category", {}).items()},
            "approved_amount":           0.0,
            "category_approved_amounts": {cat: 0.0 for cat in category_approved_mr},
            "deductions":                [],
            "rejection_reasons":         list(codes),
            "violation_reasoning":       reasoning,
            "fraud_flags":               list(review_codes),
            "medical_necessity_verdict": None,
            "confidence_score":          0.65,
            "notes":                     "Claim flagged for manual review due to suspicious submission pattern.",
            "next_steps":                "A claims officer will review your claim and contact you within 2 business days.",
            "requires_manual_review":    True,
            "manual_review_reasons":     [d["description"] for d in state["violation_details"]
                                          if d["rule_code"] in manual_review_codes],
        }}

    if hard_codes:
        category_approved_rej = {cat: float(val) for cat, val in claim.get("amounts_by_category", {}).items()}
        return {"decision": {
            "claim_id":                  state["claim_id"],
            "decision":                  "REJECTED",
            "claimed_amount":            total,
            "category_claimed_amounts":  {cat: float(val) for cat, val in claim.get("amounts_by_category", {}).items()},
            "approved_amount":           0.0,
            "category_approved_amounts": {cat: 0.0 for cat in category_approved_rej},
            "deductions":                [],
            "rejection_reasons":         list(codes),
            "violation_reasoning":       reasoning,
            "fraud_flags":               [],
            "medical_necessity_verdict": None,
            "confidence_score":          0.97,
            "notes":                     f"Claim rejected due to {len(hard_codes)} policy violation(s).",
            "next_steps":                "Review the violations listed. Correct the issues and resubmit, or contact support to appeal.",
            "requires_manual_review":    False,
            "manual_review_reasons":     [],
        }}

    # Deduct cosmetic procedures
    if "COSMETIC_PROCEDURE" in codes:
        bill_items     = ((claim.get("raw_docs") or {}).get("medical_bill") or {}).get("items", [])
        cosmetic_total = sum(
            float(i["amount"]) for i in bill_items
            if i.get("is_covered") is False
            or any(kw in i.get("description", "").lower() for kw in _COSMETIC_KW)
        )
        if cosmetic_total > 0:
            deductions.append({
                "type":        "excluded_item",
                "description": "Cosmetic/excluded procedures removed",
                "amount":      round(cosmetic_total, 2),
            })
            for i in bill_items:
                if i.get("is_covered") is False or any(kw in i.get("description", "").lower() for kw in _COSMETIC_KW):
                    item_cat = i.get("category", "other")
                    if item_cat in category_approved:
                        category_approved[item_cat] = max(category_approved[item_cat] - float(i.get("amount", 0)), 0.0)
        else:
            category_approved_mr = {cat: float(val) for cat, val in claim.get("amounts_by_category", {}).items()}
            return {"decision": {
                "claim_id":                  state["claim_id"],
                "decision":                  "MANUAL_REVIEW",
                "claimed_amount":            total,
                "category_claimed_amounts":  {cat: float(val) for cat, val in claim.get("amounts_by_category", {}).items()},
                "approved_amount":           0.0,
                "category_approved_amounts": {cat: 0.0 for cat in category_approved_mr},
                "deductions":                [],
                "rejection_reasons":         list(codes),
                "violation_reasoning":       reasoning,
                "fraud_flags":               [],
                "medical_necessity_verdict": None,
                "confidence_score":          0.60,
                "notes":                     "Cosmetic procedure detected but individual item amounts could not be determined.",
                "next_steps":                "A claims officer will review your bill and contact you within 2 business days.",
                "requires_manual_review":    True,
                "manual_review_reasons":     ["Cosmetic item amounts indeterminate"],
            }}

    # Deduct sub-limits exceeded
    if "SUB_LIMIT_EXCEEDED" in codes:
        ytd_cat = state.get("ytd_category_approved") or {}
        for cat, limit in SUB_LIMITS.items():
            cat_amt = category_approved.get(cat, 0.0)
            ytd_spent = float(ytd_cat.get(cat, 0.0))
            remaining = max(limit - ytd_spent, 0.0)
            if cat_amt > remaining:
                excess = round(cat_amt - remaining, 2)
                deductions.append({
                    "type":        "sub_limit_exceeded",
                    "description": f"{cat.capitalize()} remaining sub-limit (₹{remaining:,.2f})",
                    "amount":      excess,
                })
                if cat in category_approved:
                    category_approved[cat] = round(remaining, 2)

    # Base eligible amount is the sum of category approved amounts
    eligible_base = sum(category_approved.values())

    # Deduct per-claim limit exceeded
    if "PER_CLAIM_EXCEEDED" in codes:
        if eligible_base > PER_CLAIM_LIMIT:
            excess = round(eligible_base - PER_CLAIM_LIMIT, 2)
            eligible_base = PER_CLAIM_LIMIT
            deductions.append({
                "type":        "per_claim_limit_exceeded",
                "description": f"Claim amount exceeds per-claim limit (limit: ₹{PER_CLAIM_LIMIT:,.2f})",
                "amount":      excess,
            })

    # Deduct annual limit exceeded
    if "ANNUAL_LIMIT_EXCEEDED" in codes:
        ytd_val = float(state.get("ytd_approved") or 0.0)
        remaining = max(ANNUAL_LIMIT - ytd_val, 0.0)
        if eligible_base > remaining:
            excess = round(eligible_base - remaining, 2)
            eligible_base = remaining
            deductions.append({
                "type":        "annual_limit_exceeded",
                "description": f"Claim amount exceeds remaining annual limit (remaining: ₹{remaining:,.2f})",
                "amount":      excess,
            })

    # Final approved amount is capped by the user's claimed amount
    approved = min(eligible_base, total)

    # Apply copay / discount only to consultation category (preserves separability)
    copay_info = state.get("copay_info") or {}
    if copay_info.get("network_discount"):
        nd = copay_info["network_discount"]
        category_approved["consultation"] = max(category_approved.get("consultation", 0.0) - nd, 0.0)
        deductions.append({
            "type":        "network_discount",
            "description": "20% network hospital discount on consultation fee",
            "amount":      nd,
        })
    if copay_info.get("copay"):
        cp = copay_info["copay"]
        category_approved["consultation"] = max(category_approved.get("consultation", 0.0) - cp, 0.0)
        deductions.append({
            "type":        "copay",
            "description": "10% co-payment on consultation fee",
            "amount":      cp,
        })
    if copay_info.get("branded_drug_copay"):
        bdcp = copay_info["branded_drug_copay"]
        category_approved["pharmacy"] = max(category_approved.get("pharmacy", 0.0) - bdcp, 0.0)
        deductions.append({
            "type":        "branded_drug_copay",
            "description": "30% co-pay on branded drugs",
            "amount":      bdcp,
        })

    # Recalculate approved from updated category amounts
    approved = min(sum(category_approved.values()), total)

    # Ensure category approved amounts sum up to final approved
    sum_cat_approved = sum(category_approved.values())
    diff = sum_cat_approved - approved
    if diff > 0:
        if "consultation" in category_approved and category_approved["consultation"] >= diff:
            category_approved["consultation"] = round(category_approved["consultation"] - diff, 2)
        else:
            scale = approved / sum_cat_approved if sum_cat_approved > 0 else 0.0
            for cat in category_approved:
                category_approved[cat] = round(category_approved[cat] * scale, 2)
    elif diff < 0:
        scale = approved / sum_cat_approved if sum_cat_approved > 0 else 0.0
        for cat in category_approved:
            category_approved[cat] = round(category_approved[cat] * scale, 2)

    # Scale deductions so approved + sum(deductions) == total
    current_deductions_sum = sum(d["amount"] for d in deductions)
    target_deductions_sum = max(total - approved, 0.0)
    if current_deductions_sum > target_deductions_sum:
        scale = target_deductions_sum / current_deductions_sum if current_deductions_sum > 0 else 0.0
        for d in deductions:
            d["amount"] = round(d["amount"] * scale, 2)
        deductions = [d for d in deductions if d["amount"] > 0]

    extra = _cashless_info(claim, state.get("copay_info") or {}, round(max(approved, 0.0), 2), "PARTIAL")
    return {"decision": {
        "claim_id":                  state["claim_id"],
        "decision":                  "PARTIAL",
        "claimed_amount":            total,
        "category_claimed_amounts":  {cat: float(val) for cat, val in claim.get("amounts_by_category", {}).items()},
        "approved_amount":           round(max(approved, 0.0), 2),
        "category_approved_amounts": category_approved,
        "deductions":                deductions,
        "rejection_reasons":         list(codes),
        "violation_reasoning":       reasoning,
        "fraud_flags":               [],
        "medical_necessity_verdict": None,
        "confidence_score":          0.95,
        "notes":                     "Claim partially approved. Excluded items have been deducted.",
        "next_steps":                "The approved amount will be reimbursed. Excluded items cannot be claimed under this policy.",
        "requires_manual_review":    False,
        "manual_review_reasons":     [],
        **extra,
    }}


def adjudication_llm_node(state: PipelineState) -> dict:
    """
    All policy rules passed.
    LLM performs final assessment: medical necessity, fraud, cross-doc consistency.

    NOTE: "unsupported_claim_amount" deduction removed — claim is already clamped
    to bill totals in aggregate_node so this case can no longer occur.
    """
    claim = state["aggregated_claim"]
    total = float(claim["total_claimed_amount"])
    copay = state["copay_info"]

    llm = run_final_adjudication(
        claim=claim,
        previous_claims_same_day=state["previous_claims_same_day"],
        high_value=total > 25000,
        member=state.get("member"),
    )

    approved   = total
    deductions = []
    category_approved = {cat: float(val) for cat, val in claim.get("amounts_by_category", {}).items()}

    # Deduct uncovered categories (e.g. procedure, other)
    COVERED_CATEGORIES = {"consultation", "pharmacy", "diagnostic", "dental_routine", "dental_procedure", "vision", "alternative"}
    for cat in list(category_approved.keys()):
        if cat not in COVERED_CATEGORIES:
            cat_amt = category_approved[cat]
            if cat_amt > 0:
                category_approved[cat] = 0.0
                deductions.append({
                    "type":        "uncovered_category",
                    "description": f"Category '{cat}' is not covered under this OPD policy.",
                    "amount":      cat_amt,
                })

    # Apply copay / discount only to consultation category (preserves separability)
    if copay.get("network_discount"):
        nd = copay["network_discount"]
        category_approved["consultation"] = max(category_approved.get("consultation", 0.0) - nd, 0.0)
        deductions.append({
            "type":        "network_discount",
            "description": "20% network hospital discount on consultation fee",
            "amount":      nd,
        })
    if copay.get("copay"):
        cp = copay["copay"]
        category_approved["consultation"] = max(category_approved.get("consultation", 0.0) - cp, 0.0)
        deductions.append({"type": "copay", "description": "10% co-payment on consultation fee", "amount": cp})
    if copay.get("branded_drug_copay"):
        bdcp = copay["branded_drug_copay"]
        category_approved["pharmacy"] = max(category_approved.get("pharmacy", 0.0) - bdcp, 0.0)
        deductions.append({"type": "copay_branded_drug", "description": "30% co-pay on branded drugs", "amount": bdcp})

    # Base eligible amount is the sum of category approved amounts after per-category deductions
    eligible_base = sum(category_approved.values())

    # Final approved amount is capped by the user's claimed amount
    approved = min(eligible_base, total)

    decision_type = llm.get("decision", "APPROVED")
    if decision_type in ("APPROVED", "PARTIAL"):
        real_deductions = [d for d in deductions if d["type"] not in ("copay", "copay_branded_drug", "network_discount")]
        if real_deductions:
            decision_type = "PARTIAL"
        else:
            decision_type = "APPROVED"

    rejection_reasons = llm.get("rejection_reasons", [])
    if decision_type == "PARTIAL" and not rejection_reasons:
        for d in deductions:
            if d["type"] == "uncovered_category":
                rejection_reasons.append("UNCOVERED_CATEGORY")

    if decision_type == "REJECTED":
        approved   = 0.0
        deductions = []
        for cat in category_approved:
            category_approved[cat] = 0.0
    else:
        # Ensure category approved amounts sum up to final approved
        sum_cat_approved = sum(category_approved.values())
        diff = sum_cat_approved - approved
        if diff > 0:
            if "consultation" in category_approved and category_approved["consultation"] >= diff:
                category_approved["consultation"] = round(category_approved["consultation"] - diff, 2)
            else:
                scale = approved / sum_cat_approved if sum_cat_approved > 0 else 0.0
                for cat in category_approved:
                    category_approved[cat] = round(category_approved[cat] * scale, 2)
        elif diff < 0:
            scale = approved / sum_cat_approved if sum_cat_approved > 0 else 0.0
            for cat in category_approved:
                category_approved[cat] = round(category_approved[cat] * scale, 2)

    # Scale deductions so approved + sum(deductions) == total
    current_deductions_sum = sum(d["amount"] for d in deductions)
    target_deductions_sum = max(total - approved, 0.0)
    if current_deductions_sum > target_deductions_sum:
        scale = target_deductions_sum / current_deductions_sum if current_deductions_sum > 0 else 0.0
        for d in deductions:
            d["amount"] = round(d["amount"] * scale, 2)
        deductions = [d for d in deductions if d["amount"] > 0]

    extra = _cashless_info(claim, copay, round(max(approved, 0), 2), decision_type)
    return {"decision": {
        "claim_id":                  state["claim_id"],
        "decision":                  decision_type,
        "claimed_amount":            total,
        "category_claimed_amounts":  {cat: float(val) for cat, val in claim.get("amounts_by_category", {}).items()},
        "approved_amount":           round(max(approved, 0), 2),
        "category_approved_amounts": category_approved,
        "deductions":                deductions,
        "rejection_reasons":         rejection_reasons,
        "violation_reasoning":       [],
        "fraud_flags":               llm.get("fraud_flags", []),
        "medical_necessity_verdict": llm.get("medical_necessity_verdict"),
        "confidence_score":          float(llm.get("confidence_score", 0.9)),
        "notes":                     llm.get("notes", ""),
        "next_steps":                llm.get("next_steps", ""),
        "requires_manual_review":    llm.get("requires_manual_review", False),
        "manual_review_reasons":     llm.get("manual_review_reasons", []),
        **extra,
    }}


# ── Build ──────────────────────────────────────────────────────────────────────

def build_pipeline():
    g = StateGraph(PipelineState)

    g.add_node("extract",          extract_node)
    g.add_node("aggregate",        aggregate_node)
    g.add_node("rules",            rules_node)
    g.add_node("violation_llm",    violation_llm_node)
    g.add_node("adjudication_llm", adjudication_llm_node)

    g.set_entry_point("extract")
    g.add_edge("extract",   "aggregate")
    g.add_edge("aggregate", "rules")
    g.add_conditional_edges("rules", _route, {
        "violation_path":    "violation_llm",
        "adjudication_path": "adjudication_llm",
    })
    g.add_edge("violation_llm",    END)
    g.add_edge("adjudication_llm", END)

    return g.compile()


pipeline = build_pipeline()