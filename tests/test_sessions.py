"""Pin session detection: Asia/London/NY grouping, the midnight wrap, latest."""

import pandas as pd

from src.indicators.sessions import latest_session_bars, session_instances, session_names


def _day_bars():
    """23 hourly bars, Chicago 2020-01-15 18:00 -> 2020-01-16 16:00 (winter = CST,
    no DST). Covers Asia (18:00-02:00), London (03:00-07:00), NY (08:00-16:00)."""
    idx_chi = pd.date_range("2020-01-15 18:00", periods=23, freq="1h", tz="America/Chicago")
    idx_utc = idx_chi.tz_convert("UTC")
    n = len(idx_utc)
    return pd.DataFrame(
        {"open": range(n), "high": range(n), "low": range(n), "close": range(n),
         "volume": [100] * n},
        index=idx_utc,
    )


def test_three_sessions_in_order():
    insts = session_instances(_day_bars())
    assert [it["session"] for it in insts] == ["Asia", "London", "NY"]


def test_session_bar_counts():
    insts = {it["session"]: it for it in session_instances(_day_bars())}
    assert len(insts["Asia"]["positions"]) == 9    # 18,19,20,21,22,23,00,01,02
    assert len(insts["London"]["positions"]) == 5  # 03,04,05,06,07
    assert len(insts["NY"]["positions"]) == 9      # 08..16


def test_asia_wraps_midnight_into_one_instance():
    # All 9 Asia bars (incl. the 00/01/02 after midnight) anchor to one instance.
    asia = [it for it in session_instances(_day_bars()) if it["session"] == "Asia"]
    assert len(asia) == 1
    assert asia[0]["start_pos"] == 0


def test_latest_session_bars_is_ny():
    df = _day_bars()
    ny = [it for it in session_instances(df) if it["session"] == "NY"][0]
    latest = latest_session_bars(df)
    assert len(latest) == len(ny["positions"]) == 9
    assert latest.index[0] == df.index[ny["start_pos"]]


def test_empty_frame_returns_no_sessions():
    assert session_instances(pd.DataFrame()) == []


def test_session_names():
    assert session_names() == ["Asia", "London", "NY"]
