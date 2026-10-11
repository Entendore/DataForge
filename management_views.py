"""DataForge – Teams, QA Review, Labels, and Activity views."""

from __future__ import annotations

import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QLineEdit, QTextEdit, QComboBox, QDialog, QFormLayout, QDialogButtonBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox,
    QTabWidget, QScrollArea, QSizePolicy, QColorDialog, QCheckBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from models import Team, TeamMember, LabelSchema, Review, Annotation, ActivityLog, create, update, delete
from store import Store
from models import (
    BG_DARK, BG_CARD, BG_HOVER, BG_INPUT, FG_PRIMARY, FG_SECONDARY,
    FG_MUTED, ACCENT, ACCENT2, BORDER, SUCCESS, WARNING, DANGER, INFO, RADIUS,
)
from dashboard_projects import make_section_header, make_button, make_btn_secondary


# ═══════════════════════════════════════════════════════════════════════════
#  TEAMS VIEW
# ═══════════════════════════════════════════════════════════════════════════
class TeamsView(QWidget):
    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(20)

        header = QHBoxLayout()
        title = QLabel("Teams")
        title.setStyleSheet(f"color: {FG_PRIMARY}; font-size: 26px; font-weight: 800;")
        header.addWidget(title)
        header.addStretch()
        add_btn = make_button("New Team", ACCENT, "+")
        add_btn.clicked.connect(self._add_team)
        header.addWidget(add_btn)
        layout.addLayout(header)

        # Teams list
        self.teams_container = QWidget()
        self.teams_layout = QVBoxLayout(self.teams_container)
        self.teams_layout.setContentsMargins(0, 0, 0, 0)
        self.teams_layout.setSpacing(16)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setWidget(self.teams_container)
        layout.addWidget(scroll)
        self._populate()

    def _populate(self):
        while self.teams_layout.count():
            item = self.teams_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for team in self.store.teams:
            card = QFrame()
            card.setStyleSheet(f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS}px; }}")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(20, 16, 20, 16)
            cl.setSpacing(12)

            top = QHBoxLayout()
            color_dot = QLabel("●")
            color_dot.setStyleSheet(f"color: {team.get('color', ACCENT)}; font-size: 20px;")
            top.addWidget(color_dot)
            name = QLabel(team["name"])
            name.setStyleSheet(f"color: {FG_PRIMARY}; font-size: 18px; font-weight: 700;")
            top.addWidget(name)
            top.addStretch()

            edit_btn = make_btn_secondary("Edit")
            edit_btn.clicked.connect(lambda c=False, tid=team["id"]: self._edit_team(tid))
            top.addWidget(edit_btn)
            del_btn = make_btn_secondary("Delete", "🗑️")
            del_btn.setStyleSheet(f"""
                QPushButton {{ background: transparent; color: {DANGER}; border: 1px solid {DANGER}40;
                    border-radius: {RADIUS}px; padding: 8px 16px; font-weight: 500; }}
                QPushButton:hover {{ background: {DANGER}18; }}
            """)
            del_btn.clicked.connect(lambda c=False, tid=team["id"]: self._delete_team(tid))
            top.addWidget(del_btn)
            cl.addLayout(top)

            desc = QLabel(team.get("description", "No description"))
            desc.setWordWrap(True)
            desc.setStyleSheet(f"color: {FG_MUTED}; font-size: 13px;")
            cl.addWidget(desc)

            # Members
            members = self.store.team_members_for(team["id"])
            if members:
                members_lbl = QLabel(f"  Members: {', '.join(m['name'] for m in members)}")
                members_lbl.setWordWrap(True)
                members_lbl.setStyleSheet(f"color: {FG_SECONDARY}; font-size: 12px;")
                cl.addWidget(members_lbl)

            add_member_btn = make_btn_secondary("Add Member", "+")
            add_member_btn.clicked.connect(lambda c=False, tid=team["id"]: self._add_member(tid))
            cl.addWidget(add_member_btn, alignment=Qt.AlignmentFlag.AlignLeft)

            self.teams_layout.addWidget(card)

        self.teams_layout.addStretch()

    def _add_team(self):
        dlg = TeamDialog(self.store, parent=self)
        if dlg.exec():
            self.store.reload("teams")
            self.refresh()

    def _edit_team(self, tid: str):
        team = next((t for t in self.store.teams if t["id"] == tid), None)
        if team:
            dlg = TeamDialog(self.store, team=team, parent=self)
            if dlg.exec():
                self.store.reload("teams")
                self.refresh()

    def _delete_team(self, tid: str):
        if QMessageBox.question(self, "Delete Team", "Delete this team?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            delete(Team, tid)
            self.store.reload("teams")
            self.refresh()

    def _add_member(self, tid: str):
        dlg = MemberDialog(tid, parent=self)
        if dlg.exec():
            self.store.reload("team_members")
            self.refresh()

    def refresh(self):
        layout = self.layout()
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._build_ui()


class TeamDialog(QDialog):
    def __init__(self, store, team=None, parent=None):
        super().__init__(parent)
        self.store = store
        self.team = team
        self.team_color = team.get("color", "#8b5cf6") if team else "#8b5cf6"
        self.setWindowTitle("Edit Team" if team else "New Team")
        self.setMinimumWidth(450)
        self.setStyleSheet(f"QDialog {{ background: {BG_DARK}; color: {FG_PRIMARY}; }}")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(16)

        self.name_input = QLineEdit(team["name"] if team else "")
        form.addRow("Name:", self.name_input)

        self.desc_input = QTextEdit(team.get("description", "") if team else "")
        self.desc_input.setMaximumHeight(80)
        form.addRow("Description:", self.desc_input)

        self.color_btn = QPushButton("  Choose Color")
        self.color_btn.setStyleSheet(f"background: {self.team_color}; color: #fff; border: none; border-radius: {RADIUS}px; padding: 8px;")
        self.color_btn.clicked.connect(self._pick_color)
        form.addRow("Color:", self.color_btn)

        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self.team_color), self)
        if color.isValid():
            self.team_color = color.name()
            self.color_btn.setStyleSheet(f"background: {self.team_color}; color: #fff; border: none; border-radius: {RADIUS}px; padding: 8px;")

    def _save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Team name required.")
            return
        data = {"name": name, "description": self.desc_input.toPlainText(), "color": self.team_color}
        if self.team:
            update(Team, self.team["id"], **data)
        else:
            create(Team, **data)
        self.accept()


