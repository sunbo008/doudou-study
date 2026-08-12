from __future__ import annotations

import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from scripts.validate_math_map import main, parse_frontmatter, validate


class MathMapValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_kp(
        self,
        filename: str,
        *,
        kp_id: str | None = None,
        status: str = "active",
        source: str = "verified_book",
        example_body: str | None = None,
    ) -> Path:
        if kp_id is None:
            kp_id = Path(filename).stem
        if example_body is None:
            example_body = """#### 题目

1 + 1 等于多少？

#### 难度

L1

#### 解题技巧

直接计算。

#### 步骤要点

1. 相加。

#### 避坑思路

不要漏写结果。

#### 答案

2

### 例题 2

#### 题目

2 + 2 等于多少？

#### 难度

L2

#### 解题技巧

直接计算。

#### 步骤要点

1. 相加。

#### 避坑思路

不要漏写结果。

#### 答案

4"""

        path = self.root / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"""---
kp_id: {kp_id}
title: 测试条目
specialty_id: S01
grades: [1]
pep_units:
  - {{ grade: 1, volume: 上, unit: \"测试单元\" }}
status: {status}
source_verification: {source}
practice: practice/W1
weak_ref: W1
lateral_tags: []
---

# 测试条目

## 典型题型（按难度）

| 难度 | 题型描述 | 状态 |
|---|---|---|
| L1 | 基础 | 已写 |
| L2 | 熟练 | 已写 |

## 例题

### 例题 1

{example_body}
""",
            encoding="utf-8",
        )
        return path

    def test_minimal_valid_entry_has_no_issues(self) -> None:
        self.write_kp("kp_s01_valid.md")

        self.assertEqual(validate(self.root), [])

    def test_duplicate_kp_id_is_rejected(self) -> None:
        self.write_kp("first/kp_s01_shared.md")
        self.write_kp("second/kp_s01_shared.md")

        rules = {issue.rule for issue in validate(self.root)}

        self.assertIn("duplicate-kp-id", rules)

    def test_active_pending_source_is_rejected(self) -> None:
        self.write_kp("kp_s01_bad.md", status="active", source="pending")

        rules = {issue.rule for issue in validate(self.root)}

        self.assertIn("active-pending-source", rules)

    def test_example_without_required_subsection_is_rejected(self) -> None:
        self.write_kp(
            "kp_s01_missing_answer.md",
            status="draft",
            example_body="""#### 题目

1 + 1 等于多少？

#### 难度

L1

#### 解题技巧

直接计算。

#### 步骤要点

1. 相加。

#### 避坑思路

不要漏写结果。""",
        )

        rules = {issue.rule for issue in validate(self.root)}

        self.assertIn("example-section-missing", rules)

    def test_example_does_not_borrow_answer_from_later_level_two_section(self) -> None:
        path = self.write_kp(
            "kp_s01_missing_answer_before_common_pitfalls.md",
            status="draft",
            example_body="""#### 题目

1 + 1 等于多少？

#### 难度

L1

#### 解题技巧

直接计算。

#### 步骤要点

1. 相加。

#### 避坑思路

不要漏写结果。""",
        )
        with path.open("a", encoding="utf-8") as file:
            file.write("\n\n## 常见坑\n\n#### 答案\n\n不能借给例题。\n")

        rules = {issue.rule for issue in validate(self.root)}

        self.assertIn("example-section-missing", rules)

    def test_example_does_not_borrow_difficulty_from_later_non_example(self) -> None:
        path = self.write_kp(
            "kp_s01_missing_difficulty_before_note.md",
            status="draft",
            example_body="""#### 题目

1 + 1 等于多少？

#### 解题技巧

直接计算。

#### 步骤要点

1. 相加。

#### 避坑思路

不要漏写结果。

#### 答案

2""",
        )
        with path.open("a", encoding="utf-8") as file:
            file.write("\n\n### 补充说明\n\n#### 难度\n\nL1\n")

        rules = {issue.rule for issue in validate(self.root)}

        self.assertIn("example-section-missing", rules)

    def test_example_subsection_without_content_is_rejected(self) -> None:
        self.write_kp(
            "kp_s01_empty_answer.md",
            status="draft",
            example_body="""#### 题目

1 + 1 等于多少？

#### 难度

L1

#### 解题技巧

直接计算。

#### 步骤要点

1. 相加。

#### 避坑思路

不要漏写结果。

#### 答案

### 例题 2

#### 题目

2 + 2 等于多少？

#### 难度

L2

#### 解题技巧

直接计算。

#### 步骤要点

1. 相加。

#### 避坑思路

不要漏写结果。

#### 答案

4""",
        )

        rules = {issue.rule for issue in validate(self.root)}

        self.assertIn("example-section-empty", rules)

    def test_example_difficulty_must_be_l1_through_l4(self) -> None:
        self.write_kp(
            "kp_s01_invalid_difficulty.md",
            status="draft",
            example_body="""#### 题目

1 + 1 等于多少？

#### 难度

L5

#### 解题技巧

直接计算。

#### 步骤要点

1. 相加。

#### 避坑思路

不要漏写结果。

#### 答案

2""",
        )

        rules = {issue.rule for issue in validate(self.root)}

        self.assertIn("invalid-example-difficulty", rules)

    def test_active_l1_l2_must_come_from_actual_examples(self) -> None:
        self.write_kp(
            "kp_s01_wrong_levels.md",
            example_body="""#### 题目

1 + 1 等于多少？

#### 难度

L5

#### 解题技巧

直接计算。

#### 步骤要点

1. 相加。

#### 避坑思路

不要漏写结果。

#### 答案

2

#### 难度

L1

#### 难度

L2""",
        )

        rules = {issue.rule for issue in validate(self.root)}

        self.assertIn("active-missing-required-levels", rules)

    def test_missing_root_is_rejected(self) -> None:
        missing_root = self.root / "missing"

        issues = validate(missing_root)

        self.assertEqual([issue.rule for issue in issues], ["invalid-root"])

    def test_file_root_is_rejected(self) -> None:
        file_root = self.root / "not-a-directory.md"
        file_root.write_text("not a map directory\n", encoding="utf-8")

        issues = validate(file_root)

        self.assertEqual([issue.rule for issue in issues], ["invalid-root"])

    def test_broken_markdown_link_is_rejected(self) -> None:
        self.write_kp("kp_s01_valid.md")
        (self.root / "README.md").write_text(
            "[不存在的文件](missing.md)\n", encoding="utf-8"
        )

        rules = {issue.rule for issue in validate(self.root)}

        self.assertIn("broken-link", rules)

    def test_cli_prints_issues_and_returns_one(self) -> None:
        self.write_kp("kp_s01_valid.md")
        (self.root / "README.md").write_text(
            "[不存在的文件](missing.md)\n", encoding="utf-8"
        )
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            status = main([str(self.root)])

        self.assertEqual(status, 1)
        self.assertIn("README.md: broken-link:", output.getvalue())

    def test_cli_rejects_missing_root(self) -> None:
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            status = main([str(self.root / "missing")])

        self.assertEqual(status, 1)
        self.assertIn("missing: invalid-root:", output.getvalue())


class CatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        meta = self.root / "_meta"
        meta.mkdir()
        self.catalog = meta / "教材目录基线.md"

    def write_catalog(
        self,
        entry_type: str,
        coverage: str,
        *,
        header: str = "| 年级 | 册次 | 顺序 | 单元 | 类型 | 核验 | 证据 | 覆盖入口 |",
        grade: str = "6",
        volume: str = "上",
        verification: str = "verified_book",
        evidence: str = "[目录](../目录.jpg)",
    ) -> None:
        (self.root / "目录.jpg").write_bytes(b"catalog evidence")
        self.catalog.write_text(
            """# 教材目录基线

%s
|---|---|---:|---|---|---|---|---|
| %s | %s | 1 | 分数乘法 | %s | %s | %s | %s |
""" % (header, grade, volume, entry_type, verification, evidence, coverage),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_catalog_entry_uncovered_rejects_required_unit_without_coverage(self) -> None:
        self.write_catalog("正式单元", "")

        rules = {issue.rule for issue in validate(self.root)}

        self.assertIn("catalog-entry-uncovered", rules)

    def test_catalog_entry_uncovered_rejects_placeholder_or_broken_coverage(self) -> None:
        for coverage in ("占位", "[待建条目](../missing.md)"):
            with self.subTest(coverage=coverage):
                self.write_catalog("综合实践", coverage)

                rules = {issue.rule for issue in validate(self.root)}

                self.assertIn("catalog-entry-uncovered", rules)

    def test_review_aggregate_may_link_to_grade_index_anchor(self) -> None:
        (self.root / "年级索引.md").write_text("# 六年级\n", encoding="utf-8")
        self.write_catalog("复习聚合", "[六年级索引](../年级索引.md#六年级)")

        rules = {issue.rule for issue in validate(self.root)}

        self.assertNotIn("catalog-entry-uncovered", rules)

    def test_catalog_entry_uncovered_rejects_grade_index_or_readme_as_unit_coverage(self) -> None:
        for filename in ("年级索引.md", "README.md"):
            with self.subTest(filename=filename):
                (self.root / filename).write_text("# 六年级\n", encoding="utf-8")
                self.write_catalog("正式单元", f"[导航](../{filename})")

                rules = {issue.rule for issue in validate(self.root)}

                self.assertIn("catalog-entry-uncovered", rules)

    def test_catalog_entry_coverage_accepts_an_existing_knowledge_point_document(self) -> None:
        kp = self.root / "specialties" / "S01" / "kp_s01_valid.md"
        kp.parent.mkdir(parents=True)
        kp.write_text("# 知识正文\n", encoding="utf-8")
        self.write_catalog("正式单元", "[知识正文](../specialties/S01/kp_s01_valid.md)")

        rules = {issue.rule for issue in validate(self.root)}

        self.assertNotIn("catalog-entry-uncovered", rules)

    def test_review_aggregate_rejects_an_index_link_with_missing_anchor(self) -> None:
        (self.root / "年级索引.md").write_text("# 五年级\n", encoding="utf-8")
        self.write_catalog("复习聚合", "[六年级索引](../年级索引.md#六年级)")

        rules = {issue.rule for issue in validate(self.root)}

        self.assertIn("catalog-review-anchor-invalid", rules)

    def test_catalog_rejects_missing_or_inexact_fixed_header(self) -> None:
        self.write_catalog(
            "正式单元",
            "[知识正文](../specialties/S01/kp_s01_valid.md)",
            header="| 年级 | 册次 | 单元 | 类型 | 核验 | 证据 | 覆盖入口 |",
        )

        rules = {issue.rule for issue in validate(self.root)}

        self.assertIn("catalog-header-invalid", rules)

    def test_catalog_rejects_data_row_with_wrong_column_count(self) -> None:
        self.catalog.write_text(
            """# 教材目录基线

| 年级 | 册次 | 顺序 | 单元 | 类型 | 核验 | 证据 | 覆盖入口 |
|---|---|---:|---|---|---|---|---|
| 6 | 上 | 1 | 分数乘法 | 正式单元 | verified_book | [目录](../目录.jpg) |
""",
            encoding="utf-8",
        )

        rules = {issue.rule for issue in validate(self.root)}

        self.assertIn("catalog-row-column-count", rules)

    def test_catalog_rejects_invalid_entry_metadata_and_evidence(self) -> None:
        cases = (
            ("未知类型", "6", "上", "verified_book", "[目录](../目录.jpg)", "catalog-entry-type-invalid"),
            ("正式单元", "5", "上", "verified_book", "[目录](../目录.jpg)", "catalog-entry-grade-invalid"),
            ("正式单元", "6", "中", "verified_book", "[目录](../目录.jpg)", "catalog-entry-volume-invalid"),
            ("正式单元", "6", "上", "pending", "[目录](../目录.jpg)", "catalog-entry-verification-invalid"),
            ("正式单元", "6", "上", "verified_book", "[目录](../missing.jpg)", "catalog-entry-evidence-invalid"),
        )
        for entry_type, grade, volume, verification, evidence, expected_rule in cases:
            with self.subTest(expected_rule=expected_rule):
                self.write_catalog(
                    entry_type,
                    "[知识正文](../specialties/S01/kp_s01_valid.md)",
                    grade=grade,
                    volume=volume,
                    verification=verification,
                    evidence=evidence,
                )

                rules = {issue.rule for issue in validate(self.root)}

                self.assertIn(expected_rule, rules)


class CoverageTests(unittest.TestCase):
    MAP_ROOT = Path(__file__).resolve().parents[1] / "docs" / "小学数学地图"
    GRADE_INDEX = MAP_ROOT / "年级索引.md"
    SPECIALTY_INDEX = MAP_ROOT / "专项索引.md"
    TARGETS = (
        ("S03-分数", "kp_s03_fraction_multiply_meaning", "分数乘法"),
        ("S03-分数", "kp_s03_fraction_multiply_compute", "分数乘法"),
        ("S03-分数", "kp_s03_fraction_mixed_operations", "分数乘法"),
        ("S03-分数", "kp_s03_fraction_multiply_word_problems", "分数乘法"),
        ("S03-分数", "kp_s03_fraction_divide_meaning", "分数除法"),
        ("S03-分数", "kp_s03_fraction_divide_compute", "分数除法"),
        ("S03-分数", "kp_s03_fraction_divide_word_problems", "分数除法"),
        ("S05-比比例与正反比例", "kp_s05_ratio_meaning", "比"),
        ("S05-比比例与正反比例", "kp_s05_ratio_simplify", "比"),
        ("S05-比比例与正反比例", "kp_s05_ratio_application", "比"),
    )

    def test_phase_two_entries_exist_and_are_linked_once_in_each_view(self) -> None:
        grade_index = self.GRADE_INDEX.read_text(encoding="utf-8")
        specialty_index = self.SPECIALTY_INDEX.read_text(encoding="utf-8")

        for specialty, kp_id, unit in self.TARGETS:
            with self.subTest(kp_id=kp_id):
                entry = self.MAP_ROOT / "specialties" / specialty / f"{kp_id}.md"
                readme = entry.parent / "README.md"

                self.assertTrue(entry.is_file(), f"缺失知识点文件：{entry}")
                self.assertEqual(readme.read_text(encoding="utf-8").count(kp_id), 1)
                self.assertEqual(specialty_index.count(kp_id), 1)
                self.assertEqual(grade_index.count(kp_id), 1)

                frontmatter = parse_frontmatter(entry.read_text(encoding="utf-8"))
                self.assertEqual(
                    frontmatter.get("pep_units"),
                    [{"grade": 6, "volume": "上", "unit": unit}],
                )
                self.assertEqual(frontmatter.get("source_verification"), "verified_book")
                self.assertEqual(frontmatter.get("status"), "active")

    def test_active_phase_two_entries_do_not_use_placeholder_optional_references(self) -> None:
        forbidden = {"待建", "待归档"}

        for specialty, kp_id, _ in self.TARGETS:
            with self.subTest(kp_id=kp_id):
                entry = self.MAP_ROOT / "specialties" / specialty / f"{kp_id}.md"
                frontmatter = parse_frontmatter(entry.read_text(encoding="utf-8"))

                for field in ("practice", "weak_ref"):
                    if field in frontmatter:
                        self.assertNotIn(frontmatter[field], forbidden)

    def test_grade_six_index_orders_task_three_units(self) -> None:
        grade_index = self.GRADE_INDEX.read_text(encoding="utf-8")
        positions: dict[str, list[int]] = {"分数乘法": [], "分数除法": [], "比": []}

        for _, kp_id, unit in self.TARGETS:
            positions[unit].append(grade_index.index(f"{kp_id}.md"))

        self.assertLess(max(positions["分数乘法"]), min(positions["分数除法"]))
        self.assertLess(max(positions["分数除法"]), min(positions["比"]))


if __name__ == "__main__":
    unittest.main()
