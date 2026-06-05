"""Merge all extracted document JSONs into a single unified claim dict."""
from typing import Optional, Dict, Any
from app.config import POLICY

_NETWORK = [h.lower() for h in POLICY["network_hospitals"]]


def aggregate(
    prescription: Optional[Dict] = None,
    pharmacy_bill: Optional[Dict] = None,
    diagnosis_test: Optional[Dict] = None,
    medical_bill: Optional[Dict] = None,
    member_id: str = "",
    treatment_date: str = "",
    claim_amount: float = 0.0,
) -> Dict[str, Any]:

    # Network hospital detection
    hospital_name = (medical_bill or {}).get("hospital_name", "")
    is_network = any(nh in hospital_name.lower() for nh in _NETWORK)

    # Amounts by category (from medical bill line items)
    amounts: Dict[str, float] = {
        "consultation": 0.0, "diagnostic": 0.0, "pharmacy": 0.0,
        "dental_routine": 0.0, "dental_procedure": 0.0, "vision": 0.0,
        "alternative": 0.0, "procedure": 0.0, "other": 0.0,
    }
    if medical_bill:
        items_sum = sum(float(item.get("amount", 0)) for item in medical_bill.get("items", []))
        total_amount = float(medical_bill.get("total_amount", 0) or 0)
        
        # Proportional scale factor to distribute GST/taxes to categories
        scale = 1.0
        if items_sum > 0 and total_amount > items_sum:
            scale = total_amount / items_sum

        consultation_items_sum = sum(
            float(item.get("amount", 0)) * scale
            for item in medical_bill.get("items", [])
            if item.get("category") == "consultation"
        )
        if consultation_items_sum > 0:
            amounts["consultation"] = consultation_items_sum
        elif medical_bill.get("consultation_fee"):
            amounts["consultation"] = float(medical_bill["consultation_fee"]) * scale

        for item in medical_bill.get("items", []):
            cat = item.get("category", "other")
            if cat == "consultation" and consultation_items_sum > 0:
                continue
            item_amt = float(item.get("amount", 0)) * scale
            if cat == "dental":
                desc = item.get("description", "").lower()
                if any(kw in desc for kw in ["checkup", "check-up", "consultation", "examination", "routine"]):
                    amounts["dental_routine"] += item_amt
                else:
                    amounts["dental_procedure"] += item_amt
            elif cat in amounts:
                amounts[cat] += item_amt
            else:
                amounts["other"] += item_amt

    # Pharmacy amount from separate pharmacy bill
    if pharmacy_bill:
        amounts["pharmacy"] += float(pharmacy_bill.get("total_amount", 0))

    # Branded drug amount for copay calc
    branded_amount = sum(
        float(i.get("amount", 0))
        for i in (pharmacy_bill or {}).get("items", [])
        if i.get("is_branded") is True
    )

    # Total claimed
    total = claim_amount or (
        float((medical_bill or {}).get("total_amount", 0)) +
        float((pharmacy_bill or {}).get("total_amount", 0))
    )

    # Doc dates
    dates = [
        doc.get("date") for doc in [prescription, pharmacy_bill, diagnosis_test, medical_bill]
        if doc and doc.get("date")
    ]

    # Patient names across docs
    patient_names = [
        doc.get("patient_name") for doc in [prescription, pharmacy_bill, diagnosis_test, medical_bill]
        if doc and doc.get("patient_name")
    ]

    # Patient ages and genders across docs
    patient_ages = [
        doc.get("patient_age") for doc in [prescription, diagnosis_test]
        if doc and doc.get("patient_age") is not None
    ]
    patient_genders = [
        doc.get("patient_gender") for doc in [prescription]
        if doc and doc.get("patient_gender")
    ]

    # Avg extraction confidence
    confs = [
        doc.get("extraction_confidence")
        for doc in [prescription, pharmacy_bill, diagnosis_test, medical_bill]
        if doc and doc.get("extraction_confidence") is not None
    ]
    avg_conf = round(sum(confs) / len(confs), 3) if confs else 1.0

    return {
        "member_id": member_id,
        "treatment_date": treatment_date,
        "total_claimed_amount": total,
        "hospital_name": hospital_name,
        "is_network_hospital": is_network,
        "amounts_by_category": amounts,
        "branded_drug_amount": branded_amount,
        "diagnosis": (prescription or {}).get("diagnosis", ""),
        "bill_items": [i["description"] for i in (medical_bill or {}).get("items", [])],
        "medicines": (prescription or {}).get("medicines", []),
        "tests_requested": (prescription or {}).get("investigations_advised", []) or [],
        "tests_results": (diagnosis_test or {}).get("tests", []),
        "doc_dates": dates,
        "patient_names": patient_names,
        "patient_ages": patient_ages,
        "patient_genders": patient_genders,
        "doctor_registration": (prescription or {}).get("doctor_registration"),
        "medical_bill_number": (medical_bill or {}).get("bill_number"),
        "pharmacy_bill_number": (pharmacy_bill or {}).get("bill_number"),
        "avg_extraction_confidence": avg_conf,
        "has_prescription":   prescription is not None,
        "has_pharmacy_bill":  pharmacy_bill is not None,
        "has_diagnosis_test": diagnosis_test is not None,
        "has_medical_bill":   medical_bill is not None,
        "raw_docs": {
            "prescription":   prescription,
            "pharmacy_bill":  pharmacy_bill,
            "diagnosis_test": diagnosis_test,
            "medical_bill":   medical_bill,
        },
    }