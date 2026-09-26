"""PROTOTYPE — throwaway, answers wayfinder ticket #7 (Three-pane UI layout & panel behavior).

Three radically different layouts for the same workspace: icon sidebar, a
Knowledge/File Tree panel, Chat, Preview, an activity/ingest-progress
surface, and the review queue. Cycle variants with the Left/Right arrow
keys or the floating switcher pill at the bottom of the window.

Run: python3 prototype/three_pane_ui_prototype.py
"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

ICONS = ["Wiki", "Sources", "Search", "Graph", "Lint", "Review (3)", "Settings"]
FAKE_TREE = {
    "Wiki": ["Personal Knowledge Base.md", "Projects/", "People/", "Concepts/"],
    "Sources": ["inbox/", "meeting-notes-2026-09-24.md", "research-paper.pdf"],
}


def panel(title: str, bg: str) -> QFrame:
    f = QFrame()
    f.setStyleSheet(f"background:{bg}; border:1px solid #444;")
    f.setMinimumSize(80, 60)
    lay = QVBoxLayout(f)
    lbl = QLabel(title)
    lbl.setStyleSheet("color:white; font-weight:bold; padding:6px;")
    lay.addWidget(lbl, alignment=Qt.AlignTop)
    lay.addStretch()
    return f


def fake_tree() -> QTreeWidget:
    t = QTreeWidget()
    t.setHeaderHidden(True)
    for section, items in FAKE_TREE.items():
        top = QTreeWidgetItem([section])
        for i in items:
            top.addChild(QTreeWidgetItem([i]))
        t.addTopLevelItem(top)
    t.expandAll()
    return t


def fake_chat() -> QPlainTextEdit:
    chat = QPlainTextEdit()
    chat.setPlainText(
        "you: summarize the Q3 planning doc\n\n"
        "agent: Q3 planning covers three workstreams... [tool: search_wiki]\n"
    )
    return chat


# --- Variant A: Classic IDE docks -----------------------------------------
# Icon rail (left, narrow) | File Tree | Chat | Preview
# Ingest activity = persistent bottom status bar, expandable.
# Review queue = badge count on the Review icon; opens by replacing Preview.
def build_variant_a() -> QWidget:
    root = QWidget()
    outer = QVBoxLayout(root)
    outer.setContentsMargins(0, 0, 0, 0)

    body = QHBoxLayout()
    outer.addLayout(body, 1)

    rail = QListWidget()
    rail.setFixedWidth(110)
    for name in ICONS:
        QListWidgetItem(name, rail)
    body.addWidget(rail)

    split = QSplitter()
    split.addWidget(fake_tree())
    split.addWidget(fake_chat())
    split.addWidget(panel("Preview", "#2b5"))
    split.setSizes([180, 420, 300])
    body.addWidget(split, 1)

    status = QFrame()
    status.setFixedHeight(28)
    status.setStyleSheet("background:#222;")
    srow = QHBoxLayout(status)
    srow.setContentsMargins(8, 2, 8, 2)
    srow.addWidget(QLabel("Ingesting 4/12 documents — Louvain re-cluster pending"))
    srow.addStretch()
    expand = QPushButton("▲ details")
    expand.setFlat(True)
    srow.addWidget(expand)
    outer.addWidget(status)

    note = QLabel(
        "Variant A — classic IDE docks. Activity = bottom status bar (VS Code style, "
        "click ▲ to expand a scroll-back log). Review = badge count on rail icon, "
        "opening in place of Preview."
    )
    note.setWordWrap(True)
    note.setStyleSheet("color:#888; padding:4px;")
    outer.addWidget(note)
    return root


# --- Variant B: Command-center, vertical split on the right ---------------
# Icon rail | File Tree | (Preview over Chat, stacked) | persistent Activity column
# Review queue = full "Review Mode" replacing the whole workspace.
def build_variant_b() -> QWidget:
    root = QWidget()
    outer = QVBoxLayout(root)
    outer.setContentsMargins(0, 0, 0, 0)
    body = QHBoxLayout()
    outer.addLayout(body, 1)

    rail = QListWidget()
    rail.setFixedWidth(110)
    for name in ICONS:
        item = QListWidgetItem(name, rail)
        if name.startswith("Review"):
            item.setBackground(Qt.darkRed)
    body.addWidget(rail)

    tree = fake_tree()
    tree.setFixedWidth(200)
    body.addWidget(tree)

    center_split = QSplitter(Qt.Vertical)
    center_split.addWidget(panel("Preview", "#2b5"))
    center_split.addWidget(fake_chat())
    center_split.setSizes([420, 240])
    body.addWidget(center_split, 1)

    activity = QFrame()
    activity.setFixedWidth(220)
    activity.setStyleSheet("background:#1a1a1a;")
    alay = QVBoxLayout(activity)
    alay.addWidget(QLabel("<b>Activity</b>"))
    for line in [
        "✓ scanned inbox/ (12 files)",
        "→ captioning image 3/5",
        "→ embedding chunks 88/140",
        "• community detection queued",
    ]:
        alay.addWidget(QLabel(line))
    alay.addStretch()
    body.addWidget(activity)

    note = QLabel(
        "Variant B — command center. Preview/Chat stack vertically instead of "
        "side-by-side; a persistent right-hand Activity column always shows ingest "
        "state (no expand/collapse). Selecting the Review icon (highlighted) would "
        "replace this whole workspace with a dedicated full-window Review Mode."
    )
    note.setWordWrap(True)
    note.setStyleSheet("color:#888; padding:4px;")
    outer.addWidget(note)
    return root


# --- Variant C: Fluid top tabs, chat as a persistent side companion -------
# Top tab bar swaps the left pane's content; Chat is a persistent right dock;
# Activity = ephemeral toast stack; Review = inline badge inside the tree.
def build_variant_c() -> QWidget:
    root = QWidget()
    outer = QVBoxLayout(root)
    outer.setContentsMargins(0, 0, 0, 0)

    tabs = QTabBar()
    for name in ICONS:
        tabs.addTab(name)
    outer.addWidget(tabs)

    body = QHBoxLayout()
    outer.addLayout(body, 1)

    left = fake_tree()
    review_badge = QTreeWidgetItem(["⚠ Needs review (3)"])
    left.insertTopLevelItem(0, review_badge)
    body.addWidget(left, 1)

    body.addWidget(panel("Preview", "#2b5"), 2)

    chat_dock = QFrame()
    chat_dock.setFixedWidth(280)
    chat_dock.setStyleSheet("background:#242424;")
    clay = QVBoxLayout(chat_dock)
    clay.addWidget(QLabel("<b>Copilot (always on)</b>"))
    clay.addWidget(fake_chat())
    body.addWidget(chat_dock)

    toast = QLabel("⏳ embedding chunks 88/140")
    toast.setStyleSheet(
        "background:#333; color:white; padding:6px 10px; border-radius:8px;"
    )
    toast.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    outer.addWidget(toast, alignment=Qt.AlignRight | Qt.AlignBottom)

    note = QLabel(
        "Variant C — fluid tabs. Icon rail becomes a top tab bar that swaps only "
        "the left pane's content; Chat is a permanent right-hand companion, never "
        "hidden. Ingest activity is an ephemeral bottom-right toast (disappears when "
        "idle), and the review queue is inline as a badge row inside the file tree, "
        "not a separate surface."
    )
    note.setWordWrap(True)
    note.setStyleSheet("color:#888; padding:4px;")
    outer.addWidget(note)
    return root


VARIANTS = [
    ("A", "Classic IDE docks + bottom status bar", build_variant_a),
    ("B", "Command center + persistent activity column", build_variant_b),
    ("C", "Fluid top tabs + always-on chat companion", build_variant_c),
]


class SwitcherBar(QWidget):
    def __init__(self, on_prev, on_next):
        super().__init__()
        self.setStyleSheet(
            "background:#000; border-radius:14px; color:white; padding:4px 12px;"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, 4)
        left = QPushButton("◀")
        right = QPushButton("▶")
        left.clicked.connect(on_prev)
        right.clicked.connect(on_next)
        self.label = QLabel()
        lay.addWidget(left)
        lay.addWidget(self.label)
        lay.addWidget(right)

    def set_label(self, key: str, name: str) -> None:
        self.label.setText(f"  {key} — {name}  ")


class PrototypeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("mindstew — three-pane layout prototype (#7)")
        self.resize(1200, 760)
        self.index = 0

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        for _, _, builder in VARIANTS:
            self.stack.addWidget(builder())
        outer.addWidget(self.stack, 1)

        self.switcher = SwitcherBar(self.prev_variant, self.next_variant)
        bar_row = QHBoxLayout()
        bar_row.addStretch()
        bar_row.addWidget(self.switcher)
        bar_row.addStretch()
        outer.addLayout(bar_row)
        outer.setContentsMargins(0, 0, 0, 12)

        self._refresh()

    def _refresh(self):
        self.stack.setCurrentIndex(self.index)
        key, name, _ = VARIANTS[self.index]
        self.switcher.set_label(key, name)

    def next_variant(self):
        self.index = (self.index + 1) % len(VARIANTS)
        self._refresh()

    def prev_variant(self):
        self.index = (self.index - 1) % len(VARIANTS)
        self._refresh()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Right:
            self.next_variant()
        elif event.key() == Qt.Key_Left:
            self.prev_variant()
        else:
            super().keyPressEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = PrototypeWindow()
    win.show()
    sys.exit(app.exec())
