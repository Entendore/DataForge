"""DataForge – Dashboard and Projects views."""

from __future__ import annotations

import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QGridLayout, QScrollArea, QLineEdit, QComboBox, QTextEdit, QDialog,
    QFormLayout, QDialogButtonBox, QSizePolicy, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from models import create, update, delete, Project, Dataset, Annotation
from store import Store

# Import theme from main_window
from models import (
    BG_DARK, BG_CARD, BG_HOVER, BG_INPUT, FG_PRIMARY, FG_SECONDARY,
    FG_MUTED, ACCENT, ACCENT2, BORDER, SUCCESS, WARNING, DANGER, INFO, RADIUS,
)


def make_card(title: str, value: str, subtitle: str = "", color: str = ACCENT) -> QFrame:
    card = QFrame()
    card.setStyleSheet(f"""
        QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS}px; padding: 0; }}
    """)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(20, 16, 20, 16)

    top_bar = QHBoxLayout()
    dot = QLabel("●")
    dot.setFixedSize(10, 10)
    dot.setStyleSheet(f"background: {color}; border-radius: 5px;")
    top_bar.addWidget(dot)
    lbl = QLabel(title)
    lbl.setStyleSheet(f"color: {FG_MUTED}; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;")
    top_bar.addWidget(lbl)
    top_bar.addStretch()
    lay.addLayout(top_bar)

    val = QLabel(str(value))
    val.setStyleSheet(f"color: {FG_PRIMARY}; font-size: 28px; font-weight: 800;")
    lay.addWidget(val)

    if subtitle:
        sub = QLabel(subtitle)
        sub.setStyleSheet(f"color: {FG_MUTED}; font-size: 12px;")
        lay.addWidget(sub)
    return card


def make_section_header(title: str) -> QLabel:
    lbl = QLabel(title)
    lbl.setStyleSheet(f"""
        QLabel {{ color: {FG_PRIMARY}; font-size: 18px; font-weight: 700; padding: 8px 0; }}
    """)
    return lbl


def make_button(text: str, color: str = ACCENT, icon: str = "") -> QPushButton:
    btn = QPushButton(f"{'  ' + icon if icon else ''}  {text}")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{ background: {color}; color: #fff; border: none; border-radius: {RADIUS}px;
            padding: 10px 20px; font-weight: 600; font-size: 13px; }}
        QPushButton:hover {{ opacity: 0.9; }}
        QPushButton:pressed {{ background: {color}cc; }}
    """)
    return btn


def make_btn_secondary(text: str, icon: str = "") -> QPushButton:
    btn = QPushButton(f"{'  ' + icon if icon else ''}  {text}")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{ background: {BG_CARD}; color: {FG_SECONDARY}; border: 1px solid {BORDER};
            border-radius: {RADIUS}px; padding: 8px 16px; font-weight: 500; font-size: 13px; }}
        QPushButton:hover {{ background: {BG_HOVER}; color: {FG_PRIMARY}; }}
    """)
    return btn


