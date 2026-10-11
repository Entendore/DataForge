"""DataForge – Workflows View: diagram & editor for annotation workflow pipelines."""

from __future__ import annotations

import json
import uuid
import math
from collections import Counter

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton,
    QLabel, QFrame, QScrollArea, QSizePolicy, QComboBox, QTableWidget,
    QTableWidgetItem, QTextEdit, QLineEdit, QAbstractItemView,
    QMenu, QToolButton, QHeaderView, QSplitter, QSpacerItem,
    QInputDialog, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, Signal, QSize
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPainterPath,
    QLinearGradient, QRadialGradient, QFontMetrics,
)

from models import (
    BG_DARK, BG_CARD, BG_HOVER, BG_INPUT, FG_PRIMARY, FG_SECONDARY,
    FG_MUTED, ACCENT, ACCENT2, BORDER, SUCCESS, WARNING, DANGER, INFO, RADIUS,
)
from store import Store
from models import Workflow, create, update, delete

# ---------------------------------------------------------------------------
# Step type constants
# ---------------------------------------------------------------------------
STEP_TYPES = ["input", "process", "decision", "annotation", "review", "output"]
STEP_TYPE_COLORS = {
    "input": "#22c55e",
    "process": "#3b82f6",
    "decision": "#eab308",
    "annotation": "#8b5cf6",
    "review": "#ec4899",
    "output": "#06b6d4",
}
STEP_TYPE_ICONS = {
    "input": "⬇",
    "process": "⚙",
    "decision": "◇",
    "annotation": "🏷",
    "review": "✓",
    "output": "⬆",
}
WORKFLOW_STATUSES = ["draft", "active", "paused", "completed"]
STATUS_COLORS = {
    "draft": FG_MUTED,
    "active": SUCCESS,
    "paused": WARNING,
    "completed": INFO,
}

# ---------------------------------------------------------------------------
# Workflow templates
# ---------------------------------------------------------------------------
WORKFLOW_TEMPLATES = {
    "Basic Annotation Pipeline": [
        {"name": "Data Input", "type": "input", "config": {}},
        {"name": "Pre-processing", "type": "process", "config": {}},
        {"name": "Quality Gate", "type": "decision", "config": {}, "branchTo": ""},
        {"name": "Annotation", "type": "annotation", "config": {}},
        {"name": "Review", "type": "review", "config": {}},
        {"name": "Export", "type": "output", "config": {}},
    ],
    "Multi-Stage NER": [
        {"name": "Load Documents", "type": "input", "config": {}},
        {"name": "Tokenize", "type": "process", "config": {}},
        {"name": "NER Annotator A", "type": "annotation", "config": {},
         "parallelGroup": "parallel1", "parallelBranch": "A"},
        {"name": "NER Annotator B", "type": "annotation", "config": {},
         "parallelGroup": "parallel1", "parallelBranch": "B"},
        {"name": "Merge & Adjudicate", "type": "process", "config": {}},
        {"name": "Final Review", "type": "review", "config": {}},
        {"name": "Export", "type": "output", "config": {}},
    ],
    "Image Classification": [
        {"name": "Image Input", "type": "input", "config": {}},
        {"name": "Pre-process", "type": "process", "config": {}},
        {"name": "Classify", "type": "annotation", "config": {}},
        {"name": "Quality Review", "type": "review", "config": {}},
        {"name": "Export Labels", "type": "output", "config": {}},
    ],
    "Data Processing & Enrichment": [
        {"name": "Data Ingestion", "type": "input", "config": {}},
        {"name": "Clean & Transform", "type": "process", "config": {}},
        {"name": "Validation Check", "type": "decision", "config": {}, "branchTo": ""},
        {"name": "Enrichment", "type": "process", "config": {}},
        {"name": "Human Review", "type": "review", "config": {}},
        {"name": "Output", "type": "output", "config": {}},
    ],
}


