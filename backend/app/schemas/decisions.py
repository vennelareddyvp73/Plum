from pydantic import BaseModel
from typing import Optional, List, Literal


class Deduction(BaseModel):
    type: str
    description: str
    amount: float


class ViolationReasoning(BaseModel):
    rule_code: str
    explanation: str


class ClaimDecision(BaseModel):
    claim_id: str
    decision: Literal["APPROVED", "REJECTED", "PARTIAL", "MANUAL_REVIEW"]
    claimed_amount: float
    approved_amount: float
    deductions: List[Deduction] = []
    rejection_reasons: List[str] = []
    violation_reasoning: List[ViolationReasoning] = []
    fraud_flags: List[str] = []
    medical_necessity_verdict: Optional[str] = None
    confidence_score: float
    notes: str
    next_steps: str
    requires_manual_review: bool = False
    manual_review_reasons: List[str] = []
    # Cashless & network fields
    cashless_approved: Optional[bool] = None          # True if auto-approved cashless at network hospital
    network_discount_amount: Optional[float] = None   # Rupee value of the network discount applied