class MemberDialog(QDialog):
    def __init__(self, team_id: str, parent=None):
        super().__init__(parent)
        self.team_id = team_id
        self.setWindowTitle("Add Team Member")
        self.setMinimumWidth(400)
        self.setStyleSheet(f"QDialog {{ background: {BG_DARK}; color: {FG_PRIMARY}; }}")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(16)

        self.name_input = QLineEdit()
        form.addRow("Name:", self.name_input)
        self.role_combo = QComboBox()
        self.role_combo.addItems(["annotator", "reviewer", "lead", "admin"])
        form.addRow("Role:", self.role_combo)
        self.email_input = QLineEdit()
        form.addRow("Email:", self.email_input)

        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Name required.")
            return
        create(TeamMember, teamId=self.team_id, name=name,
               role=self.role_combo.currentText(), email=self.email_input.text())
        self.accept()


# ═══════════════════════════════════════════════════════════════════════════
#  QA REVIEW VIEW
# ═══════════════════════════════════════════════════════════════════════════
class QAReviewView(QWidget):
    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(20)

        header = QHBoxLayout()
        title = QLabel("QA Review")
        title.setStyleSheet(f"color: {FG_PRIMARY}; font-size: 26px; font-weight: 800;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # Stats row
        stats = QHBoxLayout()
        stats.setSpacing(16)
        total_reviews = len(self.store.reviews)
        approved = sum(1 for r in self.store.reviews if r.get("status") == "approved")
        pending = sum(1 for r in self.store.reviews if r.get("status") == "pending")
        rejected = sum(1 for r in self.store.reviews if r.get("status") == "rejected")

        for label, val, color in [("Total Reviews", total_reviews, ACCENT), ("Approved", approved, SUCCESS),
                                   ("Pending", pending, WARNING), ("Rejected", rejected, DANGER)]:
            card = QFrame()
            card.setStyleSheet(f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS}px; }}")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(16, 12, 16, 12)
            l = QLabel(label)
            l.setStyleSheet(f"color: {FG_MUTED}; font-size: 12px; font-weight: 600;")
            cl.addWidget(l)
            v = QLabel(str(val))
            v.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: 800;")
            cl.addWidget(v)
            stats.addWidget(card)
        layout.addLayout(stats)

        # Review table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Annotation ID", "Reviewer", "Status", "Comments", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet(f"""
            QTableWidget {{ background: {BG_DARK}; color: {FG_PRIMARY}; gridline-color: {BORDER};
                border: 1px solid {BORDER}; border-radius: {RADIUS}px; }}
        """)

        for row_idx, review in enumerate(self.store.reviews):
            self.table.insertRow(row_idx)
            aid = review.get("annotationId", "")[:8] + "..."
            self.table.setItem(row_idx, 0, QTableWidgetItem(aid))
            self.table.setItem(row_idx, 1, QTableWidgetItem(review.get("reviewer", "")))
            status = review.get("status", "pending")
            status_item = QTableWidgetItem(status.title())
            sc = {"approved": SUCCESS, "pending": WARNING, "rejected": DANGER}.get(status, FG_MUTED)
            status_item.setForeground(QColor(sc))
            self.table.setItem(row_idx, 2, status_item)
            self.table.setItem(row_idx, 3, QTableWidgetItem(review.get("comments", "")[:50]))
            self.table.setItem(row_idx, 4, QTableWidgetItem())

        layout.addWidget(self.table)

        # Add review button
        add_btn = make_button("Add Review", ACCENT, "+")
        add_btn.clicked.connect(self._add_review)
        layout.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignLeft)

    def _add_review(self):
        dlg = ReviewDialog(self.store, parent=self)
        if dlg.exec():
            self.store.reload("reviews")
            self.refresh()

    def refresh(self):
        layout = self.layout()
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._build_ui()


class ReviewDialog(QDialog):
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("Add Review")
        self.setMinimumWidth(450)
        self.setStyleSheet(f"QDialog {{ background: {BG_DARK}; color: {FG_PRIMARY}; }}")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(16)

        self.ann_combo = QComboBox()
        for ann in self.store.annotations:
            self.ann_combo.addItem(f"{ann.get('id', '')[:12]}... (idx {ann.get('dataIndex', 0)})", ann["id"])
        form.addRow("Annotation:", self.ann_combo)

        self.proj_combo = QComboBox()
        for p in self.store.projects:
            self.proj_combo.addItem(p["name"], p["id"])
        form.addRow("Project:", self.proj_combo)

        self.reviewer_input = QLineEdit()
        form.addRow("Reviewer:", self.reviewer_input)

        self.status_combo = QComboBox()
        self.status_combo.addItems(["pending", "approved", "rejected"])
        form.addRow("Status:", self.status_combo)

        self.comments_input = QTextEdit()
        self.comments_input.setMaximumHeight(80)
        form.addRow("Comments:", self.comments_input)

        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _save(self):
        ann_id = self.ann_combo.currentData()
        proj_id = self.proj_combo.currentData()
        if ann_id and proj_id:
            create(Review, annotationId=ann_id, projectId=proj_id,
                   reviewer=self.reviewer_input.text(), status=self.status_combo.currentText(),
                   comments=self.comments_input.toPlainText())
        self.accept()


# ═══════════════════════════════════════════════════════════════════════════
#  LABELS VIEW (with hierarchy)
# ═══════════════════════════════════════════════════════════════════════════
class LabelsView(QWidget):
    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(20)

        header = QHBoxLayout()
        title = QLabel("Labels")
        title.setStyleSheet(f"color: {FG_PRIMARY}; font-size: 26px; font-weight: 800;")
        header.addWidget(title)
        header.addStretch()

        add_btn = make_button("New Label", ACCENT, "+")
        add_btn.clicked.connect(self._add_label)
        header.addWidget(add_btn)
        layout.addLayout(header)

        # Filter by type
        filters = QHBoxLayout()
        filters.setSpacing(12)
        self.type_filter = QComboBox()
        self.type_filter.addItems(["All Types", "category", "entity", "relation", "attribute"])
        self.type_filter.setFixedWidth(150)
        self.type_filter.currentTextChanged.connect(self._populate)
        filters.addWidget(self.type_filter)
        filters.addStretch()
        layout.addLayout(filters)

        # Labels table with hierarchy
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Color", "Description", "Parent", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet(f"""
            QTableWidget {{ background: {BG_DARK}; color: {FG_PRIMARY}; gridline-color: {BORDER};
                border: 1px solid {BORDER}; border-radius: {RADIUS}px; }}
        """)
        self._populate()
        layout.addWidget(self.table)

    def _populate(self):
        self.table.setRowCount(0)
        type_filter = self.type_filter.currentText()
        labels = self.store.labels
        if type_filter != "All Types":
            labels = [l for l in labels if l.get("type", "") == type_filter]

        for row_idx, lbl in enumerate(labels):
            self.table.insertRow(row_idx)

            # Name with color dot
            name_item = QTableWidgetItem(f"  ●  {lbl.get('name', '')}")
            name_item.setForeground(QColor(lbl.get("color", FG_PRIMARY)))
            self.table.setItem(row_idx, 0, name_item)

            self.table.setItem(row_idx, 1, QTableWidgetItem(lbl.get("type", "")))

            color_item = QTableWidgetItem(lbl.get("color", ""))
            color_item.setBackground(QColor(lbl.get("color", BG_INPUT)))
            self.table.setItem(row_idx, 2, color_item)

            self.table.setItem(row_idx, 3, QTableWidgetItem(lbl.get("description", "")[:60]))

            parent_id = lbl.get("parentId")
            parent_name = ""
            if parent_id:
                parent = next((l for l in self.store.labels if l["id"] == parent_id), None)
                if parent:
                    parent_name = parent["name"]
            self.table.setItem(row_idx, 4, QTableWidgetItem(parent_name))

            # Actions button
            actions_widget = QWidget()
            actions_lay = QHBoxLayout(actions_widget)
            actions_lay.setContentsMargins(4, 2, 4, 2)
            actions_lay.setSpacing(4)

            edit_btn = make_btn_secondary("Edit")
            edit_btn.setFixedSize(60, 30)
            edit_btn.clicked.connect(lambda c=False, lid=lbl["id"]: self._edit_label(lid))
            actions_lay.addWidget(edit_btn)

            del_btn = make_btn_secondary("Del", "×")
            del_btn.setFixedSize(50, 30)
            del_btn.setStyleSheet(f"""
                QPushButton {{ background: transparent; color: {DANGER}; border: 1px solid {DANGER}40;
                    border-radius: 4px; font-weight: 500; }}
                QPushButton:hover {{ background: {DANGER}18; }}
            """)
            del_btn.clicked.connect(lambda c=False, lid=lbl["id"]: self._delete_label(lid))
            actions_lay.addWidget(del_btn)
            self.table.setCellWidget(row_idx, 5, actions_widget)

    def _add_label(self):
        dlg = LabelDialog(self.store, parent=self)
        if dlg.exec():
            self.store.reload("labels")
            self._populate()

    def _edit_label(self, lid: str):
        lbl = next((l for l in self.store.labels if l["id"] == lid), None)
        if lbl:
            dlg = LabelDialog(self.store, label=lbl, parent=self)
            if dlg.exec():
                self.store.reload("labels")
                self._populate()

    def _delete_label(self, lid: str):
        if QMessageBox.question(self, "Delete Label", "Delete this label?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            delete(LabelSchema, lid)
            self.store.reload("labels")
            self._populate()

    def refresh(self):
        self._populate()


class LabelDialog(QDialog):
    def __init__(self, store, label=None, parent=None):
        super().__init__(parent)
        self.store = store
        self.label = label
        self.label_color = label.get("color", "#8b5cf6") if label else "#8b5cf6"
        self.setWindowTitle("Edit Label" if label else "New Label")
        self.setMinimumWidth(450)
        self.setStyleSheet(f"QDialog {{ background: {BG_DARK}; color: {FG_PRIMARY}; }}")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(16)

        self.name_input = QLineEdit(label["name"] if label else "")
        form.addRow("Name:", self.name_input)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["category", "entity", "relation", "attribute"])
        if label:
            idx = self.type_combo.findText(label.get("type", "category"))
            if idx >= 0: self.type_combo.setCurrentIndex(idx)
        form.addRow("Type:", self.type_combo)

        self.color_btn = QPushButton("  Choose Color")
        self.color_btn.setStyleSheet(f"background: {self.label_color}; color: #fff; border: none; border-radius: {RADIUS}px; padding: 8px;")
        self.color_btn.clicked.connect(self._pick_color)
        form.addRow("Color:", self.color_btn)

        self.desc_input = QTextEdit(label.get("description", "") if label else "")
        self.desc_input.setMaximumHeight(60)
        form.addRow("Description:", self.desc_input)

        # Parent label (hierarchy)
        self.parent_combo = QComboBox()
        self.parent_combo.addItem("None (Root)", "")
        for lbl in self.store.labels:
            if not label or lbl["id"] != label["id"]:
                self.parent_combo.addItem(lbl["name"], lbl["id"])
        if label and label.get("parentId"):
            idx = self.parent_combo.findData(label["parentId"])
            if idx >= 0: self.parent_combo.setCurrentIndex(idx)
        form.addRow("Parent Label:", self.parent_combo)

        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self.label_color), self)
        if color.isValid():
            self.label_color = color.name()
            self.color_btn.setStyleSheet(f"background: {self.label_color}; color: #fff; border: none; border-radius: {RADIUS}px; padding: 8px;")

    def _save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Label name required.")
            return
        data = {
            "name": name,
            "type": self.type_combo.currentText(),
            "color": self.label_color,
            "description": self.desc_input.toPlainText(),
        }
        parent_id = self.parent_combo.currentData()
        if parent_id:
            data["parentId"] = parent_id
        else:
            data["parentId"] = None

        # Need a project ID - use first project
        proj_id = self.store.projects[0]["id"] if self.store.projects else None
        if not proj_id:
            QMessageBox.warning(self, "Error", "No projects available.")
            return
        data["projectId"] = proj_id

        if self.label:
            data.pop("projectId", None)
            update(LabelSchema, self.label["id"], **data)
        else:
            create(LabelSchema, **data)
        self.accept()


# ═══════════════════════════════════════════════════════════════════════════
#  ACTIVITY VIEW
# ═══════════════════════════════════════════════════════════════════════════
class ActivityView(QWidget):
    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(20)

        header = QHBoxLayout()
        title = QLabel("Activity Log")
        title.setStyleSheet(f"color: {FG_PRIMARY}; font-size: 26px; font-weight: 800;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # Stats
        stats = QHBoxLayout()
        stats.setSpacing(16)
        total = len(self.store.activities)

        # Group by action type
        from collections import Counter
        action_counts = Counter(a.get("action", "") for a in self.store.activities)

        for label, count, color in [("Total Events", total, ACCENT)] + [
            (a.replace("_", " ").title(), c, ACCENT2) for a, c in action_counts.most_common(4)
        ]:
            card = QFrame()
            card.setStyleSheet(f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS}px; }}")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(16, 12, 16, 12)
            l = QLabel(label)
            l.setStyleSheet(f"color: {FG_MUTED}; font-size: 12px; font-weight: 600;")
            cl.addWidget(l)
            v = QLabel(str(count))
            v.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: 800;")
            cl.addWidget(v)
            stats.addWidget(card)
        layout.addLayout(stats)

        # Activity table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Action", "Details", "Timestamp", "Project"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet(f"""
            QTableWidget {{ background: {BG_DARK}; color: {FG_PRIMARY}; gridline-color: {BORDER};
                border: 1px solid {BORDER}; border-radius: {RADIUS}px; }}
        """)

        # Sort by time descending
        activities = sorted(self.store.activities, key=lambda a: a.get("createdAt", ""), reverse=True)

        for row_idx, act in enumerate(activities):
            self.table.insertRow(row_idx)
            action = act.get("action", "")
            self.table.setItem(row_idx, 0, QTableWidgetItem(action.replace("_", " ").title()))

            details = act.get("details", {})
            if isinstance(details, str):
                try: details = json.loads(details)
                except: details = {}
            if isinstance(details, dict):
                detail_str = ", ".join(f"{k}: {v}" for k, v in list(details.items())[:3])
            else:
                detail_str = str(details)
            self.table.setItem(row_idx, 1, QTableWidgetItem(detail_str[:100]))

            self.table.setItem(row_idx, 2, QTableWidgetItem(act.get("createdAt", "")[:19].replace("T", " ")))

            proj = self.store.get_project(act.get("projectId", ""))
            proj_name = proj["name"] if proj else "N/A"
            self.table.setItem(row_idx, 3, QTableWidgetItem(proj_name))

        layout.addWidget(self.table)

    def refresh(self):
        layout = self.layout()
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._build_ui()