# ---------------------------------------------------------------------------
# Workflow Diagram Widget (custom painted)
# ---------------------------------------------------------------------------
class WorkflowDiagramWidget(QWidget):
    """Custom painted widget that draws workflow steps as nodes with connectors."""

    stepClicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.steps: list[dict] = []
        self.selected_step_index: int = -1
        self.sim_step_index: int = -1
        self._pulse_phase: float = 0.0
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(50)
        self._pulse_timer.timeout.connect(self._advance_pulse)
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self._hover_index: int = -1
        self._node_rects: list[QRectF] = []
        self._node_centers: list[tuple[float, float]] = []

    def set_steps(self, steps: list[dict]) -> None:
        self.steps = steps
        self._layout_nodes()
        self.update()

    def set_selected(self, index: int) -> None:
        self.selected_step_index = index
        self.update()

    def set_sim_step(self, index: int) -> None:
        self.sim_step_index = index
        self._pulse_phase = 0.0
        if index >= 0 and not self._pulse_timer.isActive():
            self._pulse_timer.start()
        elif index < 0:
            self._pulse_timer.stop()
        self.update()

    def _advance_pulse(self) -> None:
        self._pulse_phase = (self._pulse_phase + 0.15) % (2 * math.pi)
        self.update()

    def _layout_nodes(self) -> None:
        """Calculate node positions in a vertical flow layout."""
        self._node_rects.clear()
        self._node_centers.clear()
        if not self.steps:
            return

        w = max(self.width(), 500)
        node_w = 200
        node_h = 64
        v_gap = 44
        h_gap = 40

        # Group parallel steps
        groups: dict[str, list[int]] = {}
        for i, step in enumerate(self.steps):
            pg = step.get("parallelGroup", "")
            if pg:
                groups.setdefault(pg, []).append(i)

        # Determine effective step count (parallel groups collapse vertically)
        effective_indices: list[list[int]] = []
        i = 0
        while i < len(self.steps):
            pg = self.steps[i].get("parallelGroup", "")
            if pg and i in groups.get(pg, []):
                members = groups[pg]
                effective_indices.append(sorted(members))
                i = max(members) + 1
            else:
                effective_indices.append([i])
                i += 1

        total_height = len(effective_indices) * (node_h + v_gap) - v_gap
        y_start = max(30, (max(self.height(), total_height + 60) - total_height) // 2)

        step_pos: dict[int, tuple[float, float]] = {}

        for row_idx, row_members in enumerate(effective_indices):
            y = y_start + row_idx * (node_h + v_gap)
            n = len(row_members)
            total_w = n * node_w + (n - 1) * h_gap
            x_start = (w - total_w) / 2

            for col, si in enumerate(row_members):
                x = x_start + col * (node_w + h_gap)
                step_pos[si] = (x, y)

        for i in range(len(self.steps)):
            if i in step_pos:
                x, y = step_pos[i]
            else:
                # Fallback: vertical flow
                y = y_start + i * (node_h + v_gap)
                x = (w - node_w) / 2
            rect = QRectF(x, y, node_w, node_h)
            self._node_rects.append(rect)
            self._node_centers.append((x + node_w / 2, y + node_h / 2))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_nodes()
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(BG_DARK))

        if not self.steps:
            painter.setPen(QColor(FG_MUTED))
            painter.setFont(QFont("Segoe UI", 14))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "No steps yet.\nAdd steps in the editor or use a template.")
            painter.end()
            return

        self._draw_connections(painter)
        self._draw_parallel_groups(painter)
        self._draw_nodes(painter)
        painter.end()

    def _draw_connections(self, painter: QPainter) -> None:
        """Draw arrow connections between sequential steps."""
        pen = QPen(QColor(FG_MUTED), 2, Qt.PenStyle.SolidLine)
        painter.setPen(pen)

        for i in range(len(self.steps) - 1):
            if i >= len(self._node_centers) or i + 1 >= len(self._node_centers):
                continue
            x1, y1 = self._node_centers[i]
            x2, y2 = self._node_centers[i + 1]

            # Skip connection within same parallel group
            pg1 = self.steps[i].get("parallelGroup", "")
            pg2 = self.steps[i + 1].get("parallelGroup", "")
            if pg1 and pg1 == pg2:
                continue

            self._draw_arrow(painter, x1, y1 + 32, x2, y2 - 32)

        # Decision branching arrows
        for i, step in enumerate(self.steps):
            if step.get("type") == "decision" and step.get("branchTo"):
                branch_target_id = step["branchTo"]
                target_idx = -1
                for j, s in enumerate(self.steps):
                    if s.get("id") == branch_target_id:
                        target_idx = j
                        break
                if target_idx >= 0 and target_idx < len(self._node_centers) and i < len(self._node_centers):
                    x1, y1 = self._node_centers[i]
                    x2, y2 = self._node_centers[target_idx]
                    branch_pen = QPen(QColor(WARNING), 2, Qt.PenStyle.DashLine)
                    painter.setPen(branch_pen)
                    # Draw curved branch arrow to the right side
                    self._draw_curved_arrow(painter, x1 + 100, y1, x2 + 100, y2)
                    # Label
                    painter.setFont(QFont("Segoe UI", 9))
                    painter.setPen(QColor(WARNING))
                    mid_x = (x1 + 100 + x2 + 100) / 2 + 10
                    mid_y = (y1 + y2) / 2
                    painter.drawText(QPointF(mid_x, mid_y), "branch")

    def _draw_arrow(self, painter: QPainter, x1: float, y1: float,
                    x2: float, y2: float) -> None:
        """Draw a straight arrow from (x1,y1) to (x2,y2)."""
        painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        # Arrowhead
        angle = math.atan2(y2 - y1, x2 - x1)
        arrow_size = 8
        p1 = QPointF(x2 - arrow_size * math.cos(angle - 0.4),
                     y2 - arrow_size * math.sin(angle - 0.4))
        p2 = QPointF(x2 - arrow_size * math.cos(angle + 0.4),
                     y2 - arrow_size * math.sin(angle + 0.4))
        path = QPainterPath()
        path.moveTo(x2, y2)
        path.lineTo(p1)
        path.lineTo(p2)
        path.closeSubpath()
        painter.setBrush(QColor(FG_MUTED))
        painter.drawPath(path)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def _draw_curved_arrow(self, painter: QPainter, x1: float, y1: float,
                           x2: float, y2: float) -> None:
        """Draw a curved arrow along the right side."""
        path = QPainterPath()
        path.moveTo(x1, y1)
        ctrl_x = max(x1, x2) + 80
        path.cubicTo(ctrl_x, y1, ctrl_x, y2, x2, y2)
        painter.drawPath(path)
        # Arrowhead at end
        angle = math.atan2(y2 - (y2 + y1) / 2, x2 - ctrl_x)
        arrow_size = 8
        p1 = QPointF(x2 - arrow_size * math.cos(angle - 0.4),
                     y2 - arrow_size * math.sin(angle - 0.4))
        p2 = QPointF(x2 - arrow_size * math.cos(angle + 0.4),
                     y2 - arrow_size * math.sin(angle + 0.4))
        arrow_path = QPainterPath()
        arrow_path.moveTo(x2, y2)
        arrow_path.lineTo(p1)
        arrow_path.lineTo(p2)
        arrow_path.closeSubpath()
        painter.setBrush(painter.pen().color())
        painter.drawPath(arrow_path)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def _draw_parallel_groups(self, painter: QPainter) -> None:
        """Draw dashed borders around parallel groups."""
        groups: dict[str, list[int]] = {}
        for i, step in enumerate(self.steps):
            pg = step.get("parallelGroup", "")
            if pg:
                groups.setdefault(pg, []).append(i)

        for pg_name, indices in groups.items():
            if not indices or max(indices) >= len(self._node_rects):
                continue
            rects = [self._node_rects[i] for i in indices if i < len(self._node_rects)]
            if not rects:
                continue
            union = rects[0]
            for r in rects[1:]:
                union = union.united(r)
            padding = 16
            group_rect = union.adjusted(-padding, -padding, padding, padding + 20)

            pen = QPen(QColor(FG_MUTED), 1.5, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(BG_DARK))
            painter.drawRoundedRect(group_rect, 12, 12)

            # Group label
            painter.setPen(QColor(FG_SECONDARY))
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.drawText(QPointF(group_rect.left() + 8, group_rect.top() - 4),
                             f"Parallel: {pg_name}")

    def _draw_nodes(self, painter: QPainter) -> None:
        """Draw each step as a rounded rectangle node."""
        for i, step in enumerate(self.steps):
            if i >= len(self._node_rects):
                continue
            rect = self._node_rects[i]
            step_type = step.get("type", "process")
            color = QColor(STEP_TYPE_COLORS.get(step_type, INFO))
            name = step.get("name", f"Step {i + 1}")
            icon = STEP_TYPE_ICONS.get(step_type, "●")

            is_selected = (i == self.selected_step_index)
            is_hovered = (i == self._hover_index)
            is_sim = (i == self.sim_step_index)

            # Shadow
            shadow_color = QColor(0, 0, 0, 60)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shadow_color)
            painter.drawRoundedRect(rect.adjusted(3, 3, 3, 3), RADIUS, RADIUS)

            # Background fill
            bg = QColor(BG_CARD)
            if is_selected:
                bg = QColor(BG_HOVER)
            if is_hovered and not is_selected:
                bg = QColor(BG_HOVER)
            painter.setBrush(bg)

            # Border
            if is_sim:
                pulse = (math.sin(self._pulse_phase) + 1) / 2  # 0..1
                glow_alpha = int(120 + 135 * pulse)
                glow_color = QColor(color)
                glow_color.setAlpha(glow_alpha)
                pen = QPen(glow_color, 3)
                # Outer glow
                painter.setPen(QPen(QColor(color.red(), color.green(), color.blue(), int(40 * pulse)), 6))
                painter.drawRoundedRect(rect.adjusted(-3, -3, 3, 3), RADIUS + 2, RADIUS + 2)
                painter.setPen(pen)
            elif is_selected:
                painter.setPen(QPen(color, 2))
            else:
                painter.setPen(QPen(QColor(BORDER), 1))
            painter.drawRoundedRect(rect, RADIUS, RADIUS)

            # Color accent bar on left
            accent_rect = QRectF(rect.left(), rect.top() + 8, 4, rect.height() - 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(accent_rect, 2, 2)

            # Icon badge
            painter.setFont(QFont("Segoe UI", 14))
            painter.setPen(color)
            painter.drawText(QPointF(rect.left() + 14, rect.top() + rect.height() / 2 + 5),
                             icon)

            # Step name
            painter.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
            painter.setPen(QColor(FG_PRIMARY))
            fm = QFontMetrics(painter.font())
            elided = fm.elidedText(name, Qt.TextElideMode.ElideRight,
                                   int(rect.width() - 60))
            painter.drawText(QPointF(rect.left() + 38, rect.top() + rect.height() / 2 - 2),
                             elided)

            # Type badge
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(QColor(FG_SECONDARY))
            painter.drawText(QPointF(rect.left() + 38, rect.top() + rect.height() / 2 + 14),
                             step_type.upper())

            # Parallel branch label
            branch = step.get("parallelBranch", "")
            if branch:
                painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                painter.setPen(QColor(ACCENT))
                painter.drawText(QPointF(rect.right() - 22, rect.top() + 16), branch)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self._hit_test(event.position())
            if idx >= 0:
                self.selected_step_index = idx
                self.stepClicked.emit(idx)
                self.update()
            else:
                self.selected_step_index = -1
                self.stepClicked.emit(-1)
                self.update()

    def mouseMoveEvent(self, event) -> None:
        idx = self._hit_test(event.position())
        if idx != self._hover_index:
            self._hover_index = idx
            self.setCursor(Qt.CursorShape.PointingHandCursor if idx >= 0
                           else Qt.CursorShape.ArrowCursor)
            self.update()

    def _hit_test(self, pos: QPointF) -> int:
        for i, rect in enumerate(self._node_rects):
            if rect.contains(pos):
                return i
        return -1


# ---------------------------------------------------------------------------
# Main Workflows View
# ---------------------------------------------------------------------------
class WorkflowsView(QWidget):
    """Complete workflows management view with diagram and editor modes."""

    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self.current_workflow: dict | None = None
        self.current_steps: list[dict] = []
        self._current_mode: str = "diagram"  # "diagram" or "editor"

        # Simulation state
        self._sim_timer = QTimer(self)
        self._sim_timer.setInterval(1500)
        self._sim_timer.timeout.connect(self._sim_next_step)
        self._sim_running: bool = False
        self._sim_index: int = -1

        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # ---- Header ----
        header = QHBoxLayout()
        header.setSpacing(12)

        title = QLabel("🔀 Workflows")
        title.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {FG_PRIMARY};")
        header.addWidget(title)

        header.addStretch()

        # Workflow selector
        self.workflow_combo = QComboBox()
        self.workflow_combo.setMinimumWidth(220)
        self.workflow_combo.setSizePolicy(QSizePolicy.Policy.Expanding,
                                          QSizePolicy.Policy.Fixed)
        header.addWidget(self.workflow_combo)

        self.btn_create = QPushButton("+ New")
        self.btn_create.setFixedWidth(80)
        self.btn_create.setCursor(Qt.CursorShape.PointingHandCursor)
        header.addWidget(self.btn_create)

        self.btn_duplicate = QPushButton("⧉ Duplicate")
        self.btn_duplicate.setFixedWidth(100)
        self.btn_duplicate.setCursor(Qt.CursorShape.PointingHandCursor)
        header.addWidget(self.btn_duplicate)

        # Status display
        self.status_label = QLabel("—")
        self.status_label.setFixedWidth(90)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            f"background: {BG_INPUT}; color: {FG_MUTED}; border: 1px solid {BORDER};"
            f"border-radius: {RADIUS}px; padding: 6px 12px; font-weight: 600; font-size: 12px;"
        )
        header.addWidget(self.status_label)

        self.btn_status = QToolButton()
        self.btn_status.setText("▼")
        self.btn_status.setFixedSize(32, 32)
        self.btn_status.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_status.setStyleSheet(
            f"QToolButton {{ background: {BG_CARD}; color: {FG_SECONDARY}; border: 1px solid {BORDER};"
            f"border-radius: {RADIUS}px; font-size: 10px; }}"
            f"QToolButton:hover {{ background: {BG_HOVER}; color: {FG_PRIMARY}; }}"
        )
        header.addWidget(self.btn_status)

        root.addLayout(header)

        # ---- Toolbar: mode toggle, templates, simulation ----
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        # Mode toggle buttons
        self.btn_diagram = QPushButton("◫ Diagram")
        self.btn_diagram.setFixedWidth(120)
        self.btn_diagram.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_diagram.setCheckable(True)
        self.btn_diagram.setChecked(True)
        toolbar.addWidget(self.btn_diagram)

        self.btn_editor = QPushButton("☰ Editor")
        self.btn_editor.setFixedWidth(120)
        self.btn_editor.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_editor.setCheckable(True)
        toolbar.addWidget(self.btn_editor)

        toolbar.addSpacing(16)

        # Templates button
        self.btn_templates = QPushButton("📋 Templates")
        self.btn_templates.setFixedWidth(120)
        self.btn_templates.setCursor(Qt.CursorShape.PointingHandCursor)
        toolbar.addWidget(self.btn_templates)

        # Simulation button
        self.btn_simulate = QPushButton("▶ Simulate")
        self.btn_simulate.setFixedWidth(120)
        self.btn_simulate.setCursor(Qt.CursorShape.PointingHandCursor)
        toolbar.addWidget(self.btn_simulate)

        self.btn_stop_sim = QPushButton("■ Stop")
        self.btn_stop_sim.setFixedWidth(80)
        self.btn_stop_sim.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop_sim.setVisible(False)
        toolbar.addWidget(self.btn_stop_sim)

        # Simulation status area
        self.sim_status_label = QLabel("")
        self.sim_status_label.setStyleSheet(
            f"color: {ACCENT}; font-size: 12px; font-weight: 500; padding: 0 8px;"
        )
        toolbar.addWidget(self.sim_status_label)

        toolbar.addStretch()
        root.addLayout(toolbar)

        # ---- Main content splitter ----
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(2)
        self.splitter.setStyleSheet(f"QSplitter::handle {{ background: {BORDER}; }}")

        # Left: diagram / editor stack
        self.content_stack = QWidget()
        content_layout = QVBoxLayout(self.content_stack)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Diagram view (scrollable)
        self.diagram_scroll = QScrollArea()
        self.diagram_scroll.setWidgetResizable(True)
        self.diagram_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.diagram_scroll.setStyleSheet(f"QScrollArea {{ border: 1px solid {BORDER};"
                                          f"border-radius: {RADIUS}px; background: {BG_DARK}; }}")
        self.diagram_widget = WorkflowDiagramWidget()
        self.diagram_widget.stepClicked.connect(self._on_diagram_step_clicked)
        self.diagram_scroll.setWidget(self.diagram_widget)

        # Editor view (table)
        self.editor_container = QWidget()
        editor_layout = QVBoxLayout(self.editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(8)

        # Editor toolbar
        ed_toolbar = QHBoxLayout()
        ed_toolbar.setSpacing(6)
        self.btn_add_step = QPushButton("+ Add Step")
        self.btn_add_step.setCursor(Qt.CursorShape.PointingHandCursor)
        ed_toolbar.addWidget(self.btn_add_step)

        self.btn_del_step = QPushButton("✕ Delete")
        self.btn_del_step.setCursor(Qt.CursorShape.PointingHandCursor)
        ed_toolbar.addWidget(self.btn_del_step)

        self.btn_dup_step = QPushButton("⧉ Duplicate")
        self.btn_dup_step.setCursor(Qt.CursorShape.PointingHandCursor)
        ed_toolbar.addWidget(self.btn_dup_step)

        self.btn_move_up = QPushButton("↑ Up")
        self.btn_move_up.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_move_up.setFixedWidth(70)
        ed_toolbar.addWidget(self.btn_move_up)

        self.btn_move_down = QPushButton("↓ Down")
        self.btn_move_down.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_move_down.setFixedWidth(70)
        ed_toolbar.addWidget(self.btn_move_down)

        ed_toolbar.addStretch()
        editor_layout.addLayout(ed_toolbar)

        # Steps table
        self.steps_table = QTableWidget(0, 7)
        self.steps_table.setHorizontalHeaderLabels(
            ["Name", "Type", "Description", "Branch To", "Parallel Group", "Branch", "Config"]
        )
        self.steps_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive)
        self.steps_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.steps_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.steps_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.steps_table.verticalHeader().setVisible(False)
        self.steps_table.setAlternatingRowColors(True)
        editor_layout.addWidget(self.steps_table)

        # Show diagram by default
        self.editor_container.setVisible(False)
        content_layout.addWidget(self.diagram_scroll)
        content_layout.addWidget(self.editor_container)

        self.splitter.addWidget(self.content_stack)

        # Right: Step Configuration Panel
        self.config_panel = self._build_config_panel()
        self._set_config_visible(False)
        self.splitter.addWidget(self.config_panel)
        self.splitter.setSizes([700, 340])

        root.addWidget(self.splitter, 1)

        # ---- Bottom: Stats + Description ----
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        bottom_splitter.setHandleWidth(2)
        bottom_splitter.setStyleSheet(f"QSplitter::handle {{ background: {BORDER}; }}")

        self.stats_panel = self._build_stats_panel()
        bottom_splitter.addWidget(self.stats_panel)

        self.desc_panel = self._build_description_panel()
        bottom_splitter.addWidget(self.desc_panel)
        bottom_splitter.setSizes([400, 600])

        root.addWidget(bottom_splitter)

        # Initial mode styling
        self._apply_mode_style()

    def _build_config_panel(self) -> QFrame:
        """Build the right-side step configuration panel."""
        panel = QFrame()
        panel.setFixedWidth(320)
        panel.setStyleSheet(f"""
            QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER};
                      border-radius: {RADIUS}px; }}
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QLabel("Step Configuration")
        header.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {FG_PRIMARY};")
        layout.addWidget(header)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BORDER};")
        layout.addWidget(sep)

        # Name
        layout.addWidget(QLabel("Name"))
        self.cfg_name = QLineEdit()
        self.cfg_name.setPlaceholderText("Step name")
        layout.addWidget(self.cfg_name)

        # Type display
        layout.addWidget(QLabel("Type"))
        self.cfg_type = QComboBox()
        self.cfg_type.addItems(STEP_TYPES)
        layout.addWidget(self.cfg_type)

        # Description
        layout.addWidget(QLabel("Description"))
        self.cfg_desc = QLineEdit()
        self.cfg_desc.setPlaceholderText("Step description")
        layout.addWidget(self.cfg_desc)

        # Branch To
        layout.addWidget(QLabel("Branch To (decision)"))
        self.cfg_branch = QComboBox()
        self.cfg_branch.addItem("— None —", "")
        layout.addWidget(self.cfg_branch)

        # Parallel Group
        layout.addWidget(QLabel("Parallel Group"))
        self.cfg_pgroup = QLineEdit()
        self.cfg_pgroup.setPlaceholderText("e.g. parallel1")
        layout.addWidget(self.cfg_pgroup)

        # Parallel Branch
        layout.addWidget(QLabel("Parallel Branch"))
        self.cfg_pbranch = QComboBox()
        self.cfg_pbranch.addItems(["None", "A", "B", "C", "D"])
        layout.addWidget(self.cfg_pbranch)

        # Config JSON
        layout.addWidget(QLabel("Config (JSON)"))
        self.cfg_json = QTextEdit()
        self.cfg_json.setPlaceholderText('{ "key": "value" }')
        self.cfg_json.setFixedHeight(120)
        self.cfg_json.setStyleSheet(f"QTextEdit {{ font-family: 'Consolas', monospace;"
                                    f"font-size: 12px; }}")
        layout.addWidget(self.cfg_json)

        # Save button
        self.btn_save_step = QPushButton("💾 Save Step")
        self.btn_save_step.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_step.setStyleSheet(
            f"QPushButton {{ background: {ACCENT}; color: #fff; border: none;"
            f"border-radius: {RADIUS}px; padding: 10px; font-weight: 600; font-size: 13px; }}"
            f"QPushButton:hover {{ background: #7c3aed; }}"
        )
        layout.addWidget(self.btn_save_step)

        layout.addStretch()

        # Placeholder when nothing selected
        self.cfg_placeholder = QLabel("Select a step to configure")
        self.cfg_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cfg_placeholder.setStyleSheet(f"color: {FG_MUTED}; font-size: 13px; padding: 40px;")
        layout.addWidget(self.cfg_placeholder)

        return panel

    def _build_stats_panel(self) -> QFrame:
        """Build the workflow stats panel."""
        panel = QFrame()
        panel.setMinimumHeight(140)
        panel.setMaximumHeight(200)
        panel.setStyleSheet(f"""
            QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER};
                      border-radius: {RADIUS}px; }}
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        header = QLabel("📊 Workflow Stats")
        header.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {FG_PRIMARY};")
        layout.addWidget(header)

        self.stats_content = QWidget()
        self.stats_layout = QVBoxLayout(self.stats_content)
        self.stats_layout.setContentsMargins(0, 0, 0, 0)
        self.stats_layout.setSpacing(6)

        self.stat_total = QLabel("Total steps: 0")
        self.stat_total.setStyleSheet(f"color: {FG_SECONDARY}; font-size: 12px;")
        self.stats_layout.addWidget(self.stat_total)

        self.stat_status = QLabel("Status: —")
        self.stat_status.setStyleSheet(f"color: {FG_MUTED}; font-size: 12px;")
        self.stats_layout.addWidget(self.stat_status)

        # Type distribution bars container
        self.type_bars_widget = QWidget()
        self.type_bars_layout = QVBoxLayout(self.type_bars_widget)
        self.type_bars_layout.setContentsMargins(0, 0, 0, 0)
        self.type_bars_layout.setSpacing(4)
        self.stats_layout.addWidget(self.type_bars_widget)

        layout.addWidget(self.stats_content)
        return panel

    def _build_description_panel(self) -> QFrame:
        """Build the workflow description panel."""
        panel = QFrame()
        panel.setMinimumHeight(140)
        panel.setMaximumHeight(200)
        panel.setStyleSheet(f"""
            QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER};
                      border-radius: {RADIUS}px; }}
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        header = QLabel("📝 Description")
        header.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {FG_PRIMARY};")
        header_row.addWidget(header)
        header_row.addStretch()

        self.btn_save_desc = QPushButton("Save")
        self.btn_save_desc.setFixedWidth(70)
        self.btn_save_desc.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_desc.setStyleSheet(
            f"QPushButton {{ background: {ACCENT}; color: #fff; border: none;"
            f"border-radius: {RADIUS}px; padding: 6px 12px; font-weight: 600; font-size: 12px; }}"
            f"QPushButton:hover {{ background: #7c3aed; }}"
        )
        header_row.addWidget(self.btn_save_desc)
        layout.addLayout(header_row)

        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("Describe this workflow...")
        self.desc_edit.setStyleSheet(f"QTextEdit {{ font-size: 12px; background: {BG_INPUT};"
                                     f"border: 1px solid {BORDER}; border-radius: {RADIUS}px;"
                                     f"padding: 8px; }}")
        layout.addWidget(self.desc_edit)

        return panel

    # ------------------------------------------------------------------
    # Signal connections
    # ------------------------------------------------------------------
    def _connect_signals(self) -> None:
        self.workflow_combo.currentIndexChanged.connect(self._on_workflow_selected)
        self.btn_create.clicked.connect(self._create_workflow)
        self.btn_duplicate.clicked.connect(self._duplicate_workflow)
        self.btn_status.clicked.connect(self._show_status_menu)
        self.btn_diagram.clicked.connect(lambda: self._set_mode("diagram"))
        self.btn_editor.clicked.connect(lambda: self._set_mode("editor"))
        self.btn_templates.clicked.connect(self._show_templates_menu)
        self.btn_simulate.clicked.connect(self._start_simulation)
        self.btn_stop_sim.clicked.connect(self._stop_simulation)

        # Editor buttons
        self.btn_add_step.clicked.connect(self._add_step)
        self.btn_del_step.clicked.connect(self._delete_step)
        self.btn_dup_step.clicked.connect(self._duplicate_step)
        self.btn_move_up.clicked.connect(self._move_step_up)
        self.btn_move_down.clicked.connect(self._move_step_down)

        # Table selection
        self.steps_table.currentCellChanged.connect(self._on_table_selection_changed)
        self.steps_table.cellChanged.connect(self._on_table_cell_changed)

        # Config panel
        self.cfg_type.currentTextChanged.connect(self._on_cfg_type_changed)
        self.btn_save_step.clicked.connect(self._save_step_config)
        self.btn_save_desc.clicked.connect(self._save_description)

    # ------------------------------------------------------------------
    # Mode switching
    # ------------------------------------------------------------------
    def _set_mode(self, mode: str) -> None:
        self._current_mode = mode
        if mode == "diagram":
            self.diagram_scroll.setVisible(True)
            self.editor_container.setVisible(False)
            self.btn_diagram.setChecked(True)
            self.btn_editor.setChecked(False)
        else:
            self.diagram_scroll.setVisible(False)
            self.editor_container.setVisible(True)
            self.btn_diagram.setChecked(False)
            self.btn_editor.setChecked(True)
            self._populate_table()
        self._apply_mode_style()

    def _apply_mode_style(self) -> None:
        active_ss = (
            f"QPushButton {{ background: {ACCENT}; color: #fff; border: none;"
            f"border-radius: {RADIUS}px; padding: 8px 16px; font-weight: 600; }}"
            f"QPushButton:hover {{ background: #7c3aed; }}"
        )
        inactive_ss = (
            f"QPushButton {{ background: {BG_CARD}; color: {FG_SECONDARY};"
            f"border: 1px solid {BORDER}; border-radius: {RADIUS}px;"
            f"padding: 8px 16px; font-weight: 500; }}"
            f"QPushButton:hover {{ background: {BG_HOVER}; color: {FG_PRIMARY}; }}"
        )
        if self._current_mode == "diagram":
            self.btn_diagram.setStyleSheet(active_ss)
            self.btn_editor.setStyleSheet(inactive_ss)
        else:
            self.btn_diagram.setStyleSheet(inactive_ss)
            self.btn_editor.setStyleSheet(active_ss)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self.store.reload("workflows")
        self._populate_workflow_combo()
        # Re-select current workflow if still valid
        if self.current_workflow:
            cid = self.current_workflow["id"]
            for i in range(self.workflow_combo.count()):
                if self.workflow_combo.itemData(i) == cid:
                    self.workflow_combo.setCurrentIndex(i)
                    return
            self.current_workflow = None
            self.current_steps = []
        elif self.workflow_combo.count() > 0:
            self.workflow_combo.setCurrentIndex(0)

        self._update_views()

    def _populate_workflow_combo(self) -> None:
        self.workflow_combo.blockSignals(True)
        self.workflow_combo.clear()
        pid = self.store.current_project_id
        workflows = self.store.project_workflows(pid) if pid else self.store.workflows
        for wf in workflows:
            self.workflow_combo.addItem(wf["name"], wf["id"])
        self.workflow_combo.blockSignals(False)

    def _update_views(self) -> None:
        """Update diagram, editor, config panel, and stats."""
        steps = self.current_steps

        # Diagram
        self.diagram_widget.set_steps(steps)
        if self.diagram_widget.selected_step_index >= len(steps):
            self.diagram_widget.set_selected(-1)

        # Stats
        self._update_stats()

        # Description
        if self.current_workflow:
            desc = self.current_workflow.get("description", "")
            if isinstance(desc, list):
                desc = json.dumps(desc)
            self.desc_edit.blockSignals(True)
            self.desc_edit.setPlainText(desc)
            self.desc_edit.blockSignals(False)

            # Status label
            status = self.current_workflow.get("status", "draft")
            sc = STATUS_COLORS.get(status, FG_MUTED)
            self.status_label.setText(status.upper())
            self.status_label.setStyleSheet(
                f"background: {BG_INPUT}; color: {sc}; border: 1px solid {BORDER};"
                f"border-radius: {RADIUS}px; padding: 6px 12px; font-weight: 600; font-size: 12px;"
            )

        # Config panel placeholder
        if not self.current_workflow or not steps:
            self._set_config_visible(False)

    # ------------------------------------------------------------------
    # Workflow selection & CRUD
    # ------------------------------------------------------------------
    def _on_workflow_selected(self, index: int) -> None:
        if index < 0:
            self.current_workflow = None
            self.current_steps = []
            self._update_views()
            return
        wf_id = self.workflow_combo.itemData(index)
        for wf in self.store.workflows:
            if wf["id"] == wf_id:
                self.current_workflow = wf
                raw_steps = wf.get("steps", [])
                if isinstance(raw_steps, str):
                    try:
                        self.current_steps = json.loads(raw_steps)
                    except Exception:
                        self.current_steps = []
                elif isinstance(raw_steps, list):
                    self.current_steps = raw_steps
                else:
                    self.current_steps = []
                self._stop_simulation()
                self._update_views()
                if self._current_mode == "editor":
                    self._populate_table()
                break

    def _create_workflow(self) -> None:
        name, ok = QInputDialog.getText(self, "New Workflow", "Workflow name:")
        if not ok or not name.strip():
            return
        pid = self.store.current_project_id
        wf = create(Workflow, name=name.strip(), projectId=pid or "",
                     description="", steps="[]", status="draft")
        if wf:
            self.store.reload("workflows")
            self._populate_workflow_combo()
            # Select the new workflow
            for i in range(self.workflow_combo.count()):
                if self.workflow_combo.itemData(i) == wf["id"]:
                    self.workflow_combo.setCurrentIndex(i)
                    break

    def _duplicate_workflow(self) -> None:
        if not self.current_workflow:
            return
        name, ok = QInputDialog.getText(
            self, "Duplicate Workflow", "New name:",
            text=self.current_workflow["name"] + " (copy)")
        if not ok or not name.strip():
            return
        steps = json.dumps(self.current_steps)
        wf = create(Workflow, name=name.strip(),
                     projectId=self.current_workflow.get("projectId", ""),
                     description=self.current_workflow.get("description", ""),
                     steps=steps, status="draft")
        if wf:
            self.store.reload("workflows")
            self._populate_workflow_combo()
            for i in range(self.workflow_combo.count()):
                if self.workflow_combo.itemData(i) == wf["id"]:
                    self.workflow_combo.setCurrentIndex(i)
                    break

    def _show_status_menu(self) -> None:
        if not self.current_workflow:
            return
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background: {BG_CARD}; color: {FG_PRIMARY}; border: 1px solid {BORDER};
                     border-radius: {RADIUS}px; padding: 4px; }}
            QMenu::item {{ padding: 8px 24px; border-radius: 4px; }}
            QMenu::item:selected {{ background: {ACCENT}; }}
        """)
        current = self.current_workflow.get("status", "draft")
        for st in WORKFLOW_STATUSES:
            color = STATUS_COLORS.get(st, FG_MUTED)
            action = menu.addAction(f"  {st.upper()}")
            action.setData(st)
            if st == current:
                font = action.font()
                font.setBold(True)
                action.setFont(font)
        chosen = menu.exec(self.btn_status.mapToGlobal(
            self.btn_status.rect().bottomLeft()))
        if chosen:
            new_status = chosen.data()
            if new_status and new_status != current:
                update(Workflow, self.current_workflow["id"], status=new_status)
                self.store.reload("workflows")
                # Re-select to refresh
                self._on_workflow_selected(self.workflow_combo.currentIndex())

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------
    def _show_templates_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background: {BG_CARD}; color: {FG_PRIMARY}; border: 1px solid {BORDER};
                     border-radius: {RADIUS}px; padding: 4px; }}
            QMenu::item {{ padding: 10px 24px; border-radius: 4px; font-size: 13px; }}
            QMenu::item:selected {{ background: {ACCENT}; }}
        """)
        for tmpl_name in WORKFLOW_TEMPLATES:
            action = menu.addAction(f"  📋 {tmpl_name}")
            action.setData(tmpl_name)
        chosen = menu.exec(self.btn_templates.mapToGlobal(
            self.btn_templates.rect().bottomLeft()))
        if chosen:
            tmpl_name = chosen.data()
            self._apply_template(tmpl_name)

    def _apply_template(self, template_name: str) -> None:
        if template_name not in WORKFLOW_TEMPLATES:
            return
        tmpl_steps = WORKFLOW_TEMPLATES[template_name]
        # Generate unique IDs for each step
        steps = []
        for s in tmpl_steps:
            step = dict(s)
            step["id"] = str(uuid.uuid4())[:8]
            step.setdefault("config", {})
            step.setdefault("branchTo", "")
            step.setdefault("parallelGroup", "")
            step.setdefault("parallelBranch", "")
            steps.append(step)

        pid = self.store.current_project_id
        wf = create(Workflow, name=template_name, projectId=pid or "",
                     description=f"Created from template: {template_name}",
                     steps=json.dumps(steps), status="draft")
        if wf:
            self.store.reload("workflows")
            self._populate_workflow_combo()
            for i in range(self.workflow_combo.count()):
                if self.workflow_combo.itemData(i) == wf["id"]:
                    self.workflow_combo.setCurrentIndex(i)
                    break

    # ------------------------------------------------------------------
    # Diagram interaction
    # ------------------------------------------------------------------
    def _on_diagram_step_clicked(self, index: int) -> None:
        self._show_step_config(index)
        if self._current_mode == "editor":
            self.steps_table.selectRow(index)

    # ------------------------------------------------------------------
    # Editor table
    # ------------------------------------------------------------------
    def _populate_table(self) -> None:
        self.steps_table.blockSignals(True)
        self.steps_table.setRowCount(len(self.current_steps))
        for i, step in enumerate(self.current_steps):
            # Name
            name_item = QTableWidgetItem(step.get("name", ""))
            name_item.setData(Qt.ItemDataRole.UserRole, i)
            self.steps_table.setItem(i, 0, name_item)

            # Type combo
            type_combo = QComboBox()
            type_combo.addItems(STEP_TYPES)
            current_type = step.get("type", "process")
            idx = STEP_TYPES.index(current_type) if current_type in STEP_TYPES else 1
            type_combo.setCurrentIndex(idx)
            type_combo.setProperty("row", i)
            type_combo.currentTextChanged.connect(
                lambda text, row=i: self._on_editor_type_changed(row, text))
            self.steps_table.setCellWidget(i, 1, type_combo)

            # Description
            desc_item = QTableWidgetItem(step.get("description", ""))
            self.steps_table.setItem(i, 2, desc_item)

            # Branch To combo
            branch_combo = QComboBox()
            branch_combo.addItem("— None —", "")
            for j, s in enumerate(self.current_steps):
                if j != i:
                    branch_combo.addItem(s.get("name", f"Step {j + 1}"), s.get("id", ""))
            current_branch = step.get("branchTo", "")
            for bi in range(branch_combo.count()):
                if branch_combo.itemData(bi) == current_branch:
                    branch_combo.setCurrentIndex(bi)
                    break
            branch_combo.currentIndexChanged.connect(
                lambda _, row=i, cb=branch_combo: self._on_editor_branch_changed(row, cb))
            self.steps_table.setCellWidget(i, 3, branch_combo)

            # Parallel Group
            pg_item = QTableWidgetItem(step.get("parallelGroup", ""))
            self.steps_table.setItem(i, 4, pg_item)

            # Parallel Branch combo
            pb_combo = QComboBox()
            pb_combo.addItems(["None", "A", "B", "C", "D"])
            current_pb = step.get("parallelBranch", "")
            if current_pb:
                pb_idx = pb_combo.findText(current_pb)
                if pb_idx >= 0:
                    pb_combo.setCurrentIndex(pb_idx)
            pb_combo.currentTextChanged.connect(
                lambda text, row=i: self._on_editor_pbranch_changed(row, text))
            self.steps_table.setCellWidget(i, 5, pb_combo)

            # Config (simplified display)
            config = step.get("config", {})
            if isinstance(config, dict):
                config_str = json.dumps(config) if config else ""
            else:
                config_str = str(config)
            config_item = QTableWidgetItem(config_str)
            self.steps_table.setItem(i, 6, config_item)

        self.steps_table.blockSignals(False)

        # Resize columns
        self.steps_table.setColumnWidth(0, 150)
        self.steps_table.setColumnWidth(1, 100)
        self.steps_table.setColumnWidth(2, 180)
        self.steps_table.setColumnWidth(3, 130)
        self.steps_table.setColumnWidth(4, 110)
        self.steps_table.setColumnWidth(5, 80)
        self.steps_table.setColumnWidth(6, 160)

    def _on_editor_type_changed(self, row: int, text: str) -> None:
        if 0 <= row < len(self.current_steps):
            self.current_steps[row]["type"] = text
            self._persist_steps()

    def _on_editor_branch_changed(self, row: int, combo: QComboBox) -> None:
        if 0 <= row < len(self.current_steps):
            self.current_steps[row]["branchTo"] = combo.currentData() or ""
            self._persist_steps()

    def _on_editor_pbranch_changed(self, row: int, text: str) -> None:
        if 0 <= row < len(self.current_steps):
            self.current_steps[row]["parallelBranch"] = text if text != "None" else ""
            self._persist_steps()

    def _on_table_selection_changed(self, row: int, _col: int, _prev_row: int, _prev_col: int) -> None:
        if 0 <= row < len(self.current_steps):
            self._show_step_config(row)
            self.diagram_widget.set_selected(row)

    def _on_table_cell_changed(self, row: int, col: int) -> None:
        if not self.current_workflow or row < 0 or row >= len(self.current_steps):
            return
        item = self.steps_table.item(row, col)
        if item is None:
            return
        text = item.text()
        if col == 0:
            self.current_steps[row]["name"] = text
            self._persist_steps()
        elif col == 2:
            self.current_steps[row]["description"] = text
            self._persist_steps()
        elif col == 4:
            self.current_steps[row]["parallelGroup"] = text
            self._persist_steps()
        elif col == 6:
            try:
                config = json.loads(text) if text else {}
            except Exception:
                config = {}
            self.current_steps[row]["config"] = config
            self._persist_steps()

    # ------------------------------------------------------------------
    # Step CRUD (editor)
    # ------------------------------------------------------------------
    def _add_step(self) -> None:
        if not self.current_workflow:
            return
        step = {
            "id": str(uuid.uuid4())[:8],
            "name": f"Step {len(self.current_steps) + 1}",
            "type": "process",
            "config": {},
            "branchTo": "",
            "parallelGroup": "",
            "parallelBranch": "",
            "description": "",
        }
        self.current_steps.append(step)
        self._persist_steps()
        self._populate_table()
        self._update_views()
        # Select the new row
        self.steps_table.selectRow(len(self.current_steps) - 1)

    def _delete_step(self) -> None:
        if not self.current_workflow:
            return
        row = self.steps_table.currentRow()
        if row < 0 or row >= len(self.current_steps):
            return
        self.current_steps.pop(row)
        self._persist_steps()
        self._populate_table()
        self._update_views()
        self._set_config_visible(False)
        self.diagram_widget.set_selected(-1)

    def _duplicate_step(self) -> None:
        if not self.current_workflow:
            return
        row = self.steps_table.currentRow()
        if row < 0 or row >= len(self.current_steps):
            return
        original = dict(self.current_steps[row])
        original["id"] = str(uuid.uuid4())[:8]
        original["name"] = original.get("name", "") + " (copy)"
        self.current_steps.insert(row + 1, original)
        self._persist_steps()
        self._populate_table()
        self._update_views()
        self.steps_table.selectRow(row + 1)

    def _move_step_up(self) -> None:
        if not self.current_workflow:
            return
        row = self.steps_table.currentRow()
        if row <= 0:
            return
        self.current_steps[row - 1], self.current_steps[row] = \
            self.current_steps[row], self.current_steps[row - 1]
        self._persist_steps()
        self._populate_table()
        self._update_views()
        self.steps_table.selectRow(row - 1)

    def _move_step_down(self) -> None:
        if not self.current_workflow:
            return
        row = self.steps_table.currentRow()
        if row < 0 or row >= len(self.current_steps) - 1:
            return
        self.current_steps[row], self.current_steps[row + 1] = \
            self.current_steps[row + 1], self.current_steps[row]
        self._persist_steps()
        self._populate_table()
        self._update_views()
        self.steps_table.selectRow(row + 1)

    # ------------------------------------------------------------------
    # Step configuration panel
    # ------------------------------------------------------------------
    def _show_step_config(self, index: int) -> None:
        if index < 0 or index >= len(self.current_steps):
            self._set_config_visible(False)
            return
        step = self.current_steps[index]
        self._set_config_visible(True)
        self._config_step_index = index

        self.cfg_name.blockSignals(True)
        self.cfg_type.blockSignals(True)
        self.cfg_desc.blockSignals(True)
        self.cfg_pgroup.blockSignals(True)
        self.cfg_pbranch.blockSignals(True)
        self.cfg_json.blockSignals(True)

        self.cfg_name.setText(step.get("name", ""))
        stype = step.get("type", "process")
        tidx = STEP_TYPES.index(stype) if stype in STEP_TYPES else 1
        self.cfg_type.setCurrentIndex(tidx)
        self.cfg_desc.setText(step.get("description", ""))
        self.cfg_pgroup.setText(step.get("parallelGroup", ""))

        # Branch To dropdown
        self.cfg_branch.blockSignals(True)
        self.cfg_branch.clear()
        self.cfg_branch.addItem("— None —", "")
        for j, s in enumerate(self.current_steps):
            if j != index:
                self.cfg_branch.addItem(s.get("name", f"Step {j + 1}"), s.get("id", ""))
        branch_to = step.get("branchTo", "")
        for bi in range(self.cfg_branch.count()):
            if self.cfg_branch.itemData(bi) == branch_to:
                self.cfg_branch.setCurrentIndex(bi)
                break
        self.cfg_branch.blockSignals(False)

        # Parallel Branch
        pb = step.get("parallelBranch", "")
        pb_idx = self.cfg_pbranch.findText(pb) if pb else 0
        if pb_idx < 0:
            pb_idx = 0
        self.cfg_pbranch.setCurrentIndex(pb_idx)

        # Config JSON
        config = step.get("config", {})
        if isinstance(config, dict):
            self.cfg_json.setPlainText(json.dumps(config, indent=2) if config else "")
        else:
            self.cfg_json.setPlainText(str(config))

        self.cfg_name.blockSignals(False)
        self.cfg_type.blockSignals(False)
        self.cfg_desc.blockSignals(False)
        self.cfg_pgroup.blockSignals(False)
        self.cfg_pbranch.blockSignals(False)
        self.cfg_json.blockSignals(False)

    def _on_cfg_type_changed(self, text: str) -> None:
        if hasattr(self, '_config_step_index') and 0 <= self._config_step_index < len(self.current_steps):
            self.current_steps[self._config_step_index]["type"] = text
            self._persist_steps()
            self._update_views()
            if self._current_mode == "editor":
                self._populate_table()

    def _save_step_config(self) -> None:
        if not hasattr(self, '_config_step_index'):
            return
        idx = self._config_step_index
        if idx < 0 or idx >= len(self.current_steps):
            return

        self.current_steps[idx]["name"] = self.cfg_name.text().strip() or f"Step {idx + 1}"
        self.current_steps[idx]["type"] = self.cfg_type.currentText()
        self.current_steps[idx]["description"] = self.cfg_desc.text()
        self.current_steps[idx]["branchTo"] = self.cfg_branch.currentData() or ""
        self.current_steps[idx]["parallelGroup"] = self.cfg_pgroup.text().strip()
        pb = self.cfg_pbranch.currentText()
        self.current_steps[idx]["parallelBranch"] = pb if pb != "None" else ""

        # Parse config JSON
        json_text = self.cfg_json.toPlainText().strip()
        try:
            config = json.loads(json_text) if json_text else {}
        except Exception:
            config = {}
        self.current_steps[idx]["config"] = config

        self._persist_steps()
        self._update_views()
        if self._current_mode == "editor":
            self._populate_table()
        self.steps_table.selectRow(idx)

    def _set_config_visible(self, visible: bool) -> None:
        """Toggle between config fields and placeholder."""
        for w in [self.cfg_name, self.cfg_type, self.cfg_desc,
                  self.cfg_branch, self.cfg_pgroup, self.cfg_pbranch,
                  self.cfg_json, self.btn_save_step]:
            # Find the label preceding each widget in the layout
            w.setVisible(visible)
        self.cfg_placeholder.setVisible(not visible)
        # Also toggle labels (they are QLabels in the layout)
        config_layout = self.config_panel.layout()
        for i in range(config_layout.count()):
            item = config_layout.itemAt(i)
            if item.widget() and isinstance(item.widget(), QLabel):
                lbl = item.widget()
                text = lbl.text()
                if text in ("Name", "Type", "Description", "Branch To (decision)",
                            "Parallel Group", "Parallel Branch", "Config (JSON)"):
                    lbl.setVisible(visible)

    # ------------------------------------------------------------------
    # Persist steps
    # ------------------------------------------------------------------
    def _persist_steps(self) -> None:
        if not self.current_workflow:
            return
        result = update(Workflow, self.current_workflow["id"], steps=self.current_steps)
        if result:
            self.current_workflow = result
            self.store.reload("workflows")

    def _save_description(self) -> None:
        if not self.current_workflow:
            return
        desc = self.desc_edit.toPlainText()
        result = update(Workflow, self.current_workflow["id"], description=desc)
        if result:
            self.current_workflow = result
            self.store.reload("workflows")

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------
    def _update_stats(self) -> None:
        steps = self.current_steps
        total = len(steps)
        self.stat_total.setText(f"Total steps: {total}")

        if self.current_workflow:
            status = self.current_workflow.get("status", "draft")
            sc = STATUS_COLORS.get(status, FG_MUTED)
            self.stat_status.setText(f"Status: {status.upper()}")
            self.stat_status.setStyleSheet(f"color: {sc}; font-size: 12px; font-weight: 600;")
        else:
            self.stat_status.setText("Status: —")
            self.stat_status.setStyleSheet(f"color: {FG_MUTED}; font-size: 12px;")

        # Clear old bars
        while self.type_bars_layout.count():
            item = self.type_bars_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if total == 0:
            return

        type_counts = Counter(s.get("type", "process") for s in steps)
        max_count = max(type_counts.values()) if type_counts else 1

        for stype in STEP_TYPES:
            count = type_counts.get(stype, 0)
            if count == 0:
                continue
            color = STEP_TYPE_COLORS.get(stype, INFO)

            row_layout = QHBoxLayout()
            row_layout.setSpacing(8)
            row_layout.setContentsMargins(0, 0, 0, 0)

            label = QLabel(f"{stype}")
            label.setFixedWidth(70)
            label.setStyleSheet(f"color: {FG_SECONDARY}; font-size: 11px;")
            row_layout.addWidget(label)

            bar_bg = QFrame()
            bar_bg.setFixedHeight(14)
            bar_bg.setStyleSheet(f"background: {BG_INPUT}; border-radius: 3px;")
            bar_bg.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            bar_layout = QHBoxLayout(bar_bg)
            bar_layout.setContentsMargins(0, 0, 0, 0)
            bar_layout.setSpacing(0)

            bar_fill = QFrame()
            width_pct = int((count / max_count) * 100) if max_count > 0 else 0
            bar_fill.setFixedWidth(max(width_pct, 8))
            bar_fill.setFixedHeight(14)
            bar_fill.setStyleSheet(
                f"background: {color}; border-radius: 3px;"
            )
            bar_layout.addWidget(bar_fill)
            bar_layout.addStretch()
            row_layout.addWidget(bar_bg)

            count_label = QLabel(str(count))
            count_label.setFixedWidth(20)
            count_label.setStyleSheet(f"color: {FG_MUTED}; font-size: 11px;")
            row_layout.addWidget(count_label)

            row_widget = QWidget()
            row_widget.setLayout(row_layout)
            self.type_bars_layout.addWidget(row_widget)

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------
    def _start_simulation(self) -> None:
        if not self.current_steps:
            return
        self._sim_running = True
        self._sim_index = 0
        self.btn_simulate.setVisible(False)
        self.btn_stop_sim.setVisible(True)
        self._set_mode("diagram")
        self.diagram_widget.set_sim_step(0)
        step = self.current_steps[0]
        self.sim_status_label.setText(
            f"▶ Step 1/{len(self.current_steps)}: {step.get('name', '')}"
        )
        self._sim_timer.start()

    def _sim_next_step(self) -> None:
        if not self._sim_running:
            return
        self._sim_index += 1
        if self._sim_index >= len(self.current_steps):
            self._stop_simulation()
            self.sim_status_label.setText("✅ Simulation complete")
            return
        self.diagram_widget.set_sim_step(self._sim_index)
        step = self.current_steps[self._sim_index]
        desc = step.get("description", "")
        label = f"▶ Step {self._sim_index + 1}/{len(self.current_steps)}: {step.get('name', '')}"
        if desc:
            label += f" — {desc}"
        self.sim_status_label.setText(label)

    def _stop_simulation(self) -> None:
        self._sim_running = False
        self._sim_timer.stop()
        self._sim_index = -1
        self.diagram_widget.set_sim_step(-1)
        self.btn_simulate.setVisible(True)
        self.btn_stop_sim.setVisible(False)
        self.sim_status_label.setText("")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def hideEvent(self, event) -> None:
        self._stop_simulation()
        super().hideEvent(event)