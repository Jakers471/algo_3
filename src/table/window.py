"""The desktop snapshot table: a second window watching the same replay.

One job: show each snapshot as a row, newest at the bottom, and stay out of the
way. The chart draws the shapes; this shows the numbers behind them. Both read
the identical row from the same server-side session, so they cannot disagree.

Two behaviours it must get right, and they are the reason this is a real table
widget rather than terminal output:

**It never wraps.** Columns clip and the view scrolls horizontally, per pixel.
A wrapped row destroys a table - the columns stop lining up and the eye has
nothing to follow.

**Auto-follow, with escape.** It sticks to the newest row while rows arrive,
but the moment you scroll up it lets go and stays where you put it, showing how
many rows have landed since. Click Follow (or scroll back to the bottom) and it
resumes. Without this you cannot study a moment while a replay is playing.

Rows are capped and the oldest are dropped, exactly as the chart trims bars.
"""

from __future__ import annotations

import logging
from collections import deque

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QTableView, QVBoxLayout, QWidget,
)

from src.config import table as cfg
from src.table import columns as cols

logger = logging.getLogger(__name__)

_ALIGN = {
    cols.LEFT: Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    cols.RIGHT: Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
    cols.CENTER: Qt.AlignmentFlag.AlignCenter,
}


class SnapshotModel(QAbstractTableModel):
    """Rows are snapshots; columns come from the session's own field names."""

    def __init__(self, fields: list[str]) -> None:
        super().__init__()
        self._columns = cols.columns_for(fields)
        self._rows: deque = deque(maxlen=cfg.MAX_ROWS)

    # --- Qt plumbing --------------------------------------------------------

    def rowCount(self, _parent=QModelIndex()) -> int:  # noqa: N802
        return len(self._rows)

    def columnCount(self, _parent=QModelIndex()) -> int:  # noqa: N802
        return len(self._columns)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if orientation != Qt.Orientation.Horizontal:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return self._columns[section][1]
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return _ALIGN[self._columns[section][2]]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        snapshot = self._rows[index.row()]
        key, _label, align = self._columns[index.column()]

        if role == Qt.ItemDataRole.DisplayRole:
            return cols.cell_text(key, snapshot)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return _ALIGN[align]
        if role == Qt.ItemDataRole.ForegroundRole:
            if cols.row_is_halt(snapshot):
                return QColor(cfg.HALT_COLOR)
            colour = cols.cell_color(key, snapshot)
            return QColor(colour) if colour else None
        if role == Qt.ItemDataRole.BackgroundRole and cols.row_is_session_open(snapshot):
            # A session opening is structure, not decoration - the chart draws a
            # rule at the same bar.
            return QColor(cfg.PANEL)
        return None

    # --- feeding ------------------------------------------------------------

    def append(self, snapshot: dict) -> None:
        """Append one row, dropping the oldest if the buffer is full."""
        full = len(self._rows) == self._rows.maxlen
        if full:
            self.beginRemoveRows(QModelIndex(), 0, 0)
            self._rows.popleft()
            self.endRemoveRows()

        row = len(self._rows)
        self.beginInsertRows(QModelIndex(), row, row)
        self._rows.append(snapshot)
        self.endInsertRows()


