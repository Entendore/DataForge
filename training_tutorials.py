"""DataForge – Tutorials and RL Training views."""

from __future__ import annotations

import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QLineEdit, QTextEdit, QComboBox, QDialog, QFormLayout, QDialogButtonBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox,
    QScrollArea, QSpinBox, QProgressBar, QTabWidget,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from models import Tutorial, TutorialStep, RLModel, create, update, delete, get_by_id
from store import Store
from models import (
    BG_DARK, BG_CARD, BG_HOVER, BG_INPUT, FG_PRIMARY, FG_SECONDARY,
    FG_MUTED, ACCENT, ACCENT2, BORDER, SUCCESS, WARNING, DANGER, INFO, RADIUS,
)
from dashboard_projects import make_section_header, make_button, make_btn_secondary


# ═══════════════════════════════════════════════════════════════════════════
#  TUTORIALS VIEW
# ═══════════════════════════════════════════════════════════════════════════
class TutorialsView(QWidget):
    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(20)

        header = QHBoxLayout()
        title = QLabel("Tutorials")
        title.setStyleSheet(f"color: {FG_PRIMARY}; font-size: 26px; font-weight: 800;")
        header.addWidget(title)
        header.addStretch()
        add_btn = make_button("New Tutorial", ACCENT, "+")
        add_btn.clicked.connect(self._add_tutorial)
        header.addWidget(add_btn)
        layout.addLayout(header)

        # Stats
        published = sum(1 for t in self.store.tutorials if t.get("isPublished"))
        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)
        for label, val, color in [("Total", len(self.store.tutorials), ACCENT),
                                    ("Published", published, SUCCESS),
                                    ("Draft", len(self.store.tutorials) - published, WARNING)]:
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
            stats_row.addWidget(card)
        layout.addLayout(stats_row)

        # Tutorials list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        container = QWidget()
        self.tutorials_layout = QVBoxLayout(container)
        self.tutorials_layout.setContentsMargins(0, 0, 0, 0)
        self.tutorials_layout.setSpacing(16)

        for tut in self.store.tutorials:
            card = self._make_tutorial_card(tut)
            self.tutorials_layout.addWidget(card)

        self.tutorials_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def _make_tutorial_card(self, tut: dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS}px; }}")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 16, 20, 16)
        cl.setSpacing(12)

        top = QHBoxLayout()
        name = QLabel(tut["name"])
        name.setStyleSheet(f"color: {FG_PRIMARY}; font-size: 18px; font-weight: 700;")
        top.addWidget(name)
        top.addStretch()

        if tut.get("isPublished"):
            badge = QLabel("  ● Published  ")
            badge.setStyleSheet(f"color: {SUCCESS}; background: {SUCCESS}18; border-radius: 10px; padding: 3px 10px; font-size: 11px; font-weight: 600;")
        else:
            badge = QLabel("  ● Draft  ")
            badge.setStyleSheet(f"color: {WARNING}; background: {WARNING}18; border-radius: 10px; padding: 3px 10px; font-size: 11px; font-weight: 600;")
        top.addWidget(badge)

        edit_btn = make_btn_secondary("Edit")
        edit_btn.clicked.connect(lambda c=False, tid=tut["id"]: self._edit_tutorial(tid))
        top.addWidget(edit_btn)

        if not tut.get("isPublished"):
            pub_btn = make_btn_secondary("Publish", "📢")
            pub_btn.clicked.connect(lambda c=False, tid=tut["id"]: self._publish(tid))
            top.addWidget(pub_btn)

        del_btn = make_btn_secondary("Delete", "🗑️")
        del_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {DANGER}; border: 1px solid {DANGER}40;
                border-radius: {RADIUS}px; padding: 8px 16px; font-weight: 500; }}
            QPushButton:hover {{ background: {DANGER}18; }}
        """)
        del_btn.clicked.connect(lambda c=False, tid=tut["id"]: self._delete_tutorial(tid))
        top.addWidget(del_btn)
        cl.addLayout(top)

        desc = QLabel(tut.get("description", "No description"))
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {FG_MUTED}; font-size: 13px;")
        cl.addWidget(desc)

        # Steps preview
        steps = self.store.tutorial_steps_for(tut["id"])
        steps_lbl = QLabel(f"  {len(steps)} steps")
        steps_lbl.setStyleSheet(f"color: {FG_SECONDARY}; font-size: 12px;")
        cl.addWidget(steps_lbl)

        # Steps list (collapsible-like)
        if steps:
            steps_frame = QFrame()
            steps_frame.setStyleSheet(f"QFrame {{ background: {BG_INPUT}; border-radius: 6px; }}")
            sl = QVBoxLayout(steps_frame)
            sl.setContentsMargins(16, 12, 16, 12)
            sl.setSpacing(8)
            for i, step in enumerate(steps):
                step_row = QHBoxLayout()
                num = QLabel(f"{i+1}.")
                num.setStyleSheet(f"color: {ACCENT}; font-weight: 700; font-size: 13px; min-width: 20px;")
                step_row.addWidget(num)
                st = QLabel(step.get("title", ""))
                st.setStyleSheet(f"color: {FG_PRIMARY}; font-size: 13px;")
                step_row.addWidget(st, 1)
                sl.addLayout(step_row)
            cl.addWidget(steps_frame)

        return card

    def _add_tutorial(self):
        dlg = TutorialDialog(self.store, parent=self)
        if dlg.exec():
            self.store.reload("tutorials")
            self.store.reload("tutorial_steps")
            self.refresh()

    def _edit_tutorial(self, tid: str):
        tut = next((t for t in self.store.tutorials if t["id"] == tid), None)
        if tut:
            dlg = TutorialDialog(self.store, tutorial=tut, parent=self)
            if dlg.exec():
                self.store.reload("tutorials")
                self.store.reload("tutorial_steps")
                self.refresh()

    def _publish(self, tid: str):
        update(Tutorial, tid, isPublished=True)
        self.store.reload("tutorials")
        self.refresh()

    def _delete_tutorial(self, tid: str):
        if QMessageBox.question(self, "Delete Tutorial", "Delete this tutorial and all steps?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            delete(Tutorial, tid)
            self.store.reload("tutorials")
            self.store.reload("tutorial_steps")
            self.refresh()

    def refresh(self):
        layout = self.layout()
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._build_ui()


class TutorialDialog(QDialog):
    def __init__(self, store, tutorial=None, parent=None):
        super().__init__(parent)
        self.store = store
        self.tutorial = tutorial
        self.setWindowTitle("Edit Tutorial" if tutorial else "New Tutorial")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.setStyleSheet(f"QDialog {{ background: {BG_DARK}; color: {FG_PRIMARY}; }}")

        layout = QVBoxLayout(self)

        # Tutorial info
        form = QFormLayout()
        form.setSpacing(16)

        self.name_input = QLineEdit(tutorial["name"] if tutorial else "")
        form.addRow("Name:", self.name_input)

        self.desc_input = QTextEdit(tutorial.get("description", "") if tutorial else "")
        self.desc_input.setMaximumHeight(60)
        form.addRow("Description:", self.desc_input)

        layout.addLayout(form)

        # Steps
        steps_lbl = make_section_header("Tutorial Steps")
        layout.addWidget(steps_lbl)

        self.steps_container = QWidget()
        self.steps_layout = QVBoxLayout(self.steps_container)
        self.steps_layout.setContentsMargins(0, 0, 0, 0)
        self.steps_layout.setSpacing(8)

        if tutorial:
            steps = self.store.tutorial_steps_for(tutorial["id"])
            for step in steps:
                self._add_step_row(step.get("title", ""), step.get("content", ""))

        layout.addWidget(self.steps_container)

        add_step_btn = make_btn_secondary("Add Step", "+")
        add_step_btn.clicked.connect(lambda: self._add_step_row())
        layout.addWidget(add_step_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _add_step_row(self, title: str = "", content: str = ""):
        row_frame = QFrame()
        row_frame.setStyleSheet(f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 6px; }}")
        rl = QVBoxLayout(row_frame)
        rl.setContentsMargins(12, 8, 12, 8)
        rl.setSpacing(6)

        top = QHBoxLayout()
        title_input = QLineEdit(title)
        title_input.setPlaceholderText("Step title...")
        top.addWidget(title_input, 1)
        del_btn = make_btn_secondary("×")
        del_btn.setFixedSize(30, 30)
        del_btn.clicked.connect(lambda: (self.steps_layout.removeWidget(row_frame), row_frame.deleteLater()))
        top.addWidget(del_btn)
        rl.addLayout(top)

        content_input = QTextEdit(content)
        content_input.setPlaceholderText("Step content...")
        content_input.setMaximumHeight(60)
        rl.addWidget(content_input)

        self.steps_layout.insertWidget(self.steps_layout.count(), row_frame)

    def _get_steps_data(self) -> list[dict]:
        steps = []
        for i in range(self.steps_layout.count()):
            frame = self.steps_layout.itemAt(i).widget()
            if frame:
                children = frame.findChildren(QLineEdit)
                title = children[0].text() if children else ""
                text_edits = frame.findChildren(QTextEdit)
                content = text_edits[0].toPlainText() if text_edits else ""
                steps.append({"title": title, "content": content, "order": i})
        return steps

    def _save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Tutorial name required.")
            return

        proj_id = self.store.projects[0]["id"] if self.store.projects else None
        if not proj_id:
            QMessageBox.warning(self, "Error", "No projects available.")
            return

        if self.tutorial:
            update(Tutorial, self.tutorial["id"], name=name,
                   description=self.desc_input.toPlainText())
            # Update steps
            old_steps = self.store.tutorial_steps_for(self.tutorial["id"])
            for old in old_steps:
                delete(TutorialStep, old["id"])
            for step in self._get_steps_data():
                create(TutorialStep, tutorialId=self.tutorial["id"], **step)
        else:
            tut = create(Tutorial, name=name, projectId=proj_id,
                        description=self.desc_input.toPlainText())
            for step in self._get_steps_data():
                create(TutorialStep, tutorialId=tut["id"], **step)
        self.accept()


# ═══════════════════════════════════════════════════════════════════════════
#  RL TRAINING VIEW
# ═══════════════════════════════════════════════════════════════════════════
class RLTrainingView(QWidget):
    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(20)

        header = QHBoxLayout()
        title = QLabel("RL Training")
        title.setStyleSheet(f"color: {FG_PRIMARY}; font-size: 26px; font-weight: 800;")
        header.addWidget(title)
        header.addStretch()
        add_btn = make_button("New Model", ACCENT, "+")
        add_btn.clicked.connect(self._add_model)
        header.addWidget(add_btn)
        layout.addLayout(header)

        # Stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)
        statuses = {"idle": ("Idle", FG_MUTED), "training": ("Training", WARNING),
                    "completed": ("Completed", SUCCESS), "failed": ("Failed", DANGER)}
        for status_key, (label, color) in statuses.items():
            count = sum(1 for m in self.store.rl_models if m.get("status") == status_key)
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
            stats_row.addWidget(card)
        layout.addLayout(stats_row)

        # Models list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        container = QWidget()
        models_layout = QVBoxLayout(container)
        models_layout.setContentsMargins(0, 0, 0, 0)
        models_layout.setSpacing(16)

        for model in self.store.rl_models:
            card = self._make_model_card(model)
            models_layout.addWidget(card)

        models_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def _make_model_card(self, model: dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS}px; }}")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 16, 20, 16)
        cl.setSpacing(12)

        top = QHBoxLayout()
        name = QLabel(model["name"])
        name.setStyleSheet(f"color: {FG_PRIMARY}; font-size: 18px; font-weight: 700;")
        top.addWidget(name)

        type_badge = QLabel(f"  {model.get('modelType', 'ppo').upper()}  ")
        type_badge.setStyleSheet(f"color: {ACCENT}; background: {ACCENT}18; border-radius: 10px; padding: 3px 10px; font-size: 11px; font-weight: 600;")
        top.addWidget(type_badge)
        top.addStretch()

        status_colors = {"idle": FG_MUTED, "training": WARNING, "completed": SUCCESS, "failed": DANGER}
        status = model.get("status", "idle")
        sc = status_colors.get(status, FG_MUTED)
        status_badge = QLabel(f"  ● {status.title()}  ")
        status_badge.setStyleSheet(f"color: {sc}; background: {sc}18; border-radius: 10px; padding: 3px 10px; font-size: 11px; font-weight: 600;")
        top.addWidget(status_badge)

        edit_btn = make_btn_secondary("Edit")
        edit_btn.clicked.connect(lambda c=False, mid=model["id"]: self._edit_model(mid))
        top.addWidget(edit_btn)

        del_btn = make_btn_secondary("Delete", "🗑️")
        del_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {DANGER}; border: 1px solid {DANGER}40;
                border-radius: {RADIUS}px; padding: 8px 16px; font-weight: 500; }}
            QPushButton:hover {{ background: {DANGER}18; }}
        """)
        del_btn.clicked.connect(lambda c=False, mid=model["id"]: self._delete_model(mid))
        top.addWidget(del_btn)
        cl.addLayout(top)

        # Config
        config = model.get("config", {})
        if isinstance(config, str):
            try: config = json.loads(config)
            except: config = {}
        config_lbl = QLabel(f"Config: {json.dumps(config, indent=2)[:200]}")
        config_lbl.setWordWrap(True)
        config_lbl.setStyleSheet(f"color: {FG_SECONDARY}; font-size: 12px; font-family: monospace;")
        cl.addWidget(config_lbl)

        # Metrics
        metrics = model.get("metrics", {})
        if isinstance(metrics, str):
            try: metrics = json.loads(metrics)
            except: metrics = {}

        if metrics:
            metrics_frame = QFrame()
            metrics_frame.setStyleSheet(f"QFrame {{ background: {BG_INPUT}; border-radius: 6px; }}")
            ml = QHBoxLayout(metrics_frame)
            ml.setContentsMargins(16, 10, 16, 10)
            ml.setSpacing(24)
            for key, val in list(metrics.items())[:4]:
                metric_row = QVBoxLayout()
                mk = QLabel(key)
                mk.setStyleSheet(f"color: {FG_MUTED}; font-size: 11px; font-weight: 600; text-transform: uppercase;")
                metric_row.addWidget(mk)
                mv = QLabel(f"{val:.4f}" if isinstance(val, float) else str(val))
                mv.setStyleSheet(f"color: {FG_PRIMARY}; font-size: 20px; font-weight: 800;")
                metric_row.addWidget(mv)
                ml.addLayout(metric_row)
            cl.addWidget(metrics_frame)

        # Training progress bar (if training)
        if status == "training":
            progress = QProgressBar()
            progress.setValue(67)
            progress.setFormat("Training... 67%")
            progress.setStyleSheet(f"""
                QProgressBar {{ background: {BG_INPUT}; border-radius: 4px; text-align: center;
                    color: {FG_PRIMARY}; font-size: 12px; height: 24px; border: 1px solid {BORDER}; }}
                QProgressBar::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {ACCENT},stop:1 {ACCENT2}); border-radius: 4px; }}
            """)
            cl.addWidget(progress)

        return card

    def _add_model(self):
        dlg = RLModelDialog(self.store, parent=self)
        if dlg.exec():
            self.store.reload("rl_models")
            self.refresh()

    def _edit_model(self, mid: str):
        model = next((m for m in self.store.rl_models if m["id"] == mid), None)
        if model:
            dlg = RLModelDialog(self.store, model=model, parent=self)
            if dlg.exec():
                self.store.reload("rl_models")
                self.refresh()

    def _delete_model(self, mid: str):
        if QMessageBox.question(self, "Delete Model", "Delete this model?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            delete(RLModel, mid)
            self.store.reload("rl_models")
            self.refresh()

    def refresh(self):
        layout = self.layout()
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._build_ui()


class RLModelDialog(QDialog):
    def __init__(self, store, model=None, parent=None):
        super().__init__(parent)
        self.store = store
        self.model = model
        self.setWindowTitle("Edit Model" if model else "New Model")
        self.setMinimumWidth(500)
        self.setStyleSheet(f"QDialog {{ background: {BG_DARK}; color: {FG_PRIMARY}; }}")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(16)

        self.name_input = QLineEdit(model["name"] if model else "")
        form.addRow("Name:", self.name_input)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["ppo", "dqn", "a2c", "sac", "td3"])
        if model:
            idx = self.type_combo.findText(model.get("modelType", "ppo"))
            if idx >= 0: self.type_combo.setCurrentIndex(idx)
        form.addRow("Algorithm:", self.type_combo)

        config = model.get("config", {})
        if isinstance(config, str):
            try: config = json.loads(config)
            except: config = {}
        self.config_input = QTextEdit(json.dumps(config, indent=2))
        self.config_input.setMaximumHeight(120)
        form.addRow("Config (JSON):", self.config_input)

        metrics = model.get("metrics", {})
        if isinstance(metrics, str):
            try: metrics = json.loads(metrics)
            except: metrics = {}
        self.metrics_input = QTextEdit(json.dumps(metrics, indent=2))
        self.metrics_input.setMaximumHeight(100)
        form.addRow("Metrics (JSON):", self.metrics_input)

        self.status_combo = QComboBox()
        self.status_combo.addItems(["idle", "training", "completed", "failed"])
        if model:
            idx = self.status_combo.findText(model.get("status", "idle"))
            if idx >= 0: self.status_combo.setCurrentIndex(idx)
        form.addRow("Status:", self.status_combo)

        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Model name required.")
            return
        try:
            config = json.loads(self.config_input.toPlainText())
        except json.JSONDecodeError:
            QMessageBox.warning(self, "Validation", "Invalid JSON in config.")
            return
        try:
            metrics = json.loads(self.metrics_input.toPlainText())
        except json.JSONDecodeError:
            metrics = {}

        data = {
            "name": name,
            "modelType": self.type_combo.currentText(),
            "config": json.dumps(config),
            "metrics": json.dumps(metrics),
            "status": self.status_combo.currentText(),
        }
        if self.model:
            update(RLModel, self.model["id"], **data)
        else:
            proj_id = self.store.projects[0]["id"] if self.store.projects else None
            if proj_id:
                create(RLModel, projectId=proj_id, **data)
            else:
                QMessageBox.warning(self, "Error", "No projects available.")
        self.accept()
