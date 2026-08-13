"""Validate the Markdown structure of the primary-school math map."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Sequence
from urllib.parse import unquote, urlparse


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
CATALOG_COLUMNS = ("年级", "册次", "顺序", "单元", "类型", "核验", "证据", "覆盖入口")
CATALOG_COVERED_TYPES = {"正式单元", "综合实践"}
CATALOG_ENTRY_TYPES = CATALOG_COVERED_TYPES | {"复习聚合"}
CATALOG_PATH = Path("_meta/教材目录基线.md")
CATALOG_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
DECLARED_LEVEL_ROW = re.compile(
    r"^\|\s*(L[34])\s*\|[^\n|]*\|\s*([^|\n]+?)\s*\|\s*$", re.MULTILINE
)
PUBLIC_SOURCE_DOMAINS = ("pep.com.cn", "gov.cn", "edu.cn")
PUBLIC_SOURCE_PATH = Path("_meta/三期来源核验记录.md")
PUBLIC_SOURCE_COLUMNS = (
    "年级",
    "册次",
    "核验",
    "页面标题",
    "证据",
    "访问日期",
    "可见目录",
    "版本与限制",
)


@dataclass(frozen=True)
class CatalogEntry:
    grade: str
    volume: str
    order: str
    unit: str
    entry_type: str
    verification: str
    evidence: str
    coverage: str


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


def _table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _catalog_table_start(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if line.startswith("|") and tuple(_table_cells(line)) == CATALOG_COLUMNS:
            return index
    return None


def parse_catalog(path: Path) -> list[CatalogEntry]:
    """Parse valid fixed-column curriculum catalog rows."""
    lines = path.read_text(encoding="utf-8").splitlines()
    header_index = _catalog_table_start(lines)
    if header_index is None:
        return []
    entries: list[CatalogEntry] = []
    for line in lines[header_index + 2 :]:
        if not line.startswith("|"):
            break
        cells = _table_cells(line)
        if len(cells) == len(CATALOG_COLUMNS):
            entries.append(CatalogEntry(*cells))
    return entries


def _approved_public_url(value: str) -> bool:
    targets = scan_markdown_links(value)
    if len(targets) != 1:
        return False
    parsed = urlparse(targets[0])
    hostname = (parsed.hostname or "").lower()
    return (
        parsed.scheme == "https"
        and not re.search(r"(?:^|\.)(?:google|bing|baidu)\.", hostname)
        and any(
            hostname == domain or hostname.endswith(f".{domain}")
            for domain in PUBLIC_SOURCE_DOMAINS
        )
    )


def validate_public_sources(root: Path) -> list[Issue]:
    """Validate the grades 1--5 public-source evidence ledger when present."""
    path = root / PUBLIC_SOURCE_PATH
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if line.startswith("|") and tuple(_table_cells(line)) == PUBLIC_SOURCE_COLUMNS
        ),
        None,
    )
    if header_index is None:
        return [Issue(path, "public-source-invalid", "公开来源表头或字段不完整")]

    issues: list[Issue] = []
    seen: set[tuple[int, str]] = set()
    for number, line in enumerate(lines[header_index + 2 :], header_index + 3):
        if not line.startswith("|"):
            break
        cells = _table_cells(line)
        if len(cells) != len(PUBLIC_SOURCE_COLUMNS):
            issues.append(Issue(path, "public-source-invalid", f"来源第 {number} 行必须恰有 8 列"))
            continue
        grade_text, volume, verification, title, evidence, date, catalog, limits = cells
        grade = int(grade_text) if grade_text.isdigit() else 0
        key = (grade, volume)
        if grade not in range(1, 6) or volume not in {"上", "下"} or key in seen:
            issues.append(Issue(path, "public-source-invalid", f"来源第 {number} 行年级册次非法或重复"))
        seen.add(key)
        if verification != "verified_public":
            issues.append(Issue(path, "public-source-invalid", f"来源第 {number} 行必须为 verified_public"))
        if not title or not _approved_public_url(evidence):
            issues.append(Issue(path, "public-source-invalid", f"来源第 {number} 行缺直接 HTTPS 权威原页或页面标题"))
        if date != "2026-08-12":
            issues.append(Issue(path, "public-source-invalid", f"来源第 {number} 行访问日期必须为 2026-08-12"))
        if not catalog or re.search(r"待核验|未取得|pending", catalog, re.IGNORECASE):
            issues.append(Issue(path, "public-source-invalid", f"来源第 {number} 行缺可见目录"))
        if not limits or "实书" not in limits:
            issues.append(Issue(path, "public-source-invalid", f"来源第 {number} 行须披露实书复核限制"))

    expected = {(grade, volume) for grade in range(1, 6) for volume in ("上", "下")}
    if seen != expected:
        missing = sorted(expected - seen)
        issues.append(Issue(path, "public-source-invalid", f"公开来源须覆盖十册，缺少：{missing}"))
    return issues


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
            elif not missing and not empty:
                actual_levels.add(difficulty)

    if status == "active" and not {"L1", "L2"}.issubset(actual_levels):
        issues.append(Issue(path, "active-missing-required-levels", "active 条目至少需要 L1 和 L2 例题"))
    return issues


def _is_external_link(target: str) -> bool:
    return target.startswith(("http://", "https://", "mailto:", "tel:", "#"))


def _catalog_local_links(catalog_path: Path, value: str) -> list[tuple[Path, str]]:
    links: list[tuple[Path, str]] = []
    for target in scan_markdown_links(value):
        if _is_external_link(target):
            continue
        local_target, _, anchor = unquote(target).partition("#")
        local_target = local_target.split("?", 1)[0]
        if local_target:
            links.append(((catalog_path.parent / local_target).resolve(), anchor))
    return links


def _catalog_coverage_is_valid(catalog_path: Path, coverage: str) -> bool:
    if not coverage.strip() or re.search(r"占位|待建|待补", coverage):
        return False
    links = _catalog_local_links(catalog_path, coverage)
    if len(links) != 1:
        return False
    path, _ = links[0]
    return path.is_file() and path.suffix == ".md" and path.name.startswith("kp_")


def _heading_anchor(heading: str) -> str:
    normalized = heading.strip().lower()
    normalized = re.sub(r"[^\w\u4e00-\u9fff -]", "", normalized)
    return re.sub(r"[ -]+", "-", normalized).strip("-")


def _catalog_review_anchor_is_valid(catalog_path: Path, coverage: str) -> bool:
    links = _catalog_local_links(catalog_path, coverage)
    if len(links) != 1:
        return False
    path, anchor = links[0]
    if path.name != "年级索引.md" or not anchor or not path.is_file():
        return False
    return any(_heading_anchor(match.group(1)) == anchor for match in MARKDOWN_HEADING.finditer(path.read_text(encoding="utf-8")))


def _catalog_evidence_is_valid(catalog_path: Path, entry: CatalogEntry) -> bool:
    targets = scan_markdown_links(entry.evidence)
    if len(targets) != 1:
        return False
    target = targets[0]
    if entry.verification == "verified_public":
        return _approved_public_url(entry.evidence)
    links = _catalog_local_links(catalog_path, entry.evidence)
    return (
        len(links) == 1
        and links[0][0].is_file()
        and links[0][0].suffix.lower() in CATALOG_IMAGE_SUFFIXES
    )


def _catalog_target(catalog_path: Path, coverage: str) -> Path | None:
    links = _catalog_local_links(catalog_path, coverage)
    if len(links) != 1:
        return None
    path, _ = links[0]
    return path if path.is_file() and path.name.startswith("kp_") else None


def validate_catalog(root: Path) -> list[Issue]:
    """Ensure required curriculum catalog entries lead to real content."""
    catalog_path = root / CATALOG_PATH
    if not catalog_path.is_file():
        if (root / "specialties").is_dir() or (root / "专项索引.md").is_file():
            return [Issue(catalog_path, "catalog-missing", "地图缺少教材目录基线")]
        return []
    issues: list[Issue] = []
    lines = catalog_path.read_text(encoding="utf-8").splitlines()
    header_index = _catalog_table_start(lines)
    if header_index is None:
        return [Issue(catalog_path, "catalog-header-invalid", "目录表头必须精确为：" + " | ".join(CATALOG_COLUMNS))]

    for number, line in enumerate(lines[header_index + 2 :], header_index + 3):
        if not line.startswith("|"):
            break
        cells = _table_cells(line)
        if len(cells) != len(CATALOG_COLUMNS):
            issues.append(Issue(catalog_path, "catalog-row-column-count", f"目录第 {number} 行必须恰有 8 列"))
            continue
        entry = CatalogEntry(*cells)
        if entry.entry_type not in CATALOG_ENTRY_TYPES:
            issues.append(Issue(catalog_path, "catalog-entry-type-invalid", f"目录第 {number} 行类型非法：{entry.entry_type}"))
        try:
            grade = int(entry.grade)
        except ValueError:
            grade = 0
        if grade not in range(1, 7):
            issues.append(Issue(catalog_path, "catalog-entry-grade-invalid", f"目录第 {number} 行年级必须为 1 到 6"))
        if entry.volume not in {"上", "下"}:
            issues.append(Issue(catalog_path, "catalog-entry-volume-invalid", f"目录第 {number} 行册次必须为 上 或 下"))
        expected_verification = "verified_book" if grade == 6 else "verified_public"
        if grade in range(1, 7) and entry.verification != expected_verification:
            issues.append(
                Issue(
                    catalog_path,
                    "catalog-entry-verification-invalid",
                    f"目录第 {number} 行核验必须为 {expected_verification}",
                )
            )
        if not _catalog_evidence_is_valid(catalog_path, entry):
            issues.append(
                Issue(
                    catalog_path,
                    "catalog-entry-evidence-invalid",
                    f"目录第 {number} 行证据与核验方式不匹配或不可解析",
                )
            )
        if entry.entry_type in CATALOG_COVERED_TYPES and not _catalog_coverage_is_valid(catalog_path, entry.coverage):
            issues.append(
                Issue(
                    catalog_path,
                    "catalog-entry-uncovered",
                    f"{entry.grade}年级{entry.volume}册《{entry.unit}》的覆盖入口为空、占位或断链",
                )
            )
        if entry.entry_type in CATALOG_COVERED_TYPES:
            target = _catalog_target(catalog_path, entry.coverage)
            if target is not None:
                target_frontmatter = parse_frontmatter(target.read_text(encoding="utf-8"))
                if target_frontmatter.get("status") != "active":
                    issues.append(
                        Issue(
                            catalog_path,
                            "catalog-target-not-active",
                            f"目录第 {number} 行覆盖目标必须是 active 条目",
                        )
                    )
                expected_unit = {"grade": grade, "volume": entry.volume, "unit": entry.unit}
                if expected_unit not in target_frontmatter.get("pep_units", []):
                    issues.append(
                        Issue(
                            catalog_path,
                            "catalog-target-pep-unit-mismatch",
                            f"目录第 {number} 行覆盖目标 pep_units 与目录年级、册次、单元不一致",
                        )
                    )
        if entry.entry_type == "复习聚合" and not _catalog_review_anchor_is_valid(catalog_path, entry.coverage):
            issues.append(
                Issue(
                    catalog_path,
                    "catalog-review-anchor-invalid",
                    f"{entry.grade}年级{entry.volume}册《{entry.unit}》的复习聚合必须链接存在的年级索引锚点",
                )
            )
    return issues


def _resolved_local_markdown_targets(path: Path, text: str) -> list[tuple[Path, str]]:
    targets: list[tuple[Path, str]] = []
    for target in scan_markdown_links(text):
        if target.startswith(("http://", "https://", "mailto:", "tel:")):
            continue
        local_target, _, anchor = unquote(target).partition("#")
        local_target = local_target.split("?", 1)[0]
        resolved = (path.parent / local_target).resolve() if local_target else path.resolve()
        targets.append((resolved, anchor))
    return targets


def _linked_paths(path: Path) -> set[Path]:
    if not path.is_file():
        return set()
    return {
        target
        for target, _ in _resolved_local_markdown_targets(
            path, path.read_text(encoding="utf-8")
        )
    }


def _normalized_stable_title(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[^\w\u4e00-\u9fff]", "", value).lower()


def _normalized_body(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        try:
            end = next(
                index for index, line in enumerate(lines[1:], 1) if line.strip() == "---"
            )
            lines = lines[end + 1 :]
        except StopIteration:
            pass
    return re.sub(r"\s+", "", "\n".join(lines))


def _declared_advanced_levels(path: Path, text: str) -> dict[str, bool]:
    declarations: dict[str, bool] = {}
    for level, state in DECLARED_LEVEL_ROW.findall(text):
        if "已写" in state:
            declarations[level] = False
            continue
        links = _resolved_local_markdown_targets(path, state)
        if not links:
            continue
        declarations[level] = any(
            target.is_file()
            and parse_frontmatter(target.read_text(encoding="utf-8")).get("status")
            == "active"
            for target, _ in links
        )
    return declarations


def _complete_example_levels(text: str) -> set[str]:
    """Return levels backed by one complete six-block example."""
    levels: set[str] = set()
    examples = list(EXAMPLE_HEADING.finditer(text))
    for number, match in enumerate(examples, 1):
        end = examples[number].start() if number < len(examples) else len(text)
        next_non_example_heading = EXAMPLE_END_HEADING.search(text, match.end())
        if next_non_example_heading is not None:
            end = min(end, next_non_example_heading.start())
        sections = _example_sections(text[match.end() : end])
        if any(
            heading not in sections or not _section_content(sections[heading])
            for heading in REQUIRED_EXAMPLE_HEADINGS
        ):
            continue
        difficulty = _section_content(sections["难度"])
        if difficulty in {"L1", "L2", "L3", "L4"}:
            levels.add(difficulty)
    return levels


def validate_global_contract(
    root: Path,
    entries: list[tuple[Path, str, dict[str, Any]]],
) -> list[Issue]:
    """Validate cross-file invariants whose source of truth is each kp document."""
    issues: list[Issue] = []
    specialty_index = root / "专项索引.md"
    grade_index = root / "年级索引.md"
    specialty_links = _linked_paths(specialty_index)
    grade_links = _linked_paths(grade_index)
    catalog_path = root / CATALOG_PATH
    enforce_catalog_contract = catalog_path.is_file() or (root / "specialties").is_dir()
    catalog_keys = {
        (int(entry.grade), entry.volume, entry.unit)
        for entry in (parse_catalog(catalog_path) if catalog_path.is_file() else [])
        if entry.grade.isdigit()
        and int(entry.grade) in range(1, 7)
        and entry.entry_type in CATALOG_COVERED_TYPES
    }
    titles: dict[str, list[Path]] = {}
    bodies: dict[str, list[Path]] = {}
    map_layout_present = (
        (root / "specialties").is_dir()
        or specialty_index.is_file()
        or grade_index.is_file()
    )

    for path, text, frontmatter in entries:
        specialty_id = frontmatter.get("specialty_id")
        relative_parts = path.relative_to(root).parts
        valid_location = (
            len(relative_parts) == 3
            and relative_parts[0] == "specialties"
            and re.fullmatch(r"S(?:0[1-9]|1[0-4])-.+", relative_parts[1]) is not None
        )
        if map_layout_present and not valid_location:
            issues.append(
                Issue(
                    path,
                    "kp-outside-specialties",
                    "kp_*.md 必须直接位于 specialties/Sxx-*/ 目录",
                )
            )
        directory_specialty = relative_parts[1].split("-", 1)[0] if valid_location else None
        if directory_specialty is not None and specialty_id != directory_specialty:
            issues.append(
                Issue(path, "specialty-directory-mismatch", "specialty_id 与专项目录不一致")
            )

        title_key = _normalized_stable_title(frontmatter.get("title"))
        if title_key:
            titles.setdefault(title_key, []).append(path)
        body_key = _normalized_body(text)
        if body_key:
            bodies.setdefault(body_key, []).append(path)

        grades = frontmatter.get("grades")
        pep_units = frontmatter.get("pep_units")
        if isinstance(grades, list) and isinstance(pep_units, list):
            pep_grades = {
                unit.get("grade") for unit in pep_units if isinstance(unit, dict)
            }
            if set(grades) != pep_grades:
                issues.append(
                    Issue(
                        path,
                        "grades-pep-units-mismatch",
                        "grades 必须与 pep_units 中实际出现的年级完全一致",
                    )
                )
            if (
                enforce_catalog_contract
                and frontmatter.get("status") == "active"
                and pep_grades
            ):
                expected_source = (
                    "verified_book"
                    if pep_grades == {6}
                    else "verified_public"
                    if all(isinstance(grade, int) and grade in range(1, 6) for grade in pep_grades)
                    else None
                )
                if expected_source is None or frontmatter.get("source_verification") != expected_source:
                    issues.append(
                        Issue(
                            path,
                            "source-verification-grade-mismatch",
                            "active 条目的来源核验状态必须与教材年级证据口径一致",
                        )
                    )
                for unit in pep_units:
                    if not isinstance(unit, dict):
                        continue
                    catalog_unit = str(unit.get("unit", "")).split(" / 分班衔接", 1)[0]
                    key = (unit.get("grade"), unit.get("volume"), catalog_unit)
                    if key not in catalog_keys:
                        issues.append(
                            Issue(
                                path,
                                "active-pep-unit-not-in-catalog",
                                f"active 条目的教材归属未出现在目录基线：{key}",
                            )
                        )

        actual_levels = _complete_example_levels(text)
        for level, valid_reference in _declared_advanced_levels(path, text).items():
            if level not in actual_levels and not valid_reference:
                issues.append(
                    Issue(
                        path,
                        "declared-level-missing-example",
                        f"典型题型声明 {level} 已写，但没有对应例题或 active 跨条目链接",
                    )
                )

        if frontmatter.get("status") != "active" or not valid_location:
            continue
        readme = path.parent / "README.md"
        if path.resolve() not in _linked_paths(readme):
            issues.append(
                Issue(path, "active-missing-specialty-readme", "active 条目未被专项 README 覆盖")
            )
        if path.resolve() not in specialty_links:
            issues.append(
                Issue(path, "active-missing-specialty-index", "active 条目未被专项索引覆盖")
            )
        if path.resolve() not in grade_links:
            issues.append(
                Issue(path, "active-missing-grade-index", "active 条目未被年级索引覆盖")
            )

    for paths in titles.values():
        if len(paths) > 1:
            for path in paths:
                issues.append(
                    Issue(path, "duplicate-stable-knowledge", "稳定知识点标题重复维护")
                )
    for paths in bodies.values():
        if len(paths) > 1:
            for path in paths:
                issues.append(Issue(path, "duplicate-body", "知识正文重复维护"))
    return issues


def validate(root: Path) -> list[Issue]:
    """Validate a math-map directory and return all detected issues."""
    root = root.resolve()
    if not root.is_dir():
        return [Issue(root, "invalid-root", "地图根目录不存在或不是目录")]
    issues: list[Issue] = []
    issues.extend(validate_public_sources(root))
    issues.extend(validate_catalog(root))
    kp_paths = sorted(root.rglob("kp_*.md"))
    kp_ids: dict[str, list[Path]] = {}
    entries: list[tuple[Path, str, dict[str, Any]]] = []

    for path in kp_paths:
        text = path.read_text(encoding="utf-8")
        frontmatter = parse_frontmatter(text)
        entries.append((path, text, frontmatter))
        issues.extend(validate_kp(path, text=text, frontmatter=frontmatter))
        kp_id = frontmatter.get("kp_id")
        if isinstance(kp_id, str) and kp_id:
            kp_ids.setdefault(kp_id, []).append(path)

    for kp_id, paths in kp_ids.items():
        if len(paths) > 1:
            for path in paths:
                issues.append(Issue(path, "duplicate-kp-id", f"kp_id 重复：{kp_id}"))

    issues.extend(validate_global_contract(root, entries))

    for path in sorted(root.rglob("*.md")):
        if path.resolve() == (root / CATALOG_PATH).resolve():
            continue
        text = path.read_text(encoding="utf-8")
        for target in scan_markdown_links(text):
            if target.startswith(("http://", "https://", "mailto:", "tel:")):
                continue
            local_target, _, anchor = unquote(target).partition("#")
            local_target = local_target.split("?", 1)[0]
            resolved = (path.parent / local_target).resolve() if local_target else path.resolve()
            if not resolved.exists():
                issues.append(Issue(path, "broken-link", f"链接目标不存在：{target}"))
                continue
            if anchor and resolved.is_file() and resolved.suffix == ".md":
                headings = MARKDOWN_HEADING.findall(resolved.read_text(encoding="utf-8"))
                if anchor not in {_heading_anchor(heading) for heading in headings}:
                    issues.append(Issue(path, "broken-anchor", f"链接锚点不存在：{target}"))

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
