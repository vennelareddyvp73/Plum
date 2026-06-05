import sys
import os

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from app.db.database import SessionLocal
from app.db.models import Claim, Document, Decision, Member
from app.db import crud
from app.services.rules_engine import run_rules
from app.pipeline.graph import adjudication_llm_node, PipelineState

db = SessionLocal()
try:
    print("==================================================")
    print("Testing Requirement 2: Duplicate / Fraud Controls")
    print("==================================================")
    
    # Verify EMP026 exists
    member = db.query(Member).filter(Member.id == "EMP026").first()
    if not member:
        print("EMP026 not found in DB! Creating...")
        member = Member(id="EMP026", name="Test Member 026")
        db.add(member)
        db.commit()
    
    # 1. Clean up any left over test claims for EMP026 first
    claims = db.query(Claim).filter(Claim.member_id == "EMP026").all()
    for c in claims:
        db.query(Decision).filter(Decision.claim_id == c.id).delete()
        db.query(Document).filter(Document.claim_id == c.id).delete()
        db.query(Claim).filter(Claim.id == c.id).delete()
    db.commit()
    print("Database cleaned for EMP026.")
    
    # 2. Check initial bill numbers and counts
    init_bills = crud.get_existing_bill_numbers(db, "EMP026")
    init_counts = crud.get_bill_number_counts(db, "EMP026")
    print(f"Initial existing bills: {init_bills}")
    print(f"Initial bill counts: {init_counts}")
    assert len(init_bills) == 0
    assert len(init_counts) == 0
    
    # 3. Create a REJECTED claim with bill number "BILL_TST_123"
    print("\nCreating first rejected claim...")
    c1 = Claim(id="TEST_C1", member_id="EMP026", treatment_date="2024-10-15", claimed_amount=1000, approved_amount=0, status="REJECTED")
    db.add(c1)
    db.commit()
    doc1 = Document(claim_id="TEST_C1", doc_type="medical_bill", file_path="", extracted_json={"bill_number": "BILL_TST_123"})
    db.add(doc1)
    db.commit()
    
    # 4. Verify duplicate bypass
    existing_bills = crud.get_existing_bill_numbers(db, "EMP026")
    bill_counts = crud.get_bill_number_counts(db, "EMP026")
    print(f"After 1 rejected claim:")
    print(f"  get_existing_bill_numbers: {existing_bills} (Expected: [] because it was rejected)")
    print(f"  get_bill_number_counts: {bill_counts} (Expected: {{'BILL_TST_123': 1}})")
    assert "BILL_TST_123" not in existing_bills
    assert bill_counts.get("BILL_TST_123") == 1
    
    # 5. Check duplicate rule (should pass)
    violations, details, copay = run_rules(
        claim={"medical_bill_number": "BILL_TST_123", "total_claimed_amount": 1000, "amounts_by_category": {"consultation": 1000}},
        member={"id": "EMP026"},
        ytd_approved=0.0,
        previous_claims_same_day=0,
        existing_bill_numbers=existing_bills,
        bill_number_counts=bill_counts
    )
    print(f"  Violations with 1 previous rejected attempt: {violations} (Expected: no DUPLICATE_CLAIM or EXCESSIVE_REENTRIES)")
    assert "DUPLICATE_CLAIM" not in violations
    assert "EXCESSIVE_REENTRIES" not in violations

    # 6. Create 2 more rejected claims (making it 3 previous submissions)
    print("\nCreating 2 more rejected claims...")
    c2 = Claim(id="TEST_C2", member_id="EMP026", treatment_date="2024-10-15", claimed_amount=1000, approved_amount=0, status="REJECTED")
    c3 = Claim(id="TEST_C3", member_id="EMP026", treatment_date="2024-10-15", claimed_amount=1000, approved_amount=0, status="REJECTED")
    db.add(c2)
    db.add(c3)
    db.commit()
    doc2 = Document(claim_id="TEST_C2", doc_type="medical_bill", file_path="", extracted_json={"bill_number": "BILL_TST_123"})
    doc3 = Document(claim_id="TEST_C3", doc_type="medical_bill", file_path="", extracted_json={"bill_number": "BILL_TST_123"})
    db.add(doc2)
    db.add(doc3)
    db.commit()
    
    # Verify counts
    bill_counts = crud.get_bill_number_counts(db, "EMP026")
    print(f"After 3 rejected claims:")
    print(f"  get_bill_number_counts: {bill_counts} (Expected: {{'BILL_TST_123': 3}})")
    assert bill_counts.get("BILL_TST_123") == 3
    
    # 7. Check excessive reentries rule (should trigger EXCESSIVE_REENTRIES)
    violations, details, copay = run_rules(
        claim={"medical_bill_number": "BILL_TST_123", "total_claimed_amount": 1000, "amounts_by_category": {"consultation": 1000}},
        member={"id": "EMP026"},
        ytd_approved=0.0,
        previous_claims_same_day=0,
        existing_bill_numbers=[],
        bill_number_counts=bill_counts
    )
    print(f"  Violations with 3 previous rejected attempts: {violations} (Expected: ['EXCESSIVE_REENTRIES'])")
    assert "EXCESSIVE_REENTRIES" in violations
    
    # Cleanup test claims
    for cid in ("TEST_C1", "TEST_C2", "TEST_C3"):
        db.query(Document).filter(Document.claim_id == cid).delete()
        db.query(Claim).filter(Claim.id == cid).delete()
    db.commit()
    print("Cleanup successful.")

    print("\n==================================================")
    print("Testing Requirement 1: Partially Approved Status")
    print("==================================================")
    
    # Case A: Claimed amount is auto-calculated to bill total, no policy limits/copays.
    # Expected: Decision is APPROVED, with no deductions.
    state_a: PipelineState = {
        "claim_id": "TEST_CL_A",
        "member_id": "EMP026",
        "treatment_date": "2024-10-15",
        "claim_amount": 1000.0,
        "files": {},
        "ocr_texts": {},
        "member": {},
        "ytd_approved": 0.0,
        "ytd_category_approved": {},
        "previous_claims_same_day": 0,
        "existing_bill_numbers": [],
        "bill_number_counts": {},
        "prescription": {},
        "pharmacy_bill": {},
        "diagnosis_test": {},
        "medical_bill": {},
        "aggregated_claim": {
            "total_claimed_amount": 1000.0,
            "amounts_by_category": {"consultation": 1000.0} # Bill total is 1000
        },
        "violations": [],
        "violation_details": [],
        "copay_info": {},
        "decision": None,
        "error": None
    }
    
    # Mock LLM decision outputting APPROVED
    from unittest.mock import patch
    with patch("app.pipeline.graph.run_final_adjudication") as mock_adj:
        mock_adj.return_value = {
            "decision": "APPROVED",
            "confidence_score": 0.95,
            "notes": "Consultation verified.",
            "next_steps": "Process payment."
        }
        res = adjudication_llm_node(state_a)
        decision = res["decision"]
        print(f"Case A (Claim 1000 = Bill 1000):")
        print(f"  Decision: {decision['decision']} (Expected: APPROVED)")
        print(f"  Approved Amt: {decision['approved_amount']} (Expected: 1000)")
        print(f"  Deductions: {decision['deductions']}")
        assert decision["decision"] == "APPROVED"
        assert decision["approved_amount"] == 1000.0
        assert len(decision["deductions"]) == 0

    # Case B: Claimed amount is auto-calculated, and co-payment applies.
    # Expected: Decision is PARTIAL.
    state_b = dict(state_a)
    state_b["copay_info"] = {"copay": 100.0} # co-pay applies
    with patch("app.pipeline.graph.run_final_adjudication") as mock_adj:
        mock_adj.return_value = {
            "decision": "APPROVED",
            "confidence_score": 0.95,
            "notes": "Consultation verified.",
            "next_steps": "Process payment."
        }
        res = adjudication_llm_node(state_b)
        decision = res["decision"]
        print(f"Case B (Claim 1000 = Bill 1000, co-pay 100):")
        print(f"  Decision: {decision['decision']} (Expected: PARTIAL)")
        print(f"  Approved Amt: {decision['approved_amount']} (Expected: 900)")
        print(f"  Deductions: {decision['deductions']}")
        assert decision["decision"] == "PARTIAL"
        assert decision["approved_amount"] == 900.0
        assert len(decision["deductions"]) == 1
        assert decision["deductions"][0]["type"] == "copay"
        
    # Case C: Claimed amount is auto-calculated, no policy limits/copays, but LLM returned PARTIAL.
    # Expected: Decision is APPROVED, with no deductions.
    state_c = dict(state_a)
    with patch("app.pipeline.graph.run_final_adjudication") as mock_adj:
        mock_adj.return_value = {
            "decision": "PARTIAL", # LLM returned PARTIAL
            "confidence_score": 0.95,
            "notes": "Consultation verified.",
            "next_steps": "Process payment."
        }
        res = adjudication_llm_node(state_c)
        decision = res["decision"]
        print(f"Case C (Claim 1000 = Bill 1000, LLM returned PARTIAL):")
        print(f"  Decision: {decision['decision']} (Expected: APPROVED)")
        print(f"  Approved Amt: {decision['approved_amount']} (Expected: 1000)")
        print(f"  Deductions: {decision['deductions']}")
        assert decision["decision"] == "APPROVED"
        assert decision["approved_amount"] == 1000.0
        assert len(decision["deductions"]) == 0

    # Case E: Combined Consultation and Diagnostic claim, with co-payment.
    # Expected: Co-payment of 10% is deducted ONLY from Consultation category.
    state_e = dict(state_a)
    state_e["claim_amount"] = 1770.0
    state_e["aggregated_claim"] = {
        "total_claimed_amount": 1770.0,
        "amounts_by_category": {"consultation": 1180.0, "diagnostic": 590.0}
    }
    state_e["copay_info"] = {"copay": 118.0} # 10% of 1180
    with patch("app.pipeline.graph.run_final_adjudication") as mock_adj:
        mock_adj.return_value = {
            "decision": "APPROVED",
            "confidence_score": 0.95,
            "notes": "Verified.",
            "next_steps": "Process."
        }
        res = adjudication_llm_node(state_e)
        decision = res["decision"]
        print(f"Case E (Consultation ₹1,180 + Diagnostic ₹590, copay ₹118):")
        print(f"  Decision: {decision['decision']} (Expected: PARTIAL)")
        print(f"  Approved Amt: {decision['approved_amount']} (Expected: 1652)")
        print(f"  Category Approved Amounts: {decision['category_approved_amounts']}")
        assert decision["decision"] == "PARTIAL"
        assert decision["approved_amount"] == 1652.0
        assert decision["category_approved_amounts"]["consultation"] == 1062.0
        assert decision["category_approved_amounts"]["diagnostic"] == 590.0

    # Case F: Multi-category copay deduction verification (validating indentation bug fix)
    # Expected: Copay/discount is applied exactly once.
    state_f = dict(state_a)
    state_f["claim_amount"] = 4677.0
    state_f["aggregated_claim"] = {
        "total_claimed_amount": 4677.0,
        "amounts_by_category": {"consultation": 1500.0, "pharmacy": 3177.0}
    }
    # 10% copay on 1500 consultation = 150
    # 30% copay on branded drugs pharmacy = 953.10
    state_f["copay_info"] = {"copay": 150.0, "branded_drug_copay": 953.10}
    with patch("app.pipeline.graph.run_final_adjudication") as mock_adj:
        mock_adj.return_value = {
            "decision": "APPROVED",
            "confidence_score": 0.95,
            "notes": "Verified.",
            "next_steps": "Process."
        }
        res = adjudication_llm_node(state_f)
        decision = res["decision"]
        print(f"Case F (Indentation Check: Consultation ₹1,500 + Pharmacy ₹3,177):")
        print(f"  Decision: {decision['decision']} (Expected: PARTIAL)")
        print(f"  Approved Amt: {decision['approved_amount']} (Expected: 3573.9)")
        print(f"  Deductions: {decision['deductions']}")
        assert decision["decision"] == "PARTIAL"
        assert decision["approved_amount"] == 3573.90
        # Check that copay was only added once and branded drug copay was only added once
        copay_count = sum(1 for d in decision["deductions"] if d["type"] == "copay")
        branded_copay_count = sum(1 for d in decision["deductions"] if d["type"] == "copay_branded_drug")
        assert copay_count == 1
        assert branded_copay_count == 1

    # Case G: Under-claim balancing math verification
    # Expected: The approved amount plus the sum of scaled deductions must equal the claimed amount.
    state_g = dict(state_a)
    state_g["claim_amount"] = 4000.0
    state_g["aggregated_claim"] = {
        "total_claimed_amount": 4000.0,
        "amounts_by_category": {"consultation": 1500.0, "pharmacy": 3177.0}
    }
    state_g["copay_info"] = {"copay": 150.0, "branded_drug_copay": 953.10}
    with patch("app.pipeline.graph.run_final_adjudication") as mock_adj:
        mock_adj.return_value = {
            "decision": "APPROVED",
            "confidence_score": 0.95,
            "notes": "Verified.",
            "next_steps": "Process."
        }
        res = adjudication_llm_node(state_g)
        decision = res["decision"]
        print(f"Case G (Under-claim: Claimed ₹4,000, Bill ₹4,677, Eligible ₹3,573.90):")
        print(f"  Decision: {decision['decision']} (Expected: PARTIAL)")
        print(f"  Approved Amt: {decision['approved_amount']} (Expected: 3573.9)")
        print(f"  Deductions: {decision['deductions']}")
        assert decision["decision"] == "PARTIAL"
        assert decision["approved_amount"] == 3573.90
        # Verify that approved amount + sum of deductions == claimed amount (4000)
        deductions_sum = sum(d["amount"] for d in decision["deductions"])
        assert round(decision["approved_amount"] + deductions_sum, 2) == 4000.0

    # Case I: Dental limits split verification
    # We will test both the aggregator classification and the rules engine tracking.
    from app.services.aggregator import aggregate
    
    print("\nCase I: Dental limits split verification")
    # 1. Test Aggregator splitting
    medical_bill_dental = {
        "hospital_name": "Pearl Dental Clinic",
        "total_amount": 3540.0,
        "items": [
            {"description": "Routine Dental Checkup & Consultation", "category": "dental", "amount": 1000.0},
            {"description": "Composite Dental Filling Procedure", "category": "dental", "amount": 2000.0}
        ],
        "gst": 540.0
    }
    agg_claim = aggregate(
        medical_bill=medical_bill_dental,
        member_id="EMP026",
        treatment_date="2024-10-15",
        claim_amount=3540.0
    )
    print(f"  Aggregated amounts: {agg_claim['amounts_by_category']}")
    # 1000 checkup scaled by 3540/3000 = 1180
    # 2000 filling scaled by 3540/3000 = 2360
    assert abs(agg_claim["amounts_by_category"]["dental_routine"] - 1180.0) < 1e-2
    assert abs(agg_claim["amounts_by_category"]["dental_procedure"] - 2360.0) < 1e-2

    # 2. Test Rules Engine limits capping
    # Scenario A: Claim fits under remaining sub-limits (YTD spent: routine=0, procedure=0). Expected: no SUB_LIMIT_EXCEEDED
    violations, details, copay = run_rules(
        claim=agg_claim,
        member={"id": "EMP026"},
        ytd_approved=0.0,
        previous_claims_same_day=0,
        existing_bill_numbers=[],
        bill_number_counts={},
        ytd_category_approved={"dental_routine": 0.0, "dental_procedure": 0.0}
    )
    print(f"  Violations under limits (Expected: []): {violations}")
    assert "SUB_LIMIT_EXCEEDED" not in violations

    # Scenario B: Routine claim exceeds its ₹2,000 sub-limit (YTD spent routine=1500, procedure=0).
    # Since 1180 + 1500 = 2680 > 2000. Expected: SUB_LIMIT_EXCEEDED for dental_routine
    violations, details, copay = run_rules(
        claim=agg_claim,
        member={"id": "EMP026"},
        ytd_approved=0.0,
        previous_claims_same_day=0,
        existing_bill_numbers=[],
        bill_number_counts={},
        ytd_category_approved={"dental_routine": 1500.0, "dental_procedure": 0.0}
    )
    print(f"  Violations when routine limit exceeded (Expected: ['SUB_LIMIT_EXCEEDED']): {violations}")
    assert "SUB_LIMIT_EXCEEDED" in violations
    sub_limit_violation = next(d for d in details if d["rule_code"] == "SUB_LIMIT_EXCEEDED")
    assert sub_limit_violation["category"] == "dental_routine"
    assert "Dental routine amount" in sub_limit_violation["description"]

    # Scenario C: Procedure claim exceeds its ₹10,000 sub-limit (YTD spent routine=0, procedure=9000).
    # Since 2360 + 9000 = 11360 > 10000. Expected: SUB_LIMIT_EXCEEDED for dental_procedure
    violations, details, copay = run_rules(
        claim=agg_claim,
        member={"id": "EMP026"},
        ytd_approved=0.0,
        previous_claims_same_day=0,
        existing_bill_numbers=[],
        bill_number_counts={},
        ytd_category_approved={"dental_routine": 0.0, "dental_procedure": 9000.0}
    )
    print(f"  Violations when procedure limit exceeded (Expected: ['SUB_LIMIT_EXCEEDED']): {violations}")
    assert "SUB_LIMIT_EXCEEDED" in violations
    sub_limit_violation_proc = next(d for d in details if d["rule_code"] == "SUB_LIMIT_EXCEEDED")
    assert sub_limit_violation_proc["category"] == "dental_procedure"
    assert "Dental procedure amount" in sub_limit_violation_proc["description"]

    print("\nALL TEST CASES PASSED SUCCESSFULLY!")

finally:
    db.close()
