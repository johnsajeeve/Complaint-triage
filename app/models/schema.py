"""
Database schema (table definitions) using SQLAlchemy ORM.

Key design choice: We separate pre-resolution fields from post-resolution fields.
- PRE-RESOLUTION: available when complaint is filed (features)
- POST-RESOLUTION: only available after company responds (labels)

This prevents temporal leakage (using information from the future).
"""

from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, Float, Index, Date
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

# This is the base class all our models inherit from
Base = declarative_base()


class Complaint(Base):
    """A single complaint from the CFPB database."""
    
    __tablename__ = "complaints"
    
    complaint_id = Column(String(255), primary_key=True, index=True)
    date_received = Column(Date, nullable=False, index=True)
    date_sent_to_company = Column(Date, nullable=False)
    product = Column(String(255), index=True)
    sub_product = Column(String(255))
    issue = Column(String(255), index=True)
    sub_issue = Column(String(255))
    company = Column(String(255), index=True)
    state = Column(String(2), index=True)
    zip_code = Column(String(10))
    complaint_what_happened = Column(Text, nullable=False)
    tags = Column(String(255))
    submitted_via = Column(String(100))
    company_response = Column(String(255))
    timely_response = Column(Boolean)
    consumer_disputed = Column(Boolean)
    company_public_response = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    narrative_available = Column(Boolean, default=False)
    
    def __repr__(self):
        return f"<Complaint(id={self.complaint_id}, company={self.company})>"


class ComplaintFeature(Base):
    """Computed NLP features for a complaint."""
    
    __tablename__ = "complaint_features"
    
    feature_id = Column(Integer, primary_key=True, autoincrement=True)
    complaint_id = Column(String(255), index=True, nullable=False)
    sentiment_score = Column(Float)
    distress_score = Column(Float)
    hedge_ratio = Column(Float)
    narrative_length = Column(Integer)
    narrative_specificity = Column(Float)
    narrative_embedding = Column(String)
    company_complaint_history = Column(Integer)
    company_timely_response_rate = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ResolutionTarget(Base):
    """Our constructed regression target: Resolution Difficulty Score"""
    
    __tablename__ = "resolution_targets"
    
    complaint_id = Column(String(255), primary_key=True, index=True)
    difficulty_score = Column(Float, nullable=False)
    response_type_score = Column(Float)
    timeliness_score = Column(Float)
    dispute_score = Column(Float)
    score_version = Column(String(50), default="v1")
    created_at = Column(DateTime, default=datetime.utcnow)