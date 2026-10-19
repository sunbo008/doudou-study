#!/usr/bin/env python3
"""Rebuild lemma_table.json from words/*.json without full HTML rebuild."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from graph_lib import (  # noqa: E402
    DEFAULT_ROOT,
    TableLock,
    append_history,
    atomic_write_json,
    ensure_dirs,
    rebuild_table_from_words,
    sync_graph_from_table,
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None)
    args = parser.parse_args()
    root = Path(args.root) if args.root else repo_root() / DEFAULT_ROOT
    ensure_dirs(root)
    with TableLock(root):
        table = rebuild_table_from_words(root)
        atomic_write_json(root / "lemma_table.json", table)
        sync_graph_from_table(root, table)
        append_history(
            root,
            {
                "op": "rebuild_table",
                "summary": f"rebuilt table lemmas={len(table.get('lemmas', {}))}",
            },
        )
    print(f"OK rebuilt lemma_table lemmas={len(table.get('lemmas', {}))} root={root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
