#!/usr/bin/env python3
"""Content pedagogy gate: prevent 张冠李戴 (wrong core / sense / image pairing)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from graph_lib import (  # noqa: E402
    DEFAULT_ROOT,
    core_display_label,
    load_core,
    load_json,
    load_word,
)
from review_images import CONFUSABLE  # noqa: E402

CHECK_KEYS = (
    "core_key_ok",
    "lemma_on_core_ok",
    "basic_matches_lemma",
    "image_matches_sense",
    "chains_coherent",
    "child_clear",
)

# lemma -> forbidden substrings in basic / image.primary_sense (lowercase)
SENSE_FORBIDDEN: dict[str, list[str]] = {
    "bow": ["船头为主", "floating boat as main", "一艘船作为主物"],
    "boat": ["archery", "弓弦", "木弓为主"],
    "bowl": ["closed carton as main", "合上的纸箱为主"],
    "box": ["open bowl as main", "碗作为主物"],
    "book": ["empty box only", "空箱子当作书"],
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def lemma_fits_key(lemma: str, key: str) -> bool:
    if not key:
        return False
    lemma = lemma.lower()
    key = key.lower()
    if lemma.startswith(key):
        return True
    # allow key as syllable-like infix at start cluster, e.g. future rules
    if key in lemma[: max(len(key) + 2, 4)]:
        return True
    return False


def check_word(root: Path, lemma: str, doc: dict) -> list[str]:
    errors: list[str] = []
    core = doc.get("core") or {}
    cid = str(core.get("id") or "").strip().lower()
    key = str(core.get("key") or cid).strip().lower()
    prototype = str(core.get("prototype") or "").strip().lower()
    name = str(core.get("name") or "").strip()

    if not cid or not key:
        errors.append(f"word:{lemma}: core.id/key required (音形键)")
    elif cid != key:
        errors.append(f"word:{lemma}: core.id ({cid}) must equal core.key ({key})")

    if not prototype:
        errors.append(f"word:{lemma}: core.prototype required (e.g. box)")
    if not name:
        errors.append(f"word:{lemma}: core.name required (中文意象)")

    label = core_display_label(core)
    if key and prototype and name and f"{key} ---- {prototype}（{name}）" != label:
        errors.append(f"word:{lemma}: core label malformed: {label!r}")

    if key and not lemma_fits_key(lemma, key):
        # allow explicit override in content_review.claims
        claims = (doc.get("content_review") or {}).get("claims") or {}
        if not claims.get("lemma_fits_key_exception"):
            errors.append(
                f"word:{lemma}: lemma does not fit core key {key!r} "
                f"(set content_review.claims.lemma_fits_key_exception if intentional)"
            )

    basic = str(doc.get("basic") or "").strip()
    if len(basic) < 4:
        errors.append(f"word:{lemma}: basic too short")

    # sense vs confusable: image primary_sense must not look like sibling object
    img = doc.get("image") or {}
    primary = str(img.get("primary_sense") or "").lower()
    if lemma in CONFUSABLE:
        for frag in CONFUSABLE[lemma].get("must_not_show") or []:
            f = str(frag).lower()
            # only flag strong object words in primary_sense
            if f in {"boat", "ship", "hull", "archery", "bowl", "box"} and f in primary:
                # bow primary should not contain boat
                if lemma == "bow" and f in {"boat", "ship", "hull"}:
                    errors.append(
                        f"word:{lemma}: image.primary_sense looks like confusable ({f}): {primary!r}"
                    )
                if lemma == "boat" and f in {"archery"}:
                    errors.append(
                        f"word:{lemma}: image.primary_sense looks like confusable ({f}): {primary!r}"
                    )

    for frag in SENSE_FORBIDDEN.get(lemma, []):
        blob = f"{basic} {primary}".lower()
        if frag.lower() in blob:
            errors.append(f"word:{lemma}: basic/primary contains forbidden sense cue {frag!r}")

    # core file consistency
    if cid:
        core_doc = load_core(root, cid)
        if core_doc is None:
            errors.append(f"word:{lemma}: missing cores/{cid}.json")
        else:
            if str(core_doc.get("key") or core_doc.get("id")) != key:
                errors.append(f"word:{lemma}: core file key mismatch")
            if prototype and str(core_doc.get("prototype") or "").lower() not in ("", prototype):
                if str(core_doc.get("prototype") or "").lower() != prototype:
                    errors.append(
                        f"word:{lemma}: core.prototype {prototype} != file {core_doc.get('prototype')}"
                    )

    # content_review gate
    review = doc.get("content_review") or {}
    if review.get("status") != "approved":
        errors.append(f"word:{lemma}: content_review.status must be 'approved' (got {review.get('status')!r})")
    checklist = review.get("checklist") or {}
    for k in CHECK_KEYS:
        if checklist.get(k) is not True:
            errors.append(f"word:{lemma}: content_review.checklist.{k} must be true")
    if not str(review.get("reviewed_at") or "").strip():
        errors.append(f"word:{lemma}: content_review.reviewed_at required")

    return errors


def check_core(root: Path, cid: str, core: dict) -> list[str]:
    errors: list[str] = []
    key = str(core.get("key") or core.get("id") or "").strip().lower()
    if str(core.get("id") or "").lower() != key:
        errors.append(f"core:{cid}: id must equal key (音形键)")
    if not core.get("prototype"):
        errors.append(f"core:{cid}: prototype required")
    if not core.get("name"):
        errors.append(f"core:{cid}: name required")
    label = core_display_label(core)
    if "----" not in label:
        errors.append(f"core:{cid}: display label must be like 'bo ---- box（盒子）', got {label!r}")
    review = core.get("content_review") or {}
    if review.get("status") != "approved":
        errors.append(f"core:{cid}: content_review.status must be 'approved'")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None)
    args = parser.parse_args()
    root = Path(args.root) if args.root else repo_root() / DEFAULT_ROOT
    errors: list[str] = []

    table = load_json(root / "lemma_table.json", {"lemmas": {}})
    graph = load_json(root / "graph.json", {"cores": {}})

    for lemma, entry in sorted((table.get("lemmas") or {}).items()):
        if not entry.get("exists"):
            continue
        doc = load_word(root, lemma)
        errors.extend(check_word(root, lemma, doc))

    for cid in sorted((graph.get("cores") or {}).keys()):
        core = load_core(root, cid) or {}
        errors.extend(check_core(root, cid, core))

    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        print(f"FAIL review_content ({len(errors)} errors)")
        return 1
    print(f"OK review_content root={root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
