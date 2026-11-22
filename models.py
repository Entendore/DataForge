"""DataForge – SQLAlchemy ORM models, database helpers (12 tables), and theme constants."""

from __future__ import annotations

import json, uuid, datetime as dt
from typing import Optional

from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime, ForeignKey, Boolean,
    create_engine, inspect as sa_inspect,
)
from sqlalchemy.orm import (
    declarative_base, relationship, sessionmaker, Session as SASession,
)
from sqlalchemy.sql import func

# ---------------------------------------------------------------------------
# Dark premium theme constants
# ---------------------------------------------------------------------------
BG_DARK      = "#0f0f23"
BG_SIDEBAR   = "#0a0a1a"
BG_CARD      = "#16163a"
BG_HOVER     = "#1e1e4a"
BG_INPUT     = "#1a1a3e"
FG_PRIMARY   = "#e2e8f0"
FG_SECONDARY = "#94a3b8"
FG_MUTED     = "#64748b"
ACCENT       = "#8b5cf6"
ACCENT2      = "#ec4899"
BORDER       = "#1e293b"
SUCCESS      = "#22c55e"
WARNING      = "#eab308"
DANGER       = "#ef4444"
INFO         = "#3b82f6"
RADIUS       = 8

# ---------------------------------------------------------------------------
# Base & Engine
# ---------------------------------------------------------------------------
Base = declarative_base()

DB_PATH = "/home/z/my-project/pyside6/dataforge/dataforge.db"
_engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=_engine)


def init_db() -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(_engine)


def get_session() -> SASession:
    return SessionLocal()


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


# ---------------------------------------------------------------------------
# Mixin helpers
# ---------------------------------------------------------------------------
class IDMixin:
    id = Column(String, primary_key=True, default=_uuid)