class TableWindow(QMainWindow):
    """The window: a table, a status line, and a Follow toggle."""

    def __init__(self, stream, session: dict) -> None:
        super().__init__()
        self.stream = stream
        self.session = session
        self.following = True
        self.pending = 0
        self.received = 0

        self.setWindowTitle(
            f"algo_3  -  {session['symbol']} {session['timeframe']}  snapshots")
        self.resize(1100, 620)

        self.model = SnapshotModel(session.get("fields", []))
        self.view = self._build_view()
        self.status = QLabel("waiting for the first bar...")
        self.follow_button = QPushButton("Following")
        self.follow_button.setCheckable(True)
        self.follow_button.setChecked(True)
        self.follow_button.clicked.connect(self._toggle_follow)

        self.setCentralWidget(self._build_layout())
        self._apply_theme()

        self.view.verticalScrollBar().valueChanged.connect(self._on_scrolled)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._drain)
        self.timer.start(cfg.DRAIN_INTERVAL_MS)

    # --- construction -------------------------------------------------------

    def _build_view(self) -> QTableView:
        view = QTableView()
        view.setModel(self.model)

        # The whole reason this is not a terminal: clip and scroll, never wrap.
        view.setWordWrap(False)
        view.setTextElideMode(Qt.TextElideMode.ElideNone)
        view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        view.setShowGrid(False)
        view.setAlternatingRowColors(False)
        view.verticalHeader().setVisible(False)
        view.verticalHeader().setDefaultSectionSize(cfg.ROW_HEIGHT)
        view.horizontalHeader().setStretchLastSection(False)
        view.horizontalHeader().setHighlightSections(False)
        view.setFont(QFont(cfg.FONT_FAMILY.split(",")[0], cfg.FONT_SIZE_PT))
        return view

    def _build_layout(self) -> QWidget:
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 6, 8, 6)
        bar.addWidget(self.status, 1)
        bar.addWidget(self.follow_button, 0)

        chrome = QWidget()
        chrome.setLayout(bar)
        chrome.setObjectName("chrome")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.view, 1)
        layout.addWidget(chrome, 0)

        central = QWidget()
        central.setLayout(layout)
        return central

    def _apply_theme(self) -> None:
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ background: {cfg.BG}; color: {cfg.TEXT}; }}
            QWidget#chrome {{ background: {cfg.PANEL}; border-top: 1px solid {cfg.LINE}; }}
            QTableView {{
                background: {cfg.BG};
                alternate-background-color: {cfg.BG};
                gridline-color: {cfg.LINE};
                selection-background-color: {cfg.SELECTION};
                selection-color: {cfg.TEXT};
                border: none;
            }}
            QHeaderView::section {{
                background: {cfg.PANEL};
                color: {cfg.MUTED};
                border: 0px;
                border-bottom: 1px solid {cfg.LINE};
                padding: 4px 10px;
            }}
            QLabel {{ color: {cfg.MUTED}; }}
            QPushButton {{
                background: #161b22; color: {cfg.TEXT};
                border: 1px solid {cfg.LINE}; border-radius: 4px; padding: 4px 12px;
            }}
            QPushButton:checked {{ color: {cfg.ACCENT}; border-color: {cfg.ACCENT}; }}
            QScrollBar:vertical, QScrollBar:horizontal {{
                background: {cfg.BG}; border: none;
            }}
            QScrollBar::handle {{ background: #30363d; border-radius: 4px; }}
        """)

    # --- follow behaviour ---------------------------------------------------

    def _at_bottom(self) -> bool:
        bar = self.view.verticalScrollBar()
        return bar.value() >= bar.maximum() - cfg.FOLLOW_SLACK_PX

    def _on_scrolled(self, _value: int) -> None:
        """Scrolling away from the bottom releases the follow; returning resumes it."""
        at_bottom = self._at_bottom()
        if self.following and not at_bottom:
            self._set_following(False)
        elif not self.following and at_bottom:
            self._set_following(True)

    def _toggle_follow(self) -> None:
        self._set_following(self.follow_button.isChecked())
        if self.following:
            self.view.scrollToBottom()

    def _set_following(self, following: bool) -> None:
        self.following = following
        self.follow_button.setChecked(following)
        if following:
            self.pending = 0
        self.follow_button.setText("Following" if following else f"Follow ({self.pending})")
        self._render_status()

    # --- the pump -----------------------------------------------------------

    def _switch_session(self, session: dict) -> None:
        """The chart retired its replay and started another - follow it.

        A new timeframe (or symbol) is a different series, so the old rows are
        not history, they are a different story. And its indicators may publish
        different fields, so the columns are rebuilt rather than reused.
        """
        self.session = session
        self.received = 0
        self.pending = 0
        self.model = SnapshotModel(session.get("fields", []))
        self.view.setModel(self.model)
        self.setWindowTitle(
            f"algo_3  -  {session['symbol']} {session['timeframe']}  snapshots")
        self._set_following(True)
        logger.info("Following session %s (%s %s)",
                    session["id"], session["symbol"], session["timeframe"])

    def _drain(self) -> None:
        """Move everything waiting on the queue into the view, then scroll once."""
        appended = 0
        while True:
            try:
                payload = self.stream.queue.get_nowait()
            except Exception:  # queue.Empty
                break
            if "session_changed" in payload:
                self._switch_session(payload["session_changed"])
                continue
            if "state" in payload:
                self.session.update(payload["state"])
                self._render_status()
                continue
            self.model.append(payload)
            self.received += 1
            appended += 1

        if not appended:
            return

        if self.following:
            self.view.scrollToBottom()
        else:
            self.pending += appended
            self.follow_button.setText(f"Follow ({self.pending})")

        if self.received == appended:      # the very first rows: size the columns
            self.view.resizeColumnsToContents()
        self._render_status()

    def _render_status(self) -> None:
        playing = self.session.get("playing")
        state = "playing" if playing else "paused"
        speed = self.session.get("speed", 1)
        follow = "following" if self.following else f"held ({self.pending} new)"
        self.status.setText(
            f"session {self.session['id']}   {state} {speed}x   "
            f"rows {self.model.rowCount():,}   {follow}")

    def closeEvent(self, event):  # noqa: N802
        self.stream.stop()
        super().closeEvent(event)
