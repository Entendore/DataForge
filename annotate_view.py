"""DataForge – Annotation view with 4 sub-tabs: Annotate, Batch, Templates, History."""

from __future__ import annotations

import json
import copy
import random
import datetime as dt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QScrollArea, QLineEdit, QComboBox, QTextEdit, QTabWidget,
    QCheckBox, QSlider, QListWidget, QListWidgetItem, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QGridLayout,
    QSizePolicy, QToolButton, QSplitter, QMessageBox, QFileDialog,
)
from PySide6.QtCore import Qt, QTimer, Signal, QSize
from PySide6.QtGui import QFont, QKeyEvent, QKeySequence, QShortcut, QColor

from models import Annotation, update, create, delete, bulk_json
from store import Store

from models import (
    BG_DARK, BG_CARD, BG_HOVER, BG_INPUT, FG_PRIMARY, FG_SECONDARY,
    FG_MUTED, ACCENT, ACCENT2, BORDER, SUCCESS, WARNING, DANGER, INFO, RADIUS,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
STATUS_COLORS = {
    "pending": WARNING,
    "approved": SUCCESS,
    "rejected": DANGER,
    "in_review": INFO,
}

ANNOTATION_TOOLS = [
    ("Label", "1", "🏷"),
    ("Span", "2", "📐"),
    ("BBox", "3", "⬜"),
    ("Classify", "4", "📂"),
    ("NER", "5", "👤"),
    ("Segment", "6", "✂"),
]


# ---------------------------------------------------------------------------
# Helper: make a styled card frame
# ---------------------------------------------------------------------------
def make_card_frame() -> QFrame:
    frame = QFrame()
    frame.setStyleSheet(f"""
        QFrame {{
            background: {BG_CARD};
            border: 1px solid {BORDER};
            border-radius: {RADIUS}px;
        }}
    """)
    return frame


def make_section_label(text: str, color: str = FG_PRIMARY, size: int = 14) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {color}; font-size: {size}px; font-weight: 700;")
    return lbl


def make_toggled_tool_btn(name: str, shortcut: str, icon: str, active_color: str = ACCENT) -> QPushButton:
    btn = QPushButton(f"  {icon}  {name} ({shortcut})")
    btn.setCheckable(True)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            background: {BG_INPUT};
            color: {FG_SECONDARY};
            border: 1px solid {BORDER};
            border-radius: {RADIUS}px;
            padding: 6px 14px;
            font-weight: 500;
            font-size: 12px;
        }}
        QPushButton:hover {{
            background: {BG_HOVER};
            color: {FG_PRIMARY};
        }}
        QPushButton:checked {{
            background: {active_color};
            color: #fff;
            border-color: {active_color};
        }}
    """)
    return btn


def make_action_btn(text: str, color: str = ACCENT, icon: str = "") -> QPushButton:
    btn = QPushButton(f"{'  ' + icon if icon else ''}  {text}")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            background: {color};
            color: #fff;
            border: none;
            border-radius: {RADIUS}px;
            padding: 8px 16px;
            font-weight: 600;
            font-size: 12px;
        }}
        QPushButton:hover {{ opacity: 0.85; }}
        QPushButton:pressed {{ background: {color}cc; }}
    """)
    return btn


