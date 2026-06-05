"""
Document extraction: one LLM call per document → validated Pydantic JSON.

Two modes:
  - Vision mode  (real upload): image/PDF file → vision LLM → JSON
  - Text mode    (test submit): raw OCR/typed text → text LLM → JSON
"""
import base64
import io
import json
from pathlib import Path
from typing import Optional

from groq import Groq
from PIL import Image

from app.config import settings
from app.schemas.documents import (
    PrescriptionData, PharmacyBillData, DiagnosisTestData, MedicalBillData,
)

_client: Optional[Groq] = None

_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
_TEXT_MODEL   = "llama-3.1-8b-instant"

_SCHEMAS = {
    "prescription":   PrescriptionData,
    "pharmacy_bill":  PharmacyBillData,
    "diagnosis_test": DiagnosisTestData,
    "medical_bill":   MedicalBillData,
}

_INSTRUCTIONS = {
    "prescription": """\
You are an expert at reading Indian medical prescriptions — printed or handwritten.
Extract every visible field and return valid JSON matching the schema.
Rules:
- extraction_confidence (0–1): how legible and complete the document is.
- Return null for fields not visible; never guess patient-specific data.
- is_generic: true if medicine name is a generic salt (Paracetamol), false if branded (Crocin).
- has_doctor_stamp / has_signature: true only if the stamp/signature is visually present.
- doctor_registration format: STATE/NUMBER/YEAR  or  AYUR/STATE/NUMBER/YEAR
- Handle handwriting, stamps, mixed English/regional language text.
- If document is blurry or illegible, set extraction_confidence < 0.5 and extract what is readable.""",

    "pharmacy_bill": """\
You are an expert at reading Indian pharmacy bills and tax invoices.
Extract every visible field and return valid JSON matching the schema.
Rules:
- extraction_confidence (0–1): how legible and complete the document is.
- is_branded: true for proprietary brand names (Crocin), false for generic salts (Paracetamol).
- Extract all line items with amounts.
- Handle printed receipts, handwritten bills, GST invoices.
- If document is blurry or illegible, set extraction_confidence < 0.5.""",

    "diagnosis_test": """\
You are an expert at reading Indian diagnostic lab reports.
Extract every visible field and return valid JSON matching the schema.
Rules:
- extraction_confidence (0–1): how legible and complete the document is.
- is_abnormal: true if result falls outside the stated normal range.
- Extract all test results with values and ranges.
- Handle NABL-accredited lab formats, handwritten remarks.
- If document is blurry or illegible, set extraction_confidence < 0.5.""",

    "medical_bill": """\
You are an expert at reading Indian hospital and clinic bills.
Extract every visible field and return valid JSON matching the schema.
Rules:
- extraction_confidence (0–1): how legible and complete the document is.
- category: one of consultation, diagnostic, pharmacy, dental, vision, alternative, procedure, other.
- is_covered: false for items that are clearly cosmetic, weight-loss, experimental, or excluded.
- Extract all line items with amounts and categories.
- Handle GST invoices, cashless claim bills, handwritten receipts.
- If document is blurry or illegible, set extraction_confidence < 0.5.""",
}

_FEW_SHOT = {
    "prescription": """
Example output for a prescription:
{
  "doctor_name": "Dr. Sharma", "doctor_registration": "KA/45678/2015",
  "clinic_name": "Apollo Clinic", "patient_name": "Rajesh Kumar",
  "patient_age": 35, "patient_gender": "Male", "date": "01/11/2024",
  "chief_complaints": ["Fever", "body ache"], "diagnosis": "Viral Fever",
  "medicines": [
    {"name": "Paracetamol", "strength": "650mg", "dosage": "1-0-1", "duration": "5 days", "is_generic": true},
    {"name": "Vitamin C",   "strength": "500mg", "dosage": "0-0-1", "duration": "5 days", "is_generic": true}
  ],
  "investigations_advised": ["CBC", "Dengue NS1"], "follow_up_date": "07/11/2024",
  "has_doctor_stamp": true, "has_signature": true, "extraction_confidence": 0.95
}""",

    "pharmacy_bill": """
Example output for a pharmacy bill:
{
  "pharmacy_name": "MediPlus Pharmacy", "drug_license_number": "DL-MH-123456",
  "gstin": "27ABCDE1234F1Z5", "bill_number": "PH-2024-001", "date": "01/11/2024",
  "patient_name": "Rajesh Kumar", "doctor_name": "Dr. Sharma",
  "items": [
    {"name": "Crocin 650mg",  "batch_number": "A123", "expiry_date": "06/26", "quantity": 10, "mrp": 8.0,  "amount": 80.0,  "is_branded": true},
    {"name": "Limcee 500mg",  "batch_number": "B456", "expiry_date": "12/25", "quantity": 10, "mrp": 5.0,  "amount": 50.0,  "is_branded": true}
  ],
  "subtotal": 130.0, "gst": 6.5, "total_amount": 136.50,
  "payment_mode": "Cash", "has_stamp": true, "extraction_confidence": 0.92
}""",

    "diagnosis_test": """
Example output for a lab report:
{
  "lab_name": "PathCare Labs", "accreditation_number": "MC-1234", "report_id": "RPT-5678",
  "patient_name": "Rajesh Kumar", "patient_age": 35, "referred_by": "Dr. Sharma",
  "date": "01/11/2024",
  "tests": [
    {"test_name": "Hemoglobin",   "result": "13.5", "unit": "g/dL",      "normal_range": "13-17",         "is_abnormal": false},
    {"test_name": "WBC Count",    "result": "9200",  "unit": "cells/μL",  "normal_range": "4000-11000",    "is_abnormal": false},
    {"test_name": "Dengue NS1",   "result": "Negative", "unit": null,     "normal_range": "Negative",      "is_abnormal": false}
  ],
  "remarks": "No significant abnormality", "pathologist_name": "Dr. Reddy",
  "has_stamp": true, "extraction_confidence": 0.94
}""",

    "medical_bill": """
Example output for a medical bill:
{
  "hospital_name": "Apollo Clinic", "hospital_address": "12 MG Road Bangalore",
  "gstin": "29ABCDE1234F1Z5", "bill_number": "BL-2024-001", "date": "01/11/2024",
  "patient_name": "Rajesh Kumar",
  "items": [
    {"description": "Consultation Fee", "category": "consultation", "amount": 1000.0, "is_covered": true},
    {"description": "CBC Blood Test",   "category": "diagnostic",   "amount": 300.0,  "is_covered": true},
    {"description": "Dengue NS1 Test",  "category": "diagnostic",   "amount": 200.0,  "is_covered": true}
  ],
  "consultation_fee": 1000.0, "subtotal": 1500.0, "gst": 0.0, "total_amount": 1500.0,
  "payment_mode": "Cash", "has_stamp": true, "has_authorized_signature": true,
  "extraction_confidence": 0.96
}""",
}


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.groq_api_key)
    return _client


