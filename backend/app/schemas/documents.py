from pydantic import BaseModel, Field
from typing import Optional, List, Literal


class MedicineItem(BaseModel):
    name: str
    strength: Optional[str] = None
    dosage: Optional[str] = None
    duration: Optional[str] = None
    is_generic: Optional[bool] = None


class PrescriptionData(BaseModel):
    doctor_name: Optional[str] = None               # null if illegible
    doctor_registration: Optional[str] = None       # STATE/NUMBER/YEAR or AYUR/STATE/NUMBER/YEAR
    clinic_name: Optional[str] = None
    patient_name: Optional[str] = None              # null if illegible
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    date: Optional[str] = None
    chief_complaints: Optional[List[str]] = None
    diagnosis: Optional[str] = None                 # null if illegible
    medicines: List[MedicineItem] = []
    investigations_advised: Optional[List[str]] = None
    follow_up_date: Optional[str] = None
    has_doctor_stamp: bool = False
    has_signature: bool = False
    extraction_confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class PharmacyItem(BaseModel):
    name: str
    batch_number: Optional[str] = None
    expiry_date: Optional[str] = None
    quantity: Optional[int] = None
    mrp: Optional[float] = None
    amount: float
    is_branded: Optional[bool] = None              # True = branded → 30% copay


class PharmacyBillData(BaseModel):
    pharmacy_name: Optional[str] = None
    drug_license_number: Optional[str] = None
    gstin: Optional[str] = None
    bill_number: Optional[str] = None
    date: Optional[str] = None
    patient_name: Optional[str] = None             # null for B2B invoices or illegible docs
    doctor_name: Optional[str] = None
    items: List[PharmacyItem] = []
    subtotal: float = 0.0
    gst: Optional[float] = None
    total_amount: float = 0.0
    payment_mode: Optional[str] = None
    has_stamp: bool = False
    extraction_confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class TestResult(BaseModel):
    test_name: str
    result: Optional[str] = None
    unit: Optional[str] = None
    normal_range: Optional[str] = None
    is_abnormal: Optional[bool] = None             # supports medical necessity check


class DiagnosisTestData(BaseModel):
    lab_name: Optional[str] = None
    accreditation_number: Optional[str] = None     # NABL/CAP
    report_id: Optional[str] = None
    patient_name: Optional[str] = None
    patient_age: Optional[int] = None
    referred_by: Optional[str] = None
    date: Optional[str] = None
    tests: List[TestResult] = []
    remarks: Optional[str] = None
    pathologist_name: Optional[str] = None
    has_stamp: bool = False
    extraction_confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class BillLineItem(BaseModel):
    description: str
    category: Literal[
        "consultation", "diagnostic", "pharmacy",
        "dental", "vision", "alternative", "procedure", "other"
    ]
    amount: float
    is_covered: Optional[bool] = None              # False = LLM flagged as excluded


class MedicalBillData(BaseModel):
    hospital_name: Optional[str] = None
    hospital_address: Optional[str] = None
    gstin: Optional[str] = None
    bill_number: Optional[str] = None
    date: Optional[str] = None
    patient_name: Optional[str] = None
    referred_by: Optional[str] = None
    items: List[BillLineItem] = []
    consultation_fee: Optional[float] = None
    subtotal: float = 0.0
    gst: Optional[float] = None
    total_amount: float = 0.0
    payment_mode: Optional[str] = None
    transaction_id: Optional[str] = None
    has_stamp: bool = False
    has_authorized_signature: bool = False
    extraction_confidence: float = Field(default=0.5, ge=0.0, le=1.0)