class DashboardView(QWidget):
    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(24)

        # Header
        header = QHBoxLayout()
        title = QLabel("Dashboard")
        title.setStyleSheet(f"color: {FG_PRIMARY}; font-size: 26px; font-weight: 800;")
        header.addWidget(title)
        header.addStretch()

        now_lbl = QLabel()
        from datetime import datetime
        now_lbl.setText(datetime.now().strftime("%A, %B %d, %Y"))
        now_lbl.setStyleSheet(f"color: {FG_MUTED}; font-size: 13px;")
        header.addWidget(now_lbl)
        layout.addLayout(header)

        # Stats cards row
        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)

        n_projects = len(self.store.projects)
        n_annotations = len(self.store.annotations)
        n_workflows = len(self.store.workflows)
        n_teams = len(self.store.teams)

        # Count stats by status
        approved = sum(1 for a in self.store.annotations if a.get("status") == "approved")
        pending = sum(1 for a in self.store.annotations if a.get("status") == "pending")

        cards_row.addWidget(make_card("Total Projects", str(n_projects), "Active workspaces", ACCENT))
        cards_row.addWidget(make_card("Total Annotations", str(n_annotations), f"{approved} approved, {pending} pending", SUCCESS))
        cards_row.addWidget(make_card("Active Workflows", str(n_workflows), "Pipeline automation", ACCENT2))
        cards_row.addWidget(make_card("Team Members", str(n_teams), "Collaborators", INFO))
        layout.addLayout(cards_row)

        # Two columns: Recent Activity + Annotation Progress
        cols = QHBoxLayout()
        cols.setSpacing(16)

        # Left: Annotation Progress
        progress_frame = QFrame()
        progress_frame.setStyleSheet(f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS}px; }}")
        pl = QVBoxLayout(progress_frame)
        pl.setContentsMargins(20, 16, 20, 16)
        pl.addWidget(make_section_header("Annotation Progress"))

        # Progress bars by status
        statuses = [("approved", "Approved", SUCCESS), ("pending", "Pending", WARNING),
                    ("in_review", "In Review", INFO), ("rejected", "Rejected", DANGER)]
        total = max(n_annotations, 1)
        for key, label, color in statuses:
            count = sum(1 for a in self.store.annotations if a.get("status") == key)
            pct = int(count / total * 100)
            row = QHBoxLayout()
            row_l = QVBoxLayout()
            lbl_row = QHBoxLayout()
            l1 = QLabel(label)
            l1.setStyleSheet(f"color: {FG_SECONDARY}; font-size: 13px; font-weight: 500;")
            l2 = QLabel(f"{count} ({pct}%)")
            l2.setStyleSheet(f"color: {FG_MUTED}; font-size: 12px;")
            lbl_row.addWidget(l1)
            lbl_row.addStretch()
            lbl_row.addWidget(l2)
            row_l.addLayout(lbl_row)
            bar = QFrame()
            bar.setFixedHeight(8)
            bar.setStyleSheet(f"""
                QFrame {{ background: {BG_INPUT}; border-radius: 4px; }}
            """)
            bar_lay = QHBoxLayout(bar)
            bar_lay.setContentsMargins(0, 0, 0, 0)
            bar_lay.setSpacing(0)
            fill = QFrame()
            fill_w = max(int(bar.width() * pct / 100), 4) if bar.width() > 0 else pct * 3
            fill.setStyleSheet(f"QFrame {{ background: {color}; border-radius: 4px; }}")
            fill.setFixedWidth(fill_w)
            bar_lay.addWidget(fill)
            bar_lay.addStretch()
            row_l.addWidget(bar)
            row.addLayout(row_l, 1)
            pl.addLayout(row)

        pl.addStretch()
        cols.addWidget(progress_frame, 1)

        # Right: Recent Activity
        activity_frame = QFrame()
        activity_frame.setStyleSheet(f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS}px; }}")
        al = QVBoxLayout(activity_frame)
        al.setContentsMargins(20, 16, 20, 16)
        al.addWidget(make_section_header("Recent Activity"))

        for act in self.store.activities[-8:]:
            row = QHBoxLayout()
            icon = QLabel("●")
            action = act.get("action", "")
            if "created" in action:
                icon.setStyleSheet(f"color: {SUCCESS}; font-size: 8px;")
            elif "completed" in action:
                icon.setStyleSheet(f"color: {ACCENT}; font-size: 8px;")
            elif "approved" in action:
                icon.setStyleSheet(f"color: {INFO}; font-size: 8px;")
            else:
                icon.setStyleSheet(f"color: {WARNING}; font-size: 8px;")
            row.addWidget(icon)

            details = act.get("details", {})
            if isinstance(details, str):
                try: details = json.loads(details)
                except: details = {}
            desc = details.get("projectName", details.get("workflowName", details.get("count", action.replace("_", " ").title())))

            t = QLabel(f"  {desc}")
            t.setStyleSheet(f"color: {FG_PRIMARY}; font-size: 13px;")
            row.addWidget(t, 1)
            time_lbl = QLabel(act.get("createdAt", "")[:16].replace("T", " "))
            time_lbl.setStyleSheet(f"color: {FG_MUTED}; font-size: 11px;")
            row.addWidget(time_lbl)
            al.addLayout(row)

        al.addStretch()
        cols.addWidget(activity_frame, 1)
        layout.addLayout(cols)

        # Quick Actions
        actions_frame = QFrame()
        actions_frame.setStyleSheet(f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS}px; }}")
        act_l = QVBoxLayout(actions_frame)
        act_l.setContentsMargins(20, 16, 20, 16)
        act_l.addWidget(make_section_header("Quick Actions"))
        btns_row = QHBoxLayout()
        btns_row.setSpacing(12)
        for text, color in [("New Project", ACCENT), ("Annotate Data", SUCCESS), ("Create Workflow", ACCENT2), ("Export Data", INFO)]:
            b = make_button(text, color)
            b.clicked.connect(lambda c=False, t=text: self._quick_action(t))
            btns_row.addWidget(b)
        btns_row.addStretch()
        act_l.addLayout(btns_row)
        layout.addWidget(actions_frame)
        layout.addStretch()

    def _quick_action(self, action: str):
        # This would switch views in the main window
        pass

    def refresh(self):
        # Rebuild on data change - use a container to avoid layout conflict
        old_layout = self.layout()
        if old_layout:
            QWidget().setLayout(old_layout)
        self._build_ui()


