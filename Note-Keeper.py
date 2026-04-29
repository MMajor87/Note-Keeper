#!/usr/bin/env python3
"""
Notes App -- standalone PyQt6 desktop application.
Supports text notes, tasks, and attached images.
Notes are saved to ~/notes_app_data.json automatically.
Images are stored as PNG files in ~/notes_app_images/.
"""

import sys
import json
import uuid
import base64
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    import winreg

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QScrollArea,
    QFrame, QButtonGroup, QMessageBox, QFileDialog, QDialog,
    QDialogButtonBox, QCheckBox,
)
from PyQt6.QtCore import Qt, QEvent, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap

DATA_FILE = Path.home() / "notes_app_data.json"
IMAGE_DIR = Path.home() / "notes_app_images"
IMAGE_EXTS = "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp)"
IMAGE_MAX_BYTES = 8 * 1024 * 1024
IMAGE_MAX_PX    = 1600

_STARTUP_REG_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"
_STARTUP_REG_NAME = "NotesApp"


def _startup_app_path() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" "{Path(__file__).resolve()}"'


def is_startup_enabled() -> bool:
    if sys.platform != "win32":
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STARTUP_REG_KEY, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, _STARTUP_REG_NAME)
        winreg.CloseKey(key)
        return True
    except OSError:
        return False


def set_startup_enabled(enabled: bool) -> None:
    if sys.platform != "win32":
        return
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STARTUP_REG_KEY, 0, winreg.KEY_WRITE)
    try:
        if enabled:
            winreg.SetValueEx(key, _STARTUP_REG_NAME, 0, winreg.REG_SZ, _startup_app_path())
        else:
            try:
                winreg.DeleteValue(key, _STARTUP_REG_NAME)
            except FileNotFoundError:
                pass
    finally:
        winreg.CloseKey(key)

# Bright saturated dot colors visible on any dark background
ACCENT_DOTS = [
    ("#e8c87a", "Amber"),
    ("#7ac8a0", "Sage"),
    ("#7aaee8", "Sky"),
    ("#c87ab0", "Rose"),
    ("#a0a0a0", "Ash"),
]
# Matching subtle dark card backgrounds
ACCENT_CARDS = {
    "Amber": "#26231a",
    "Sage":  "#1a2620",
    "Sky":   "#1a2230",
    "Rose":  "#26182a",
    "Ash":   "#202020",
}

STYLESHEET = """
QMainWindow, QWidget#root {
    background-color: #161614;
}
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #3a3a38;
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QPushButton#addBtn {
    background-color: #c8c3ba;
    color: #161614;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#addBtn:hover { background-color: #ddd8cf; }
QPushButton#addBtn:disabled { background-color: #2e2e2c; color: #555; }

QPushButton#imgBtn {
    background: #252522;
    border: 1px solid #3a3835;
    border-radius: 7px;
    padding: 6px 12px;
    font-size: 12px;
    color: #888;
}
QPushButton#imgBtn:hover { border-color: #666; color: #c8c3ba; background: #2c2c28; }
QPushButton#imgBtn[hasImage="true"] {
    border-color: #7aaee8;
    color: #7aaee8;
    background: #1a2230;
}

QPushButton#filterBtn {
    background: transparent;
    border: 1px solid #2e2e2c;
    border-radius: 14px;
    padding: 4px 14px;
    font-size: 12px;
    color: #555;
}
QPushButton#filterBtn:hover { border-color: #555; color: #c8c3ba; }
QPushButton#filterBtn[active="true"] {
    background: #252522;
    border-color: #4a4a48;
    color: #c8c3ba;
    font-weight: 500;
}

QPushButton#typeBtn {
    background: transparent;
    border: none;
    padding: 6px 16px;
    font-size: 13px;
    color: #555;
}
QPushButton#typeBtn[active="true"] {
    background: #252522;
    color: #c8c3ba;
    font-weight: 600;
    border-radius: 6px;
}

QPushButton#clearBtn {
    background: transparent;
    border: 1px solid #2e2e2c;
    border-radius: 14px;
    padding: 4px 14px;
    font-size: 12px;
    color: #555;
}
QPushButton#clearBtn:hover { border-color: #7a2020; color: #e06060; }

QPushButton#iconBtn {
    background: transparent;
    border: none;
    border-radius: 4px;
    color: #444;
    font-size: 14px;
    padding: 2px 6px;
    min-width: 24px;
}
QPushButton#iconBtn:hover { background: #252522; color: #c8c3ba; }

QPushButton#checkBtn {
    border: 1.5px solid #444;
    border-radius: 9px;
    background: transparent;
    min-width: 18px;
    max-width: 18px;
    min-height: 18px;
    max-height: 18px;
    padding: 0;
}
QPushButton#checkBtn[checked="true"] {
    background: #2a5a8a;
    border-color: #2a5a8a;
    color: white;
}

QTextEdit {
    border: none;
    background: transparent;
    padding: 0;
    font-size: 14px;
    font-family: Georgia, serif;
    color: #c8c3ba;
    selection-background-color: #2a4060;
}

QLabel#headTitle {
    font-size: 22px;
    font-family: Georgia, serif;
    color: #c8c3ba;
    font-weight: normal;
}
QLabel#subtitle {
    font-size: 12px;
    color: #444;
}
"""


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_notes():
    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                if _migrate_b64_images(data):
                    save_notes(data)
                return data
        except Exception:
            pass
    return []


