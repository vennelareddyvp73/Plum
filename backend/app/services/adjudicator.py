"""LLM-based reasoning: violation explanations + final adjudication."""
import json
from typing import Dict, Any, List, Optional
from groq import Groq
from app.config import POLICY, settings

_client: Optional[Groq] = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.groq_api_key)
    return _client


_POLICY_SUMMARY = (
    f"Policy: Plum OPD Advantage | "
    f"Annual limit: ₹{POLICY['coverage_details']['annual_limit']} | "
    f"Per-claim limit: ₹{POLICY['coverage_details']['per_claim_limit']} | "
    f"Covered: Consultation, Diagnostics, Pharmacy, Dental, Vision, "
    f"Alternative medicine (Ayurveda/Homeopathy/Unani) | "
    f"Excluded: {', '.join(POLICY['exclusions'])} | "
    f"Network hospitals: {', '.join(POLICY['network_hospitals'])}"
)


def explain_violations(claim: Dict, violation_details: List[Dict]) -> List[Dict]:
    """Convert rule violation details into plain-English explanations for the claimant."""
    if not violation_details:
        return []

    prompt = f"""You are an insurance claims adjudicator at Plum explaining a decision to a claimant.
For each policy violation below, write a clear 1-2 sentence explanation in simple, empathetic English.
Where applicable, tell the claimant what they can do to resolve it.

Claim summary:
- Member: {claim.get('member_id')}
- Treatment date: {claim.get('treatment_date')}
- Claimed amount: ₹{claim.get('total_claimed_amount', 0):.0f}
- Diagnosis: {claim.get('diagnosis', 'N/A')}

Violations:
{json.dumps(violation_details, indent=2)}

Return JSON: {{"items": [{{"rule_code": "...", "explanation": "..."}}]}}"""

    try:
        resp = _get_client().chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=1024,
        )
        data = json.loads(resp.choices[0].message.content)
        result = data.get("items", data.get("explanations", data.get("violations", [])))
        return result if isinstance(result, list) else []
    except Exception as e:
        print(f"[explain_violations] LLM call failed: {e}")
        # fallback to standard rule descriptions
        return [{"rule_code": v.get("rule_code"), "explanation": v.get("description")} for v in violation_details if v]


