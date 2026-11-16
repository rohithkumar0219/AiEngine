"""
Iryax Enterprise Database Layer — SQLAlchemy models and connection manager.

Supports:
- PostgreSQL (Production / Staging) via psycopg2 / asyncpg
- SQLite (Local Dev / Fallback when PostgreSQL URL is not provided)

Models:
- User (Admins, Reviewers, Staff)
- ApprovalRequestRecord (Human-in-the-loop approvals)
- AuditLogRecord (Tamper-evident audit trail)
- ConversationRecord & MessageRecord (Conversations & Agent chat history)
- TransactionRecord (Financial / Workflow transactions)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, scoped_session

logger = logging.getLogger(__name__)

Base = declarative_base()


# ── SQLAlchemy Models ─────────────────────────────────────────────────────────

class UserModel(Base):
    """User account record for authentication and RBAC."""
    __tablename__ = "users"

    id = Column(String(64), primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    tenant_id = Column(String(64), nullable=False, index=True)
    role = Column(String(64), nullable=False, default="tenant_admin")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login_at = Column(DateTime, nullable=True)

    approvals = relationship("ApprovalRecord", back_populates="reviewer", foreign_keys="ApprovalRecord.reviewed_by")
    audit_logs = relationship("AuditRecord", back_populates="user")


class ApprovalRecord(Base):
    """Persistent Human-in-the-Loop approval requests."""
    __tablename__ = "approvals"

    approval_id = Column(String(64), primary_key=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    product_id = Column(String(64), nullable=False, index=True)
    operation_name = Column(String(128), nullable=False)
    payload_json = Column(Text, nullable=False, default="{}")
    required_roles_json = Column(Text, nullable=False, default="[]")
    status = Column(String(32), nullable=False, default="pending", index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String(64), ForeignKey("users.id"), nullable=True)
    decision_reason = Column(Text, nullable=True)

    reviewer = relationship("UserModel", back_populates="approvals", foreign_keys=[reviewed_by])

    __table_args__ = (
        Index("idx_approvals_tenant_status", "tenant_id", "status"),
    )


class AuditRecord(Base):
    """Persistent audit log of all system actions and decisions."""
    __tablename__ = "audit_logs"

    audit_id = Column(String(64), primary_key=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=True, index=True)
    product_id = Column(String(64), nullable=False, index=True)
    action = Column(String(128), nullable=False)
    status = Column(String(64), nullable=False)
    details_json = Column(Text, nullable=False, default="{}")
    timestamp = Column(Float, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("UserModel", back_populates="audit_logs")

    __table_args__ = (
        Index("idx_audit_tenant_product", "tenant_id", "product_id"),
    )


class ConversationRecord(Base):
    """Conversations initiated by users across the 7 subagents."""
    __tablename__ = "conversations"

    conversation_id = Column(String(64), primary_key=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    product_id = Column(String(64), nullable=False, index=True)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    messages = relationship("MessageRecord", back_populates="conversation", cascade="all, delete-orphan")


class MessageRecord(Base):
    """Individual messages inside a conversation."""
    __tablename__ = "messages"

    message_id = Column(String(64), primary_key=True)
    conversation_id = Column(String(64), ForeignKey("conversations.conversation_id"), nullable=False, index=True)
    role = Column(String(32), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    conversation = relationship("ConversationRecord", back_populates="messages")


class TransactionRecord(Base):
    """Financial & operational transaction ledgers (e.g., payroll runs, coworking bookings)."""
    __tablename__ = "transactions"

    transaction_id = Column(String(64), primary_key=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    product_id = Column(String(64), nullable=False, index=True)
    reference_id = Column(String(64), nullable=True)
    amount = Column(Float, default=0.0)
    currency = Column(String(8), default="INR")
    status = Column(String(32), nullable=False, default="pending")  # completed, pending, cancelled
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ── Database Connection & Lifecycle Management ───────────────────────────────

BACKEND_DIR = Path(__file__).resolve().parent

def get_database_url() -> str:
    """
    Returns the configured database URL:
    - POSTGRES_URL or DATABASE_URL if set.
    - Otherwise, falls back to a persistent SQLite database in backend/data/iryax_production.db.
    """
    url = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
    if url:
        return url
    
    db_path = BACKEND_DIR / "data" / "iryax_production.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


DATABASE_URL = get_database_url()

# Create SQLAlchemy engine
is_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False,
)

SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
db_session = scoped_session(SessionFactory)


def init_db() -> None:
    """Initialize database tables idempotently."""
    logger.info("Initializing database with engine: %s (is_sqlite=%s)", engine.url.drivername, is_sqlite)
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized successfully.")


def get_db():
    """FastAPI dependency for DB session."""
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()

