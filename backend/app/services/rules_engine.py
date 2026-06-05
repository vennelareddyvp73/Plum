"""Pure Python rule engine — no LLM calls."""
import re
from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

from rapidfuzz import fuzz
from app.config import POLICY

# --- Policy constants ---
ANNUAL_LIMIT     = POLICY["coverage_details"]["annual_limit"]             # 50000
PER_CLAIM_LIMIT  = POLICY["coverage_details"]["per_claim_limit"]          # 5000
MIN_AMOUNT       = POLICY["claim_requirements"]["minimum_claim_amount"]   # 500
SUBMIT_DAYS      = POLICY["claim_requirements"]["submission_timeline_days"] # 30

SUB_LIMITS = {
    "consultation": POLICY["coverage_details"]["consultation_fees"]["sub_limit"],           # 2000
    "pharmacy":     POLICY["coverage_details"]["pharmacy"]["sub_limit"],                    # 15000
    "diagnostic":   POLICY["coverage_details"]["diagnostic_tests"]["sub_limit"],            # 10000
    "dental_routine":   POLICY["coverage_details"]["dental"]["routine_checkup_limit"],      # 2000
    "dental_procedure": POLICY["coverage_details"]["dental"]["sub_limit"],                  # 10000
    "vision":       POLICY["coverage_details"]["vision"]["sub_limit"],                      # 5000
    "alternative":  POLICY["coverage_details"]["alternative_medicine"]["sub_limit"],        # 8000
}

WAITING = {
    "initial":        POLICY["waiting_periods"]["initial_waiting"],              # 30
    "pre_existing":   POLICY["waiting_periods"]["pre_existing_diseases"],        # 365
    "maternity":      POLICY["waiting_periods"]["maternity"],                    # 270
    "diabetes":       POLICY["waiting_periods"]["specific_ailments"]["diabetes"],        # 90
    "hypertension":   POLICY["waiting_periods"]["specific_ailments"]["hypertension"],    # 90
    "joint_replace":  POLICY["waiting_periods"]["specific_ailments"]["joint_replacement"], # 730
}

CONSULTATION_COPAY = POLICY["coverage_details"]["consultation_fees"]["copay_percentage"] / 100  # 0.10
NETWORK_DISCOUNT   = POLICY["coverage_details"]["consultation_fees"]["network_discount"] / 100  # 0.20
BRANDED_COPAY      = POLICY["coverage_details"]["pharmacy"]["branded_drugs_copay"] / 100        # 0.30
DENTAL_ROUTINE_CAP = POLICY["coverage_details"]["dental"]["routine_checkup_limit"]              # 2000

NETWORK_HOSPITALS = [h.lower() for h in POLICY["network_hospitals"]]

# --- Regex patterns ---
_DR_REG   = re.compile(r"[A-Z]+/\d+/\d{4}")
_AYUR_REG = re.compile(r"AYUR/[A-Z]+/\d+/\d{4}")

# --- Keyword sets ---
_DIABETES_KW     = {"diabetes", "diabetic", "type 1 diabetes", "type 2 diabetes",
                    "hyperglycemia", "metformin", "glimepiride", "insulin"}
_HYPER_KW        = {"hypertension", "high blood pressure", "amlodipine", "losartan", "atenolol"}
_MATERNITY_KW    = {"pregnancy", "prenatal", "antenatal", "maternity", "obstetric", "childbirth"}
_JOINT_KW        = {"joint replacement", "knee replacement", "hip replacement", "arthroplasty"}
_COSMETIC_KW     = {"whitening", "bleaching", "cosmetic", "aesthetic", "lasik",
                    "laser vision", "liposuction", "botox", "filler", "teeth whitening"}
_WEIGHT_LOSS_KW  = {"weight loss", "obesity treatment", "bariatric", "slimming", "diet plan"}
_INFERTILITY_KW  = {"infertility", "ivf", "iui", "fertility treatment"}
_EXPERIMENTAL_KW = {"experimental", "clinical trial", "unproven", "investigational"}
_SELF_HARM_KW    = {"self inflicted", "self-harm", "suicide attempt"}
_ADVENTURE_KW    = {"adventure sport", "skydiving", "bungee", "mountaineering"}
_HIV_KW          = {"hiv", "aids"}
_ALCOHOL_KW      = {"alcoholism", "substance abuse", "drug abuse", "de-addiction"}
_WAR_KW          = {"war", "nuclear", "riot", "civil war"}
_VITAMIN_KW      = {"vitamin", "supplement", "multivitamin"}


