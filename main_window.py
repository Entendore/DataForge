"""DataForge – Main window with sidebar navigation and 11-view switching."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QStackedWidget, QLabel, QFrame, QScrollArea, QSizePolicy,
    QStatusBar, QGraphicsOpacityEffect,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor, QPalette, QIcon

from store import Store
from models import (
    BG_DARK, BG_SIDEBAR, BG_CARD, BG_HOVER, BG_INPUT, FG_PRIMARY, FG_SECONDARY,
    FG_MUTED, ACCENT, ACCENT2, BORDER, SUCCESS, WARNING, DANGER, INFO, RADIUS,
)

# View imports
from dashboard_projects import DashboardView, ProjectsView
from annotate_view import AnnotateView
from workflows_view import WorkflowsView
from management_views import TeamsView, QAReviewView, LabelsView, ActivityView
from training_tutorials import TutorialsView, RLTrainingView
from export_view import ExportCenterView


def apply_base_theme(app) -> None:
    app.setStyle("Fusion")
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(BG_DARK))
    p.setColor(QPalette.ColorRole.WindowText, QColor(FG_PRIMARY))
    p.setColor(QPalette.ColorRole.Base, QColor(BG_INPUT))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(BG_CARD))
    p.setColor(QPalette.ColorRole.Text, QColor(FG_PRIMARY))
    p.setColor(QPalette.ColorRole.Button, QColor(BG_CARD))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(FG_PRIMARY))
    p.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(BG_CARD))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor(FG_PRIMARY))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor(FG_MUTED))
    app.setPalette(p)
    app.setStyleSheet(f"""
        * {{ font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 13px; }}
        QMainWindow {{ background: {BG_DARK}; }}
        QFrame {{ border: none; }}
        QStatusBar {{ background: {BG_SIDEBAR}; color: {FG_SECONDARY}; font-size: 12px; padding: 2px 8px; }}
        QStatusBar QLabel {{ color: {FG_SECONDARY}; }}
        QToolTip {{ background: {BG_CARD}; color: {FG_PRIMARY}; border: 1px solid {BORDER}; padding: 6px 10px; border-radius: 6px; }}
        QScrollBar:vertical {{ background: {BG_DARK}; width: 8px; margin: 0; }}
        QScrollBar::handle:vertical {{ background: {BG_HOVER}; border-radius: 4px; min-height: 30px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        QScrollBar:horizontal {{ background: {BG_DARK}; height: 8px; }}
        QScrollBar::handle:horizontal {{ background: {BG_HOVER}; border-radius: 4px; min-width: 30px; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
        QTableWidget {{ background: {BG_DARK}; color: {FG_PRIMARY}; gridline-color: {BORDER}; border: 1px solid {BORDER}; border-radius: {RADIUS}px; selection-background-color: {ACCENT}; }}
        QTableWidget::item {{ padding: 8px 12px; }}
        QHeaderView::section {{ background: {BG_CARD}; color: {FG_SECONDARY}; padding: 10px 12px; border: none; border-right: 1px solid {BORDER}; border-bottom: 1px solid {BORDER}; font-weight: 600; font-size: 12px; }}
        QTabWidget::pane {{ border: none; background: transparent; }}
        QTabBar::tab {{ background: {BG_CARD}; color: {FG_SECONDARY}; padding: 8px 20px; margin-right: 2px; border-radius: 6px 6px 0 0; font-weight: 500; }}
        QTabBar::tab:selected {{ background: {ACCENT}; color: #fff; }}
        QTabBar::tab:hover:!selected {{ background: {BG_HOVER}; color: {FG_PRIMARY}; }}
        QListWidget {{ background: {BG_DARK}; color: {FG_PRIMARY}; border: 1px solid {BORDER}; border-radius: {RADIUS}px; padding: 4px; }}
        QListWidget::item {{ padding: 8px 12px; border-radius: 6px; margin: 2px; }}
        QListWidget::item:hover {{ background: {BG_HOVER}; }}
        QListWidget::item:selected {{ background: {ACCENT}; color: #fff; }}
        QLineEdit, QTextEdit, QComboBox, QSpinBox {{ background: {BG_INPUT}; color: {FG_PRIMARY}; border: 1px solid {BORDER}; border-radius: {RADIUS}px; padding: 8px 12px; selection-background-color: {ACCENT}; }}
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
        QComboBox::drop-down {{ border: none; width: 30px; }}
        QComboBox QAbstractItemView {{ background: {BG_CARD}; color: {FG_PRIMARY}; border: 1px solid {BORDER}; selection-background-color: {ACCENT}; }}
        QPushButton {{ background: {BG_CARD}; color: {FG_PRIMARY}; border: 1px solid {BORDER}; border-radius: {RADIUS}px; padding: 8px 16px; font-weight: 500; }}
        QPushButton:hover {{ background: {BG_HOVER}; }}
        QPushButton:pressed {{ background: {ACCENT}; }}
        QMenu {{ background: {BG_CARD}; color: {FG_PRIMARY}; border: 1px solid {BORDER}; border-radius: {RADIUS}px; padding: 4px; }}
        QMenu::item {{ padding: 8px 16px; border-radius: 4px; }}
        QMenu::item:selected {{ background: {ACCENT}; }}
        QProgressBar {{ background: {BG_INPUT}; border-radius: 4px; text-align: center; color: {FG_PRIMARY}; font-size: 12px; height: 20px; border: 1px solid {BORDER}; }}
        QProgressBar::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {ACCENT},stop:1 {ACCENT2}); border-radius: 4px; }}
        QSlider::groove:horizontal {{ background: {BG_INPUT}; height: 6px; border-radius: 3px; }}
        QSlider::handle:horizontal {{ background: {ACCENT}; width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; }}
        QGroupBox {{ background: {BG_CARD}; color: {FG_PRIMARY}; border: 1px solid {BORDER}; border-radius: {RADIUS}px; margin-top: 12px; padding: 16px; padding-top: 28px; font-weight: 600; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; }}
        QCheckBox {{ color: {FG_PRIMARY}; spacing: 8px; }}
        QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px; border: 2px solid {BORDER}; background: {BG_INPUT}; }}
        QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
        QSplitter::handle {{ background: {BORDER}; }}
        QToolButton {{ background: transparent; color: {FG_SECONDARY}; border: none; border-radius: 6px; padding: 8px; }}
        QToolButton:hover {{ background: {BG_HOVER}; color: {FG_PRIMARY}; }}
    """)


# ---------------------------------------------------------------------------
# Sidebar nav items
# ---------------------------------------------------------------------------
NAV_ITEMS = [
    ("workspace", "WORKSPACE", None),
    ("dashboard", "Dashboard", "📊"),
    ("projects", "Projects", "📁"),
    ("annotate", "Annotate", "🏷️"),
    ("workflows", "Workflows", "🔀"),
    ("tutorials", "Tutorials", "📖"),
    ("rl_training", "RL Training", "🤖"),
    ("mgmt", "MANAGEMENT", None),
    ("teams", "Teams", "👥"),
    ("qa_review", "QA Review", "✅"),
    ("labels", "Labels", "🏷"),
    ("export", "Export", "📦"),
    ("activity", "Activity", "📋"),
]

VIEW_INDEX = {name: i for i, (name, *_) in enumerate(NAV_ITEMS) if name not in ("workspace", "mgmt")}


class NavButton(QPushButton):
    """A sidebar navigation button."""
    def __init__(self, key: str, label: str, icon: str | None = None, is_header: bool = False):
        super().__init__()
        self.key = key
        self.is_header = is_header
        if is_header:
            self.setText(f"  {label}")
            self.setFixedHeight(32)
            self.setStyleSheet(f"""
                QPushButton {{ background: transparent; color: {FG_MUTED}; border: none;
                    font-size: 11px; font-weight: 700; letter-spacing: 1px; text-align: left; padding-left: 20px; }}
            """)
            self.setEnabled(False)
        else:
            icon_str = icon or "●"
            self.setText(f"  {icon_str}  {label}")
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setFixedHeight(40)
            self._set_normal()

    def _set_normal(self):
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {FG_SECONDARY}; border: none; border-radius: 0;
                font-size: 13px; text-align: left; padding-left: 16px; border-left: 3px solid transparent;
            }}
            QPushButton:hover {{ background: {BG_HOVER}; color: {FG_PRIMARY}; }}
        """)

    def set_active(self):
        self.setStyleSheet(f"""
            QPushButton {{
                background: {BG_HOVER}; color: #fff; border: none; border-radius: 0;
                font-size: 13px; text-align: left; padding-left: 16px;
                border-left: 3px solid {ACCENT};
            }}
        """)

    def set_inactive(self):
        self._set_normal()


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DataForge – AI Training Data Platform")
        self.setMinimumSize(1280, 800)
        self.resize(1500, 900)

        # State
        self.store = Store()
        self.store.reload_all()

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- Sidebar ----
        sidebar_frame = QFrame()
        sidebar_frame.setFixedWidth(240)
        sidebar_frame.setStyleSheet(f"QFrame {{ background: {BG_SIDEBAR}; border-right: 1px solid {BORDER}; }}")
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # Logo
        logo = QLabel("  🔥 DataForge")
        logo.setFixedHeight(56)
        logo.setStyleSheet(f"""
            QLabel {{ background: transparent; color: #fff; font-size: 20px; font-weight: 800;
            padding-left: 16px; border-bottom: 1px solid {BORDER}; letter-spacing: -0.5px; }}
        """)
        sidebar_layout.addWidget(logo)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: transparent; }}")
        scroll_w = QWidget()
        scroll_lay = QVBoxLayout(scroll_w)
        scroll_lay.setContentsMargins(0, 8, 0, 8)
        scroll_lay.setSpacing(2)

        self.nav_buttons: dict[str, NavButton] = {}
        for key, label, icon in NAV_ITEMS:
            is_header = icon is None
            btn = NavButton(key, label, icon, is_header)
            if not is_header:
                btn.clicked.connect(lambda checked=False, k=key: self._switch_view(k))
                self.nav_buttons[key] = btn
            scroll_lay.addWidget(btn)

        scroll_lay.addStretch()
        scroll.setWidget(scroll_w)
        sidebar_layout.addWidget(scroll)
        root.addWidget(sidebar_frame)

        # ---- Content area ----
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"QStackedWidget {{ background: {BG_DARK}; }}")

        # Instantiate all views
        self.views: dict[str, QWidget] = {}
        self.views["dashboard"] = DashboardView(self.store)
        self.views["projects"] = ProjectsView(self.store)
        self.views["annotate"] = AnnotateView(self.store)
        self.views["workflows"] = WorkflowsView(self.store)
        self.views["tutorials"] = TutorialsView(self.store)
        self.views["rl_training"] = RLTrainingView(self.store)
        self.views["teams"] = TeamsView(self.store)
        self.views["qa_review"] = QAReviewView(self.store)
        self.views["labels"] = LabelsView(self.store)
        self.views["export"] = ExportCenterView(self.store)
        self.views["activity"] = ActivityView(self.store)

        for key in VIEW_INDEX:
            self.stack.addWidget(self.views[key])

        root.addWidget(self.stack, 1)

        # ---- Status bar ----
        self.statusBar().showMessage("Ready")
        self._update_status_bar()

        # Connect store signal for auto-refresh
        self.store.data_changed.connect(self._on_data_changed)

        # Start on Dashboard
        self._switch_view("dashboard")

    # ---- Navigation ----
    def _switch_view(self, key: str) -> None:
        idx = VIEW_INDEX.get(key, 0)
        self.stack.setCurrentIndex(idx)
        self.store.active_tab = idx

        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.set_active()
            elif not btn.is_header:
                btn.set_inactive()

        # Refresh the view when switching to it
        view = self.views.get(key)
        if hasattr(view, 'refresh'):
            view.refresh()

        # Update status
        labels_map = {
            "dashboard": "📊 Dashboard", "projects": "📁 Projects",
            "annotate": "🏷️ Annotate", "workflows": "🔀 Workflows",
            "tutorials": "📖 Tutorials", "rl_training": "🤖 RL Training",
            "teams": "👥 Teams", "qa_review": "✅ QA Review",
            "labels": "🏷 Labels", "export": "📦 Export", "activity": "📋 Activity",
        }
        self.statusBar().showMessage(f"  {labels_map.get(key, key)}")

    def _on_data_changed(self, entity: str) -> None:
        if entity == "all":
            for view in self.views.values():
                if hasattr(view, 'refresh'):
                    view.refresh()
            self._update_status_bar()
        else:
            current_key = [k for k, i in VIEW_INDEX.items() if i == self.store.active_tab]
            if current_key:
                view = self.views.get(current_key[0])
                if view and hasattr(view, 'refresh'):
                    view.refresh()
            self._update_status_bar()

    def _update_status_bar(self) -> None:
        n_proj = len(self.store.projects)
        n_ann = len(self.store.annotations)
        n_wf = len(self.store.workflows)
        self.statusBar().showMessage(
            f"  📁 {n_proj} Projects  |  🏷️ {n_ann} Annotations  |  🔀 {n_wf} Workflows  |  🔥 DataForge v1.0"
        )
