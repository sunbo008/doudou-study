"""Validate the Markdown structure of the primary-school math map."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Sequence
from urllib.parse import unquote


@dataclass(frozen=True)
class Issue:
    path: Path
    rule: str
    message: str


REQUIRED_EXAMPLE_HEADINGS = (
    "题目",
    "难度",
    "解题技巧",
    "步骤要点",
    "避坑思路",
    "答案",
)

VALID_STATUSES = {"draft", "active", "deprecated"}
VALID_SOURCE_VERIFICATIONS = {"verified_book", "verified_public", "pending"}
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
EXAMPLE_HEADING = re.compile(r"^### 例题(?:\s|$)", re.MULTILINE)
EXAMPLE_END_HEADING = re.compile(
    r"^(?:#{1,2}\s|### (?!例题(?:\s|$)))", re.MULTILINE
)
SECTION_HEADING = re.compile(r"^#### (.+?)\s*$", re.MULTILINE)
ANY_HEADING = re.compile(r"^#{1,4}\s", re.MULTILINE)


def _split_inline_values(value: str) -> list[str]:
    """Split the small YAML-like inline lists and maps used by this project."""
    values: list[str] = []
    current: list[str] = []
    quote: str | None = None
    for character in value:
        if character in {"'", '"'}:
            if quote == character:
                quote = None
            elif quote is None:
                quote = character
        if character == "," and quote is None:
            values.append("".join(current).strip())
            current = []
        else:
            current.append(character)
    values.append("".join(current).strip())
    return values


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        contents = value[1:-1].strip()
        return [] if not contents else [_parse_scalar(item) for item in _split_inline_values(contents)]
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def _parse_inline_map(value: str) -> dict[str, Any]:
    contents = value.strip()
    if not (contents.startswith("{") and contents.endswith("}")):
        return {}
    result: dict[str, Any] = {}
    for entry in _split_inline_values(contents[1:-1]):
        if ":" not in entry:
            return {}
        key, raw_value = entry.split(":", 1)
        result[key.strip()] = _parse_scalar(raw_value)
    return result


def parse_frontmatter(text: str) -> dict[str, Any]:
    """Parse the constrained frontmatter shape used by math-map entries."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    try:
        end = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration:
        return {}

    result: dict[str, Any] = {}
    index = 1
    while index < end:
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            index += 1
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.split(" #", 1)[0].strip()
        if key != "pep_units":
            result[key] = _parse_scalar(raw_value)
            index += 1
            continue

        units: list[dict[str, Any]] = []
        index += 1
        while index < end and lines[index].startswith((" ", "\t")):
            item = lines[index].strip()
            if item.startswith("- "):
                parsed = _parse_inline_map(item[2:])
                if parsed:
                    units.append(parsed)
            index += 1
        result[key] = units
    return result


def scan_markdown_links(text: str) -> list[str]:
    """Return inline Markdown link targets, excluding image links."""
    links: list[str] = []
    for match in MARKDOWN_LINK.finditer(text):
        target = match.group(1).strip()
        if target.startswith("<") and target.endswith(">"):
            target = target[1:-1]
        links.append(target.split(maxsplit=1)[0])
    return links


def _section_content(section: str) -> str:
    return "\n".join(
        line for line in section.splitlines() if line.strip() and line.strip() != "---"
    ).strip()