def _parse_date(s: str) -> Optional[date]:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _contains_any(text: str, keywords: set) -> Optional[str]:
    t = text.lower()
    for kw in keywords:
        if kw in t:
            return kw
    return None


def run_rules(
    claim: Dict[str, Any],
    member: Optional[Dict],
    ytd_approved: float,
    previous_claims_same_day: int,
    existing_bill_numbers: List[str],
    today: Optional[date] = None,
    ytd_category_approved: Optional[Dict[str, float]] = None,
    bill_number_counts: Optional[Dict[str, int]] = None,
) -> Tuple[List[str], List[Dict], Dict[str, float]]:
    """
    Returns:
      violations        — list of rule codes that fired
      violation_details — list of dicts with rule_code + description
      copay_info        — adjustments to apply to approved_amount
    """
    if today is None:
        today = date.today()

    violations: List[str] = []
    details:    List[Dict] = []
    copay:      Dict[str, float] = {}

    def _add(code: str, desc: str, **kw):
        violations.append(code)
        details.append({"rule_code": code, "description": desc, **kw})

    total = float(claim.get("total_claimed_amount", 0))
    tx_date = _parse_date(claim.get("treatment_date", ""))
    amounts = claim.get("amounts_by_category", {})

    # 1. BELOW_MIN_AMOUNT
    if total < MIN_AMOUNT:
        _add("BELOW_MIN_AMOUNT", f"Claim ₹{total:.0f} is below the minimum claimable amount of ₹{MIN_AMOUNT}")

    # 2. LATE_SUBMISSION
    if tx_date and (today - tx_date).days > SUBMIT_DAYS:
        _add("LATE_SUBMISSION",
             f"Claim submitted {(today - tx_date).days} days after treatment; limit is {SUBMIT_DAYS} days")

    # 3. MISSING_DOCUMENTS
    has_rx  = claim.get("has_prescription", False)
    has_bill = claim.get("has_medical_bill", False)
    has_pharma = claim.get("has_pharmacy_bill", False)

    if not has_rx:
        _add("MISSING_DOCUMENTS",
             "Prescription from a registered doctor was not submitted. A prescription is mandatory for all OPD claims.")
    elif not has_bill:
        _add("MISSING_DOCUMENTS",
             "Medical bill was not submitted. A medical bill is required to process the claim.")

    # 4. INVALID_PRESCRIPTION / DOCTOR_REG_INVALID
    reg = claim.get("doctor_registration")
    if has_rx:
        if not reg:
            _add("INVALID_PRESCRIPTION", "Doctor registration number is missing from the prescription.")
        else:
            match_dr = _DR_REG.search(reg)
            match_ayur = _AYUR_REG.search(reg)
            if not (match_dr or match_ayur):
                _add("DOCTOR_REG_INVALID",
                     f"Doctor registration '{reg}' does not match the required format "
                     "[STATE]/[NUMBER]/[YEAR] or AYUR/[STATE]/[NUMBER]/[YEAR].")
            else:
                claim["doctor_registration"] = (match_ayur or match_dr).group(0)

    # 5. DATE_MISMATCH
    parsed_dates = [_parse_date(d) for d in claim.get("doc_dates", []) if _parse_date(d)]
    if len(parsed_dates) > 1:
        span = (max(parsed_dates) - min(parsed_dates)).days
        if span > 1:
            _add("DATE_MISMATCH",
                 f"Document dates span {span} days. All documents must reflect the same treatment date.")

    # 6. ILLEGIBLE_DOCUMENTS
    if claim.get("avg_extraction_confidence", 1.0) < 0.5:
        _add("ILLEGIBLE_DOCUMENTS",
             "One or more documents appear illegible or of poor quality. "
             "Please resubmit clear scans.")

    # 7. PATIENT_MISMATCH
    names = [n for n in claim.get("patient_names", []) if n]
    if len(names) > 1:
        for i, n1 in enumerate(names):
            for n2 in names[i + 1:]:
                if fuzz.token_sort_ratio(n1.lower(), n2.lower()) < 80:
                    _add("PATIENT_MISMATCH",
                         f"Patient name mismatch across documents: '{n1}' vs '{n2}'. "
                         "Names must match policy records.")
                    break
    if member and member.get("name"):
        member_name = member["name"]
        for n in names:
            if fuzz.token_sort_ratio(n.lower(), member_name.lower()) < 80:
                _add("PATIENT_MISMATCH",
                     f"Patient name in documents ('{n}') does not match member's name in policy records ('{member_name}'). "
                     "Names must match policy records.")
                break

    # 8–11. MEMBER / POLICY / WAITING
    if not member:
        _add("MEMBER_NOT_COVERED", "Member ID not found in policy records.")
    else:
        if not member.get("is_active", True):
            _add("POLICY_INACTIVE", "The policy is currently inactive.")
        elif tx_date:
            ps = _parse_date(str(member.get("policy_start_date", "")))
            pe = _parse_date(str(member.get("policy_end_date", "")))
            if ps and tx_date < ps:
                _add("POLICY_INACTIVE",
                     f"Treatment date {tx_date} is before policy start date {ps}.")
            if pe and tx_date > pe:
                _add("POLICY_INACTIVE",
                     f"Treatment date {tx_date} is after policy end date {pe}.")

        # Waiting period
        if tx_date:
            join = _parse_date(str(member.get("join_date", "")))
            if join:
                days_in = (tx_date - join).days
                diag = (claim.get("diagnosis") or "").lower()
                meds = " ".join(m.get("name") or "" for m in (claim.get("medicines") or []) if m).lower()
                text = f"{diag} {meds}"

                def _waiting(period_key: str, eligible_days: int, label: str):
                    if days_in < eligible_days:
                        eligible = join + timedelta(days=eligible_days)
                        _add("WAITING_PERIOD",
                             f"{label} has a {eligible_days}-day waiting period. "
                             f"Eligible from {eligible}.")

                if days_in < WAITING["initial"]:
                    _waiting("initial", WAITING["initial"], "All new OPD claims")
                elif _contains_any(text, _DIABETES_KW):
                    _waiting("diabetes", WAITING["diabetes"], "Diabetes")
                elif _contains_any(text, _HYPER_KW):
                    _waiting("hypertension", WAITING["hypertension"], "Hypertension")
                elif _contains_any(text, _MATERNITY_KW):
                    _waiting("maternity", WAITING["maternity"], "Maternity")
                elif _contains_any(text, _JOINT_KW):
                    _waiting("joint_replace", WAITING["joint_replace"], "Joint replacement")

    # 12. COSMETIC_PROCEDURE
    diagnosis_text = claim.get("diagnosis") or ""
    bill_items = claim.get("bill_items") or []
    medicines = claim.get("medicines") or []
    
    all_text = " ".join([
        diagnosis_text,
        " ".join(item or "" for item in bill_items if item),
        " ".join(m.get("name") or "" for m in medicines if m),
    ]).lower()

    kw = _contains_any(all_text, _COSMETIC_KW)
    if kw:
        _add("COSMETIC_PROCEDURE",
             f"Cosmetic/aesthetic procedure detected ('{kw}'). "
             "Such procedures are excluded from coverage.")

    # 13. EXCLUDED_CONDITION
    for kw_set, code_label in [
        (_WEIGHT_LOSS_KW,  "Weight loss treatment"),
        (_INFERTILITY_KW,  "Infertility treatment"),
        (_EXPERIMENTAL_KW, "Experimental treatment"),
        (_SELF_HARM_KW,    "Self-inflicted injury"),
        (_ADVENTURE_KW,    "Adventure sports injury"),
        (_HIV_KW,          "HIV/AIDS treatment"),
        (_ALCOHOL_KW,      "Alcohol/substance abuse treatment"),
        (_WAR_KW,          "War/nuclear risk"),
    ]:
        kw = _contains_any(all_text, kw_set)
        if kw:
            _add("EXCLUDED_CONDITION",
                 f"{code_label} ('{kw}') is excluded from coverage under this policy.")
            break

    # Vitamins: allowed only if diagnosed deficiency and pharmacy expenses are claimed
    has_pharmacy_claim = claim.get("has_pharmacy_bill", False) or (amounts.get("pharmacy", 0) > 0)
    if has_pharmacy_claim:
        vit_kw = _contains_any(all_text, _VITAMIN_KW)
        if vit_kw and "deficiency" not in (claim.get("diagnosis") or "").lower():
            _add("EXCLUDED_CONDITION",
                 f"Vitamins/supplements ('{vit_kw}') are covered only when prescribed "
                 "for a diagnosed deficiency. Please provide diagnosis confirming deficiency.")

    # 14. PRE_AUTH_MISSING
    tests_requested = claim.get("tests_requested") or []
    tests_text = " ".join(str(t) if isinstance(t, str) else (t.get("test_name") or "")
                          for t in tests_requested if t).lower()
    if ("mri" in tests_text or "ct scan" in tests_text or "ct-scan" in tests_text) and total > 10000:
        _add("PRE_AUTH_MISSING",
             "MRI and CT Scan require pre-authorization for claims above ₹10,000. "
             "Please obtain pre-authorization and resubmit.")

    # 15. PER_CLAIM_EXCEEDED
    if total > PER_CLAIM_LIMIT:
        _add("PER_CLAIM_EXCEEDED",
             f"Claim amount ₹{total:.0f} exceeds the per-claim limit of ₹{PER_CLAIM_LIMIT}.",
             value=total, limit=PER_CLAIM_LIMIT)

    # 16. ANNUAL_LIMIT_EXCEEDED
    if ytd_approved + total > ANNUAL_LIMIT:
        _add("ANNUAL_LIMIT_EXCEEDED",
             f"Adding this claim would bring your year-to-date total to "
             f"₹{ytd_approved + total:.0f}, exceeding the annual limit of ₹{ANNUAL_LIMIT}.",
             ytd=ytd_approved, total=total, limit=ANNUAL_LIMIT)

    # 17. SUB_LIMIT_EXCEEDED
    for cat, limit in SUB_LIMITS.items():
        ytd_spent = float((ytd_category_approved or {}).get(cat, 0.0))
        remaining_limit = max(limit - ytd_spent, 0.0)
        amt = float(amounts.get(cat, 0))
        if amt > remaining_limit:
            _add("SUB_LIMIT_EXCEEDED",
                 f"{cat.replace('_', ' ').capitalize()} amount ₹{amt:.0f} exceeds the remaining sub-limit of ₹{remaining_limit:.0f} (YTD spent: ₹{ytd_spent:.0f}, total sub-limit: ₹{limit:.0f}).",
                 category=cat, value=amt, limit=remaining_limit, ytd_spent=ytd_spent)

    # 18. DUPLICATE_CLAIM
    for bn_key in ("medical_bill_number", "pharmacy_bill_number"):
        bn = claim.get(bn_key)
        if bn and bn in existing_bill_numbers:
            _add("DUPLICATE_CLAIM",
                 f"Bill number '{bn}' has already been submitted in a previous claim.")
            break

    # 19. SUSPICIOUS_PATTERN (3+ claims on same treatment date)
    if previous_claims_same_day >= 3:
        _add("SUSPICIOUS_PATTERN",
             f"This member has {previous_claims_same_day} claims on the same treatment date. "
             "The claim has been flagged for manual review due to unusual submission frequency.")

    # 20. EXCESSIVE_REENTRIES (4+ attempts of same bill number, meaning >= 3 previous ones)
    for bn_key in ("medical_bill_number", "pharmacy_bill_number"):
        bn = claim.get(bn_key)
        if bn:
            prev_cnt = bill_number_counts.get(bn, 0) if bill_number_counts else 0
            if prev_cnt >= 3:
                _add("EXCESSIVE_REENTRIES",
                     f"Bill number '{bn}' has been submitted {prev_cnt} times previously. "
                     f"This exceeds the limit of 3 attempts for re-entering a bill. "
                     f"The claim is flagged for manual review under suspicion of fraud.")
                break

    # --- Copay / discount (not rejections) ---
    consultation_amt = float(amounts.get("consultation", 0.0))
    if consultation_amt > 0:
        is_net = claim.get("is_network_hospital", False)
        if is_net:
            discount_amt = round(consultation_amt * NETWORK_DISCOUNT, 2)
            copay["network_discount"] = discount_amt
            remaining_consult = consultation_amt - discount_amt
            copay["copay"] = round(remaining_consult * CONSULTATION_COPAY, 2)
        else:
            copay["copay"] = round(consultation_amt * CONSULTATION_COPAY, 2)

    branded = float(claim.get("branded_drug_amount", 0))
    if branded > 0:
        copay["branded_drug_copay"] = round(branded * BRANDED_COPAY, 2)

    return violations, details, copay