def run_final_adjudication(
    claim: Dict[str, Any],
    previous_claims_same_day: int,
    high_value: bool,
    member: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Called when all policy rules pass.
    LLM performs final assessment: medical necessity, fraud signals, cross-document consistency.
    Can output: APPROVED, PARTIAL, REJECTED, or MANUAL_REVIEW.
    """
    lean_claim = {k: v for k, v in claim.items() if k != "raw_docs"}

    member_info_str = "N/A"
    if member:
        member_info_str = json.dumps({
            "db_name": member.get("name"),
            "db_gender": member.get("gender"),
            "db_is_active": member.get("is_active"),
        }, indent=2)

    prompt = f"""You are a senior insurance claims adjudicator at Plum.
All automated policy rules have passed for this claim. Perform a final quality review.

{_POLICY_SUMMARY}

Database Member Record (Ground Truth):
{member_info_str}

Claim data:
{json.dumps(lean_claim, indent=2, default=str)}

Context:
- Previous claims by this member on the same treatment date: {previous_claims_same_day}
- High-value claim (>₹25,000): {high_value}
- Average document extraction confidence: {claim.get('avg_extraction_confidence', 1.0):.2f}

Evaluate:
1. MEDICAL NECESSITY — Does the diagnosis justify the prescribed treatment, medicines, and tests?
   - Ensure the treatment aligns with standard medical practice.
   - Note: Standard orthopedic consultations, physiotherapy sessions (e.g., spine mobilization), and general diagnostic workups for common pain/injury conditions are standard medical care and are medically necessary. They are NOT cosmetic procedures.

2. AGE AND GENDER RELEVANCY & MISMATCH (CRITICAL)
   - Extract the patient name, age, and gender from all submitted documents (available in 'patient_names', 'patient_ages', 'patient_genders' inside Claim data).
   - Compare these extracted values against the Database Member Record (Ground Truth) and against each other.
   - ONLY flag an age or gender incompatibility if there is a clear, biologically impossible contradiction or absolute anatomical incompatibility.
   - Examples of actual incompatibilities:
     - Male patients undergoing pregnancy/obstetric checkups, gynecological consultations, NT scans, or taking pregnancy-related medication.
     - Female patients undergoing prostate procedures/surgeries, prostate-specific tests, or taking prostate medications.
     - Adults receiving purely pediatric-specific treatments, or children receiving geriatric-specific treatments.
   - DO NOT reject common general medical conditions (e.g., lower back pain, fever, dental work, etc.) or general medical services (e.g., Orthopedic Consultation Fee, general practitioner consultations, physiotherapy, standard pain medications) as they are fully compatible across all adult ages and genders.
   - If a genuine gender/age mismatch or biological incompatibility is found, reject the claim and set decision to "REJECTED" with a clear reason in "rejection_reasons". Otherwise, if names/genders match ground truth and are anatomically compatible, they should pass.

3. LAB REPORTS & OTHER BILLS RELEVANCY (CRITICAL)
   - Verify if the diagnostic tests performed in the lab reports (refer to 'tests_results') are relevant to the patient's diagnosis and matches what was prescribed ('tests_requested') or billed.
   - Check if there are bills for tests that were never prescribed, or if the lab reports/results are incompatible/irrelevant to the patient's diagnosis, age, or gender.
   - If a test report contains a test result (e.g. NT scan showing live fetus) that is completely irrelevant or impossible for the patient's ground truth gender (e.g. Male), this is a critical fraud signal and the claim must be REJECTED.

4. EXCLUSIONS & COSMETIC CLASSIFICATION
   - Only classify treatments as excluded (such as "Cosmetic procedures" or "Weight loss treatments") if they are explicitly aesthetic/cosmetic (e.g., teeth whitening, Botox for wrinkles, cosmetic surgery, liposuction, weight loss diets).
   - Do NOT classify physical therapy, orthopedic treatment, spine mobilization, or standard dental cleanings/extractions as cosmetic.
   - Note: If a treatment or service is simply not covered by the policy terms (for example, general procedures or surgeries under an OPD policy), do NOT reject the entire claim. Set the decision to PARTIAL or APPROVED and mention the non-covered item in the notes. The system will automatically deduct the non-covered category amount.

5. FRAUD SIGNALS
   - Unusual patterns (multiple same-day claims, document inconsistencies, suspicious changes, impossible medical reports)?

6. CROSS-DOCUMENT CONSISTENCY
   - Does the prescription diagnosis align with the bill items and test results?

Decision guide:
- APPROVED: Everything checks out, claim is legitimate, medically justified, and consistent in name, age, gender, and test relevancy.
- PARTIAL: Some items are medically justified/covered, others are not. Use this if there are uncovered services/procedures alongside covered consultations.
- REJECTED: Medical necessity clearly not established for the primary diagnosis, severe biological age/gender mismatch, or strong fraud evidence. Do not use this for simple uncovered category exclusions.
- MANUAL_REVIEW: Ambiguous case, conflicting signals, high value, or low confidence — needs human review.

Allowed values for decision:
- APPROVED
- PARTIAL
- REJECTED
- MANUAL_REVIEW

Return JSON exactly:
{{
  "decision": "APPROVED",
  "rejection_reasons": [],
  "medical_necessity_verdict": "one sentence",
  "fraud_flags": [],
  "confidence_score": 0.0,
  "notes": "overall assessment detailing any age/gender mismatches or lab report irrelevance if found",
  "next_steps": "what the claimant should do next",
  "requires_manual_review": false,
  "manual_review_reasons": []
}}
"""

    try:
        resp = _get_client().chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=1024,
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        print(f"[run_final_adjudication] LLM call failed: {e}")
        # fallback to a safe MANUAL_REVIEW decision
        return {
            "decision": "MANUAL_REVIEW",
            "rejection_reasons": [],
            "medical_necessity_verdict": "LLM final quality review failed due to rate limits or API constraints.",
            "fraud_flags": [],
            "confidence_score": 0.5,
            "notes": f"System error during automated final review: {e}. Sent for manual review.",
            "next_steps": "A claims officer will review your claim and contact you within 2 business days.",
            "requires_manual_review": True,
            "manual_review_reasons": ["Automated adjudication exception / rate limit"]
        }
