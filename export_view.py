"""DataForge – Export Center view with multi-format export and ZIP archive."""

from __future__ import annotations

import json, csv, io, os, zipfile, datetime as dt
from collections import Counter
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QComboBox, QTextEdit, QFileDialog, QMessageBox, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QGroupBox, QCheckBox, QRadioButton, QButtonGroup, QScrollArea,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor

from models import Annotation, Dataset, Workflow, Project, Tutorial, RLModel, Review, LabelSchema, Team, ActivityLog
from store import Store
from models import (
    BG_DARK, BG_CARD, BG_HOVER, BG_INPUT, FG_PRIMARY, FG_SECONDARY,
    FG_MUTED, ACCENT, ACCENT2, BORDER, SUCCESS, WARNING, DANGER, INFO, RADIUS,
)
from dashboard_projects import make_section_header, make_button, make_btn_secondary


# ═══════════════════════════════════════════════════════════════════════════
#  Export formats
# ═══════════════════════════════════════════════════════════════════════════
FORMATS = {
    "jsonl": "JSONL – JSON Lines (one annotation per line)",
    "json": "JSON – Full JSON array",
    "csv": "CSV – Comma-separated values",
    "coco": "COCO – Common Objects in Context format",
    "pascal_voc": "Pascal VOC – XML-based annotation format",
}


def annotations_to_jsonl(annotations: list[dict]) -> str:
    """Convert annotations to JSONL format."""
    lines = []
    for ann in annotations:
        record = {
            "id": ann["id"],
            "dataIndex": ann.get("dataIndex", 0),
            "labels": ann.get("labels", []),
            "confidence": ann.get("confidence", 1.0),
            "annotator": ann.get("annotator", ""),
            "status": ann.get("status", "pending"),
            "notes": ann.get("notes", ""),
            "createdAt": ann.get("createdAt", ""),
        }
        lines.append(json.dumps(record))
    return "\n".join(lines)


def annotations_to_json(annotations: list[dict]) -> str:
    """Convert annotations to JSON array format."""
    records = []
    for ann in annotations:
        records.append({
            "id": ann["id"],
            "dataIndex": ann.get("dataIndex", 0),
            "labels": ann.get("labels", []),
            "confidence": ann.get("confidence", 1.0),
            "annotator": ann.get("annotator", ""),
            "status": ann.get("status", "pending"),
            "notes": ann.get("notes", ""),
            "createdAt": ann.get("createdAt", ""),
        })
    return json.dumps(records, indent=2)


