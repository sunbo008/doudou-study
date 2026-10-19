#!/usr/bin/env python3
"""Upsert word(s): update lemma_table, bidirectional links, render HTML."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from graph_lib import (  # noqa: E402
    DEFAULT_ROOT,
    append_history,
    atomic_write_json,
    ensure_dirs,
    load_json,
    rebuild_table_from_words,
    render_core_html,
    render_index_html,
    render_words_parallel,
    sync_graph_from_table,
    upsert_words,
    TableLock,
    load_core,
)


def repo_root() -> Path:
    # scripts -> logic-english-mindmap -> skills -> .cursor -> repo
    return Path(__file__).resolve().parents[4]


def main() -> int:
    parser = argparse.ArgumentParser(description="Upsert logic-english word mindmap pages")
    parser.add_argument("lemma", nargs="?", help="Word lemma to upsert")
    parser.add_argument("--batch", help="Comma-separated lemmas")
    parser.add_argument("--root", default=None, help="Graph root (default: docs/逻辑英语/graph)")
    parser.add_argument("--jobs", type=int, default=min(8, os.cpu_count() or 4))
    parser.add_argument("--rebuild-all", action="store_true", help="Rebuild table and re-render all words")
    args = parser.parse_args()

    root = Path(args.root) if args.root else repo_root() / DEFAULT_ROOT
    ensure_dirs(root)

    if args.rebuild_all:
        with TableLock(root):
            table = rebuild_table_from_words(root)
            atomic_write_json(root / "lemma_table.json", table)
            graph = sync_graph_from_table(root, table)
            lemmas = [k for k, v in table.get("lemmas", {}).items() if v.get("exists")]
            updated = render_words_parallel(root, lemmas, table, args.jobs)
            for cid in (graph.get("cores") or {}):
                core = load_core(root, cid)
                if core:
                    from graph_lib import atomic_write_text

                    atomic_write_text(
                        root / "cores" / f"{cid}.html",
                        render_core_html(core, table),
                    )
            from graph_lib import atomic_write_text

            atomic_write_text(root / "index.html", render_index_html(root, graph, table))
            append_history(
                root,
                {
                    "op": "rebuild_table",
                    "links_updated": updated,
                    "workers": args.jobs,
                    "summary": f"rebuild-all {len(updated)} words",
                },
            )
        print(f"OK rebuild-all root={root} words={len(updated)} jobs={args.jobs}")
        return 0

    lemmas: list[str] = []
    if args.batch:
        lemmas.extend(x.strip().lower() for x in args.batch.split(",") if x.strip())
    if args.lemma:
        lemmas.append(args.lemma.strip().lower())
    lemmas = list(dict.fromkeys(lemmas))
    if not lemmas:
        parser.error("Provide lemma or --batch or --rebuild-all")

    event = upsert_words(root, lemmas, jobs=args.jobs)
    print(
        f"OK upsert {event.get('word')} cores_created={event.get('cores_created')} "
        f"rerender={event.get('links_updated')} jobs={args.jobs}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