def make_secondary_btn(text: str, icon: str = "") -> QPushButton:
    btn = QPushButton(f"{'  ' + icon if icon else ''}  {text}")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            background: {BG_INPUT};
            color: {FG_SECONDARY};
            border: 1px solid {BORDER};
            border-radius: {RADIUS}px;
            padding: 6px 14px;
            font-weight: 500;
            font-size: 12px;
        }}
        QPushButton:hover {{
            background: {BG_HOVER};
            color: {FG_PRIMARY};
        }}
    """)
    return btn


# ---------------------------------------------------------------------------
# AnnotateView
# ---------------------------------------------------------------------------
class AnnotateView(QWidget):
    """Full annotation workspace with Annotate, Batch, Templates, and History sub-tabs."""

    def __init__(self, store: Store):
        super().__init__()
        self.store = store

        # ---- Internal state ----
        self._current_project_id: str | None = None
        self._current_annotation_id: str | None = None
        self._data_items: list[dict] = []          # flattened from datasets
        self._annotations_map: dict[int, dict] = {} # dataIndex -> annotation
        self._selected_tool: int = 0
        self._annotator_name: str = ""
        self._auto_save_enabled: bool = False
        self._grid_view: bool = False
        self._filter_status: str = "all"
        self._search_text: str = ""
        self._elapsed_seconds: int = 0
        self._annotation_open_time: dt.datetime | None = None

        # Undo / Redo history
        self._history_stack: list[dict] = []
        self._history_index: int = -1
        self._history_max: int = 100

        # Templates (in-memory)
        self._templates: list[dict] = []

        # Build UI
        self._build_ui()

        # Timers
        self._timer_clock = QTimer(self)
        self._timer_clock.timeout.connect(self._tick_annotation_timer)
        self._timer_clock.setInterval(1000)

        self._timer_autosave = QTimer(self)
        self._timer_autosave.timeout.connect(self._auto_save)
        self._timer_autosave.setInterval(30000)

    # -----------------------------------------------------------------------
    # UI Construction
    # -----------------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # ---- Top header ----
        header = QHBoxLayout()
        self._title = QLabel("Annotate")
        self._title.setStyleSheet(f"color: {FG_PRIMARY}; font-size: 24px; font-weight: 800;")
        header.addWidget(self._title)
        header.addStretch()

        # Project selector
        self._project_combo = QComboBox()
        self._project_combo.setPlaceholderText("Select a project…")
        self._project_combo.setFixedWidth(260)
        self._project_combo.setStyleSheet(f"""
            QComboBox {{
                background: {BG_INPUT}; color: {FG_PRIMARY};
                border: 1px solid {BORDER}; border-radius: {RADIUS}px;
                padding: 8px 12px; font-weight: 500;
            }}
            QComboBox::drop-down {{ border: none; width: 30px; }}
            QComboBox QAbstractItemView {{
                background: {BG_CARD}; color: {FG_PRIMARY};
                border: 1px solid {BORDER}; selection-background-color: {ACCENT};
            }}
        """)
        self._project_combo.currentIndexChanged.connect(self._on_project_changed)
        header.addWidget(self._project_combo)
        root.addLayout(header)

        # ---- No-project placeholder ----
        self._placeholder = QFrame()
        self._placeholder.setStyleSheet(f"""
            QFrame {{
                background: {BG_CARD}; border: 1px solid {BORDER};
                border-radius: {RADIUS}px;
            }}
        """)
        ph_layout = QVBoxLayout(self._placeholder)
        ph_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_icon = QLabel("🏷️")
        ph_icon.setStyleSheet("font-size: 48px; background: transparent; border: none;")
        ph_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_layout.addWidget(ph_icon)
        ph_text = QLabel("Select a project from the dropdown above to start annotating.")
        ph_text.setStyleSheet(f"color: {FG_MUTED}; font-size: 15px; background: transparent; border: none;")
        ph_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_layout.addWidget(ph_text)
        root.addWidget(self._placeholder)

        # ---- Main tabs ----
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background: transparent;
            }}
            QTabBar::tab {{
                background: {BG_CARD};
                color: {FG_SECONDARY};
                padding: 10px 24px;
                margin-right: 2px;
                border-radius: {RADIUS}px {RADIUS}px 0 0;
                font-weight: 600;
                font-size: 13px;
            }}
            QTabBar::tab:selected {{
                background: {ACCENT};
                color: #fff;
            }}
            QTabBar::tab:hover:!selected {{
                background: {BG_HOVER};
                color: {FG_PRIMARY};
            }}
        """)

        self._annotate_tab = QWidget()
        self._batch_tab = QWidget()
        self._templates_tab = QWidget()
        self._history_tab = QWidget()

        self._build_annotate_tab()
        self._build_batch_tab()
        self._build_templates_tab()
        self._build_history_tab()

        self._tabs.addTab(self._annotate_tab, "  ✏️  Annotate  ")
        self._tabs.addTab(self._batch_tab, "  📦  Batch  ")
        self._tabs.addTab(self._templates_tab, "  📋  Templates  ")
        self._tabs.addTab(self._history_tab, "  🕰  History  ")

        self._tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self._tabs)

        # Initially hide tabs, show placeholder
        self._tabs.hide()
        self._placeholder.show()

    # -----------------------------------------------------------------------
    # Annotate Tab
    # -----------------------------------------------------------------------
    def _build_annotate_tab(self):
        outer = QVBoxLayout(self._annotate_tab)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---- Toolbar ----
        toolbar_frame = QFrame()
        toolbar_frame.setStyleSheet(f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS}px; }}")
        toolbar = QHBoxLayout(toolbar_frame)
        toolbar.setContentsMargins(12, 8, 12, 8)
        toolbar.setSpacing(6)

        toolbar.addWidget(make_section_label("Tools:", FG_SECONDARY, 12))

        self._tool_buttons: list[QPushButton] = []
        for i, (name, shortcut, icon) in enumerate(ANNOTATION_TOOLS):
            btn = make_toggled_tool_btn(name, shortcut, icon)
            btn.setChecked(i == 0)
            btn.clicked.connect(lambda checked=False, idx=i: self._select_tool(idx))
            self._tool_buttons.append(btn)
            toolbar.addWidget(btn)

        toolbar.addStretch()

        # Bookmark toggle
        self._bookmark_btn = make_secondary_btn("☆ Bookmark", "🔖")
        self._bookmark_btn.clicked.connect(self._toggle_bookmark)
        toolbar.addWidget(self._bookmark_btn)

        # Auto-save checkbox
        self._autosave_cb = QCheckBox("Auto-save (30s)")
        self._autosave_cb.setStyleSheet(f"QCheckBox {{ color: {FG_SECONDARY}; font-size: 12px; spacing: 6px; }} QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 2px solid {BORDER}; background: {BG_INPUT}; }} QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}")
        self._autosave_cb.toggled.connect(self._toggle_auto_save)
        toolbar.addWidget(self._autosave_cb)

        # Annotation timer
        self._timer_label = QLabel("⏱ 00:00")
        self._timer_label.setStyleSheet(f"color: {FG_MUTED}; font-size: 12px; font-weight: 600; background: transparent; border: none;")
        toolbar.addWidget(self._timer_label)

        # Undo / Redo buttons
        self._undo_btn = make_secondary_btn("↩ Undo", "")
        self._undo_btn.clicked.connect(self._undo)
        toolbar.addWidget(self._undo_btn)

        self._redo_btn = make_secondary_btn("↪ Redo", "")
        self._redo_btn.clicked.connect(self._redo)
        toolbar.addWidget(self._redo_btn)

        # Export JSON button
        self._export_btn = make_action_btn("Export JSON", INFO, "📥")
        self._export_btn.clicked.connect(self._export_annotations)
        toolbar.addWidget(self._export_btn)

        outer.addWidget(toolbar_frame)

        # ---- Main content split ----
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {BORDER}; width: 2px; }}")

        # Left panel: Data navigator + data display + label assignment
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 12, 8, 0)
        left_layout.setSpacing(12)

        # Data navigator bar: search + filter + view toggle
        nav_bar = QHBoxLayout()
        nav_bar.setSpacing(8)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search data items…")
        self._search_input.setFixedWidth(200)
        self._search_input.textChanged.connect(self._on_search_changed)
        nav_bar.addWidget(self._search_input)

        self._filter_combo = QComboBox()
        self._filter_combo.addItems(["All", "Pending", "Approved", "Rejected", "In Review"])
        self._filter_combo.setFixedWidth(130)
        self._filter_combo.currentTextChanged.connect(self._on_filter_changed)
        nav_bar.addWidget(self._filter_combo)

        nav_bar.addStretch()

        self._view_grid_btn = make_secondary_btn("⊞ Grid", "")
        self._view_grid_btn.clicked.connect(lambda: self._set_view_mode(True))
        nav_bar.addWidget(self._view_grid_btn)

        self._view_list_btn = make_secondary_btn("☰ List", "")
        self._view_list_btn.clicked.connect(lambda: self._set_view_mode(False))
        self._view_list_btn.setStyleSheet(self._view_list_btn.styleSheet().replace(f"background: {BG_INPUT};", f"background: {ACCENT}; color: #fff; border-color: {ACCENT};"))
        nav_bar.addWidget(self._view_list_btn)

        left_layout.addLayout(nav_bar)

        # Data navigator (mini-list of data items with status dots)
        nav_frame = make_card_frame()
        nav_lay = QVBoxLayout(nav_frame)
        nav_lay.setContentsMargins(8, 8, 8, 8)
        nav_lay.setSpacing(0)

        nav_header = QHBoxLayout()
        nav_header.addWidget(make_section_label("Data Navigator", FG_SECONDARY, 12))
        self._nav_count_label = QLabel("0 items")
        self._nav_count_label.setStyleSheet(f"color: {FG_MUTED}; font-size: 11px; background: transparent; border: none;")
        nav_header.addStretch()
        nav_header.addWidget(self._nav_count_label)
        nav_lay.addLayout(nav_header)

        self._nav_list = QListWidget()
        self._nav_list.setFixedHeight(180)
        self._nav_list.setStyleSheet(f"""
            QListWidget {{
                background: {BG_DARK};
                color: {FG_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: {RADIUS - 2}px;
                padding: 2px;
                font-size: 12px;
            }}
            QListWidget::item {{
                padding: 4px 8px;
                border-radius: 4px;
                margin: 1px;
            }}
            QListWidget::item:hover {{
                background: {BG_HOVER};
            }}
            QListWidget::item:selected {{
                background: {ACCENT};
                color: #fff;
            }}
        """)
        self._nav_list.currentRowChanged.connect(self._on_nav_selection_changed)
        nav_lay.addWidget(self._nav_list)
        left_layout.addWidget(nav_frame)

        # Data display area
        data_frame = make_card_frame()
        data_lay = QVBoxLayout(data_frame)
        data_lay.setContentsMargins(16, 12, 16, 12)
        data_lay.addWidget(make_section_label("Data Preview", FG_SECONDARY, 13))

        self._data_preview = QTextEdit()
        self._data_preview.setReadOnly(True)
        self._data_preview.setMaximumHeight(200)
        self._data_preview.setStyleSheet(f"""
            QTextEdit {{
                background: {BG_DARK};
                color: {FG_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: {RADIUS - 2}px;
                padding: 12px;
                font-size: 13px;
                font-family: 'Cascadia Code', 'Fira Code', monospace;
            }}
        """)
        self._data_preview.setPlaceholderText("Select a data item to preview…")
        data_lay.addWidget(self._data_preview)
        left_layout.addWidget(data_frame)

        # Label assignment area
        labels_frame = make_card_frame()
        labels_lay = QVBoxLayout(labels_frame)
        labels_lay.setContentsMargins(16, 12, 16, 12)
        labels_lay.addWidget(make_section_label("Label Assignment", FG_SECONDARY, 13))

        self._labels_container = QWidget()
        self._labels_grid = QGridLayout(self._labels_container)
        self._labels_grid.setSpacing(8)
        self._labels_grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._label_checkboxes: list[tuple[QCheckBox, str]] = []
        labels_lay.addWidget(self._labels_container)

        # Confidence slider
        conf_row = QHBoxLayout()
        conf_row.addWidget(QLabel("Confidence:"))
        conf_lbl_style = f"color: {FG_SECONDARY}; font-size: 12px; background: transparent; border: none;"
        conf_row.itemAt(0).widget().setStyleSheet(conf_lbl_style)

        self._confidence_slider = QSlider(Qt.Orientation.Horizontal)
        self._confidence_slider.setRange(0, 100)
        self._confidence_slider.setValue(100)
        self._confidence_slider.setFixedWidth(200)
        self._confidence_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {BG_INPUT};
                height: 6px;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {ACCENT};
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }}
        """)
        self._confidence_slider.valueChanged.connect(self._on_confidence_changed)
        conf_row.addWidget(self._confidence_slider)

        self._confidence_label = QLabel("1.00")
        self._confidence_label.setFixedWidth(40)
        self._confidence_label.setStyleSheet(f"color: {ACCENT}; font-size: 12px; font-weight: 700; background: transparent; border: none;")
        conf_row.addWidget(self._confidence_label)
        conf_row.addStretch()
        labels_lay.addLayout(conf_row)

        left_layout.addWidget(labels_frame, 1)

        # Annotator + Notes
        meta_frame = make_card_frame()
        meta_lay = QVBoxLayout(meta_frame)
        meta_lay.setContentsMargins(16, 12, 16, 12)
        meta_lay.setSpacing(10)

        annotator_row = QHBoxLayout()
        annotator_row.addWidget(QLabel("Annotator:"))
        annotator_row.itemAt(0).widget().setStyleSheet(f"color: {FG_SECONDARY}; font-size: 12px; background: transparent; border: none;")
        self._annotator_input = QLineEdit()
        self._annotator_input.setPlaceholderText("Your name…")
        self._annotator_input.setFixedWidth(200)
        self._annotator_input.textChanged.connect(self._on_annotator_changed)
        annotator_row.addWidget(self._annotator_input)
        annotator_row.addStretch()
        meta_lay.addLayout(annotator_row)

        meta_lay.addWidget(QLabel("Notes:"))
        meta_lay.itemAt(meta_lay.count() - 1).widget().setStyleSheet(f"color: {FG_SECONDARY}; font-size: 12px; background: transparent; border: none;")
        self._notes_input = QTextEdit()
        self._notes_input.setPlaceholderText("Add notes for this annotation…")
        self._notes_input.setMaximumHeight(80)
        self._notes_input.textChanged.connect(self._on_notes_changed)
        meta_lay.addWidget(self._notes_input)

        # Save button
        save_btn = make_action_btn("💾  Save Annotation", SUCCESS)
        save_btn.clicked.connect(self._save_current_annotation)
        meta_lay.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignRight)

        left_layout.addWidget(meta_frame)
        splitter.addWidget(left_panel)

        # Right panel: AI Assist
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 12, 0, 0)
        right_layout.setSpacing(12)

        # AI Assist card
        ai_frame = make_card_frame()
        ai_lay = QVBoxLayout(ai_frame)
        ai_lay.setContentsMargins(16, 12, 16, 12)
        ai_lay.setSpacing(12)

        ai_header = QHBoxLayout()
        ai_header.addWidget(make_section_label("🤖  AI Assist", ACCENT2, 14))
        ai_header.addStretch()
        ai_lay.addLayout(ai_header)

        # Suggested labels
        ai_lay.addWidget(QLabel("Suggested Labels:"))
        ai_lay.itemAt(ai_lay.count() - 1).widget().setStyleSheet(f"color: {FG_MUTED}; font-size: 12px; font-weight: 600; background: transparent; border: none;")

        self._suggested_container = QWidget()
        self._suggested_layout = QVBoxLayout(self._suggested_container)
        self._suggested_layout.setSpacing(4)
        ai_lay.addWidget(self._suggested_container)

        ai_lay.addWidget(self._make_separator())

        # Quick labels
        ai_lay.addWidget(QLabel("Quick Labels:"))
        ai_lay.itemAt(ai_lay.count() - 1).widget().setStyleSheet(f"color: {FG_MUTED}; font-size: 12px; font-weight: 600; background: transparent; border: none;")

        self._quick_labels_container = QWidget()
        self._quick_labels_layout = QGridLayout(self._quick_labels_container)
        self._quick_labels_layout.setSpacing(6)
        self._quick_labels_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        ai_lay.addWidget(self._quick_labels_container)

        ai_lay.addWidget(self._make_separator())

        # Label frequency
        ai_lay.addWidget(QLabel("Label Frequency:"))
        ai_lay.itemAt(ai_lay.count() - 1).widget().setStyleSheet(f"color: {FG_MUTED}; font-size: 12px; font-weight: 600; background: transparent; border: none;")

        self._frequency_container = QWidget()
        self._frequency_layout = QVBoxLayout(self._frequency_container)
        self._frequency_layout.setSpacing(6)
        ai_lay.addWidget(self._frequency_container)

        ai_lay.addStretch()
        right_layout.addWidget(ai_frame)

        # Shortcuts help card
        shortcuts_frame = make_card_frame()
        shortcuts_lay = QVBoxLayout(shortcuts_frame)
        shortcuts_lay.setContentsMargins(16, 12, 16, 12)
        shortcuts_lay.setSpacing(6)
        shortcuts_lay.addWidget(make_section_label("⌨  Shortcuts", FG_MUTED, 12))

        shortcuts = [
            ("←/→", "Navigate items"),
            ("1–6", "Switch tools"),
            ("Ctrl+Z", "Undo"),
            ("Ctrl+Shift+Z", "Redo"),
            ("Ctrl+S", "Save"),
            ("B", "Bookmark"),
            ("/", "Toggle help"),
            ("Esc", "Deselect"),
        ]
        for key, desc in shortcuts:
            row = QHBoxLayout()
            k_lbl = QLabel(f"  {key}")
            k_lbl.setFixedWidth(90)
            k_lbl.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: 600; background: transparent; border: none;")
            row.addWidget(k_lbl)
            d_lbl = QLabel(desc)
            d_lbl.setStyleSheet(f"color: {FG_MUTED}; font-size: 11px; background: transparent; border: none;")
            row.addWidget(d_lbl)
            shortcuts_lay.addLayout(row)

        right_layout.addWidget(shortcuts_frame)
        right_layout.addStretch()

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        outer.addWidget(splitter, 1)

    def _make_separator(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"QFrame {{ background: {BORDER}; border: none; max-height: 1px; }}")
        return sep

    # -----------------------------------------------------------------------
    # Batch Tab
    # -----------------------------------------------------------------------
    def _build_batch_tab(self):
        layout = QVBoxLayout(self._batch_tab)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        header.addWidget(make_section_label("Batch Operations", FG_PRIMARY, 16))
        header.addStretch()

        self._selection_count_label = QLabel("Selected: 0")
        self._selection_count_label.setStyleSheet(f"color: {FG_MUTED}; font-size: 12px; background: transparent; border: none;")
        header.addWidget(self._selection_count_label)
        layout.addLayout(header)

        # Action bar
        action_bar = QHBoxLayout()
        action_bar.setSpacing(10)

        self._select_all_cb = QCheckBox("Select All")
        self._select_all_cb.setStyleSheet(f"QCheckBox {{ color: {FG_SECONDARY}; font-size: 12px; spacing: 6px; }} QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 2px solid {BORDER}; background: {BG_INPUT}; }} QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}")
        self._select_all_cb.toggled.connect(self._batch_select_all)
        action_bar.addWidget(self._select_all_cb)

        _lbl1 = QLabel("Set Status:")
        _lbl1.setStyleSheet(f"color: {FG_SECONDARY}; font-size: 12px; background: transparent; border: none;")
        action_bar.addWidget(_lbl1)
        self._batch_status_combo = QComboBox()
        self._batch_status_combo.addItems(["pending", "approved", "rejected", "in_review"])
        self._batch_status_combo.setFixedWidth(130)
        action_bar.addWidget(self._batch_status_combo)

        apply_status_btn = make_action_btn("Apply Status", ACCENT)
        apply_status_btn.clicked.connect(self._batch_apply_status)
        action_bar.addWidget(apply_status_btn)

        _lbl2 = QLabel("Add Labels:")
        _lbl2.setStyleSheet(f"color: {FG_SECONDARY}; font-size: 12px; background: transparent; border: none;")
        action_bar.addWidget(_lbl2)
        self._batch_label_input = QLineEdit()
        self._batch_label_input.setPlaceholderText("label1, label2…")
        self._batch_label_input.setFixedWidth(180)
        action_bar.addWidget(self._batch_label_input)

        apply_labels_btn = make_action_btn("Apply Labels", ACCENT2)
        apply_labels_btn.clicked.connect(self._batch_apply_labels)
        action_bar.addWidget(apply_labels_btn)

        action_bar.addStretch()

        delete_btn = make_action_btn("🗑  Delete Selected", DANGER)
        delete_btn.clicked.connect(self._batch_delete_selected)
        action_bar.addWidget(delete_btn)

        layout.addLayout(action_bar)

        # Table
        table_frame = make_card_frame()
        table_lay = QVBoxLayout(table_frame)
        table_lay.setContentsMargins(8, 8, 8, 8)

        self._batch_table = QTableWidget()
        self._batch_table.setColumnCount(5)
        self._batch_table.setHorizontalHeaderLabels(["Select", "ID", "Labels", "Status", "Annotator"])
        self._batch_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._batch_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._batch_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._batch_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._batch_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._batch_table.setColumnWidth(0, 50)
        self._batch_table.setColumnWidth(3, 100)
        self._batch_table.setColumnWidth(4, 120)
        self._batch_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._batch_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._batch_table.setStyleSheet(f"""
            QTableWidget {{
                background: {BG_DARK};
                color: {FG_PRIMARY};
                gridline-color: {BORDER};
                border: 1px solid {BORDER};
                border-radius: {RADIUS - 2}px;
                selection-background-color: {ACCENT};
            }}
            QTableWidget::item {{
                padding: 6px 10px;
            }}
            QHeaderView::section {{
                background: {BG_CARD};
                color: {FG_SECONDARY};
                padding: 8px 10px;
                border: none;
                border-right: 1px solid {BORDER};
                border-bottom: 1px solid {BORDER};
                font-weight: 600;
                font-size: 12px;
            }}
        """)
        table_lay.addWidget(self._batch_table)
        layout.addWidget(table_frame, 1)

    # -----------------------------------------------------------------------
    # Templates Tab
    # -----------------------------------------------------------------------
    def _build_templates_tab(self):
        layout = QVBoxLayout(self._templates_tab)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(make_section_label("Annotation Templates", FG_PRIMARY, 16))

        # Save template section
        save_frame = make_card_frame()
        save_lay = QHBoxLayout(save_frame)
        save_lay.setContentsMargins(16, 12, 16, 12)
        save_lay.setSpacing(12)

        save_lay.addWidget(QLabel("Template Name:"))
        save_lay.itemAt(0).widget().setStyleSheet(f"color: {FG_SECONDARY}; font-size: 13px; background: transparent; border: none;")

        self._template_name_input = QLineEdit()
        self._template_name_input.setPlaceholderText("Enter template name…")
        self._template_name_input.setFixedWidth(300)
        save_lay.addWidget(self._template_name_input)

        save_btn = make_action_btn("💾  Save Current as Template", ACCENT)
        save_btn.clicked.connect(self._save_template)
        save_lay.addWidget(save_btn)
        save_lay.addStretch()

        layout.addWidget(save_frame)

        # Templates list
        list_frame = make_card_frame()
        list_lay = QVBoxLayout(list_frame)
        list_lay.setContentsMargins(16, 12, 16, 12)
        list_lay.setSpacing(8)

        list_lay.addWidget(make_section_label("Saved Templates", FG_SECONDARY, 13))

        self._templates_list = QListWidget()
        self._templates_list.setStyleSheet(f"""
            QListWidget {{
                background: {BG_DARK};
                color: {FG_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: {RADIUS - 2}px;
                padding: 4px;
                font-size: 13px;
            }}
            QListWidget::item {{
                padding: 10px 12px;
                border-radius: 6px;
                margin: 2px;
            }}
            QListWidget::item:hover {{
                background: {BG_HOVER};
            }}
            QListWidget::item:selected {{
                background: {ACCENT};
                color: #fff;
            }}
        """)
        list_lay.addWidget(self._templates_list, 1)

        btns_row = QHBoxLayout()
        apply_btn = make_action_btn("✅  Apply Template", SUCCESS)
        apply_btn.clicked.connect(self._apply_template)
        btns_row.addWidget(apply_btn)

        delete_btn = make_action_btn("🗑  Delete Template", DANGER)
        delete_btn.clicked.connect(self._delete_template)
        btns_row.addWidget(delete_btn)
        btns_row.addStretch()
        list_lay.addLayout(btns_row)

        layout.addWidget(list_frame, 1)

    # -----------------------------------------------------------------------
    # History Tab
    # -----------------------------------------------------------------------
    def _build_history_tab(self):
        layout = QVBoxLayout(self._history_tab)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.addWidget(make_section_label("Undo / Redo History", FG_PRIMARY, 16))
        header.addStretch()

        self._history_info_label = QLabel("Index: -1 / 0 entries")
        self._history_info_label.setStyleSheet(f"color: {FG_MUTED}; font-size: 12px; background: transparent; border: none;")
        header.addWidget(self._history_info_label)

        clear_btn = make_action_btn("🗑  Clear History", DANGER)
        clear_btn.clicked.connect(self._clear_history)
        header.addWidget(clear_btn)
        layout.addLayout(header)

        # History list
        hist_frame = make_card_frame()
        hist_lay = QVBoxLayout(hist_frame)
        hist_lay.setContentsMargins(12, 12, 12, 12)

        self._history_list = QListWidget()
        self._history_list.setStyleSheet(f"""
            QListWidget {{
                background: {BG_DARK};
                color: {FG_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: {RADIUS - 2}px;
                padding: 4px;
                font-size: 13px;
            }}
            QListWidget::item {{
                padding: 10px 12px;
                border-radius: 6px;
                margin: 2px;
            }}
            QListWidget::item:hover {{
                background: {BG_HOVER};
            }}
            QListWidget::item:selected {{
                background: {ACCENT};
                color: #fff;
            }}
        """)
        self._history_list.currentRowChanged.connect(self._on_history_entry_clicked)
        hist_lay.addWidget(self._history_list, 1)
        layout.addWidget(hist_frame, 1)

    # -----------------------------------------------------------------------
    # Project selection & data loading
    # -----------------------------------------------------------------------
    def _on_project_changed(self, index: int):
        pid = self._project_combo.currentData()
        if pid:
            self._current_project_id = pid
            self._placeholder.hide()
            self._tabs.show()
            self._load_project_data()
        else:
            self._current_project_id = None
            self._placeholder.show()
            self._tabs.hide()

    def _load_project_data(self):
        if not self._current_project_id:
            return

        pid = self._current_project_id

        # Load annotations
        anns = self.store.project_annotations(pid)
        self._annotations_map = {}
        for a in anns:
            idx = a.get("dataIndex", 0)
            self._annotations_map[idx] = a

        # Load data items from datasets
        datasets = self.store.project_datasets(pid)
        self._data_items = []
        for ds in datasets:
            raw_data = ds.get("data", [])
            if isinstance(raw_data, str):
                try:
                    raw_data = json.loads(raw_data)
                except Exception:
                    raw_data = []
            if isinstance(raw_data, list):
                for item in raw_data:
                    entry = dict(item) if isinstance(item, dict) else {"text": str(item)}
                    entry.setdefault("_datasetId", ds.get("id", ""))
                    entry.setdefault("_datasetName", ds.get("name", ""))
                    self._data_items.append(entry)

        # Reload labels
        self._rebuild_label_checkboxes()
        self._rebuild_nav_list()
        self._rebuild_quick_labels()
        self._rebuild_suggested_labels()
        self._rebuild_frequency_display()
        self._rebuild_batch_table()

        # Reset annotation state
        self._current_annotation_id = None
        self._history_stack = []
        self._history_index = -1
        self._refresh_history_list()

        # Reset timers
        self._elapsed_seconds = 0
        self._annotation_open_time = None
        self._timer_label.setText("⏱ 00:00")
        self._timer_clock.stop()

        # Select first item if any
        if self._data_items:
            self._nav_list.setCurrentRow(0)

    # -----------------------------------------------------------------------
    # Navigation list
    # -----------------------------------------------------------------------
    def _rebuild_nav_list(self):
        self._nav_list.blockSignals(True)
        self._nav_list.clear()

        filtered_items = self._get_filtered_items()
        for i, item in enumerate(filtered_items):
            data_idx = self._data_items.index(item) if item in self._data_items else i
            ann = self._annotations_map.get(data_idx)
            status = ann.get("status", "pending") if ann else "pending"
            color = STATUS_COLORS.get(status, FG_MUTED)

            text_key = None
            for k in ("text", "content", "note", "url"):
                if k in item:
                    text_key = k
                    break
            display = item.get(text_key, f"Item {data_idx}")[:60] if text_key else f"Item {data_idx}"

            bookmarked = ann.get("bookmarked", False) if ann else False
            bm_str = " ★" if bookmarked else ""
            status_str = f" [{status}]"

            list_item = QListWidgetItem(f"  ● {display}{status_str}{bm_str}")
            list_item.setData(Qt.ItemDataRole.UserRole, data_idx)

            # Color the dot via foreground on a small label is tricky;
            # We set the whole row text color to hint at status
            list_item.setForeground(QColor(color))

            self._nav_list.addItem(list_item)

        self._nav_count_label.setText(f"{len(filtered_items)} items")
        self._nav_list.blockSignals(False)

    def _get_filtered_items(self):
        items = self._data_items
        if self._filter_status != "all":
            items = [
                item for i, item in enumerate(items)
                if self._annotations_map.get(i, {}).get("status", "pending") == self._filter_status
            ]
        if self._search_text:
            items = [
                item for item in items
                if any(isinstance(v, str) and self._search_text.lower() in v.lower() for v in item.values())
            ]
        return items

    def _on_nav_selection_changed(self, row: int):
        if row < 0 or row >= self._nav_list.count():
            return
        item = self._nav_list.item(row)
        data_idx = item.data(Qt.ItemDataRole.UserRole)
        if data_idx is not None and data_idx < len(self._data_items):
            self._load_data_item(data_idx)

    def _load_data_item(self, data_idx: int):
        if data_idx < 0 or data_idx >= len(self._data_items):
            return

        item = self._data_items[data_idx]

        # Show data preview
        preview_lines = []
        for key, val in item.items():
            if key.startswith("_"):
                continue
            if isinstance(val, (str, int, float, bool)):
                preview_lines.append(f"{key}: {val}")
            elif isinstance(val, list):
                preview_lines.append(f"{key}: [{', '.join(str(v) for v in val[:5])}]")
            elif isinstance(val, dict):
                preview_lines.append(f"{key}: {json.dumps(val, indent=2, ensure_ascii=False)[:200]}")
        self._data_preview.setPlainText("\n".join(preview_lines))

        # Load annotation if exists
        ann = self._annotations_map.get(data_idx)
        if ann:
            self._current_annotation_id = ann.get("id")
            labels = ann.get("labels", [])
            if isinstance(labels, str):
                try:
                    labels = json.loads(labels)
                except Exception:
                    labels = []
            self._set_checked_labels(labels)
            self._confidence_slider.setValue(int(ann.get("confidence", 1.0) * 100))
            self._annotator_input.setText(ann.get("annotator", ""))
            self._notes_input.setPlainText(ann.get("notes", ""))
            self._bookmark_btn.setText("★ Bookmarked" if ann.get("bookmarked") else "☆ Bookmark")
        else:
            self._current_annotation_id = None
            self._set_checked_labels([])
            self._confidence_slider.setValue(100)
            self._annotator_input.setText(self._annotator_name)
            self._notes_input.clear()
            self._bookmark_btn.setText("☆ Bookmark")

        # Start timer
        self._elapsed_seconds = 0
        self._annotation_open_time = dt.datetime.now()
        self._timer_label.setText("⏱ 00:00")
        self._timer_clock.start()

    # -----------------------------------------------------------------------
    # Label checkboxes
    # -----------------------------------------------------------------------
    def _rebuild_label_checkboxes(self):
        # Clear old
        while self._labels_grid.count():
            child = self._labels_grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._label_checkboxes.clear()

        if not self._current_project_id:
            return

        labels = self.store.project_labels(self._current_project_id)
        col = 0
        row = 0
        max_cols = 3
        for lbl in labels:
            name = lbl.get("name", "")
            color = lbl.get("color", ACCENT)

            cb = QCheckBox(f"  {name}")
            cb.setStyleSheet(f"""
                QCheckBox {{
                    color: {color};
                    font-size: 12px;
                    font-weight: 600;
                    spacing: 6px;
                }}
                QCheckBox::indicator {{
                    width: 16px;
                    height: 16px;
                    border-radius: 4px;
                    border: 2px solid {color};
                    background: {BG_INPUT};
                }}
                QCheckBox::indicator:checked {{
                    background: {color};
                    border-color: {color};
                }}
            """)
            cb.toggled.connect(lambda checked=False, n=name: self._on_label_toggled(n, checked))
            self._labels_grid.addWidget(cb, row, col)
            self._label_checkboxes.append((cb, name))

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def _set_checked_labels(self, label_names: list[str]):
        for cb, name in self._label_checkboxes:
            cb.blockSignals(True)
            cb.setChecked(name in label_names)
            cb.blockSignals(False)

    def _get_checked_labels(self) -> list[str]:
        return [name for cb, name in self._label_checkboxes if cb.isChecked()]

    def _on_label_toggled(self, name: str, checked: bool):
        self._push_history("label_toggle", f"Toggle label '{name}'")
        self._rebuild_frequency_display()

    # -----------------------------------------------------------------------
    # AI Assist panels
    # -----------------------------------------------------------------------
    def _rebuild_suggested_labels(self):
        # Clear
        while self._suggested_layout.count():
            child = self._suggested_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not self._current_project_id:
            return

        labels = self.store.project_labels(self._current_project_id)
        names = [l.get("name", "") for l in labels]
        # Pick up to 3 random suggestions
        suggestions = random.sample(names, min(3, len(names))) if names else []

        if not suggestions:
            lbl = QLabel("  No labels available")
            lbl.setStyleSheet(f"color: {FG_MUTED}; font-size: 12px; background: transparent; border: none;")
            self._suggested_layout.addWidget(lbl)
            return

        for name in suggestions:
            row = QHBoxLayout()
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {ACCENT2}; font-size: 10px; background: transparent; border: none;")
            row.addWidget(dot)
            lbl = QLabel(f"  {name}")
            lbl.setStyleSheet(f"color: {FG_PRIMARY}; font-size: 12px; background: transparent; border: none;")
            row.addWidget(lbl, 1)
            add_btn = make_secondary_btn("+", "")
            add_btn.setFixedWidth(30)
            add_btn.clicked.connect(lambda checked=False, n=name: self._quick_add_label(n))
            row.addWidget(add_btn)
            self._suggested_layout.addLayout(row)

    def _rebuild_quick_labels(self):
        while self._quick_labels_layout.count():
            child = self._quick_labels_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not self._current_project_id:
            return

        labels = self.store.project_labels(self._current_project_id)
        col = 0
        for lbl in labels:
            name = lbl.get("name", "")
            color = lbl.get("color", ACCENT)
            btn = QPushButton(f"  {name}  ")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(30)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {color}20;
                    color: {color};
                    border: 1px solid {color}40;
                    border-radius: 6px;
                    padding: 4px 12px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {color}40;
                }}
                QPushButton:pressed {{
                    background: {color}60;
                }}
            """)
            btn.clicked.connect(lambda checked=False, n=name: self._quick_add_label(n))
            self._quick_labels_layout.addWidget(btn, 0, col)
            col += 1

    def _rebuild_frequency_display(self):
        while self._frequency_layout.count():
            child = self._frequency_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                while child.layout().count():
                    sub = child.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

        if not self._current_project_id:
            return

        anns = self.store.project_annotations(self._current_project_id)
        freq: dict[str, int] = {}
        total = len(anns) or 1
        for ann in anns:
            labels = ann.get("labels", [])
            if isinstance(labels, str):
                try:
                    labels = json.loads(labels)
                except Exception:
                    labels = []
            for lbl in labels:
                freq[lbl] = freq.get(lbl, 0) + 1

        all_labels = self.store.project_labels(self._current_project_id)
        if not all_labels and not freq:
            lbl = QLabel("  No label data yet")
            lbl.setStyleSheet(f"color: {FG_MUTED}; font-size: 11px; background: transparent; border: none;")
            self._frequency_layout.addWidget(lbl)
            return

        for schema in all_labels:
            name = schema.get("name", "")
            color = schema.get("color", ACCENT)
            count = freq.get(name, 0)
            pct = count / total

            row = QHBoxLayout()
            lbl = QLabel(f"  {name}")
            lbl.setFixedWidth(100)
            lbl.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 600; background: transparent; border: none;")
            row.addWidget(lbl)

            bar_bg = QFrame()
            bar_bg.setFixedHeight(8)
            bar_bg.setStyleSheet(f"QFrame {{ background: {BG_INPUT}; border-radius: 4px; }}")
            bar_bg_lay = QHBoxLayout(bar_bg)
            bar_bg_lay.setContentsMargins(0, 0, 0, 0)
            bar_bg_lay.setSpacing(0)

            fill = QFrame()
            fill_w = max(int(200 * pct), 2) if pct > 0 else 2
            fill.setFixedWidth(fill_w)
            fill.setStyleSheet(f"QFrame {{ background: {color}; border-radius: 4px; }}")
            bar_bg_lay.addWidget(fill)
            bar_bg_lay.addStretch()
            row.addWidget(bar_bg, 1)

            count_lbl = QLabel(f" {count} ({int(pct * 100)}%)")
            count_lbl.setStyleSheet(f"color: {FG_MUTED}; font-size: 10px; background: transparent; border: none;")
            row.addWidget(count_lbl)

            self._frequency_layout.addLayout(row)

    def _quick_add_label(self, name: str):
        for cb, lbl_name in self._label_checkboxes:
            if lbl_name == name and not cb.isChecked():
                cb.setChecked(True)
                break
        self._push_history("quick_label", f"Quick add label '{name}'")
        self._rebuild_frequency_display()

    # -----------------------------------------------------------------------
    # Tool selection
    # -----------------------------------------------------------------------
    def _select_tool(self, idx: int):
        self._selected_tool = idx
        for i, btn in enumerate(self._tool_buttons):
            btn.blockSignals(True)
            btn.setChecked(i == idx)
            btn.blockSignals(False)

    # -----------------------------------------------------------------------
    # Bookmark
    # -----------------------------------------------------------------------
    def _toggle_bookmark(self):
        if not self._current_annotation_id:
            return
        ann = self._annotations_map.get(self._nav_list.currentItem().data(Qt.ItemDataRole.UserRole) if self._nav_list.currentItem() else -1)
        if ann:
            new_val = not ann.get("bookmarked", False)
            update(Annotation, ann["id"], bookmarked=new_val)
            ann["bookmarked"] = new_val
            self._bookmark_btn.setText("★ Bookmarked" if new_val else "☆ Bookmark")
            self._rebuild_nav_list()
            self._push_history("bookmark", "Toggle bookmark")

    # -----------------------------------------------------------------------
    # Auto-save
    # -----------------------------------------------------------------------
    def _toggle_auto_save(self, checked: bool):
        self._auto_save_enabled = checked
        if checked:
            self._timer_autosave.start()
        else:
            self._timer_autosave.stop()

    def _auto_save(self):
        if self._auto_save_enabled and self._current_annotation_id:
            self._save_current_annotation(silent=True)

    # -----------------------------------------------------------------------
    # Timer
    # -----------------------------------------------------------------------
    def _tick_annotation_timer(self):
        self._elapsed_seconds += 1
        minutes = self._elapsed_seconds // 60
        seconds = self._elapsed_seconds % 60
        self._timer_label.setText(f"⏱ {minutes:02d}:{seconds:02d}")

    # -----------------------------------------------------------------------
    # Confidence / Annotator / Notes
    # -----------------------------------------------------------------------
    def _on_confidence_changed(self, value: int):
        conf = value / 100.0
        self._confidence_label.setText(f"{conf:.2f}")

    def _on_annotator_changed(self, text: str):
        self._annotator_name = text

    def _on_notes_changed(self):
        pass

    # -----------------------------------------------------------------------
    # Save annotation
    # -----------------------------------------------------------------------
    def _save_current_annotation(self, silent: bool = False):
        data_idx = self._nav_list.currentItem().data(Qt.ItemDataRole.UserRole) if self._nav_list.currentItem() else None
        if data_idx is None:
            if not silent:
                QMessageBox.information(self, "Info", "No data item selected.")
            return

        labels = self._get_checked_labels()
        confidence = self._confidence_slider.value() / 100.0
        annotator = self._annotator_input.text().strip()
        notes = self._notes_input.toPlainText()

        if self._current_annotation_id:
            update(Annotation, self._current_annotation_id,
                   labels=json.dumps(labels),
                   confidence=confidence,
                   annotator=annotator,
                   notes=notes)
        else:
            new_ann = create(Annotation,
                             projectId=self._current_project_id,
                             datasetId=self._data_items[data_idx].get("_datasetId", ""),
                             dataIndex=data_idx,
                             labels=json.dumps(labels),
                             confidence=confidence,
                             annotator=annotator,
                             status="pending",
                             notes=notes,
                             bookmarked=False)
            self._current_annotation_id = new_ann.get("id")

        # Reload annotations map
        anns = self.store.project_annotations(self._current_project_id)
        self._annotations_map = {a.get("dataIndex", 0): a for a in anns}

        self._rebuild_nav_list()
        self._rebuild_frequency_display()
        self._rebuild_batch_table()
        self._push_history("save", f"Saved annotation for item {data_idx}")

        if not silent:
            QMessageBox.information(self, "Saved", "Annotation saved successfully.")

        self.store.reload("annotations")

    # -----------------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------------
    def _export_annotations(self):
        if not self._current_project_id:
            QMessageBox.information(self, "Info", "No project selected.")
            return

        anns = self.store.project_annotations(self._current_project_id)
        export_data = []
        for a in anns:
            entry = dict(a)
            entry["labels"] = a.get("labels", [])
            if isinstance(entry["labels"], str):
                try:
                    entry["labels"] = json.loads(entry["labels"])
                except Exception:
                    entry["labels"] = []
            export_data.append(entry)

        path, _ = QFileDialog.getSaveFileName(self, "Export Annotations", "annotations.json", "JSON Files (*.json)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
            QMessageBox.information(self, "Exported", f"Exported {len(export_data)} annotations.")

    # -----------------------------------------------------------------------
    # Search / Filter / View
    # -----------------------------------------------------------------------
    def _on_search_changed(self, text: str):
        self._search_text = text.strip()
        self._rebuild_nav_list()

    def _on_filter_changed(self, text: str):
        mapping = {"All": "all", "Pending": "pending", "Approved": "approved",
                    "Rejected": "rejected", "In Review": "in_review"}
        self._filter_status = mapping.get(text, "all")
        self._rebuild_nav_list()

    def _set_view_mode(self, grid: bool):
        self._grid_view = grid
        if grid:
            self._view_grid_btn.setStyleSheet(self._view_grid_btn.styleSheet().replace(f"background: {BG_INPUT};", f"background: {ACCENT}; color: #fff; border-color: {ACCENT};"))
            self._view_list_btn.setStyleSheet(self._view_list_btn.styleSheet().replace(f"background: {ACCENT};", f"background: {BG_INPUT};").replace(f"color: #fff;", f"color: {FG_SECONDARY};").replace(f"border-color: {ACCENT};", f"border-color: {BORDER};"))
        else:
            self._view_list_btn.setStyleSheet(self._view_list_btn.styleSheet().replace(f"background: {BG_INPUT};", f"background: {ACCENT}; color: #fff; border-color: {ACCENT};"))
            self._view_grid_btn.setStyleSheet(self._view_grid_btn.styleSheet().replace(f"background: {ACCENT};", f"background: {BG_INPUT};").replace(f"color: #fff;", f"color: {FG_SECONDARY};").replace(f"border-color: {ACCENT};", f"border-color: {BORDER};"))

        if self._grid_view:
            self._nav_list.setViewMode(QListWidget.ViewMode.IconMode)
            self._nav_list.setFlow(QListWidget.Flow.LeftToRight)
            self._nav_list.setWrapping(True)
            self._nav_list.setFixedHeight(280)
            self._nav_list.setGridSize(QSize(160, 50))
        else:
            self._nav_list.setViewMode(QListWidget.ViewMode.ListMode)
            self._nav_list.setFlow(QListWidget.Flow.TopToBottom)
            self._nav_list.setWrapping(False)
            self._nav_list.setFixedHeight(180)
            self._nav_list.setGridSize(QSize())

    # -----------------------------------------------------------------------
    # Undo / Redo
    # -----------------------------------------------------------------------
    def _push_history(self, action_type: str, description: str):
        # Discard future entries if we're not at the end
        if self._history_index < len(self._history_stack) - 1:
            self._history_stack = self._history_stack[:self._history_index + 1]

        # Capture current annotation state
        snapshot = self._capture_annotation_state()

        entry = {
            "action": action_type,
            "description": description,
            "timestamp": dt.datetime.now().isoformat(),
            "snapshot": snapshot,
        }
        self._history_stack.append(entry)

        # Trim if too long
        if len(self._history_stack) > self._history_max:
            self._history_stack = self._history_stack[-self._history_max:]

        self._history_index = len(self._history_stack) - 1
        self._refresh_history_list()

    def _capture_annotation_state(self) -> dict:
        return {
            "labels": self._get_checked_labels(),
            "confidence": self._confidence_slider.value() / 100.0,
            "annotator": self._annotator_input.text().strip(),
            "notes": self._notes_input.toPlainText(),
            "tool": self._selected_tool,
        }

    def _restore_state(self, snapshot: dict):
        self._set_checked_labels(snapshot.get("labels", []))
        self._confidence_slider.setValue(int(snapshot.get("confidence", 1.0) * 100))
        self._annotator_input.setText(snapshot.get("annotator", ""))
        self._notes_input.setPlainText(snapshot.get("notes", ""))
        self._select_tool(snapshot.get("tool", 0))

    def _undo(self):
        if self._history_index <= 0:
            return
        self._history_index -= 1
        entry = self._history_stack[self._history_index]
        self._restore_state(entry.get("snapshot", {}))
        self._refresh_history_list()

    def _redo(self):
        if self._history_index >= len(self._history_stack) - 1:
            return
        self._history_index += 1
        entry = self._history_stack[self._history_index]
        self._restore_state(entry.get("snapshot", {}))
        self._refresh_history_list()

    def _refresh_history_list(self):
        self._history_list.blockSignals(True)
        self._history_list.clear()

        for i, entry in enumerate(self._history_stack):
            action = entry.get("action", "")
            desc = entry.get("description", "")
            ts = entry.get("timestamp", "")[:19].replace("T", " ")

            is_current = (i == self._history_index)
            prefix = " ▸ " if is_current else "   "

            text = f"{prefix}[{action}] {desc}  —  {ts}"
            list_item = QListWidgetItem(text)

            if is_current:
                list_item.setForeground(QColor(ACCENT))
            else:
                list_item.setForeground(QColor(FG_MUTED))

            self._history_list.addItem(list_item)

        self._history_list.blockSignals(False)
        self._history_info_label.setText(
            f"Index: {self._history_index} / {len(self._history_stack)} entries"
        )

    def _on_history_entry_clicked(self, row: int):
        if 0 <= row < len(self._history_stack):
            self._history_index = row
            entry = self._history_stack[row]
            self._restore_state(entry.get("snapshot", {}))
            self._refresh_history_list()

    def _clear_history(self):
        self._history_stack = []
        self._history_index = -1
        self._refresh_history_list()

    # -----------------------------------------------------------------------
    # Batch operations
    # -----------------------------------------------------------------------
    def _rebuild_batch_table(self):
        if not self._current_project_id:
            return

        anns = self.store.project_annotations(self._current_project_id)
        self._batch_table.setRowCount(len(anns))

        for row, ann in enumerate(anns):
            # Checkbox
            cb = QTableWidgetItem()
            cb.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            cb.setCheckState(Qt.CheckState.Unchecked)
            self._batch_table.setItem(row, 0, cb)

            # ID (shortened)
            id_item = QTableWidgetItem(ann.get("id", "")[:12] + "…")
            id_item.setData(Qt.ItemDataRole.UserRole, ann.get("id"))
            self._batch_table.setItem(row, 1, id_item)

            # Labels
            labels = ann.get("labels", [])
            if isinstance(labels, str):
                try:
                    labels = json.loads(labels)
                except Exception:
                    labels = []
            self._batch_table.setItem(row, 2, QTableWidgetItem(", ".join(labels) if labels else "—"))

            # Status
            status = ann.get("status", "pending")
            status_item = QTableWidgetItem(status.title())
            color = STATUS_COLORS.get(status, FG_MUTED)
            status_item.setForeground(QColor(color))
            self._batch_table.setItem(row, 3, status_item)

            # Annotator
            self._batch_table.setItem(row, 4, QTableWidgetItem(ann.get("annotator", "")))

    def _get_selected_batch_ids(self) -> list[str]:
        ids = []
        for row in range(self._batch_table.rowCount()):
            item = self._batch_table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                id_item = self._batch_table.item(row, 1)
                if id_item:
                    ids.append(id_item.data(Qt.ItemDataRole.UserRole))
        self._selection_count_label.setText(f"Selected: {len(ids)}")
        return ids

    def _batch_select_all(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self._batch_table.rowCount()):
            item = self._batch_table.item(row, 0)
            if item:
                item.setCheckState(state)
        self._get_selected_batch_ids()

    def _batch_apply_status(self):
        ids = self._get_selected_batch_ids()
        if not ids:
            QMessageBox.information(self, "Batch", "No annotations selected.")
            return

        new_status = self._batch_status_combo.currentText()
        for aid in ids:
            update(Annotation, aid, status=new_status)

        self.store.reload("annotations")
        self._load_project_data()
        QMessageBox.information(self, "Batch", f"Status updated to '{new_status}' for {len(ids)} annotations.")

    def _batch_apply_labels(self):
        ids = self._get_selected_batch_ids()
        if not ids:
            QMessageBox.information(self, "Batch", "No annotations selected.")
            return

        raw = self._batch_label_input.text().strip()
        if not raw:
            QMessageBox.information(self, "Batch", "Enter comma-separated label names.")
            return

        new_labels = [l.strip() for l in raw.split(",") if l.strip()]
        for aid in ids:
            ann = None
            for a in self.store.annotations:
                if a.get("id") == aid:
                    ann = a
                    break
            existing = ann.get("labels", []) if ann else []
            if isinstance(existing, str):
                try:
                    existing = json.loads(existing)
                except Exception:
                    existing = []
            merged = list(set(existing + new_labels))
            update(Annotation, aid, labels=json.dumps(merged))

        self.store.reload("annotations")
        self._load_project_data()
        self._batch_label_input.clear()
        QMessageBox.information(self, "Batch", f"Labels applied to {len(ids)} annotations.")

    def _batch_delete_selected(self):
        ids = self._get_selected_batch_ids()
        if not ids:
            QMessageBox.information(self, "Batch", "No annotations selected.")
            return

        reply = QMessageBox.question(self, "Delete",
            f"Delete {len(ids)} selected annotations?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            for aid in ids:
                delete(Annotation, aid)
            self.store.reload("annotations")
            self._load_project_data()
            QMessageBox.information(self, "Batch", f"Deleted {len(ids)} annotations.")

    # -----------------------------------------------------------------------
    # Templates
    # -----------------------------------------------------------------------
    def _save_template(self):
        name = self._template_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Template", "Enter a template name.")
            return

        labels = self._get_checked_labels()
        if not labels:
            QMessageBox.warning(self, "Template", "No labels assigned. Add labels before saving.")
            return

        template = {
            "name": name,
            "labels": labels,
            "confidence": self._confidence_slider.value() / 100.0,
            "notes": self._notes_input.toPlainText(),
            "createdAt": dt.datetime.now().isoformat(),
        }
        self._templates.append(template)
        self._refresh_templates_list()
        self._template_name_input.clear()
        QMessageBox.information(self, "Template", f"Template '{name}' saved.")

    def _refresh_templates_list(self):
        self._templates_list.clear()
        for tmpl in self._templates:
            labels_str = ", ".join(tmpl.get("labels", []))
            text = f"  📋  {tmpl['name']}  —  Labels: {labels_str}"
            list_item = QListWidgetItem(text)
            list_item.setData(Qt.ItemDataRole.UserRole, tmpl["name"])
            self._templates_list.addItem(list_item)

    def _apply_template(self):
        current = self._templates_list.currentItem()
        if not current:
            QMessageBox.information(self, "Template", "Select a template first.")
            return

        name = current.data(Qt.ItemDataRole.UserRole)
        for tmpl in self._templates:
            if tmpl["name"] == name:
                self._set_checked_labels(tmpl.get("labels", []))
                self._confidence_slider.setValue(int(tmpl.get("confidence", 1.0) * 100))
                self._notes_input.setPlainText(tmpl.get("notes", ""))
                self._push_history("apply_template", f"Applied template '{name}'")
                QMessageBox.information(self, "Template", f"Template '{name}' applied.")
                return

    def _delete_template(self):
        current = self._templates_list.currentItem()
        if not current:
            QMessageBox.information(self, "Template", "Select a template first.")
            return

        name = current.data(Qt.ItemDataRole.UserRole)
        self._templates = [t for t in self._templates if t["name"] != name]
        self._refresh_templates_list()
        QMessageBox.information(self, "Template", f"Template '{name}' deleted.")

    # -----------------------------------------------------------------------
    # Tab change
    # -----------------------------------------------------------------------
    def _on_tab_changed(self, index: int):
        if index == 1:  # Batch
            self._rebuild_batch_table()
        elif index == 2:  # Templates
            self._refresh_templates_list()
        elif index == 3:  # History
            self._refresh_history_list()

    # -----------------------------------------------------------------------
    # Keyboard handling
    # -----------------------------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        mods = event.modifiers()

        # Arrow Left/Right: navigate data items
        if key == Qt.Key.Key_Left and not (mods & Qt.KeyboardModifier.ControlModifier):
            row = self._nav_list.currentRow()
            if row > 0:
                self._nav_list.setCurrentRow(row - 1)
            return
        if key == Qt.Key.Key_Right and not (mods & Qt.KeyboardModifier.ControlModifier):
            row = self._nav_list.currentRow()
            if row < self._nav_list.count() - 1:
                self._nav_list.setCurrentRow(row + 1)
            return

        # 1-6: switch tools
        if Qt.Key.Key_1 <= key <= Qt.Key.Key_6 and not (mods & Qt.KeyboardModifier.ControlModifier):
            self._select_tool(key - Qt.Key.Key_1)
            return

        # Ctrl+Z: undo
        if key == Qt.Key.Key_Z and mods & Qt.KeyboardModifier.ControlModifier and not (mods & Qt.KeyboardModifier.ShiftModifier):
            self._undo()
            return

        # Ctrl+Shift+Z or Ctrl+Y: redo
        if key == Qt.Key.Key_Z and mods & Qt.KeyboardModifier.ControlModifier and mods & Qt.KeyboardModifier.ShiftModifier:
            self._redo()
            return
        if key == Qt.Key.Key_Y and mods & Qt.KeyboardModifier.ControlModifier:
            self._redo()
            return

        # Ctrl+S: save
        if key == Qt.Key.Key_S and mods & Qt.KeyboardModifier.ControlModifier:
            self._save_current_annotation()
            return

        # B: bookmark
        if key == Qt.Key.Key_B and not (mods & Qt.KeyboardModifier.ControlModifier):
            self._toggle_bookmark()
            return

        # /: toggle shortcuts help (could toggle visibility)
        if key == Qt.Key.Key_Slash and not (mods & Qt.KeyboardModifier.ControlModifier):
            # Toggle the shortcuts panel visibility is complex; just focus it
            return

        # Escape: deselect
        if key == Qt.Key.Key_Escape:
            self._nav_list.clearSelection()
            self._data_preview.clear()
            self._set_checked_labels([])
            self._current_annotation_id = None
            self._timer_clock.stop()
            self._elapsed_seconds = 0
            self._timer_label.setText("⏱ 00:00")
            return

        super().keyPressEvent(event)

    # -----------------------------------------------------------------------
    # Refresh
    # -----------------------------------------------------------------------
    def refresh(self):
        """Called when view is activated or data changes."""
        # Update project combo
        self._project_combo.blockSignals(True)
        current_data = self._project_combo.currentData()
        self._project_combo.clear()
        self._project_combo.addItem("Select a project…", None)
        for proj in self.store.projects:
            self._project_combo.addItem(f"  📁  {proj['name']}", proj["id"])
        # Restore selection
        if current_data:
            for i in range(self._project_combo.count()):
                if self._project_combo.itemData(i) == current_data:
                    self._project_combo.setCurrentIndex(i)
                    break
        self._project_combo.blockSignals(False)

        # If we have a project, reload data
        if self._current_project_id:
            self._load_project_data()
