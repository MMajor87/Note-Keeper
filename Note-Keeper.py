#!/usr/bin/env python3
"""
Notes App -- standalone PyQt6 desktop application.
Supports text notes, tasks, and attached images.
Notes are saved to ~/notes_app_data.json automatically.
Images are stored as base64 inside the JSON file.
"""

import sys
import json
import uuid
import base64
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QScrollArea,
    QFrame, QButtonGroup, QMessageBox, QFileDialog, QDialog,
    QDialogButtonBox,
)
from PyQt6.QtCore import Qt, QByteArray, QEvent, QTimer, pyqtSignal  # FIX 11: QEvent moved to top-level
from PyQt6.QtGui import QFont, QPixmap, QImage

DATA_FILE = Path.home() / "notes_app_data.json"
IMAGE_EXTS = "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp)"
IMAGE_MAX_BYTES = 8 * 1024 * 1024   # FIX 5: warn if file exceeds 8 MB
IMAGE_MAX_PX    = 1600               # FIX 5: scale down images wider/taller than this

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
                return data
        except Exception:
            pass
    return []


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


def image_to_b64(path: str) -> str:
    """
    FIX 5: Check file size before loading; scale down oversized images.
    Returns a base64-encoded JPEG/PNG string suitable for storage.
    """
    p = Path(path)
    if p.stat().st_size > IMAGE_MAX_BYTES:
        raise ValueError(
            f"Image is {p.stat().st_size // (1024*1024):.1f} MB. "
            f"Please use an image under {IMAGE_MAX_BYTES // (1024*1024)} MB."
        )
    px = QPixmap(path)
    if px.isNull():
        raise ValueError("File could not be read as an image.")
    # Scale down if too large
    if px.width() > IMAGE_MAX_PX or px.height() > IMAGE_MAX_PX:
        px = px.scaled(
            IMAGE_MAX_PX, IMAGE_MAX_PX,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    buf = QByteArray()
    from PyQt6.QtCore import QBuffer
    qbuf = QBuffer(buf)
    qbuf.open(QBuffer.OpenModeFlag.WriteOnly)
    px.save(qbuf, "PNG")
    return base64.b64encode(bytes(buf)).decode()


def b64_to_pixmap(b64: str) -> QPixmap:
    # FIX 3: check for null image after decode
    data = QByteArray(base64.b64decode(b64))
    img = QImage.fromData(data)
    if img.isNull():
        raise ValueError("Stored image data is corrupt or unrecognisable.")
    return QPixmap.fromImage(img)


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
        if note.get("image"):
            try:
                px = b64_to_pixmap(note["image"])  # FIX 3: raises on null
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

        if note.get("image") and not note_done:
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
        self._filter        = "all"
        self._type          = "note"
        self._color         = 0
        self._pending_image = None

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

        self.title_lbl = QLabel("Notes")
        self.title_lbl.setObjectName("headTitle")
        self.sub_lbl = QLabel("")
        self.sub_lbl.setObjectName("subtitle")
        main.addWidget(self.title_lbl)
        main.addWidget(self.sub_lbl)
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
        if self._pending_image:
            self._pending_image = None
            self.img_preview.hide()
            self._set_img_btn(False)
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "Attach image", str(Path.home()), IMAGE_EXTS
        )
        if not path:
            return
        try:
            b64 = image_to_b64(path)
            self._pending_image = b64
            px = b64_to_pixmap(b64).scaledToHeight(
                56, Qt.TransformationMode.SmoothTransformation
            )
            self.img_preview.setPixmap(px)
            self.img_preview.show()
            self._set_img_btn(True)
        except Exception as e:
            QMessageBox.warning(self, "Image error", str(e))

    def _add_note(self):
        text = self.input_box.toPlainText().strip()
        if not text and not self._pending_image:
            return
        if not text:
            text = "(image)"
        color_name = ACCENT_DOTS[self._color][1]
        note = {
            "id": str(uuid.uuid4()),
            "text": text,
            "type": self._type,
            "color": color_name,
            "done": False,
            "createdAt": datetime.now().isoformat(),
        }
        if self._pending_image:
            note["image"] = self._pending_image
        self.notes.insert(0, note)
        self._schedule_save()
        self.input_box.clear()
        self._pending_image = None
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
                n.pop("image", None)
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