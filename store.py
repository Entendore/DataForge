"""DataForge – Centralized state management (Zustand equivalent)."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from models import (
    Project, Dataset, Annotation, Workflow, Tutorial, TutorialStep,
    RLModel, Team, TeamMember, LabelSchema, Review, ActivityLog,
    get_all, create, update, delete, bulk_json, seed_data,
)


class Store(QObject):
    """Global application state with Qt signals for reactive UI updates."""

    # ---- signals ----
    data_changed = Signal(str)  # entity name that changed

    def __init__(self):
        super().__init__()
        # Raw data arrays
        self.projects: list[dict] = []
        self.datasets: list[dict] = []
        self.annotations: list[dict] = []
        self.workflows: list[dict] = []
        self.tutorials: list[dict] = []
        self.tutorial_steps: list[dict] = []
        self.rl_models: list[dict] = []
        self.teams: list[dict] = []
        self.team_members: list[dict] = []
        self.labels: list[dict] = []
        self.reviews: list[dict] = []
        self.activities: list[dict] = []

        # Selection state
        self.current_project_id: str | None = None
        self.current_annotation_index: int = 0
        self.annotation_labels: list[str] = []
        self.selected_annotation_tool: int = 0
        self.selected_annotation_ids: list[str] = []
        self.active_tab: int = 0  # 0=Dashboard

    # ---- reload all from DB ----
    def reload_all(self) -> None:
        self.projects = get_all(Project)
        self.datasets = get_all(Dataset)
        self.annotations = get_all(Annotation)
        self.workflows = get_all(Workflow)
        self.tutorials = get_all(Tutorial)
        self.tutorial_steps = get_all(TutorialStep)
        self.rl_models = get_all(RLModel)
        self.teams = get_all(Team)
        self.team_members = get_all(TeamMember)
        self.labels = get_all(LabelSchema)
        self.reviews = get_all(Review)
        self.activities = get_all(ActivityLog)
        self.data_changed.emit("all")

    def reload(self, entity: str) -> None:
        mapping = {
            "projects": (Project, "projects"),
            "datasets": (Dataset, "datasets"),
            "annotations": (Annotation, "annotations"),
            "workflows": (Workflow, "workflows"),
            "tutorials": (Tutorial, "tutorials"),
            "tutorial_steps": (TutorialStep, "tutorial_steps"),
            "rl_models": (RLModel, "rl_models"),
            "teams": (Team, "teams"),
            "team_members": (TeamMember, "team_members"),
            "labels": (LabelSchema, "labels"),
            "reviews": (Review, "reviews"),
            "activities": (ActivityLog, "activities"),
        }
        if entity in mapping:
            Model, attr = mapping[entity]
            setattr(self, attr, get_all(Model))
            self.data_changed.emit(entity)

    # ---- convenience ----
    def get_project(self, pid: str) -> dict | None:
        for p in self.projects:
            if p["id"] == pid:
                return p
        return None

    def project_annotations(self, pid: str) -> list[dict]:
        return [a for a in self.annotations if a.get("projectId") == pid]

    def project_datasets(self, pid: str) -> list[dict]:
        return [d for d in self.datasets if d.get("projectId") == pid]

    def project_workflows(self, pid: str) -> list[dict]:
        return [w for w in self.workflows if w.get("projectId") == pid]

    def project_labels(self, pid: str) -> list[dict]:
        return [l for l in self.labels if l.get("projectId") == pid]

    def project_reviews(self, pid: str) -> list[dict]:
        return [r for r in self.reviews if r.get("projectId") == pid]

    def project_activities(self, pid: str) -> list[dict]:
        return [a for a in self.activities if a.get("projectId") == pid]

    def project_tutorials(self, pid: str) -> list[dict]:
        return [t for t in self.tutorials if t.get("projectId") == pid]

    def project_rl_models(self, pid: str) -> list[dict]:
        return [m for m in self.rl_models if m.get("projectId") == pid]

    def annotation_reviews(self, aid: str) -> list[dict]:
        return [r for r in self.reviews if r.get("annotationId") == aid]

    def tutorial_steps_for(self, tid: str) -> list[dict]:
        return [s for s in self.tutorial_steps if s.get("tutorialId") == tid]

    def team_members_for(self, tid: str) -> list[dict]:
        return [m for m in self.team_members if m.get("teamId") == tid]

    def team_names(self) -> list[str]:
        return [t["name"] for t in self.teams]

    # ---- Stats helpers ----
    def annotation_stats(self, pid: str) -> dict:
        anns = self.project_annotations(pid)
        total = len(anns)
        approved = sum(1 for a in anns if a.get("status") == "approved")
        pending = sum(1 for a in anns if a.get("status") == "pending")
        rejected = sum(1 for a in anns if a.get("status") == "rejected")
        in_review = sum(1 for a in anns if a.get("status") == "in_review")
        return {"total": total, "approved": approved, "pending": pending,
                "rejected": rejected, "in_review": in_review}

    def workflow_step_types(self, wf: dict) -> dict:
        from collections import Counter
        steps = wf.get("steps", [])
        return Counter(s.get("type", "process") for s in steps)