def _migrate_b64_images(notes) -> bool:
    """Convert legacy base64 image fields to files. Returns True if anything changed."""
    changed = False
    for note in notes:
        if "image" in note:
            try:
                IMAGE_DIR.mkdir(exist_ok=True)
                raw = base64.b64decode(note["image"])
                filename = f"{note['id']}.png"
                (IMAGE_DIR / filename).write_bytes(raw)
                note["image_file"] = filename
            except Exception:
                pass
            del note["image"]
            changed = True
    return changed


def save_notes(notes, parent_widget=None):
    # FIX 4: error handling on save
    try:
        DATA_FILE.write_text(
            json.dumps(notes, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        QMessageBox.warning(
            parent_widget,
            "Save failed",
            f"Could not save notes to disk:\n{e}\n\nYour changes are still in memory.",
        )


def _load_and_validate_image(path: str) -> QPixmap:
    """Validate size/format and return a (possibly scaled) QPixmap."""
    p = Path(path)
    if p.stat().st_size > IMAGE_MAX_BYTES:
        raise ValueError(
            f"Image is {p.stat().st_size // (1024*1024):.1f} MB. "
            f"Please use an image under {IMAGE_MAX_BYTES // (1024*1024)} MB."
        )
    px = QPixmap(path)
    if px.isNull():
        raise ValueError("File could not be read as an image.")
    if px.width() > IMAGE_MAX_PX or px.height() > IMAGE_MAX_PX:
        px = px.scaled(
            IMAGE_MAX_PX, IMAGE_MAX_PX,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return px


def save_image_file(path: str, note_id: str) -> str:
    """Copy and (if needed) scale an image into IMAGE_DIR. Returns the filename."""
    IMAGE_DIR.mkdir(exist_ok=True)
    px = _load_and_validate_image(path)
    filename = f"{note_id}.png"
    dest = IMAGE_DIR / filename
    if not px.save(str(dest)):
        raise ValueError(f"Could not write image to {dest}")
    return filename


def load_image_pixmap(filename: str) -> QPixmap:
    """Load a QPixmap from IMAGE_DIR by filename."""
    path = IMAGE_DIR / filename
    px = QPixmap(str(path))
    if px.isNull():
        raise ValueError(f"Image file missing or corrupt: {path}")
    return px


def _delete_image_file(filename):
    if filename:
        try:
            (IMAGE_DIR / filename).unlink(missing_ok=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------

class ColorDot(QPushButton):
    def __init__(self, hex_color, label, parent=None):
        super().__init__(parent)
        self._hex = hex_color
        self.setFixedSize(22, 22)
        self.setToolTip(label)
        self.setCheckable(True)
        self._refresh()
        self.toggled.connect(lambda _: self._refresh())

    def _refresh(self):
        ring = f"2.5px solid {self._hex}" if self.isChecked() else "2px solid rgba(255,255,255,0.12)"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._hex};
                border-radius: 11px;
                border: {ring};
            }}
        """)


class ClickableImageLabel(QLabel):
    # FIX 10: proper subclass instead of monkey-patching mousePressEvent
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ImageViewer(QDialog):
    """Full-size image popup."""
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image")
        self.setMinimumSize(300, 200)
        screen = QApplication.primaryScreen().availableGeometry()
        max_w = int(screen.width() * 0.85)
        max_h = int(screen.height() * 0.85)
        scaled = pixmap.scaled(
            max_w, max_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.resize(scaled.width() + 24, scaled.height() + 24)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        lbl = QLabel()
        lbl.setPixmap(scaled)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)
        self.setStyleSheet(
            "QDialog { background: #161614; } QLabel { background: transparent; }"
        )


class NoteCard(QFrame):
    deleted     = pyqtSignal(str)
    toggled     = pyqtSignal(str)
    edited      = pyqtSignal(str, str)
    img_removed = pyqtSignal(str)

    def __init__(self, note, parent=None):
        super().__init__(parent)
        self.note = note
        self._build()

    def _build(self):
        note = self.note

        # FIX 2: safe key access for potentially malformed notes
        note_type = note.get("type", "note")
        note_text = note.get("text", "")
        note_done = note.get("done", False)
        note_color = note.get("color", "Amber")

        # FIX 1: setObjectName BEFORE setStyleSheet so the selector matches
        self.setObjectName("noteCard")
        bg = ACCENT_CARDS.get(note_color, "#26231a")
        if note_done:
            bg = "#1a1a18"
        self.setStyleSheet(f"""
            QFrame#noteCard {{
                background-color: {bg};
                border-radius: 8px;
                border: 1px solid rgba(255,255,255,0.05);
            }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(10)

        if note_type == "task":
            cb = QPushButton("✓" if note_done else "")
            cb.setObjectName("checkBtn")
            cb.setProperty("checked", "true" if note_done else "false")
            cb.setFixedSize(18, 18)
            cb.clicked.connect(self._toggle)
            row.addWidget(cb, 0, Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(6)

        lbl = QLabel(note_text)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lbl.setFont(QFont("Georgia", 13))
        txt_color = "#444" if note_done else "#bfbab1"
        decoration = "line-through" if note_done else "none"
        lbl.setStyleSheet(
            f"color:{txt_color}; text-decoration:{decoration}; background:transparent; border:none;"
        )
        text_col.addWidget(lbl)

        # Image thumbnail
        if note.get("image_file"):
            try:
                px = load_image_pixmap(note["image_file"])
                thumb = px.scaledToWidth(
                    min(340, px.width()), Qt.TransformationMode.SmoothTransformation
                )
                if thumb.height() > 220:
                    thumb = px.scaledToHeight(220, Qt.TransformationMode.SmoothTransformation)
                # FIX 10: use ClickableImageLabel subclass
                img_lbl = ClickableImageLabel()
                img_lbl.setPixmap(thumb)
                img_lbl.setStyleSheet("background:transparent; border:none; border-radius:4px;")
                img_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
                img_lbl.setToolTip("Click to view full size")
                img_lbl.clicked.connect(lambda p=px: ImageViewer(p, self).exec())
                text_col.addWidget(img_lbl)
            except Exception as e:
                err_lbl = QLabel(f"[Image unavailable: {e}]")
                err_lbl.setStyleSheet("color:#7a3a3a; font-size:11px; background:transparent; border:none;")
                text_col.addWidget(err_lbl)

        # Meta row
        meta = QHBoxLayout()
        meta.setSpacing(8)

        type_bg = "#1a2535" if note_type == "task" else "#26221a"
        type_fg = "#5a9fd4" if note_type == "task" else "#c8882a"
        type_lbl = QLabel(note_type)
        type_lbl.setStyleSheet(f"""
            QLabel {{
                background:{type_bg}; color:{type_fg};
                border-radius:9px; padding:1px 8px;
                font-size:11px; font-weight:500; border:none;
            }}
        """)
        meta.addWidget(type_lbl)

        ts = note.get("createdAt", "")
        if ts:
            try:
                dt = datetime.fromisoformat(ts)
                date_str = dt.strftime("%b %-d") if sys.platform != "win32" else dt.strftime("%b %d")
            except Exception:
                date_str = ts[:10]
            d = QLabel(date_str)
            # FIX 12: was #3a3a38 (invisible); bumped to a readable shade
            d.setStyleSheet("color:#6a6a68; font-size:11px; background:transparent; border:none;")
            meta.addWidget(d)

        meta.addStretch()

        if not note_done:
            eb = QPushButton("✎")
            eb.setObjectName("iconBtn")
            eb.setFixedSize(26, 22)
            eb.setToolTip("Edit text")
            eb.clicked.connect(self._edit)
            meta.addWidget(eb)

        if note_type == "note":
            tb = QPushButton("↩" if note_done else "✓")
            tb.setObjectName("iconBtn")
            tb.setFixedSize(26, 22)
            tb.setToolTip("Toggle done")
            tb.clicked.connect(self._toggle)
            meta.addWidget(tb)

        if note.get("image_file") and not note_done:
            rmimg = QPushButton("⊗")
            rmimg.setObjectName("iconBtn")
            rmimg.setFixedSize(26, 22)
            rmimg.setToolTip("Remove image")
            rmimg.clicked.connect(self._remove_img)
            meta.addWidget(rmimg)

        db = QPushButton("✕")
        db.setObjectName("iconBtn")
        db.setFixedSize(26, 22)
        db.setToolTip("Delete note")
        db.setStyleSheet("QPushButton#iconBtn:hover { background:#2e1a1a; color:#e06060; }")
        db.clicked.connect(self._delete)
        meta.addWidget(db)

        text_col.addLayout(meta)
        row.addLayout(text_col)
        outer.addLayout(row)

    def _toggle(self):      self.toggled.emit(self.note["id"])
    def _delete(self):      self.deleted.emit(self.note["id"])
    def _remove_img(self):  self.img_removed.emit(self.note["id"])

    def _edit(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Edit note")
        dlg.setMinimumWidth(400)
        dlg.setStyleSheet(
            "QDialog { background:#1e1e1c; } "
            "QTextEdit { color:#c8c3ba; background:#252522; border:1px solid #3a3835; "
            "border-radius:6px; padding:8px; font-size:14px; font-family:Georgia,serif; } "
            "QPushButton { background:#252522; border:1px solid #3a3835; border-radius:6px; "
            "padding:5px 18px; color:#c8c3ba; } QPushButton:hover { background:#2e2e2c; }"
        )
        lay = QVBoxLayout(dlg)
        ed = QTextEdit()
        ed.setPlainText(self.note.get("text", ""))
        ed.setMinimumHeight(110)
        lay.addWidget(ed)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            t = ed.toPlainText().strip()
            if t:
                self.edited.emit(self.note["id"], t)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class NotesApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Notes")
        self.setMinimumSize(560, 600)
        self.resize(640, 740)
        self.notes = load_notes()
        self._filter             = "all"
        self._type               = "note"
        self._color              = 0
        self._pending_image_path = None

        # FIX 6: debounce saves so rapid actions don't block the UI
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self._do_save)

        self._build_ui()
        self._refresh()

    def _schedule_save(self):
        self._save_timer.start()

    def _do_save(self):
        save_notes(self.notes, parent_widget=self)

    # ------------------------------------------------------------------ build

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(28, 28, 28, 28)
        main.setSpacing(0)

        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.title_lbl = QLabel("Notes")
        self.title_lbl.setObjectName("headTitle")
        self.sub_lbl = QLabel("")
        self.sub_lbl.setObjectName("subtitle")
        title_col.addWidget(self.title_lbl)
        title_col.addWidget(self.sub_lbl)
        hdr.addLayout(title_col)
        hdr.addStretch()
        settings_btn = QPushButton("⚙")
        settings_btn.setObjectName("iconBtn")
        settings_btn.setFixedSize(28, 28)
        settings_btn.setToolTip("Settings")
        settings_btn.clicked.connect(self._show_settings)
        hdr.addWidget(settings_btn, 0, Qt.AlignmentFlag.AlignTop)
        main.addLayout(hdr)
        main.addSpacing(22)

        # Input card
        input_frame = QFrame()
        input_frame.setStyleSheet(
            "QFrame { background:#1e1e1c; border-radius:10px; border:1px solid #2e2e2c; }"
        )
        ilay = QVBoxLayout(input_frame)
        ilay.setContentsMargins(14, 12, 14, 12)
        ilay.setSpacing(10)

        self.input_box = QTextEdit()
        self.input_box.setPlaceholderText(
            "Add a note... (Enter to add, Shift+Enter for new line)"
        )
        self.input_box.setMaximumHeight(90)
        self.input_box.installEventFilter(self)
        ilay.addWidget(self.input_box)

        self.img_preview = QLabel()
        self.img_preview.setFixedHeight(64)
        self.img_preview.setStyleSheet("background:transparent; border:none;")
        self.img_preview.hide()
        ilay.addWidget(self.img_preview)

        ctrl = QHBoxLayout()
        ctrl.setSpacing(8)

        tog = QFrame()
        tog.setStyleSheet(
            "QFrame { background:#141412; border-radius:8px; border:1px solid #2e2e2c; }"
        )
        tog_lay = QHBoxLayout(tog)
        tog_lay.setContentsMargins(3, 3, 3, 3)
        tog_lay.setSpacing(2)
        self.btn_note = QPushButton("Note")
        self.btn_note.setObjectName("typeBtn")
        self.btn_note.setProperty("active", "true")
        self.btn_note.clicked.connect(lambda: self._set_type("note"))
        self.btn_task = QPushButton("Task")
        self.btn_task.setObjectName("typeBtn")
        self.btn_task.setProperty("active", "false")
        self.btn_task.clicked.connect(lambda: self._set_type("task"))
        tog_lay.addWidget(self.btn_note)
        tog_lay.addWidget(self.btn_task)
        ctrl.addWidget(tog)

        swatch_frame = QFrame()
        swatch_frame.setStyleSheet(
            "QFrame { background:#2a2826; border-radius:14px; border:1px solid #3e3c38; }"
        )
        swatch_lay = QHBoxLayout(swatch_frame)
        swatch_lay.setContentsMargins(8, 5, 8, 5)
        swatch_lay.setSpacing(6)
        self.color_group = QButtonGroup(self)
        self.color_group.setExclusive(True)
        for i, (hex_c, label) in enumerate(ACCENT_DOTS):
            dot = ColorDot(hex_c, label)
            dot.setChecked(i == 0)
            dot.clicked.connect(lambda _, idx=i: self._set_color(idx))
            self.color_group.addButton(dot, i)
            swatch_lay.addWidget(dot)
        ctrl.addWidget(swatch_frame)

        self.img_btn = QPushButton("⊕ Image")
        self.img_btn.setObjectName("imgBtn")
        self.img_btn.setProperty("hasImage", "false")
        self.img_btn.setFixedHeight(34)
        self.img_btn.clicked.connect(self._attach_image)
        ctrl.addWidget(self.img_btn)

        ctrl.addStretch()

        self.add_btn = QPushButton("Add")
        self.add_btn.setObjectName("addBtn")
        self.add_btn.setFixedHeight(34)
        self.add_btn.clicked.connect(self._add_note)
        ctrl.addWidget(self.add_btn)

        ilay.addLayout(ctrl)
        main.addWidget(input_frame)
        main.addSpacing(18)

        frow = QHBoxLayout()
        frow.setSpacing(6)
        self.filter_btns = {}
        for f in ["all", "active", "done", "tasks", "notes"]:
            b = QPushButton(f.capitalize())
            b.setObjectName("filterBtn")
            b.setProperty("active", "true" if f == "all" else "false")
            b.clicked.connect(lambda _, fv=f: self._set_filter(fv))
            self.filter_btns[f] = b
            frow.addWidget(b)
        frow.addStretch()
        self.clear_btn = QPushButton("Clear done")
        self.clear_btn.setObjectName("clearBtn")
        self.clear_btn.clicked.connect(self._clear_done)
        self.clear_btn.hide()
        frow.addWidget(self.clear_btn)
        main.addLayout(frow)
        main.addSpacing(14)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.notes_container = QWidget()
        self.notes_container.setStyleSheet("background:transparent;")
        self.notes_layout = QVBoxLayout(self.notes_container)
        self.notes_layout.setContentsMargins(0, 0, 0, 0)
        self.notes_layout.setSpacing(8)
        self.notes_layout.addStretch()
        self.scroll.setWidget(self.notes_container)
        main.addWidget(self.scroll, 1)

        self.empty_lbl = QLabel("Nothing here yet. Add your first note above.")
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_lbl.setStyleSheet("color:#333; font-size:13px; padding:40px;")
        self.empty_lbl.hide()
        main.addWidget(self.empty_lbl)

    # ------------------------------------------------------------------ events

    def eventFilter(self, obj, event):
        # FIX 11: QEvent already imported at top level
        if obj is self.input_box and event.type() == QEvent.Type.KeyPress:
            if (event.key() == Qt.Key.Key_Return
                    and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier)):
                self._add_note()
                return True
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        # Flush any pending debounced save before quitting
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._do_save()
        super().closeEvent(event)

    # ------------------------------------------------------------------ actions

    def _show_settings(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Settings")
        dlg.setMinimumWidth(300)
        dlg.setStyleSheet(
            "QDialog { background:#1e1e1c; } "
            "QCheckBox { color:#c8c3ba; font-size:13px; background:transparent; } "
            "QCheckBox::indicator { width:16px; height:16px; border:1.5px solid #555; border-radius:4px; background:#252522; } "
            "QCheckBox::indicator:checked { background:#2a5a8a; border-color:#2a5a8a; } "
            "QLabel { color:#888; font-size:11px; background:transparent; } "
            "QPushButton { background:#252522; border:1px solid #3a3835; border-radius:6px; "
            "padding:5px 18px; color:#c8c3ba; } QPushButton:hover { background:#2e2e2c; }"
        )
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)
        startup_cb = QCheckBox("Launch with Windows")
        startup_cb.setChecked(is_startup_enabled())
        startup_cb.setEnabled(sys.platform == "win32")
        lay.addWidget(startup_cb)
        if sys.platform != "win32":
            note = QLabel("Launch at startup is only available on Windows.")
            note.setWordWrap(True)
            lay.addWidget(note)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                set_startup_enabled(startup_cb.isChecked())
            except Exception as e:
                QMessageBox.warning(self, "Settings error", str(e))

    def _set_type(self, t):
        self._type = t
        for btn, val in [(self.btn_note, "note"), (self.btn_task, "task")]:
            btn.setProperty("active", "true" if t == val else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.input_box.setPlaceholderText(
            "Add a task... (Enter to add)" if t == "task"
            else "Add a note... (Enter to add, Shift+Enter for new line)"
        )

    def _set_color(self, idx):
        self._color = idx

    def _set_filter(self, f):
        self._filter = f
        for k, b in self.filter_btns.items():
            b.setProperty("active", "true" if k == f else "false")
            b.style().unpolish(b)
            b.style().polish(b)
        self._refresh()

    def _set_img_btn(self, has_image: bool):
        self.img_btn.setText("⊗ Remove" if has_image else "⊕ Image")
        self.img_btn.setProperty("hasImage", "true" if has_image else "false")
        self.img_btn.style().unpolish(self.img_btn)
        self.img_btn.style().polish(self.img_btn)

    def _attach_image(self):
        if self._pending_image_path:
            self._pending_image_path = None
            self.img_preview.hide()
            self._set_img_btn(False)
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "Attach image", str(Path.home()), IMAGE_EXTS
        )
        if not path:
            return
        try:
            px = _load_and_validate_image(path)
            self._pending_image_path = path
            thumb = px.scaledToHeight(56, Qt.TransformationMode.SmoothTransformation)
            self.img_preview.setPixmap(thumb)
            self.img_preview.show()
            self._set_img_btn(True)
        except Exception as e:
            QMessageBox.warning(self, "Image error", str(e))

    def _add_note(self):
        text = self.input_box.toPlainText().strip()
        if not text and not self._pending_image_path:
            return
        if not text:
            text = "(image)"
        color_name = ACCENT_DOTS[self._color][1]
        note_id = str(uuid.uuid4())
        note = {
            "id": note_id,
            "text": text,
            "type": self._type,
            "color": color_name,
            "done": False,
            "createdAt": datetime.now().isoformat(),
        }
        if self._pending_image_path:
            try:
                note["image_file"] = save_image_file(self._pending_image_path, note_id)
            except Exception as e:
                QMessageBox.warning(self, "Image error", str(e))
        self.notes.insert(0, note)
        self._schedule_save()
        self.input_box.clear()
        self._pending_image_path = None
        self.img_preview.hide()
        self._set_img_btn(False)
        self._refresh()

    def _toggle_note(self, nid):
        for n in self.notes:
            if n["id"] == nid:
                n["done"] = not n.get("done", False)
                break
        self._schedule_save()
        self._refresh()

    def _delete_note(self, nid):
        for n in self.notes:
            if n["id"] == nid:
                _delete_image_file(n.get("image_file"))
                break
        self.notes = [n for n in self.notes if n["id"] != nid]
        self._schedule_save()
        self._refresh()

    def _edit_note(self, nid, text):
        for n in self.notes:
            if n["id"] == nid:
                n["text"] = text
                break
        self._schedule_save()
        self._refresh()

    def _remove_image(self, nid):
        for n in self.notes:
            if n["id"] == nid:
                _delete_image_file(n.get("image_file"))
                n.pop("image_file", None)
                break
        self._schedule_save()
        self._refresh()

    def _clear_done(self):
        count = sum(1 for n in self.notes if n.get("done"))
        if not count:
            return
        r = QMessageBox.question(
            self, "Clear done",
            f"Remove {count} completed item{'s' if count != 1 else ''}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if r == QMessageBox.StandardButton.Yes:
            for n in self.notes:
                if n.get("done"):
                    _delete_image_file(n.get("image_file"))
            self.notes = [n for n in self.notes if not n.get("done")]
            self._schedule_save()
            self._refresh()

    # ------------------------------------------------------------------ refresh

    def _visible(self):
        f = self._filter
        if f == "tasks":  return [n for n in self.notes if n.get("type") == "task"]
        if f == "notes":  return [n for n in self.notes if n.get("type") == "note"]
        if f == "done":   return [n for n in self.notes if n.get("done")]
        if f == "active": return [n for n in self.notes if not n.get("done")]
        return self.notes

    def _refresh(self):
        while self.notes_layout.count() > 1:
            item = self.notes_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        vis = self._visible()
        done = sum(1 for n in self.notes if n.get("done"))
        total = len(self.notes)
        self.sub_lbl.setText(
            f"{total} item{'s' if total != 1 else ''}" + (f", {done} done" if done else "")
        )

        if done:
            self.clear_btn.setText(f"Clear done ({done})")
            self.clear_btn.show()
        else:
            self.clear_btn.hide()

        if not vis:
            msg = (
                "Nothing here yet. Add your first note above."
                if self._filter == "all"
                else f"No {self._filter} items."
            )
            self.empty_lbl.setText(msg)
            self.empty_lbl.show()
            self.scroll.hide()
        else:
            self.empty_lbl.hide()
            self.scroll.show()
            for note in vis:
                card = NoteCard(note)
                card.deleted.connect(self._delete_note)
                card.toggled.connect(self._toggle_note)
                card.edited.connect(self._edit_note)
                card.img_removed.connect(self._remove_image)
                self.notes_layout.insertWidget(self.notes_layout.count() - 1, card)


# ---------------------------------------------------------------------------

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Notes")
    app.setStyleSheet(STYLESHEET)
    win = NotesApp()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()