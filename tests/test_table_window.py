"""Pins what the table looks like, by painting it and reading the pixels back.

There is one bug here that no other kind of test can see. A `color:` rule in the
Qt stylesheet on `QHeaderView::section` silently OVERRIDES the model's
ForegroundRole, so `headerData` can return a perfectly correct colour for every
block and the screen still shows eight identical greys. Nothing raises, nothing
returns the wrong value, and the unit tests all pass.

So this test grabs the header and counts the colours actually on it.

Qt needs a display. These run offscreen; if PySide6 cannot start at all the whole
module is skipped rather than failing the suite for an environment reason.
"""

from __future__ import annotations

import os
import queue

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtGui import QColor              # noqa: E402
from PySide6.QtWidgets import QApplication    # noqa: E402

from src.config import table as cfg           # noqa: E402
from src.table.window import TableWindow      # noqa: E402


class FakeStream:
    def __init__(self):
        self.queue = queue.Queue()

    def stop(self):
        pass


GROUPS = [
    {"id": "sessions", "fields": ["session"]},
    {"id": "orderflow", "fields": ["delta"]},
    # `trigger` and `bos_level` are detail: hidden until Details is clicked.
    {"id": "swing", "fields": ["retrace", "hunting", "trigger"]},
    {"id": "breaks", "fields": ["bos", "bos_level"]},
]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    session = {"id": "t", "symbol": "NQT", "timeframe": "5m",
               "groups": GROUPS, "fields": [f for g in GROUPS for f in g["fields"]],
               "playing": False, "speed": 1}
    win = TableWindow(FakeStream(), session)
    win.model.append({"time": 1_700_000_000,
                      "bar": {"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 10},
                      "fields": {"session": "NY", "delta": 5, "retrace": 1.0,
                                 "hunting": "high", "trigger": 99.0,
                                 "bos": None, "bos_level": None}})
    win.resize(1600, 400)
    win.show()
    win._size_columns()
    yield win
    win.close()


def header_colours(window) -> set[str]:
    """Every group colour actually painted onto the horizontal header."""
    image = window.view.horizontalHeader().grab().toImage()
    wanted = {g: QColor(cfg.GROUP_COLORS[g]).rgb() | 0xFF000000
              for g in window.model.groups()}
    found = set()
    for x in range(image.width()):
        for y in range(image.height()):
            pixel = image.pixel(x, y) | 0xFF000000
            for group, rgb in wanted.items():
                if pixel == rgb:
                    found.add(group)
    return found


def test_every_block_paints_its_own_colour_onto_the_header(window):
    """A stylesheet `color:` on a header section overrides ForegroundRole silently."""
    assert header_colours(window) == set(window.model.groups())


def test_the_stylesheet_never_sets_a_header_colour(window):
    """The regression this file exists for. One line, and every hue disappears."""
    sheet = window.styleSheet()
    section = sheet.split("QHeaderView::section")[1].split("}")[0]
    assert "color:" not in section, (
        "a colour here overrides headerData's ForegroundRole and every block "
        "goes grey - the hue must come from the model")


def test_a_long_header_does_not_reserve_a_long_column(window):
    """`absorption side` is wider than any value beneath it."""
    header = window.view.horizontalHeader()
    widths = [header.sectionSize(i) for i in range(window.model.columnCount())]
    assert max(widths) <= cfg.COLUMN_MAX_PX


def test_the_legend_names_every_block_that_is_on_screen(window):
    legend = window._legend_text()
    for group in window.model.groups():
        assert group in legend
        assert cfg.GROUP_COLORS[group] in legend


def test_details_adds_blocks_and_keeps_the_rows(window):
    before, rows = window.model.columnCount(), window.model.rowCount()
    window.details_button.setChecked(True)
    window._toggle_details()
    assert window.model.columnCount() > before
    assert window.model.rowCount() == rows
    assert header_colours(window) == set(window.model.groups())
