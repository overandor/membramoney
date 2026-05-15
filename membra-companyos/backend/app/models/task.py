"""MEMBRA CompanyOS — Task, dependency, assignment, proof models (TaskOS)."""
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Text, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class TaskStatus(PyEnum):
    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskType(PyEnum):
    AI_ANALYSIS = "ai_analysis"
    HUMAN_WORK = "human_work"
    API_CALL = "api_call"
    GOVERNANCE_GATE = "governance_gate"
    PROOF_COLLECTION = "proof_collection"
    SETTLEMENT_TRIGGER = "settlement_trigger"
    ASSET_DEPLOYMENT = "asset_deployment"
    COMMUNICATION = "communication"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    objective_id = Column(UUID(as_uuid=True), ForeignKey("objectives.id"), nullable=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    task_type = Column(Enum(TaskType), nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.BACKLOG)
    priority = Column(Integer, default=3)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    owner_agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True)
    estimated_hours = Column(String(16), nullable=True)
    deadline = Column(DateTime(timezone=True), nullable=True)
    proof_requirement = Column(JSON, default=dict)
    output_schema = Column(JSON, default=dict)
    blocked_reason = Column(Text, nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    dependencies = relationship("TaskDependency", foreign_keys="TaskDependency.task_id", cascade="all, delete-orphan")
    dependents = relationship("TaskDependency", foreign_keys="TaskDependency.depends_on_task_id")
    assignments = relationship("TaskAssignment", back_populates="task", cascade="all, delete-orphan")
    proofs = relationship("TaskProof", back_populates="task", cascade="all, delete-orphan")
    objective_links = relationship("ObjectiveTaskLink", back_populates="task")


class TaskDependency(Base):
    __tablename__ = "task_dependencies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    depends_on_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    dependency_type = Column(String(32), default="blocks")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class TaskAssignment(Base):
    __tablename__ = "task_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    assignee_type = Column(String(16), nullable=False)
    assignee_id = Column(UUID(as_uuid=True), nullable=False)
    assigned_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    assigned_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)

    task = relationship("Task", back_populates="assignments")


class TaskProof(Base):
    __tablename__ = "task_proofs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    proof_type = Column(String(64), nullable=False)
    proof_data = Column(JSON, default=dict)
    ipfs_cid = Column(String(64), nullable=True)
    verification_status = Column(String(32), default="pending")
    verified_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    proof_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    task = relationship("Task", back_populates="proofs")