def _build_system(doc_type: str, schema_json: str) -> str:
    return (
        f"{_INSTRUCTIONS[doc_type]}\n\n"
        f"JSON Schema to populate:\n{schema_json}\n\n"
        f"{_FEW_SHOT[doc_type]}"
    )


# ── Image helpers ─────────────────────────────────────────────────────────────

def _load_image(file_path: str) -> Image.Image:
    """Load any supported file (image or PDF) as a single PIL Image."""
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        try:
            import fitz
            doc = fitz.open(file_path)
            pages = []
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(dpi=150)
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data)).convert("RGB")
                pages.append(img)
        except Exception as e:
            raise RuntimeError(f"PDF conversion failed: {e}")
        if not pages:
            raise ValueError("PDF has no pages")
        if len(pages) == 1:
            return pages[0]
        # Stitch multiple pages vertically
        w = max(p.width for p in pages)
        h = sum(p.height for p in pages)
        canvas = Image.new("RGB", (w, h), "white")
        y = 0
        for p in pages:
            canvas.paste(p, (0, y))
            y += p.height
        return canvas
    return Image.open(file_path).convert("RGB")


def _image_to_b64(img: Image.Image, max_dim: int = 1600) -> str:
    """Resize if needed and return base64-encoded JPEG string."""
    if max(img.width, img.height) > max_dim:
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ── Public API ────────────────────────────────────────────────────────────────

def extract_document_from_image(doc_type: str, file_path: str) -> dict:
    """
    Vision mode: sends the image directly to the vision LLM.
    Handles images (JPG, PNG, TIFF, BMP) and PDFs.
    """
    schema_class = _SCHEMAS[doc_type]
    schema_json  = json.dumps(schema_class.model_json_schema(), indent=2)
    system       = _build_system(doc_type, schema_json)

    img    = _load_image(file_path)
    b64img = _image_to_b64(img)

    response = _get_client().chat.completions.create(
        model=_VISION_MODEL,
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64img}"},
                    },
                    {
                        "type": "text",
                        "text": (
                            f"Extract all fields from this {doc_type.replace('_', ' ')} document. "
                            "Return only valid JSON matching the schema above. "
                            "Set extraction_confidence based on document legibility and completeness."
                        ),
                    },
                ],
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=2048,
    )

    raw       = json.loads(response.choices[0].message.content)
    # Coerce null list fields to empty lists to avoid validation errors
    for lf in ["medicines", "items", "tests", "chief_complaints", "investigations_advised"]:
        if lf in raw and raw[lf] is None:
            raw[lf] = []
    validated = schema_class.model_validate(raw)
    return validated.model_dump()


def extract_document(doc_type: str, ocr_text: str) -> dict:
    """
    Text mode: used by the test-submit endpoint.
    Sends raw text to the standard text LLM (no image).
    """
    schema_class = _SCHEMAS[doc_type]
    schema_json  = json.dumps(schema_class.model_json_schema(), indent=2)
    system       = _build_system(doc_type, schema_json)

    response = _get_client().chat.completions.create(
        model=_TEXT_MODEL,
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    f"Extract all fields from this {doc_type.replace('_', ' ')} text:\n\n{ocr_text}"
                ),
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=2048,
    )

    raw       = json.loads(response.choices[0].message.content)
    # Coerce null list fields to empty lists to avoid validation errors
    for lf in ["medicines", "items", "tests", "chief_complaints", "investigations_advised"]:
        if lf in raw and raw[lf] is None:
            raw[lf] = []
    validated = schema_class.model_validate(raw)
    return validated.model_dump()