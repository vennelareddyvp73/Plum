from sqlalchemy import Column, String, Float, Boolean, Date, DateTime, Integer, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base


class Member(Base):
    __tablename__ = "members"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    gender = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    policy_start_date = Column(Date)
    policy_end_date = Column(Date)
    is_active = Column(Boolean, default=True)
    join_date = Column(Date)

    claims = relationship("Claim", back_populates="member")


class Claim(Base):
    __tablename__ = "claims"

    id = Column(String, primary_key=True)
    member_id = Column(String, ForeignKey("members.id"), nullable=False)
    treatment_date = Column(Date, nullable=False)
    submission_date = Column(DateTime, default=datetime.utcnow)
    claimed_amount = Column(Float, nullable=False)
    approved_amount = Column(Float, nullable=True)
    status = Column(String, default="PENDING")
    category_approved_amounts = Column(JSON, nullable=True)
    category_claimed_amounts = Column(JSON, nullable=True)
    flagged_for_review = Column(Boolean, default=False)
    review_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    member = relationship("Member", back_populates="claims")
    documents = relationship("Document", back_populates="claim")
    decision = relationship("Decision", back_populates="claim", uselist=False)


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    claim_id = Column(String, ForeignKey("claims.id"), nullable=False)
    doc_type = Column(String, nullable=False)
    file_path = Column(String)
    ocr_text = Column(Text, nullable=True)
    extracted_json = Column(JSON, nullable=True)
    extraction_confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    claim = relationship("Claim", back_populates="documents")


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    claim_id = Column(String, ForeignKey("claims.id"), unique=True, nullable=False)
    decision = Column(String, nullable=False)
    claimed_amount = Column(Float)
    approved_amount = Column(Float)
    deductions = Column(JSON, default=list)
    rejection_reasons = Column(JSON, default=list)
    violation_reasoning = Column(JSON, default=list)
    fraud_flags = Column(JSON, default=list)
    medical_necessity_verdict = Column(Text, nullable=True)
    confidence_score = Column(Float)
    notes = Column(Text)
    next_steps = Column(Text)
    requires_manual_review = Column(Boolean, default=False)
    manual_review_reasons = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    claim = relationship("Claim", back_populates="decision")