# ---------------------------------------------------------------------------
# 1. Project
# ---------------------------------------------------------------------------
class Project(IDMixin, Base):
    __tablename__ = "projects"
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    dataType = Column(String, default="text")
    status = Column(String, default="active")
    createdAt = Column(String, default=_now)
    updatedAt = Column(String, default=_now)

    datasets = relationship("Dataset", back_populates="project", cascade="all, delete-orphan")
    annotations = relationship("Annotation", back_populates="project", cascade="all, delete-orphan")
    workflows = relationship("Workflow", back_populates="project", cascade="all, delete-orphan")
    tutorials = relationship("Tutorial", back_populates="project", cascade="all, delete-orphan")
    rlModels = relationship("RLModel", back_populates="project", cascade="all, delete-orphan")
    labelSchemas = relationship("LabelSchema", back_populates="project", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="project", cascade="all, delete-orphan")
    activityLogs = relationship("ActivityLog", back_populates="project", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# 2. Dataset
# ---------------------------------------------------------------------------
class Dataset(IDMixin, Base):
    __tablename__ = "datasets"
    name = Column(String, nullable=False)
    projectId = Column(String, ForeignKey("projects.id", ondelete="CASCADE"))
    format = Column(String, default="jsonl")
    data = Column(Text, default="[]")
    createdAt = Column(String, default=_now)

    project = relationship("Project", back_populates="datasets")


# ---------------------------------------------------------------------------
# 3. Annotation
# ---------------------------------------------------------------------------
class Annotation(IDMixin, Base):
    __tablename__ = "annotations"
    projectId = Column(String, ForeignKey("projects.id", ondelete="CASCADE"))
    datasetId = Column(String, ForeignKey("datasets.id", ondelete="SET NULL"))
    dataIndex = Column(Integer, default=0)
    labels = Column(Text, default="[]")
    confidence = Column(Float, default=1.0)
    annotator = Column(String, default="")
    status = Column(String, default="pending")
    notes = Column(Text, default="")
    bookmarked = Column(Boolean, default=False)
    createdAt = Column(String, default=_now)
    updatedAt = Column(String, default=_now)

    project = relationship("Project", back_populates="annotations")
    reviews = relationship("Review", back_populates="annotation", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# 4. Workflow
# ---------------------------------------------------------------------------
class Workflow(IDMixin, Base):
    __tablename__ = "workflows"
    name = Column(String, nullable=False)
    projectId = Column(String, ForeignKey("projects.id", ondelete="CASCADE"))
    description = Column(Text, default="")
    steps = Column(Text, default="[]")
    status = Column(String, default="draft")
    createdAt = Column(String, default=_now)
    updatedAt = Column(String, default=_now)

    project = relationship("Project", back_populates="workflows")


# ---------------------------------------------------------------------------
# 5. TutorialStep
# ---------------------------------------------------------------------------
class TutorialStep(IDMixin, Base):
    __tablename__ = "tutorial_steps"
    tutorialId = Column(String, ForeignKey("tutorials.id", ondelete="CASCADE"))
    title = Column(String, nullable=False)
    content = Column(Text, default="")
    order = Column(Integer, default=0)

    tutorial = relationship("Tutorial", back_populates="steps")


# ---------------------------------------------------------------------------
# 6. Tutorial
# ---------------------------------------------------------------------------
class Tutorial(IDMixin, Base):
    __tablename__ = "tutorials"
    name = Column(String, nullable=False)
    projectId = Column(String, ForeignKey("projects.id", ondelete="CASCADE"))
    description = Column(Text, default="")
    isPublished = Column(Boolean, default=False)
    createdAt = Column(String, default=_now)

    project = relationship("Project", back_populates="tutorials")
    steps = relationship("TutorialStep", back_populates="tutorial", cascade="all, delete-orphan", order_by="TutorialStep.order")


# ---------------------------------------------------------------------------
# 7. RLModel
# ---------------------------------------------------------------------------
class RLModel(IDMixin, Base):
    __tablename__ = "rl_models"
    name = Column(String, nullable=False)
    projectId = Column(String, ForeignKey("projects.id", ondelete="CASCADE"))
    modelType = Column(String, default="ppo")
    config = Column(Text, default="{}")
    metrics = Column(Text, default="{}")
    status = Column(String, default="idle")
    createdAt = Column(String, default=_now)

    project = relationship("Project", back_populates="rlModels")


# ---------------------------------------------------------------------------
# 8. Team
# ---------------------------------------------------------------------------
class Team(IDMixin, Base):
    __tablename__ = "teams"
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    color = Column(String, default="#8b5cf6")
    createdAt = Column(String, default=_now)

    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# 9. TeamMember
# ---------------------------------------------------------------------------
class TeamMember(IDMixin, Base):
    __tablename__ = "team_members"
    teamId = Column(String, ForeignKey("teams.id", ondelete="CASCADE"))
    name = Column(String, nullable=False)
    role = Column(String, default="annotator")
    email = Column(String, default="")

    team = relationship("Team", back_populates="members")


# ---------------------------------------------------------------------------
# 10. LabelSchema
# ---------------------------------------------------------------------------
class LabelSchema(IDMixin, Base):
    __tablename__ = "label_schemas"
    name = Column(String, nullable=False)
    projectId = Column(String, ForeignKey("projects.id", ondelete="CASCADE"))
    color = Column(String, default="#8b5cf6")
    type = Column(String, default="category")
    description = Column(Text, default="")
    parentId = Column(String, ForeignKey("label_schemas.id", ondelete="SET NULL"), nullable=True)
    createdAt = Column(String, default=_now)

    project = relationship("Project", back_populates="labelSchemas")
    children = relationship("LabelSchema", backref="parent", remote_side="LabelSchema.id")


# ---------------------------------------------------------------------------
# 11. Review
# ---------------------------------------------------------------------------
class Review(IDMixin, Base):
    __tablename__ = "reviews"
    annotationId = Column(String, ForeignKey("annotations.id", ondelete="CASCADE"))
    projectId = Column(String, ForeignKey("projects.id", ondelete="CASCADE"))
    reviewer = Column(String, default="")
    status = Column(String, default="pending")
    comments = Column(Text, default="")
    createdAt = Column(String, default=_now)

    annotation = relationship("Annotation", back_populates="reviews")
    project = relationship("Project", back_populates="reviews")


# ---------------------------------------------------------------------------
# 12. ActivityLog
# ---------------------------------------------------------------------------
class ActivityLog(IDMixin, Base):
    __tablename__ = "activity_logs"
    projectId = Column(String, ForeignKey("projects.id", ondelete="CASCADE"))
    action = Column(String, nullable=False)
    userId = Column(String, default="")
    details = Column(Text, default="")
    createdAt = Column(String, default=_now)

    project = relationship("Project", back_populates="activityLogs")


# ---------------------------------------------------------------------------
# Generic CRUD helpers
# ---------------------------------------------------------------------------
def _row2dict(row) -> dict:
    d = {c.name: getattr(row, c.name) for c in row.__table__.columns}
    for k, v in list(d.items()):
        if isinstance(v, str):
            try:
                d[k] = json.loads(v)
            except Exception:
                pass
    return d


def get_all(Model) -> list[dict]:
    with get_session() as s:
        return [_row2dict(r) for r in s.query(Model).all()]


def get_by_id(Model, rid: str) -> Optional[dict]:
    with get_session() as s:
        r = s.query(Model).filter(Model.id == rid).first()
        return _row2dict(r) if r else None


def create(Model, **kwargs) -> dict:
    with get_session() as s:
        obj = Model(**kwargs)
        s.add(obj)
        s.commit()
        s.refresh(obj)
        return _row2dict(obj)


def update(Model, rid: str, **kwargs) -> Optional[dict]:
    with get_session() as s:
        r = s.query(Model).filter(Model.id == rid).first()
        if not r:
            return None
        for k, v in kwargs.items():
            if v is not None:
                setattr(r, k, v if not isinstance(v, (list, dict)) else json.dumps(v))
        r.updatedAt = _now()
        s.commit()
        s.refresh(r)
        return _row2dict(r)


def delete(Model, rid: str) -> bool:
    with get_session() as s:
        r = s.query(Model).filter(Model.id == rid).first()
        if not r:
            return False
        s.delete(r)
        s.commit()
        return True


def bulk_json(Model, col: str, rid: str, value) -> Optional[dict]:
    """Write a Python list/dict into a JSON text column and return updated row."""
    return update(Model, rid, **{col: json.dumps(value)})


# ---------------------------------------------------------------------------
# Seed demo data (only if tables empty)
# ---------------------------------------------------------------------------
SEED_PROJECTS = [
    {"name": "NLP Sentiment Analysis", "description": "Multi-language sentiment labeling for social media posts", "dataType": "text", "status": "active"},
    {"name": "Image Object Detection", "description": "Bounding-box annotation for autonomous driving scenes", "dataType": "image", "status": "active"},
    {"name": "Medical Record Classification", "description": "HIPAA-compliant clinical text categorization", "dataType": "text", "status": "completed"},
    {"name": "Audio Transcription QA", "description": "Speech-to-text verification and correction", "dataType": "audio", "status": "paused"},
    {"name": "Video Action Recognition", "description": "Temporal action segmentation for surveillance feeds", "dataType": "video", "status": "active"},
]

SEED_DATASETS = [
    {"name": "Twitter Sentiment v2", "format": "jsonl", "data": json.dumps([{"text": "I love this product!", "id": 1}, {"text": "Terrible experience", "id": 2}, {"text": "Pretty good overall", "id": 3}, {"text": "Not worth the money", "id": 4}, {"text": "Amazing quality and fast shipping", "id": 5}])},
    {"name": "Street View Objects", "format": "json", "data": json.dumps([{"url": "https://example.com/img1.jpg", "id": 1}, {"url": "https://example.com/img2.jpg", "id": 2}])},
    {"name": "Clinical Notes Sample", "format": "csv", "data": json.dumps([{"note": "Patient presents with fever", "id": 1}, {"note": "Normal check-up results", "id": 2}])},
]

SEED_ANNOTATIONS = [
    {"dataIndex": 0, "labels": json.dumps(["positive"]), "confidence": 0.95, "annotator": "Alice", "status": "approved"},
    {"dataIndex": 1, "labels": json.dumps(["negative"]), "confidence": 0.88, "annotator": "Bob", "status": "pending"},
    {"dataIndex": 2, "labels": json.dumps(["neutral"]), "confidence": 0.72, "annotator": "Alice", "status": "in_review"},
    {"dataIndex": 3, "labels": json.dumps(["negative"]), "confidence": 0.91, "annotator": "Carol", "status": "approved"},
    {"dataIndex": 4, "labels": json.dumps(["positive"]), "confidence": 0.85, "annotator": "Bob", "status": "rejected"},
]

SEED_WORKFLOWS = [
    {"name": "Sentiment Labeling Pipeline", "description": "Standard text classification workflow", "steps": json.dumps([
        {"id": "s1", "name": "Data Ingestion", "type": "input", "config": {}},
        {"id": "s2", "name": "Pre-processing", "type": "process", "config": {}},
        {"id": "s3", "name": "Quality Check", "type": "decision", "config": {}, "branchTo": "s4"},
        {"id": "s4", "name": "Label Assignment", "type": "annotation", "config": {}},
        {"id": "s5", "name": "Peer Review", "type": "review", "config": {}},
        {"id": "s6", "name": "Export Results", "type": "output", "config": {}},
    ]), "status": "active"},
    {"name": "Multi-Stage NER Pipeline", "description": "Named entity recognition with multiple annotators", "steps": json.dumps([
        {"id": "n1", "name": "Load Documents", "type": "input", "config": {}},
        {"id": "n2", "name": "Tokenize", "type": "process", "config": {}},
        {"id": "n3", "name": "NER Annotation A", "type": "annotation", "config": {}, "parallelGroup": "pg1", "parallelBranch": "A"},
        {"id": "n4", "name": "NER Annotation B", "type": "annotation", "config": {}, "parallelGroup": "pg1", "parallelBranch": "B"},
        {"id": "n5", "name": "Merge & Adjudicate", "type": "process", "config": {}},
        {"id": "n6", "name": "Final Review", "type": "review", "config": {}},
        {"id": "n7", "name": "Export", "type": "output", "config": {}},
    ]), "status": "draft"},
]

SEED_TEAMS = [
    {"name": "Core Annotators", "description": "Primary annotation team", "color": "#8b5cf6"},
    {"name": "QA Reviewers", "description": "Quality assurance specialists", "color": "#ec4899"},
]

SEED_LABELS = [
    {"name": "Positive", "color": "#22c55e", "type": "category", "description": "Positive sentiment"},
    {"name": "Negative", "color": "#ef4444", "type": "category", "description": "Negative sentiment"},
    {"name": "Neutral", "color": "#eab308", "type": "category", "description": "Neutral sentiment"},
    {"name": "Person", "color": "#3b82f6", "type": "entity", "description": "Named person entity"},
    {"name": "Organization", "color": "#8b5cf6", "type": "entity", "description": "Organization entity"},
    {"name": "Location", "color": "#06b6d4", "type": "entity", "description": "Location entity"},
]

SEED_ACTIVITIES = [
    {"action": "created_project", "details": json.dumps({"projectName": "NLP Sentiment Analysis"}), "createdAt": dt.datetime(2026, 6, 20, 10, 0).isoformat() + "Z"},
    {"action": "completed_annotation", "details": json.dumps({"count": 5}), "createdAt": dt.datetime(2026, 6, 20, 14, 30).isoformat() + "Z"},
    {"action": "started_workflow", "details": json.dumps({"workflowName": "Sentiment Labeling Pipeline"}), "createdAt": dt.datetime(2026, 6, 21, 9, 15).isoformat() + "Z"},
    {"action": "approved_review", "details": json.dumps({"annotationCount": 3}), "createdAt": dt.datetime(2026, 6, 21, 11, 45).isoformat() + "Z"},
]


def seed_data() -> None:
    """Populate tables with demo data only when empty."""
    with get_session() as s:
        if s.query(Project).count() > 0:
            return

        # Projects
        projects = [Project(**p) for p in SEED_PROJECTS]
        s.add_all(projects)
        s.flush()

        # Datasets → first project
        for d in SEED_DATASETS:
            s.add(Dataset(projectId=projects[0].id, **d))
        s.flush()

        # Annotations → first project
        for a in SEED_ANNOTATIONS:
            s.add(Annotation(projectId=projects[0].id, **a))

        # Workflows
        for w in SEED_WORKFLOWS:
            s.add(Workflow(projectId=projects[0].id, **w))

        # Teams + members
        for t in SEED_TEAMS:
            team = Team(**t)
            s.add(team)
            s.flush()
            s.add(TeamMember(teamId=team.id, name="Alice Johnson", role="lead", email="alice@dataforge.io"))
            s.add(TeamMember(teamId=team.id, name="Bob Smith", role="annotator", email="bob@dataforge.io"))
            s.add(TeamMember(teamId=team.id, name="Carol Davis", role="reviewer", email="carol@dataforge.io"))

        # Labels
        for lbl in SEED_LABELS:
            s.add(LabelSchema(projectId=projects[0].id, **lbl))

        # Activities
        for act in SEED_ACTIVITIES:
            s.add(ActivityLog(projectId=projects[0].id, **act))

        # Tutorials
        tut = Tutorial(projectId=projects[0].id, name="Getting Started", description="Learn the basics of DataForge annotation", isPublished=True)
        s.add(tut)
        s.flush()
        for i, (title, content) in enumerate([
            ("Welcome", "Welcome to DataForge! This tutorial walks you through the annotation workspace."),
            ("Navigation", "Use the sidebar to switch between views. Keyboard shortcuts speed up your workflow."),
            ("Annotation Tools", "Select from 6 tools: Label, Span, BBox, Classify, NER, Segment. Press 1-6 to switch."),
            ("Shortcuts", "Arrow keys navigate data. Ctrl+Z/Y for undo/redo. Ctrl+S to save. B to bookmark."),
        ]):
            s.add(TutorialStep(tutorialId=tut.id, title=title, content=content, order=i))

        # RL Model
        s.add(RLModel(
            projectId=projects[0].id, name="Sentiment PPO v1", modelType="ppo",
            config=json.dumps({"learning_rate": 0.001, "epochs": 10, "batch_size": 32}),
            metrics=json.dumps({"reward": 0.82, "accuracy": 0.89, "f1": 0.87}),
            status="training",
        ))

        s.commit()
