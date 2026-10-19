#!/usr/bin/env python3
"""Refresh a core page from lemma_table membership."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from graph_lib import DEFAULT_ROOT, upsert_core_only  # noqa: E402


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("core_id")
    parser.add_argument("--root", default=None)
    args = parser.parse_args()
    root = Path(args.root) if args.root else repo_root() / DEFAULT_ROOT
    event = upsert_core_only(root, args.core_id.strip().lower())
    print(f"OK {event}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