def annotations_to_csv(annotations: list[dict]) -> str:
    """Convert annotations to CSV format."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "dataIndex", "labels", "confidence", "annotator", "status", "notes", "createdAt"])
    for ann in annotations:
        writer.writerow([
            ann["id"],
            ann.get("dataIndex", 0),
            json.dumps(ann.get("labels", [])),
            ann.get("confidence", 1.0),
            ann.get("annotator", ""),
            ann.get("status", "pending"),
            ann.get("notes", ""),
            ann.get("createdAt", ""),
        ])
    return output.getvalue()


def annotations_to_coco(annotations: list[dict]) -> str:
    """Convert annotations to COCO format."""
    coco = {
        "info": {"description": "DataForge COCO Export", "version": "1.0",
                 "date_created": dt.datetime.utcnow().isoformat() + "Z"},
        "licenses": [],
        "categories": [],
        "images": [],
        "annotations": [],
    }
    label_set = set()
    for ann in annotations:
        for label in ann.get("labels", []):
            label_set.add(label)
    for i, label in enumerate(sorted(label_set)):
        coco["categories"].append({"id": i + 1, "name": label, "supercategory": "object"})
    label_map = {name: i + 1 for i, name in enumerate(sorted(label_set))}
    for idx, ann in enumerate(annotations):
        coco["images"].append({"id": idx + 1, "file_name": f"data_{ann.get('dataIndex', 0)}.jpg",
                               "width": 640, "height": 480})
        for label in ann.get("labels", []):
            cat_id = label_map.get(label, 0)
            coco["annotations"].append({
                "id": len(coco["annotations"]) + 1,
                "image_id": idx + 1,
                "category_id": cat_id,
                "bbox": [0, 0, 100, 100],
                "area": 10000,
                "iscrowd": 0,
            })
    return json.dumps(coco, indent=2)


def annotations_to_pascal_voc(annotations: list[dict]) -> str:
    """Convert annotations to Pascal VOC XML format."""
    xml_parts = []
    xml_parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    xml_parts.append('<annotations>')
    for ann in annotations:
        xml_parts.append(f'  <annotation id="{ann["id"]}">')
        xml_parts.append(f'    <dataIndex>{ann.get("dataIndex", 0)}</dataIndex>')
        xml_parts.append(f'    <annotator>{ann.get("annotator", "")}</annotator>')
        xml_parts.append(f'    <status>{ann.get("status", "")}</status>')
        for label in ann.get("labels", []):
            xml_parts.append(f'    <object>')
            xml_parts.append(f'      <name>{label}</name>')
            xml_parts.append(f'      <bndbox><xmin>0</xmin><ymin>0</ymin><xmax>100</xmax><ymax>100</ymax></bndbox>')
            xml_parts.append(f'    </object>')
        xml_parts.append(f'  </annotation>')
    xml_parts.append('</annotations>')
    return "\n".join(xml_parts)


EXPORT_FUNCTIONS = {
    "jsonl": annotations_to_jsonl,
    "json": annotations_to_json,
    "csv": annotations_to_csv,
    "coco": annotations_to_coco,
    "pascal_voc": annotations_to_pascal_voc,
}


# ═══════════════════════════════════════════════════════════════════════════
#  ZIP Archive Builder
# ═══════════════════════════════════════════════════════════════════════════
def build_zip_archive(store: Store, output_path: str) -> None:
    """Build a comprehensive ZIP archive of all project data."""
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Annotations in all formats
        annotations = store.annotations
        if annotations:
            zf.writestr("exports/annotations.jsonl", annotations_to_jsonl(annotations))
            zf.writestr("exports/annotations.json", annotations_to_json(annotations))
            zf.writestr("exports/annotations.csv", annotations_to_csv(annotations))
            zf.writestr("exports/annotations_coco.json", annotations_to_coco(annotations))
            zf.writestr("exports/annotations_pascal_voc.xml", annotations_to_pascal_voc(annotations))

        # Projects
        zf.writestr("projects.json", json.dumps(store.projects, indent=2, default=str))

        # Workflows
        zf.writestr("workflows.json", json.dumps(store.workflows, indent=2, default=str))

        # Datasets
        zf.writestr("datasets.json", json.dumps(store.datasets, indent=2, default=str))

        # Tutorials
        tutorials_export = []
        for tut in store.tutorials:
            t = dict(tut)
            t["steps"] = store.tutorial_steps_for(tut["id"])
            tutorials_export.append(t)
        zf.writestr("tutorials.json", json.dumps(tutorials_export, indent=2, default=str))

        # RL Models
        zf.writestr("rl_models.json", json.dumps(store.rl_models, indent=2, default=str))

        # Reviews
        zf.writestr("reviews.json", json.dumps(store.reviews, indent=2, default=str))

        # Labels
        zf.writestr("labels.json", json.dumps(store.labels, indent=2, default=str))

        # Teams (with members)
        teams_export = []
        for team in store.teams:
            t = dict(team)
            t["members"] = store.team_members_for(team["id"])
            teams_export.append(t)
        zf.writestr("teams.json", json.dumps(teams_export, indent=2, default=str))

        # Activities
        zf.writestr("activity_logs.json", json.dumps(store.activities, indent=2, default=str))

        # Metadata
        metadata = {
            "version": "1.0.0",
            "platform": "DataForge Desktop (PySide6)",
            "exportDate": dt.datetime.utcnow().isoformat() + "Z",
            "stats": {
                "projects": len(store.projects),
                "annotations": len(store.annotations),
                "workflows": len(store.workflows),
                "datasets": len(store.datasets),
                "tutorials": len(store.tutorials),
                "rlModels": len(store.rl_models),
                "teams": len(store.teams),
                "labels": len(store.labels),
                "reviews": len(store.reviews),
                "activities": len(store.activities),
            }
        }
        zf.writestr("metadata.json", json.dumps(metadata, indent=2))

        # README
        readme = """# DataForge Export Archive

