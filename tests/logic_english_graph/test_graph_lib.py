#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO / ".cursor/skills/logic-english-mindmap/scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from graph_lib import (  # noqa: E402
    apply_mentions_diff,
    backlinks_from_table,
    empty_table,
    linkables,
    upsert_words,
)


def test_linkables_unions_map_related_and_single_tokens():
    doc = {
        "lemma": "book",
        "map_words": ["box", "bow"],
        "related": ["boat"],
        "chains": [
            {"id": "R", "items": ["bowl", "book a room", "fully booked"]},
        ],
    }
    got = linkables(doc)
    assert got == {"box", "bow", "boat", "bowl"}


def test_table_mentioned_by_after_book_then_bow(tmp_path: Path):
    root = tmp_path / "graph"
    (root / "words").mkdir(parents=True)
    (root / "cores").mkdir(parents=True)

    book = {
        "lemma": "book",
        "core": {"id": "hezi", "name": "盒子", "def": "有边界的容器"},
        "basic": "装页的盒",
        "chains": [{"id": "R", "title": "同核", "items": ["bow", "box"]}],
        "related": ["bow", "box"],
        "map_words": ["bow", "box"],
        "examples": ["This book is a box of pages."],
        "notes": "教学逻辑",
    }
    (root / "words" / "book.json").write_text(
        __import__("json").dumps(book, ensure_ascii=False), encoding="utf-8"
    )
    upsert_words(root, ["book"], jobs=1)

    table = __import__("json").loads((root / "lemma_table.json").read_text(encoding="utf-8"))
    assert table["lemmas"]["book"]["exists"] is True
    assert "book" in table["lemmas"]["bow"]["mentioned_by"]
    assert table["lemmas"]["bow"]["exists"] is False

    book_html = (root / "words" / "book.html").read_text(encoding="utf-8")
    assert "bow" in book_html  # appears on Mermaid mindmap
    assert "../words/bow.html" not in book_html  # not clickable until generated

    bow = {
        "lemma": "bow",
        "core": {"id": "hezi", "name": "盒子", "def": "有边界的容器"},
        "basic": "船头 / 弯曲",
        "chains": [{"id": "R", "title": "同核", "items": ["book", "boat"]}],
        "related": ["book", "boat"],
        "map_words": ["book", "boat"],
        "examples": ["Stand at the bow of the boat."],
    }
    (root / "words" / "bow.json").write_text(
        __import__("json").dumps(bow, ensure_ascii=False), encoding="utf-8"
    )
    upsert_words(root, ["bow"], jobs=2)

    table = __import__("json").loads((root / "lemma_table.json").read_text(encoding="utf-8"))
    assert table["lemmas"]["bow"]["exists"] is True
    assert backlinks_from_table(table, "bow") == ["book"]

    book_html2 = (root / "words" / "book.html").read_text(encoding="utf-8")
    assert "../words/bow.html" in book_html2  # Mermaid click-map → local page

    bow_html = (root / "words" / "bow.html").read_text(encoding="utf-8")
    assert "../words/book.html" in bow_html

    assert (root / "cores" / "hezi.html").exists()
    assert (root / "index.html").exists()
    index = (root / "index.html").read_text(encoding="utf-8")
    assert "cores/hezi.html" in index


def test_apply_mentions_diff_removes_stale():
    table = empty_table()
    apply_mentions_diff(table, "book", {"bow", "box"}, exists=True, core_id="hezi")
    apply_mentions_diff(table, "book", {"box"}, exists=True, core_id="hezi")
    assert "book" not in table["lemmas"]["bow"]["mentioned_by"]
    assert "book" in table["lemmas"]["box"]["mentioned_by"]
