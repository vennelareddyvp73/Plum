"""
Run all 10 test cases against the live API using text-based submission.
No scanned documents required — uses the /api/claims/test-submit endpoint.

Usage:
  python run_tests.py               # run all 10 cases
  python run_tests.py --case TC001  # run a specific case

Requires the backend to be running:
  uvicorn app.main:app --reload
"""
import json
import sys
import requests

BASE = "http://localhost:8000"

TEST_CASES = [
    {
        "case_id": "TC001",
        "name": "Simple Consultation — APPROVED",
        "payload": {
            "member_id": "EMP001",
            "treatment_date": "2024-11-01",
            "claim_amount": 1500,
            "prescription_text": """
                Dr. Sharma, MBBS MD
                Reg. No: KA/45678/2015
                Apollo Clinic, Bangalore
                Date: 01/11/2024
                Patient: Zephyr Thorne, Age: 35, Male
                C/O: Fever, body ache
                Diagnosis: Viral Fever
                Rx: Tab Paracetamol 650mg 1-0-1 x 5 days
                    Tab Vitamin C 500mg 0-0-1 x 5 days
                Inv: CBC, Dengue NS1
                Follow-up: 07/11/2024
                [Stamp] [Signature]
            """,
            "medical_bill_text": """
                Apollo Clinic | 12 MG Road Bangalore | GST: 29ABCDE1234F1Z5
                Bill No: BL-TC001  Date: 01/11/2024
                Patient: Zephyr Thorne
                Consultation Fee       1000
                CBC Blood Test          300
                Dengue NS1 Test         200
                Total: 1500  Cash
                [Stamp] [Authorized Signatory]
            """,
        },
        "expected_decision": "APPROVED",
        "expected_approved": 1350,
    },
    {
        "case_id": "TC002",
        "name": "Dental — Partial (whitening excluded)",
        "payload": {
            "member_id": "EMP002",
            "treatment_date": "2024-10-15",
            "claim_amount": 12000,
            "prescription_text": """
                Dr. Patel, BDS MDS
                Reg. No: MH/23456/2018
                City Dental Clinic, Mumbai
                Date: 15/10/2024
                Patient: Nova Vance, Age: 30, Female
                Diagnosis: Tooth decay requiring root canal
                Treatment: Root canal treatment, Teeth whitening
                [Stamp] [Signature]
            """,
            "medical_bill_text": """
                City Dental Clinic | Mumbai
                Bill No: BL-TC002  Date: 15/10/2024
                Patient: Nova Vance
                Root canal treatment    8000
                Teeth whitening         4000
                Total: 12000
                [Stamp]
            """,
        },
        "expected_decision": "PARTIAL",
        "expected_approved": 8000,
    },
    {
        "case_id": "TC003",
        "name": "Per-Claim Limit Exceeded — REJECTED",
        "payload": {
            "member_id": "EMP003",
            "treatment_date": "2024-10-20",
            "claim_amount": 7500,
            "prescription_text": """
                Dr. Gupta, MBBS MD
                Reg. No: DL/34567/2016
                Delhi Medical Centre
                Date: 20/10/2024
                Patient: Orion Blackwood, Age: 40, Male
                Diagnosis: Gastroenteritis
                Rx: Tab Antibiotics 500mg, Probiotics
                [Stamp] [Signature]
            """,
            "medical_bill_text": """
                Delhi Medical Centre
                Bill No: BL-TC003  Date: 20/10/2024
                Patient: Orion Blackwood
                Consultation Fee    2000
                Medicines           5500
                Total: 7500  Cash
                [Stamp]
            """,
        },
        "expected_decision": "PARTIAL",
        "expected_approved": 5000,
    },
    {
        "case_id": "TC004",
        "name": "Missing Prescription — REJECTED",
        "payload": {
            "member_id": "EMP004",
            "treatment_date": "2024-10-25",
            "claim_amount": 2000,
            "medical_bill_text": """
                HealthCare Clinic, Hyderabad
                Bill No: BL-TC004  Date: 25/10/2024
                Patient: Lyra Sterling
                Consultation Fee    1500
                Medicines            500
                Total: 2000  Cash
                [Stamp]
            """,
        },
        "expected_decision": "REJECTED",
        "expected_rules": ["MISSING_DOCUMENTS"],
    },
    {
        "case_id": "TC005",
        "name": "Diabetes Waiting Period — REJECTED",
        "payload": {
            "member_id": "EMP005",
            "treatment_date": "2024-10-15",
            "claim_amount": 3000,
            "prescription_text": """
                Dr. Mehta, MBBS MD
                Reg. No: GJ/56789/2014
                Ahmedabad Diabetes Clinic
                Date: 15/10/2024
                Patient: Atlas Hayes, Age: 45, Male
                Diagnosis: Type 2 Diabetes
                Rx: Metformin 500mg 1-0-1, Glimepiride 2mg
                [Stamp] [Signature]
            """,
            "medical_bill_text": """
                Ahmedabad Diabetes Clinic
                Bill No: BL-TC005  Date: 15/10/2024
                Patient: Atlas Hayes
                Consultation Fee    1000
                Medicines           2000
                Total: 3000  Cash
                [Stamp]
            """,
        },
        "expected_decision": "REJECTED",
        "expected_rules": ["WAITING_PERIOD"],
    },
    {
        "case_id": "TC006",
        "name": "Ayurvedic Treatment — APPROVED",
        "payload": {
            "member_id": "EMP006",
            "treatment_date": "2024-10-28",
            "claim_amount": 4000,
            "prescription_text": """
                Vaidya Krishnan, BAMS
                Reg. No: AYUR/KL/2345/2019
                Ayurvedic Wellness Centre, Kochi
                Date: 28/10/2024
                Patient: Freya Lindqvist, Age: 38, Female
                Diagnosis: Chronic joint pain
                Treatment: Panchakarma therapy
                [Stamp] [Signature]
            """,
            "medical_bill_text": """
                Ayurvedic Wellness Centre, Kochi
                Bill No: BL-TC006  Date: 28/10/2024
                Patient: Freya Lindqvist
                Consultation Fee    1000
                Panchakarma therapy 3000
                Total: 4000  Cash
                [Stamp]
            """,
        },
        "expected_decision": "APPROVED",
        "expected_approved": 4000,
    },
    {
        "case_id": "TC007",
        "name": "MRI Without Pre-Auth — REJECTED",
        "payload": {
            "member_id": "EMP007",
            "treatment_date": "2024-11-02",
            "claim_amount": 15000,
            "prescription_text": """
                Dr. Rao, MBBS MS
                Reg. No: AP/67890/2017
                Neurology Clinic, Hyderabad
                Date: 02/11/2024
                Patient: Cassian Mercer, Age: 50, Male
                Diagnosis: Suspected lumbar disc herniation
                Investigations: MRI Lumbar Spine
                [Stamp] [Signature]
            """,
            "medical_bill_text": """
                Scan Centre, Hyderabad
                Bill No: BL-TC007  Date: 02/11/2024
                Patient: Cassian Mercer
                MRI Lumbar Spine    15000
                Total: 15000  Card
                [Stamp]
            """,
        },
        "expected_decision": "REJECTED",
        "expected_rules": ["PRE_AUTH_MISSING"],
    },
    {
        "case_id": "TC008",
        "name": "Fraud — Multiple Same-Day Claims — MANUAL_REVIEW",
        "payload": {
            "member_id": "EMP008",
            "treatment_date": "2024-10-30",
            "claim_amount": 4800,
            "prescription_text": """
                Dr. Khan, MBBS MD
                Reg. No: UP/45678/2016
                Lucknow Neurology Centre
                Date: 30/10/2024
                Patient: Aria Solis, Age: 35, Male
                Diagnosis: Migraine
                Rx: Sumatriptan 50mg, Propranolol 40mg
                [Stamp] [Signature]
            """,
            "medical_bill_text": """
                Lucknow Neurology Centre
                Bill No: BL-TC008  Date: 30/10/2024
                Patient: Aria Solis
                Consultation Fee    2000
                Medicines           2800
                Total: 4800  Cash
                [Stamp]
            """,
        },
        "expected_decision": "MANUAL_REVIEW",
        "note": "TC008: Submit this AFTER submitting 2-3 other claims for EMP008 on same date to trigger fraud detection",
    },
    {
        "case_id": "TC009",
        "name": "Excluded Condition (Weight Loss) — REJECTED",
        "payload": {
            "member_id": "EMP009",
            "treatment_date": "2024-10-18",
            "claim_amount": 8000,
            "prescription_text": """
                Dr. Banerjee, MBBS MD
                Reg. No: WB/34567/2015
                Weight Management Clinic, Kolkata
                Date: 18/10/2024
                Patient: Juno Devereux, Age: 42, Female
                Diagnosis: Obesity, BMI 35 - weight loss treatment
                Treatment: Bariatric consultation and diet plan
                [Stamp] [Signature]
            """,
            "medical_bill_text": """
                Weight Management Clinic, Kolkata
                Bill No: BL-TC009  Date: 18/10/2024
                Patient: Juno Devereux
                Consultation Fee    3000
                Diet plan           5000
                Total: 8000  Card
                [Stamp]
            """,
        },
        "expected_decision": "REJECTED",
        "expected_rules": ["EXCLUDED_CONDITION"],
    },
    {
        "case_id": "TC010",
        "name": "Network Hospital Cashless — APPROVED with discount",
        "payload": {
            "member_id": "EMP010",
            "treatment_date": "2024-11-03",
            "claim_amount": 4500,
            "prescription_text": """
                Dr. Iyer, MBBS MD
                Reg. No: TN/56789/2013
                Apollo Hospitals, Chennai
                Date: 03/11/2024
                Patient: Silas Vance, Age: 32, Male
                Diagnosis: Acute bronchitis
                Rx: Antibiotics 500mg, Bronchodilators
                [Stamp] [Signature]
            """,
            "medical_bill_text": """
                Apollo Hospitals | Anna Salai, Chennai | GST: 33ABCDE1234F1Z5
                Bill No: BL-TC010  Date: 03/11/2024
                Patient: Silas Vance
                Consultation Fee    1500
                Medicines           3000
                Total: 4500  UPI
                [Stamp] [Authorized Signatory]
            """,
        },
        "expected_decision": "APPROVED",
        "expected_approved": 4080,
        "note": "Apollo Hospitals = network → 20% discount applied to Consultation Fee, then 10% copay on remaining",
    },
]


