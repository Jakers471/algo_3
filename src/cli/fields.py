"""CLI door: the field contract - which indicator publishes which column, from where.

Thin door. It asks the registry what it is running and prints the answer; the
answer is derived from the indicator classes themselves, so it cannot drift from
the code the way a hand-written table would.

    python -m src.cli.fields              print the contract
    python -m src.cli.fields --write      also regenerate FIELDS.md
    python -m src.cli.fields --json       machine-readable, for tooling

A snapshot row is a flat wall of names. Six months from now nobody - human or
model - can tell which file computed ``retrace``, which dial moved it, or what it
was allowed to read. This is that answer.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.chart import overlays
from src.core import console
from src.table import columns as cols

DOC = Path(__file__).resolve().parents[2] / "FIELDS.md"

HEADER = """# FIELDS.md — the field contract

**Generated. Do not edit by hand.** Run `python -m src.cli.fields --write` (or
`commands.bat` -> Maintenance) and commit the result alongside the code that
changed it.

Every column in the snapshot table, and every value the brain will read, is
published by exactly one indicator. This says which — and where its code and its
dials live, so a name in a row is always one click from the file that produced it.

Indicators run in **dependency order**: an indicator's fields exist before any
indicator that reads them runs. `depends` is that edge; the registry topologically
sorts on it, and a cycle is a startup error rather than a wrong number three hours
into a backtest.

A field marked **detail** is scaffolding a drawing needs and a reader does not — a
timestamp, an endpoint, or arithmetic on a column already shown. The table hides
those unless you click **Details**. Nothing is ever dropped from the row itself.

## Read the unit first

It is the thing that goes wrong first, because three of them look identical in a
table and mean completely different things.

| unit | what it does when the market changes |
|---|---|
| `price` | moves with the market. 30,698.50 means nothing next month |
| `points` | moves with volatility. Ten points is a lot at 04:00 and nothing at the open |
| `x range_scale` | moves with neither. **Dimensionless.** Multiply every price by ten and it does not change |
| `contracts` | a count. Comparable within a range, not between two of them |
| `0..1`, `-1..+1` | a ratio, already normalised |
| `epoch seconds, UTC` | a timestamp. Ten digits, not a price |
| `payload` | a structure the chart draws. Never read it as a number |

`range_scale` itself is in **points** — it is the ruler, and the only thing in the
structure layer that has to be. Everything measured *in* it is dimensionless, which
is the entire reason the rules survive a change of regime.
"""


def contract() -> list[dict]:
    """What the chart's registry is actually running, right now."""
    return overlays.build_registry(profile_mode="on").provenance()


def render_text(entries: list[dict]) -> str:
    out = []
    for entry in entries:
        title = console.paint(f"  {entry['id']}", console.BOLD, console.CYAN)
        deps = ", ".join(entry["depends"]) or console.paint("(reads the bar)", console.DIM)
        out.append(f"\n{title}   {console.paint('<- ' + deps, console.DIM)}")
        out.append(f"    {console.paint(entry['doc'], console.DIM)}")
        out.append(f"    source  {entry['source']}")
        out.append(f"    config  {entry['config'] or console.paint('(none)', console.DIM)}")
        shown, hidden = [], []
        for name in entry["fields"]:
            (hidden if cols.is_detail(name) else shown).append(name)
        out.append(f"    fields  {', '.join(shown) or '-'}")
        if hidden:
            out.append(f"    detail  {console.paint(', '.join(hidden), console.DIM)}")
    return "\n".join(out)


def _block(lines: list[str], title: str, source: str, config: str | None,
           doc: str, reads: str, about: dict, names) -> None:
    lines.append(f"\n### `{title}`\n")
    if doc:
        lines.append(f"{doc}\n")
    lines.append(f"- **reads** — {reads}")
    lines.append(f"- **source** — `{source}`")
    lines.append(f"- **config** — {f'`{config}`' if config else 'none'}\n")
    lines.append("| field | unit | shown | what it is |")
    lines.append("|---|---|---|---|")
    for name in names:
        unit, means = about.get(name, ("?", "UNDEFINED"))
        shown = "" if cols.is_detail(name) else "yes"
        lines.append(f"| `{name}` | {unit} | {shown} | {means} |")


def render_markdown(entries: list[dict]) -> str:
    lines = [HEADER, "\n## Indicators, in dependency order\n"]
    lines.append("| indicator | reads | source | config |")
    lines.append("|---|---|---|---|")
    lines.append("| **`bar`** | the dataset | `src/chart/store.py` | `src/config/chart.py` |")
    for e in entries:
        deps = ", ".join(f"`{d}`" for d in e["depends"]) or "the bar"
        config = f"`{e['config']}`" if e["config"] else "—"
        lines.append(f"| **`{e['id']}`** | {deps} | `{e['source']}` | {config} |")

    lines.append("\n## Every field, defined\n")
    lines.append("The blocks below are the table's blocks, in the order the columns appear.")

    _block(lines, "bar", "src/chart/store.py", "src/config/chart.py",
           "The candle itself, straight from the packed dataset. No indicator computes it.",
           "the dataset", cols.BAR_ABOUT, [k for k, _, _ in cols.BAR_COLUMNS])

    for e in entries:
        reads = ", ".join(f"`{d}`" for d in e["depends"]) or "the bar"
        _block(lines, e["id"], e["source"], e["config"], e["doc"], reads,
               e["about"] and {k: (v["unit"], v["means"]) for k, v in e["about"].items()},
               e["fields"])
    return "\n".join(lines) + "\n"


def main() -> None:
    console.enable_windows_ansi()
    ap = argparse.ArgumentParser(description="Which indicator publishes which field.")
    ap.add_argument("--write", action="store_true", help=f"regenerate {DOC.name}")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    entries = contract()
    if args.json:
        print(json.dumps(entries, indent=2))
        return

    print(render_text(entries))
    total = sum(len(e["fields"]) for e in entries)
    detail = sum(1 for e in entries for f in e["fields"] if cols.is_detail(f))
    print()
    print(console.paint(
        f"  {len(entries)} indicators, {total} fields ({total - detail} shown, {detail} detail)",
        console.BOLD))

    if args.write:
        DOC.write_text(render_markdown(entries), encoding="utf-8")
        print(console.paint(f"  wrote {DOC.name}", console.GREEN))
    print()


if __name__ == "__main__":
    main()