This archive contains all data exported from DataForge Desktop.

## Contents
- `exports/` - Annotations in multiple formats (JSONL, JSON, CSV, COCO, Pascal VOC)
- `projects.json` - All projects
- `workflows.json` - All workflows with step definitions
- `datasets.json` - All datasets
- `tutorials.json` - Tutorials with steps
- `rl_models.json` - RL training models and metrics
- `reviews.json` - QA review records
- `labels.json` - Label schemas
- `teams.json` - Teams with members
- `activity_logs.json` - Activity log entries
- `metadata.json` - Export metadata and statistics

Generated by DataForge Desktop v1.0
"""
        zf.writestr("README.md", readme)


# ═══════════════════════════════════════════════════════════════════════════
#  Export Thread (for async ZIP generation)
# ═══════════════════════════════════════════════════════════════════════════
class ExportThread(QThread):
    progress = Signal(int)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, store: Store, output_path: str):
        super().__init__()
        self.store = store
        self.output_path = output_path

    def run(self):
        try:
            self.progress.emit(10)
            build_zip_archive(self.store, self.output_path)
            self.progress.emit(90)
            self.finished.emit(self.output_path)
            self.progress.emit(100)
        except Exception as e:
            self.error.emit(str(e))


# ═══════════════════════════════════════════════════════════════════════════
#  EXPORT CENTER VIEW
# ═══════════════════════════════════════════════════════════════════════════
class ExportCenterView(QWidget):
    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(24)

        header = QHBoxLayout()
        title = QLabel("Export Center")
        title.setStyleSheet(f"color: {FG_PRIMARY}; font-size: 26px; font-weight: 800;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # Stats summary
        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)
        for label, count, color in [
            ("Annotations", len(self.store.annotations), ACCENT),
            ("Projects", len(self.store.projects), SUCCESS),
            ("Workflows", len(self.store.workflows), ACCENT2),
            ("Datasets", len(self.store.datasets), INFO),
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
            stats_row.addWidget(card)
        layout.addLayout(stats_row)

        # Two columns
        cols = QHBoxLayout()
        cols.setSpacing(16)

        # Left: Format export
        left_frame = QFrame()
        left_frame.setStyleSheet(f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS}px; }}")
        left_l = QVBoxLayout(left_frame)
        left_l.setContentsMargins(24, 20, 24, 20)
        left_l.setSpacing(16)

        left_l.addWidget(make_section_header("Export Annotations"))

        # Format selection
        self.format_combo = QComboBox()
        for fmt_key, desc in FORMATS.items():
            self.format_combo.addItem(desc, fmt_key)
        self.format_combo.setFixedHeight(40)
        self.format_combo.setStyleSheet(f"""
            QComboBox {{ padding: 10px 16px; font-size: 13px; }}
        """)
        left_l.addWidget(QLabel("Select Format:"))
        left_l.addWidget(self.format_combo)

        # Project filter
        self.project_combo = QComboBox()
        self.project_combo.addItem("All Projects", "all")
        for p in self.store.projects:
            self.project_combo.addItem(p["name"], p["id"])
        self.project_combo.setFixedHeight(40)
        left_l.addWidget(QLabel("Filter by Project:"))
        left_l.addWidget(self.project_combo)

        # Preview
        left_l.addWidget(make_section_header("Preview"))
        self.preview_area = QTextEdit()
        self.preview_area.setReadOnly(True)
        self.preview_area.setMaximumHeight(250)
        self.preview_area.setStyleSheet(f"""
            QTextEdit {{ background: {BG_INPUT}; color: {FG_PRIMARY}; border: 1px solid {BORDER};
                border-radius: 6px; font-family: 'Consolas', 'Monaco', monospace; font-size: 12px; padding: 12px; }}
        """)
        self.preview_area.setPlainText("// Select a format and click Preview")
        left_l.addWidget(self.preview_area)

        # Preview button
        preview_btn = make_button("Preview", ACCENT, "👁")
        preview_btn.clicked.connect(self._preview)
        left_l.addWidget(preview_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # Export single format button
        export_btn = make_button("Export Selected Format", SUCCESS, "💾")
        export_btn.clicked.connect(self._export_format)
        left_l.addWidget(export_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        cols.addWidget(left_frame, 1)

        # Right: ZIP export
        right_frame = QFrame()
        right_frame.setStyleSheet(f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS}px; }}")
        right_l = QVBoxLayout(right_frame)
        right_l.setContentsMargins(24, 20, 24, 20)
        right_l.setSpacing(16)

        right_l.addWidget(make_section_header("Download ZIP Archive"))

        desc = QLabel("Export ALL project data as a comprehensive ZIP archive including annotations in all formats, projects, workflows, datasets, tutorials, RL models, reviews, labels, teams, and activity logs.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {FG_SECONDARY}; font-size: 13px; line-height: 1.5;")
        right_l.addWidget(desc)

        # ZIP contents preview
        contents_frame = QFrame()
        contents_frame.setStyleSheet(f"QFrame {{ background: {BG_INPUT}; border-radius: 6px; }}")
        cl = QVBoxLayout(contents_frame)
        cl.setContentsMargins(16, 12, 16, 12)
        cl.setSpacing(4)

        zip_contents = [
            ("📁 exports/", "5 annotation files (JSONL, JSON, CSV, COCO, Pascal VOC)"),
            ("📄 projects.json", "All project configurations"),
            ("🔀 workflows.json", "Workflow definitions and steps"),
            ("📊 datasets.json", "Dataset metadata and data"),
            ("📖 tutorials.json", "Tutorial content with steps"),
            ("🤖 rl_models.json", "RL model configs and metrics"),
            ("✅ reviews.json", "QA review records"),
            ("🏷️ labels.json", "Label schemas with hierarchy"),
            ("👥 teams.json", "Teams with members"),
            ("📋 activity_logs.json", "Activity log entries"),
            ("📋 metadata.json", "Export metadata and stats"),
            ("📄 README.md", "Archive documentation"),
        ]
        for icon_text, desc_text in zip_contents:
            row = QHBoxLayout()
            item_lbl = QLabel(f"  {icon_text}")
            item_lbl.setStyleSheet(f"color: {FG_PRIMARY}; font-size: 12px; font-family: monospace;")
            row.addWidget(item_lbl)
            row.addStretch()
            cl.addLayout(row)

        right_l.addWidget(contents_frame)

        # Progress bar for ZIP
        self.zip_progress = QProgressBar()
        self.zip_progress.setValue(0)
        self.zip_progress.setFormat("Ready to export")
        self.zip_progress.setVisible(False)
        self.zip_progress.setStyleSheet(f"""
            QProgressBar {{ background: {BG_INPUT}; border-radius: 4px; text-align: center;
                color: {FG_PRIMARY}; font-size: 12px; height: 24px; border: 1px solid {BORDER}; }}
            QProgressBar::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {ACCENT},stop:1 {ACCENT2}); border-radius: 4px; }}
        """)
        right_l.addWidget(self.zip_progress)

        # ZIP download button
        self.zip_btn = make_button("Download ZIP", ACCENT2, "📦")
        self.zip_btn.clicked.connect(self._download_zip)
        right_l.addWidget(self.zip_btn)

        # Status label
        self.zip_status = QLabel("")
        self.zip_status.setStyleSheet(f"color: {FG_MUTED}; font-size: 12px;")
        right_l.addWidget(self.zip_status)

        right_l.addStretch()
        cols.addWidget(right_frame, 1)

        layout.addLayout(cols)
        layout.addStretch()

    def _get_filtered_annotations(self) -> list[dict]:
        proj_id = self.project_combo.currentData()
        if proj_id == "all":
            return self.store.annotations
        return self.store.project_annotations(proj_id)

    def _preview(self):
        fmt = self.format_combo.currentData()
        annotations = self._get_filtered_annotations()
        if not annotations:
            self.preview_area.setPlainText("// No annotations found for the selected project.")
            return
        func = EXPORT_FUNCTIONS.get(fmt, annotations_to_json)
        content = func(annotations)
        # Show first 5000 chars
        self.preview_area.setPlainText(content[:5000] + ("\n... (truncated)" if len(content) > 5000 else ""))

    def _export_format(self):
        fmt = self.format_combo.currentData()
        annotations = self._get_filtered_annotations()
        if not annotations:
            QMessageBox.information(self, "Export", "No annotations to export.")
            return
        func = EXPORT_FUNCTIONS.get(fmt, annotations_to_json)
        content = func(annotations)

        ext_map = {"jsonl": "jsonl", "json": "json", "csv": "csv", "coco": "json", "pascal_voc": "xml"}
        ext = ext_map.get(fmt, "json")

        default_path = os.path.expanduser(f"~/dataforge_annotations_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}")
        path, _ = QFileDialog.getSaveFileName(self, f"Export as {ext.upper()}", default_path,
                                               f"{ext.upper()} files (*.{ext})")
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            QMessageBox.information(self, "Export Complete", f"Exported {len(annotations)} annotations to:\n{path}")

    def _download_zip(self):
        default_path = os.path.expanduser(f"~/dataforge_export_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")
        path, _ = QFileDialog.getSaveFileName(self, "Save ZIP Archive", default_path, "ZIP files (*.zip)")
        if not path:
            return

        # Show progress
        self.zip_progress.setVisible(True)
        self.zip_progress.setValue(0)
        self.zip_progress.setFormat("Generating archive...")
        self.zip_btn.setEnabled(False)
        self.zip_status.setText("Building archive...")

        # Run in thread
        self._export_thread = ExportThread(self.store, path)
        self._export_thread.progress.connect(self._on_zip_progress)
        self._export_thread.finished.connect(self._on_zip_finished)
        self._export_thread.error.connect(self._on_zip_error)
        self._export_thread.start()

    def _on_zip_progress(self, val: int):
        self.zip_progress.setValue(val)
        self.zip_progress.setFormat(f"Generating... {val}%")

    def _on_zip_finished(self, path: str):
        self.zip_progress.setValue(100)
        self.zip_progress.setFormat("Complete!")
        self.zip_btn.setEnabled(True)
        self.zip_status.setText(f"Archive saved to: {path}")
        self.zip_status.setStyleSheet(f"color: {SUCCESS}; font-size: 12px;")
        QMessageBox.information(self, "ZIP Export Complete",
            f"Archive exported successfully!\n\n{path}\n\nContains all project data in multiple formats.")

    def _on_zip_error(self, err: str):
        self.zip_progress.setVisible(False)
        self.zip_btn.setEnabled(True)
        self.zip_status.setText(f"Error: {err}")
        self.zip_status.setStyleSheet(f"color: {DANGER}; font-size: 12px;")
        QMessageBox.critical(self, "Export Error", f"Failed to create ZIP archive:\n{err}")

    def refresh(self):
        # Update project combo
        current = self.project_combo.currentData()
        self.project_combo.clear()
        self.project_combo.addItem("All Projects", "all")
        for p in self.store.projects:
            self.project_combo.addItem(p["name"], p["id"])
        # Restore selection
        for i in range(self.project_combo.count()):
            if self.project_combo.itemData(i) == current:
                self.project_combo.setCurrentIndex(i)
                break