def run_case(tc: dict, verbose: bool = True) -> dict:
    if tc["case_id"] == "TC008":
        # Pre-submit 3 dummy claims on the same day to trigger the SUSPICIOUS_PATTERN rule
        import copy
        for i in range(3):
            dummy_payload = copy.deepcopy(tc["payload"])
            dummy_payload["medical_bill_text"] = dummy_payload["medical_bill_text"].replace("BL-TC008", f"BL-TC008-DUMMY-{i}")
            requests.post(f"{BASE}/api/claims/test-submit", json=dummy_payload)

    resp = requests.post(f"{BASE}/api/claims/test-submit", json=tc["payload"])
    resp.raise_for_status()
    data = resp.json()
    decision = data["decision"]

    got     = decision["decision"]
    got_amt = decision.get("approved_amount", 0)
    exp     = tc.get("expected_decision", "?")
    exp_amt = tc.get("expected_approved")
    rules   = decision.get("rejection_reasons", [])
    conf    = decision.get("confidence_score", 0)
    passed  = got == exp

    status = "✅ PASS" if passed else "❌ FAIL"

    if verbose:
        print(f"\n{'-'*60}")
        print(f"{tc['case_id']}: {tc['name']}")
        print(f"  Result:     {got}  (expected: {exp})  {status}")
        print(f"  Approved:   INR {got_amt:,.0f}" + (f"  (expected: INR {exp_amt:,.0f})" if exp_amt else ""))
        print(f"  Confidence: {conf:.0%}")
        if rules:
            print(f"  Rules fired: {', '.join(rules)}")
        if tc.get("note"):
            print(f"  Note: {tc['note']}")
        if decision.get("fraud_flags"):
            print(f"  Fraud flags: {', '.join(decision['fraud_flags'])}")

    return {"case_id": tc["case_id"], "passed": passed, "got": got, "expected": exp}


def main():
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    filter_case = None
    if "--case" in sys.argv:
        idx = sys.argv.index("--case")
        filter_case = sys.argv[idx + 1].upper()

    cases = [tc for tc in TEST_CASES if not filter_case or tc["case_id"] == filter_case]

    print(f"\n{'='*60}")
    print("  Plum OPD Claims — Test Suite")
    print(f"  Running {len(cases)} test case(s)")
    print(f"{'='*60}")

    results = []
    import time
    for i, tc in enumerate(cases):
        if i > 0:
            time.sleep(3)
        results.append(run_case(tc))
    passed  = sum(r["passed"] for r in results)
    total   = len(results)

    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{total} passed")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()