# ---------------------------------------------------------------------------
# Projects View
# ---------------------------------------------------------------------------
class ProjectsView(QWidget):
    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self.filter_text = ""
        self.filter_status = "all"
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(20)

        # Header
        header = QHBoxLayout()
        title = QLabel("Projects")
        title.setStyleSheet(f"color: {FG_PRIMARY}; font-size: 26px; font-weight: 800;")
        header.addWidget(title)
        header.addStretch()

        add_btn = make_button("New Project", ACCENT, "+")
        add_btn.clicked.connect(self._add_project)
        header.addWidget(add_btn)
        layout.addLayout(header)

        # Filters
        filters = QHBoxLayout()
        filters.setSpacing(12)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search projects...")
        self.search_input.setFixedWidth(300)
        self.search_input.textChanged.connect(self._on_search)
        filters.addWidget(self.search_input)

        self.status_combo = QComboBox()
        self.status_combo.addItems(["All Status", "Active", "Completed", "Paused"])
        self.status_combo.setFixedWidth(150)
        self.status_combo.currentTextChanged.connect(self._on_filter)
        filters.addWidget(self.status_combo)
        filters.addStretch()
        layout.addLayout(filters)

        # Project cards grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.cards_container = QWidget()
        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setSpacing(16)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.cards_container)
        layout.addWidget(scroll)
        self._populate_cards()

    def _populate_cards(self):
        # Clear
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        projects = self.store.projects
        if self.filter_text:
            projects = [p for p in projects if self.filter_text.lower() in p["name"].lower()]
        if self.filter_status != "all":
            projects = [p for p in projects if p.get("status", "") == self.filter_status]

        for i, proj in enumerate(projects):
            col = i % 3
            row = i // 3
            card = self._make_project_card(proj)
            self.cards_layout.addWidget(card, row, col)

    def _make_project_card(self, proj: dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS}px; }}
            QFrame:hover {{ border-color: {ACCENT}40; }}
        """)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 16, 20, 16)
        cl.setSpacing(12)

        # Top row
        top = QHBoxLayout()
        name = QLabel(proj["name"])
        name.setStyleSheet(f"color: {FG_PRIMARY}; font-size: 16px; font-weight: 700;")
        top.addWidget(name)
        top.addStretch()

        status_colors = {"active": SUCCESS, "completed": INFO, "paused": WARNING}
        sc = status_colors.get(proj.get("status", ""), FG_MUTED)
        status_lbl = QLabel(f"  {proj.get('status', '').title()}  ")
        status_lbl.setStyleSheet(f"color: {sc}; background: {sc}18; border-radius: 10px; padding: 3px 10px; font-size: 11px; font-weight: 600;")
        top.addWidget(status_lbl)
        cl.addLayout(top)

        desc = QLabel(proj.get("description", "No description"))
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {FG_MUTED}; font-size: 12px;")
        cl.addWidget(desc)

        # Meta row
        ann_count = len(self.store.project_annotations(proj["id"]))
        ds_count = len(self.store.project_datasets(proj["id"]))
        meta = QHBoxLayout()
        meta_lbl = QLabel(f"🏷 {ann_count} annotations  •  📄 {ds_count} datasets  •  {proj.get('dataType', 'text').title()}")
        meta_lbl.setStyleSheet(f"color: {FG_MUTED}; font-size: 12px;")
        meta.addWidget(meta_lbl)
        meta.addStretch()
        cl.addLayout(meta)

        # Action buttons
        btns = QHBoxLayout()
        btns.setSpacing(8)
        edit_btn = make_btn_secondary("Edit")
        edit_btn.clicked.connect(lambda c=False, pid=proj["id"]: self._edit_project(pid))
        btns.addWidget(edit_btn)
        del_btn = make_btn_secondary("Delete", "🗑️")
        del_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {DANGER}; border: 1px solid {DANGER}40;
                border-radius: {RADIUS}px; padding: 8px 16px; font-weight: 500; font-size: 13px; }}
            QPushButton:hover {{ background: {DANGER}18; }}
        """)
        del_btn.clicked.connect(lambda c=False, pid=proj["id"]: self._delete_project(pid))
        btns.addWidget(del_btn)
        btns.addStretch()
        cl.addLayout(btns)

        return card

    def _on_search(self, text):
        self.filter_text = text
        self._populate_cards()

    def _on_filter(self, text):
        status_map = {"All Status": "all", "Active": "active", "Completed": "completed", "Paused": "paused"}
        self.filter_status = status_map.get(text, "all")
        self._populate_cards()

    def _add_project(self):
        dlg = ProjectDialog(self.store, parent=self)
        if dlg.exec():
            self.store.reload("projects")
            self.refresh()

    def _edit_project(self, pid: str):
        proj = self.store.get_project(pid)
        if proj:
            dlg = ProjectDialog(self.store, project=proj, parent=self)
            if dlg.exec():
                self.store.reload("projects")
                self.refresh()

    def _delete_project(self, pid: str):
        reply = QMessageBox.question(self, "Delete Project",
            "Are you sure you want to delete this project and all its data?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            delete(Project, pid)
            self.store.reload_all()
            self.refresh()

    def refresh(self):
        # Rebuild
        layout = self.layout()
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._build_ui()


class ProjectDialog(QDialog):
    def __init__(self, store: Store, project: dict | None = None, parent=None):
        super().__init__(parent)
        self.store = store
        self.project = project
        self.setWindowTitle("Edit Project" if project else "New Project")
        self.setMinimumWidth(500)
        self.setStyleSheet(f"""
            QDialog {{ background: {BG_DARK}; color: {FG_PRIMARY}; }}
            QLabel {{ color: {FG_PRIMARY}; }}
            QLineEdit, QTextEdit, QComboBox {{ background: {BG_INPUT}; color: {FG_PRIMARY};
                border: 1px solid {BORDER}; border-radius: {RADIUS}px; padding: 10px; }}
        """)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(16)

        self.name_input = QLineEdit(project["name"] if project else "")
        self.name_input.setPlaceholderText("Project name...")
        form.addRow("Name:", self.name_input)

        self.desc_input = QTextEdit(project.get("description", "") if project else "")
        self.desc_input.setPlaceholderText("Describe the project...")
        self.desc_input.setMaximumHeight(100)
        form.addRow("Description:", self.desc_input)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["text", "image", "tabular", "video", "audio", "custom"])
        if project:
            idx = self.type_combo.findText(project.get("dataType", "text"))
            if idx >= 0:
                self.type_combo.setCurrentIndex(idx)
        form.addRow("Data Type:", self.type_combo)

        self.status_combo = QComboBox()
        self.status_combo.addItems(["active", "paused", "completed"])
        if project:
            idx = self.status_combo.findText(project.get("status", "active"))
            if idx >= 0:
                self.status_combo.setCurrentIndex(idx)
        form.addRow("Status:", self.status_combo)

        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Project name is required.")
            return

        data = {
            "name": name,
            "description": self.desc_input.toPlainText(),
            "dataType": self.type_combo.currentText(),
            "status": self.status_combo.currentText(),
        }
        if self.project:
            update(Project, self.project["id"], **data)
        else:
            create(Project, **data)
        self.accept()
