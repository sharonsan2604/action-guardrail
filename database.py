import os
from datetime import datetime, timezone
from typing import Generator
from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from dotenv import load_dotenv

load_dotenv()

# Get Database URL from environment, default to local SQLite db
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./guardrail.db")

# Setup SQLAlchemy engine
# "connect_args" is only needed for SQLite to avoid thread conflicts
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class AuditEntry(Base):
    """
    SQLAlchemy model representing an audit log record.
    """
    __tablename__ = "audit_entries"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    tool = Column(String, index=True, nullable=False)
    params = Column(JSON, nullable=False)
    outcome = Column(String, index=True, nullable=False)
    matched_rule = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    
    # New Multi-Layer Auditing columns
    layer1_outcome = Column(String, nullable=True)
    layer1_rule = Column(String, nullable=True)
    layer2_tags = Column(JSON, nullable=True)
    layer2_risk_level = Column(String, nullable=True)
    layer3_risk_score = Column(Integer, nullable=True)
    layer3_reasoning = Column(String, nullable=True)
    layer3_flags = Column(JSON, nullable=True)
    layer4_anomaly_score = Column(Integer, nullable=True)
    layer4_status = Column(String, nullable=True)
    layer4_flags = Column(JSON, nullable=True)
    final_reason = Column(String, nullable=True)
    reviewer_context = Column(String, nullable=True)

    reviewer_name = Column(String, nullable=True)
    reviewer_notes = Column(String, nullable=True)
    review_status = Column(String, index=True, nullable=True)  # 'approved' or 'rejected'
    review_timestamp = Column(DateTime, nullable=True)
    
    executed = Column(Boolean, default=False, nullable=False)

# Create all tables on module load
Base.metadata.create_all(bind=engine)

def get_session() -> Session:
    """
    Creates and returns a new database session.
    The caller is responsible for closing the session.
    """
    return SessionLocal()
