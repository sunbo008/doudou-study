#!/usr/bin/env python3
"""Pedagogical gate for word/core images. Exit 1 if any image fails 教研 fields."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from graph_lib import DEFAULT_ROOT, load_core, load_json, load_word  # noqa: E402

# Built-in confusable registry (extend over time)
CONFUSABLE: dict[str, dict[str, list[str] | str]] = {
    "bow": {
        "primary_sense_hint": "archery bow",
        "must_not_show": ["boat", "ship", "hull", "船", "船头"],
    },
    "boat": {
        "primary_sense_hint": "watercraft boat",
        "must_not_show": ["archery", "bowstring", "弓"],
    },
    "bowl": {
        "primary_sense_hint": "open bowl",
        "must_not_show": ["box", "carton", "closed lid"],
    },
    "box": {
        "primary_sense_hint": "box/carton",
        "must_not_show": ["bowl", "book pages"],
    },
    "book": {
        "primary_sense_hint": "book",
        "must_not_show": ["empty box only"],
    },
    "boot": {
        "primary_sense_hint": "boot footwear",
        "must_not_show": ["bottle"],
    },
    "bottle": {
        "primary_sense_hint": "bottle",
        "must_not_show": ["boot"],
    },
}

CHECK_KEYS = (
    "primary_object_match",
    "must_show_ok",
    "must_not_show_ok",
    "presentation_ok",
    "child_recognizable",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def check_image_obj(label: str, image: dict | None, root: Path, *, lemma: str | None = None) -> list[str]:
    errors: list[str] = []
    if not image:
        errors.append(f"{label}: missing image object")
        return errors

    path = image.get("path")
    if not path:
        errors.append(f"{label}: image.path missing")
    elif not (root / path).exists():
        errors.append(f"{label}: file missing: {path}")

    if not str(image.get("primary_sense") or "").strip():
        errors.append(f"{label}: image.primary_sense required")

    must_show = image.get("must_show") or []
    must_not = image.get("must_not_show") or []
    if not isinstance(must_show, list) or len(must_show) < 1:
        errors.append(f"{label}: image.must_show must be non-empty list")
    if not isinstance(must_not, list) or len(must_not) < 1:
        errors.append(f"{label}: image.must_not_show must be non-empty list")

    if lemma and lemma in CONFUSABLE:
        required_forbidden = CONFUSABLE[lemma]["must_not_show"]
        lowered = " ".join(str(x).lower() for x in must_not)
        for frag in required_forbidden:
            if str(frag).lower() not in lowered:
                errors.append(
                    f"{label}: must_not_show missing confusable cue '{frag}' "
                    f"(registry for {lemma})"
                )

    review = image.get("review") or {}
    status = review.get("status")
    if status != "approved":
        errors.append(f"{label}: review.status must be 'approved' (got {status!r})")

    checklist = review.get("checklist") or {}
    for key in CHECK_KEYS:
        if checklist.get(key) is not True:
            errors.append(f"{label}: review.checklist.{key} must be true")

    if not str(review.get("reviewed_at") or "").strip():
        errors.append(f"{label}: review.reviewed_at required")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="教研门禁：校验实物图元数据与审批状态")
    parser.add_argument("--root", default=None)
    parser.add_argument("--allow-pending", action="store_true", help="Allow pending (draft mode)")
    args = parser.parse_args()
    root = Path(args.root) if args.root else repo_root() / DEFAULT_ROOT

    errors: list[str] = []
    table = load_json(root / "lemma_table.json", {"lemmas": {}})
    graph = load_json(root / "graph.json", {"cores": {}})

    for lemma, entry in sorted((table.get("lemmas") or {}).items()):
        if not entry.get("exists"):
            continue
        doc = load_word(root, lemma)
        img = doc.get("image")
        if args.allow_pending and (img or {}).get("review", {}).get("status") == "pending":
            continue
        errors.extend(check_image_obj(f"word:{lemma}", img, root, lemma=lemma))

    for cid in sorted((graph.get("cores") or {}).keys()):
        core = load_core(root, cid) or {}
        img = core.get("image")
        if args.allow_pending and (img or {}).get("review", {}).get("status") == "pending":
            continue
        errors.extend(check_image_obj(f"core:{cid}", img, root, lemma=None))

    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        print(f"FAIL review_images ({len(errors)} errors)")
        return 1
    print(f"OK review_images root={root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