def _example_sections(example: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    headings = list(SECTION_HEADING.finditer(example))
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(example)
        next_heading = ANY_HEADING.search(example, match.end())
        if next_heading is not None and next_heading.start() < end:
            end = next_heading.start()
        sections.setdefault(match.group(1), example[match.end() : end])
    return sections


def validate_kp(
    path: Path,
    *,
    text: str | None = None,
    frontmatter: dict[str, Any] | None = None,
) -> list[Issue]:
    """Validate one knowledge-point document except global duplicate checks."""
    if text is None:
        text = path.read_text(encoding="utf-8")
    if frontmatter is None:
        frontmatter = parse_frontmatter(text)
    issues: list[Issue] = []

    for field in ("kp_id", "specialty_id", "grades", "pep_units", "status", "source_verification"):
        if field not in frontmatter or frontmatter[field] in ("", [], None):
            issues.append(Issue(path, "missing-frontmatter-field", f"缺少 {field}"))

    kp_id = frontmatter.get("kp_id")
    if isinstance(kp_id, str) and kp_id and kp_id != path.stem:
        issues.append(Issue(path, "kp-id-filename-mismatch", "kp_id 必须与文件名主干一致"))

    specialty_id = frontmatter.get("specialty_id")
    if not isinstance(specialty_id, str) or not re.fullmatch(r"S(?:0[1-9]|1[0-4])", specialty_id):
        issues.append(Issue(path, "invalid-specialty-id", "specialty_id 必须是 S01 到 S14"))

    grades = frontmatter.get("grades")
    if not isinstance(grades, list) or not grades or any(
        not isinstance(grade, int) or grade not in range(1, 7) for grade in grades
    ):
        issues.append(Issue(path, "invalid-grades", "grades 必须是 1 到 6 的行内列表"))

    pep_units = frontmatter.get("pep_units")
    if not isinstance(pep_units, list) or not pep_units or any(
        not isinstance(unit, dict)
        or not isinstance(unit.get("grade"), int)
        or unit["grade"] not in range(1, 7)
        or not isinstance(unit.get("volume"), str)
        or not unit["volume"]
        or not isinstance(unit.get("unit"), str)
        or not unit["unit"]
        for unit in pep_units
    ):
        issues.append(Issue(path, "invalid-pep-units", "pep_units 必须含有效的 grade、volume、unit"))

    status = frontmatter.get("status")
    if status not in (None, "") and status not in VALID_STATUSES:
        issues.append(Issue(path, "invalid-status", "status 必须是 draft、active 或 deprecated"))

    source = frontmatter.get("source_verification")
    if source not in (None, "") and source not in VALID_SOURCE_VERIFICATIONS:
        issues.append(
            Issue(
                path,
                "invalid-source-verification",
                "source_verification 必须是 verified_book、verified_public 或 pending",
            )
        )
    if status == "active" and source == "pending":
        issues.append(Issue(path, "active-pending-source", "pending 条目不得标为 active"))

    examples = list(EXAMPLE_HEADING.finditer(text))
    actual_levels: set[str] = set()
    for number, match in enumerate(examples, 1):
        end = examples[number].start() if number < len(examples) else len(text)
        next_non_example_heading = EXAMPLE_END_HEADING.search(text, match.end())
        if next_non_example_heading is not None:
            end = min(end, next_non_example_heading.start())
        sections = _example_sections(text[match.end() : end])
        missing = [heading for heading in REQUIRED_EXAMPLE_HEADINGS if heading not in sections]
        if missing:
            issues.append(
                Issue(
                    path,
                    "example-section-missing",
                    f"例题 {number} 缺少子块：{'、'.join(missing)}",
                )
            )
        empty = [
            heading
            for heading in REQUIRED_EXAMPLE_HEADINGS
            if heading in sections and not _section_content(sections[heading])
        ]
        if empty:
            issues.append(
                Issue(
                    path,
                    "example-section-empty",
                    f"例题 {number} 子块内容为空：{'、'.join(empty)}",
                )
            )
        difficulty = _section_content(sections.get("难度", ""))
        if difficulty:
            if difficulty not in {"L1", "L2", "L3", "L4"}:
                issues.append(
                    Issue(
                        path,
                        "invalid-example-difficulty",
                        f"例题 {number} 难度必须是 L1、L2、L3 或 L4",
                    )
                )
            else:
                actual_levels.add(difficulty)

    if status == "active" and not {"L1", "L2"}.issubset(actual_levels):
        issues.append(Issue(path, "active-missing-required-levels", "active 条目至少需要 L1 和 L2 例题"))
    return issues


def _is_external_link(target: str) -> bool:
    return target.startswith(("http://", "https://", "mailto:", "tel:", "#"))


def validate(root: Path) -> list[Issue]:
    """Validate a math-map directory and return all detected issues."""
    root = root.resolve()
    if not root.is_dir():
        return [Issue(root, "invalid-root", "地图根目录不存在或不是目录")]
    issues: list[Issue] = []
    kp_paths = sorted(root.rglob("kp_*.md"))
    kp_ids: dict[str, list[Path]] = {}

    for path in kp_paths:
        text = path.read_text(encoding="utf-8")
        frontmatter = parse_frontmatter(text)
        issues.extend(validate_kp(path, text=text, frontmatter=frontmatter))
        kp_id = frontmatter.get("kp_id")
        if isinstance(kp_id, str) and kp_id:
            kp_ids.setdefault(kp_id, []).append(path)

    for kp_id, paths in kp_ids.items():
        if len(paths) > 1:
            for path in paths:
                issues.append(Issue(path, "duplicate-kp-id", f"kp_id 重复：{kp_id}"))

    for path in sorted(root.rglob("*.md")):
        for target in scan_markdown_links(path.read_text(encoding="utf-8")):
            if _is_external_link(target):
                continue
            local_target = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if not local_target:
                continue
            if not (path.parent / local_target).resolve().exists():
                issues.append(Issue(path, "broken-link", f"链接目标不存在：{target}"))

    return sorted(issues, key=lambda issue: (str(issue.path), issue.rule, issue.message))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="小学数学地图根目录")
    args = parser.parse_args(argv)
    issues = validate(args.root)
    if issues:
        for issue in issues:
            print(f"{issue.path}: {issue.rule}: {issue.message}")
        return 1
    print("PASS: math map validation succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
