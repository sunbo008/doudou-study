#!/usr/bin/env python3
"""Validate graph / lemma_table / word JSON consistency."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from graph_lib import (  # noqa: E402
    DEFAULT_ROOT,
    backlinks_from_table,
    empty_table,
    linkables,
    load_json,
    load_word,
    rebuild_table_from_words,
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None)
    args = parser.parse_args()
    root = Path(args.root) if args.root else repo_root() / DEFAULT_ROOT
    errors: list[str] = []
    warnings: list[str] = []

    table = load_json(root / "lemma_table.json", empty_table())
    rebuilt = rebuild_table_from_words(root)

    for lemma, entry in (rebuilt.get("lemmas") or {}).items():
        if not entry.get("exists"):
            continue
        te = (table.get("lemmas") or {}).get(lemma)
        if not te or not te.get("exists"):
            errors.append(f"table missing exists lemma: {lemma}")
            continue
        if set(te.get("mentions") or []) != set(entry.get("mentions") or []):
            errors.append(f"mentions drift for {lemma}: table={te.get('mentions')} json={entry.get('mentions')}")
        if set(te.get("mentioned_by") or []) != set(entry.get("mentioned_by") or []):
            errors.append(
                f"mentioned_by drift for {lemma}: table={te.get('mentioned_by')} expected={entry.get('mentioned_by')}"
            )

        doc = load_word(root, lemma)
        links = linkables(doc)
        map_words = {str(x).lower() for x in (doc.get("map_words") or [])}
        for tok in links:
            if tok not in map_words and tok not in {str(x).lower() for x in (doc.get("related") or [])}:
                # came only from chains single token — warn if not in map_words
                if tok not in map_words:
                    warnings.append(f"{lemma}: chain token '{tok}' not in map_words")

        html_path = root / "words" / f"{lemma}.html"
        if not html_path.exists():
            errors.append(f"missing html: {html_path}")

        expected_bl = backlinks_from_table(table, lemma)
        actual_bl = list(doc.get("backlinks") or [])
        if sorted(actual_bl) != sorted(expected_bl):
            warnings.append(f"{lemma}: backlinks json {actual_bl} vs table {expected_bl}")

    for cid in (load_json(root / "graph.json", {}).get("cores") or {}):
        if not (root / "cores" / f"{cid}.html").exists():
            errors.append(f"missing core html: {cid}")
        cjson = root / "cores" / f"{cid}.json"
        if not cjson.exists():
            errors.append(f"missing core json: {cid}")
        else:
            cdoc = load_json(cjson, {})
            img = (cdoc.get("image") or {}).get("path")
            if not img:
                warnings.append(f"core {cid}: missing image")
            elif not (root / img).exists():
                errors.append(f"core {cid}: image file missing: {img}")

    # concrete lemmas often need images; warn if exists but no image
    for lemma, entry in (table.get("lemmas") or {}).items():
        if not entry.get("exists"):
            continue
        doc = load_word(root, lemma)
        img = (doc.get("image") or {}).get("path")
        if not img:
            warnings.append(f"{lemma}: missing word image (required for 实物词)")
        elif not (root / img).exists():
            errors.append(f"{lemma}: image file missing: {img}")

    if not (root / "index.html").exists() and (table.get("lemmas") or {}):
        errors.append("missing index.html")

    # 教研门禁：内容张冠李戴检查
    try:
        from review_content import check_word, check_core
        for lemma, entry in sorted((table.get("lemmas") or {}).items()):
            if not entry.get("exists"):
                continue
            doc = load_word(root, lemma)
            for err in check_word(root, lemma, doc):
                errors.append(err)
        graph2 = load_json(root / "graph.json", {})
        for cid in sorted((graph2.get("cores") or {}).keys()):
            core = load_json(root / "cores" / f"{cid}.json", {})
            for err in check_core(root, cid, core):
                errors.append(err)
    except Exception as ex:
        warnings.append(f"review_content integration skipped: {ex}")

    # 教研门禁：复用 review_images 字段检查
    try:
        from review_images import check_image_obj
        for lemma, entry in sorted((table.get("lemmas") or {}).items()):
            if not entry.get("exists"):
                continue
            doc = load_word(root, lemma)
            for err in check_image_obj(f"word:{lemma}", doc.get("image"), root, lemma=lemma):
                errors.append(err)
        graph = load_json(root / "graph.json", {})
        for cid in sorted((graph.get("cores") or {}).keys()):
            core = load_json(root / "cores" / f"{cid}.json", {})
            for err in check_image_obj(f"core:{cid}", core.get("image"), root, lemma=None):
                errors.append(err)
    except Exception as ex:
        warnings.append(f"review_images integration skipped: {ex}")

    for w in warnings:
        print(f"WARN: {w}")
    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        print(f"FAIL ({len(errors)} errors, {len(warnings)} warnings)")
        return 1
    print(f"OK validate root={root} warnings={len(warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
