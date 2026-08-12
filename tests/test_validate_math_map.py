from __future__ import annotations

import contextlib
import io
from pathlib import Path
import re
import tempfile
import unittest

from scripts.validate_math_map import main, parse_frontmatter, scan_markdown_links, validate


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
    MAP_ROOT = Path(__file__).resolve().parents[1] / "docs" / "小学数学地图"
    TASK_FIVE_UNITS = ("数学广角——数与形", "确定起跑线", "节约用水")

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

    def test_task_five_catalog_entries_are_covered(self) -> None:
        issues = validate(self.MAP_ROOT)

        for unit in self.TASK_FIVE_UNITS:
            with self.subTest(unit=unit):
                self.assertFalse(
                    any(
                        issue.rule == "catalog-entry-uncovered"
                        and f"《{unit}》" in issue.message
                        for issue in issues
                    ),
                    f"目录项目尚未覆盖：{unit}",
                )


class CoverageTests(unittest.TestCase):
    MAP_ROOT = Path(__file__).resolve().parents[1] / "docs" / "小学数学地图"
    GRADE_INDEX = MAP_ROOT / "年级索引.md"
    SPECIALTY_INDEX = MAP_ROOT / "专项索引.md"
    TASK_FOUR_TARGETS = (
        ("S13-位置与方向", "kp_s13_direction_distance_angle", "位置与方向（二）"),
        ("S13-位置与方向", "kp_s13_route_description", "位置与方向（二）"),
        ("S07-平面图形与度量", "kp_s07_circle_parts", "圆"),
        ("S07-平面图形与度量", "kp_s07_circle_circumference", "圆"),
        ("S07-平面图形与度量", "kp_s07_circle_area", "圆"),
        ("S07-平面图形与度量", "kp_s07_sector_and_ring", "圆"),
        ("S07-平面图形与度量", "kp_s07_annulus_area", "圆"),
        ("S02-小数与百分数", "kp_s02_percent_meaning", "百分数（一）"),
        ("S02-小数与百分数", "kp_s02_percent_of_quantity", "百分数（一）"),
        ("S02-小数与百分数", "kp_s02_percent_change", "百分数（一）"),
        ("S10-统计与可能性", "kp_s10_fan_chart_reading", "扇形统计图"),
        ("S10-统计与可能性", "kp_s10_chart_data_inference", "扇形统计图"),
    )
    TASK_FIVE_TARGETS = (
        ("S11-数感与规律", "kp_s11_number_shape_patterns", "数学广角——数与形"),
        ("S09-应用题与数量关系", "kp_s09_race_start_compensation", "确定起跑线"),
        ("S09-应用题与数量关系", "kp_s09_water_saving_model", "节约用水"),
    )
    TASK_SIX_TARGETS = (
        ("S12-负数与综合实践", "kp_s12_negative_numbers_meaning", "负数"),
        ("S12-负数与综合实践", "kp_s12_negative_numbers_line", "负数"),
        ("S02-小数与百分数", "kp_s02_discount", "百分数（二）"),
        ("S02-小数与百分数", "kp_s02_tax_rate", "百分数（二）"),
        ("S02-小数与百分数", "kp_s02_interest_rate", "百分数（二）"),
        ("S02-小数与百分数", "kp_s02_percent_application", "生活与百分数"),
        ("S08-立体图形", "kp_s08_cylinder_surface_area", "圆柱与圆锥"),
        ("S08-立体图形", "kp_s08_cylinder_volume", "圆柱与圆锥"),
        ("S08-立体图形", "kp_s08_cone_volume", "圆柱与圆锥"),
        ("S08-立体图形", "kp_s08_composite_solids", "圆柱与圆锥"),
        ("S05-比比例与正反比例", "kp_s05_proportion_meaning", "比例"),
        ("S05-比比例与正反比例", "kp_s05_proportion_properties", "比例"),
        ("S05-比比例与正反比例", "kp_s05_direct_proportion", "比例"),
        ("S05-比比例与正反比例", "kp_s05_inverse_proportion", "比例"),
        ("S05-比比例与正反比例", "kp_s05_scale", "比例"),
        ("S09-应用题与数量关系", "kp_s09_bicycle_gearing", "自行车里的数学"),
        ("S09-应用题与数量关系", "kp_s09_pigeonhole_principle", "数学广角——鸽巢问题"),
    )
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
    ) + TASK_FOUR_TARGETS + TASK_FIVE_TARGETS

    def read_task_four_entry(self, kp_id: str) -> str:
        specialty = next(
            specialty
            for specialty, target_id, _ in self.TASK_FOUR_TARGETS
            if target_id == kp_id
        )
        path = self.MAP_ROOT / "specialties" / specialty / f"{kp_id}.md"
        self.assertTrue(path.is_file(), f"缺失知识点文件：{path}")
        return path.read_text(encoding="utf-8")

    @staticmethod
    def example_questions(text: str) -> list[str]:
        return [
            chunk.split("#### 题目", 1)[1].split("#### 难度", 1)[0]
            for chunk in text.split("### 例题 ")[1:]
        ]

    def test_phase_two_entries_exist_and_are_linked_once_in_each_view(self) -> None:
        grade_index = self.GRADE_INDEX.read_text(encoding="utf-8")
        specialty_index = self.SPECIALTY_INDEX.read_text(encoding="utf-8")
        grade_upper_table = grade_index.split("### 上册（实书目录对齐）", 1)[1].split(
            "### 六上总复习", 1
        )[0]

        for specialty, kp_id, unit in self.TARGETS:
            with self.subTest(kp_id=kp_id):
                entry = self.MAP_ROOT / "specialties" / specialty / f"{kp_id}.md"
                readme = entry.parent / "README.md"

                self.assertTrue(entry.is_file(), f"缺失知识点文件：{entry}")
                self.assertEqual(
                    readme.read_text(encoding="utf-8").count(f"(./{kp_id}.md)"), 1
                )
                self.assertEqual(specialty_index.count(kp_id), 1)
                self.assertEqual(grade_upper_table.count(kp_id), 1)

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
                if not entry.is_file():
                    continue
                frontmatter = parse_frontmatter(entry.read_text(encoding="utf-8"))

                for field in ("practice", "weak_ref"):
                    if field in frontmatter:
                        self.assertNotIn(frontmatter[field], forbidden)

    def test_task_four_readme_first_column_is_the_linked_kp_id(self) -> None:
        for specialty, kp_id, _ in self.TASK_FOUR_TARGETS:
            with self.subTest(kp_id=kp_id):
                readme = self.MAP_ROOT / "specialties" / specialty / "README.md"
                rows = [
                    line
                    for line in readme.read_text(encoding="utf-8").splitlines()
                    if f"(./{kp_id}.md)" in line
                ]
                self.assertEqual(len(rows), 1)
                first_cell = rows[0].strip().strip("|").split("|", 1)[0].strip()
                self.assertEqual(first_cell, f"[{kp_id}](./{kp_id}.md)")

    def test_task_five_readme_first_column_is_the_linked_kp_id(self) -> None:
        for specialty, kp_id, _ in self.TASK_FIVE_TARGETS:
            with self.subTest(kp_id=kp_id):
                readme = self.MAP_ROOT / "specialties" / specialty / "README.md"
                rows = [
                    line
                    for line in readme.read_text(encoding="utf-8").splitlines()
                    if f"(./{kp_id}.md)" in line
                ]
                self.assertEqual(len(rows), 1)
                first_cell = rows[0].strip().strip("|").split("|", 1)[0].strip()
                self.assertEqual(first_cell, f"[{kp_id}](./{kp_id}.md)")

    def test_task_five_entries_have_one_example_at_each_level(self) -> None:
        for specialty, kp_id, _ in self.TASK_FIVE_TARGETS:
            with self.subTest(kp_id=kp_id):
                path = self.MAP_ROOT / "specialties" / specialty / f"{kp_id}.md"
                self.assertTrue(path.is_file(), f"缺失知识点文件：{path}")
                text = path.read_text(encoding="utf-8")
                levels = re.findall(r"^#### 难度\s*\n\s*(L[1-4])\s*$", text, re.MULTILINE)
                self.assertEqual(levels, ["L1", "L2", "L3", "L4"])

    def test_task_six_target_files_exist(self) -> None:
        for specialty, kp_id, _ in self.TASK_SIX_TARGETS:
            with self.subTest(kp_id=kp_id):
                entry = self.MAP_ROOT / "specialties" / specialty / f"{kp_id}.md"
                self.assertTrue(entry.is_file(), f"缺失知识点文件：{entry}")

    def test_task_six_entries_are_active_verified_and_linked_once(self) -> None:
        grade_index = self.GRADE_INDEX.read_text(encoding="utf-8")
        specialty_index = self.SPECIALTY_INDEX.read_text(encoding="utf-8")
        grade_lower_table = grade_index.split("### 下册", 6)[-1].split(
            "### 六下整理和复习", 1
        )[0]

        for specialty, kp_id, unit in self.TASK_SIX_TARGETS:
            with self.subTest(kp_id=kp_id):
                entry = self.MAP_ROOT / "specialties" / specialty / f"{kp_id}.md"
                self.assertTrue(entry.is_file(), f"缺失知识点文件：{entry}")
                frontmatter = parse_frontmatter(entry.read_text(encoding="utf-8"))
                self.assertEqual(frontmatter.get("kp_id"), kp_id)
                self.assertEqual(frontmatter.get("status"), "active")
                self.assertEqual(frontmatter.get("source_verification"), "verified_book")
                self.assertEqual(frontmatter.get("grades"), [6])
                self.assertEqual(
                    frontmatter.get("pep_units"),
                    [{"grade": 6, "volume": "下", "unit": unit}],
                )
                for field in ("practice", "weak_ref"):
                    self.assertNotIn(frontmatter.get(field), {"待建", "待归档"})

                readme = entry.parent / "README.md"
                rows = [
                    line
                    for line in readme.read_text(encoding="utf-8").splitlines()
                    if f"(./{kp_id}.md)" in line
                ]
                self.assertEqual(len(rows), 1)
                first_cell = rows[0].strip().strip("|").split("|", 1)[0].strip()
                self.assertEqual(first_cell, f"[{kp_id}](./{kp_id}.md)")
                self.assertEqual(specialty_index.count(kp_id), 1)
                self.assertEqual(grade_lower_table.count(kp_id), 1)

    def test_task_six_entries_have_exactly_one_six_block_example_per_level(self) -> None:
        required = ("题目", "难度", "解题技巧", "步骤要点", "避坑思路", "答案")

        for specialty, kp_id, _ in self.TASK_SIX_TARGETS:
            with self.subTest(kp_id=kp_id):
                path = self.MAP_ROOT / "specialties" / specialty / f"{kp_id}.md"
                self.assertTrue(path.is_file(), f"缺失知识点文件：{path}")
                examples = path.read_text(encoding="utf-8").split("### 例题 ")[1:]
                self.assertEqual(len(examples), 4)
                self.assertEqual(
                    [re.search(r"^#### 难度\s*\n\s*(L[1-4])\s*$", item, re.MULTILINE).group(1) for item in examples],
                    ["L1", "L2", "L3", "L4"],
                )
                for example in examples:
                    for heading in required:
                        self.assertEqual(example.count(f"#### {heading}"), 1)

    def test_grade_six_lower_review_aggregates_every_active_entry_once(self) -> None:
        grade_index = self.GRADE_INDEX.read_text(encoding="utf-8")
        self.assertIn("### 六下整理和复习", grade_index)
        aggregate = grade_index.split("### 六下整理和复习", 1)[1].split(
            "\n### ", 1
        )[0]
        self.assertNotIn("### 例题", aggregate)

        active_ids = set()
        for path in sorted(self.MAP_ROOT.rglob("kp_*.md")):
            frontmatter = parse_frontmatter(path.read_text(encoding="utf-8"))
            if frontmatter.get("status") != "active":
                continue
            if any(
                unit.get("grade") == 6 and unit.get("volume") == "下"
                for unit in frontmatter.get("pep_units", [])
            ):
                active_ids.add(frontmatter["kp_id"])

        aggregate_ids = [
            Path(target.split("#", 1)[0].split("?", 1)[0]).stem
            for target in scan_markdown_links(aggregate)
            if Path(target.split("#", 1)[0].split("?", 1)[0]).name.startswith("kp_")
        ]
        self.assertEqual(len(aggregate_ids), len(set(aggregate_ids)))
        self.assertSetEqual(set(aggregate_ids), active_ids)

    def test_task_six_content_boundaries_and_model_conditions(self) -> None:
        def read(kp_id: str) -> str:
            specialty = next(
                folder
                for folder, target_id, _ in self.TASK_SIX_TARGETS
                if target_id == kp_id
            )
            return (
                self.MAP_ROOT / "specialties" / specialty / f"{kp_id}.md"
            ).read_text(encoding="utf-8")

        percent_application = read("kp_s02_percent_application")
        self.assertIn("生活与百分数", percent_application)
        self.assertIn("综合决策", percent_application)
        for target in ("kp_s02_discount", "kp_s02_tax_rate", "kp_s02_interest_rate"):
            self.assertNotEqual(
                parse_frontmatter(read(target)).get("pep_units"),
                parse_frontmatter(percent_application).get("pep_units"),
            )

        for kp_id in (
            "kp_s08_cylinder_surface_area",
            "kp_s08_cylinder_volume",
            "kp_s08_cone_volume",
            "kp_s08_composite_solids",
        ):
            for question in self.example_questions(read(kp_id)):
                self.assertRegex(question, r"厘米|分米|米")
                self.assertRegex(question, r"半径|直径")
                self.assertIn("高", question)
                self.assertRegex(question, r"有盖|无盖|封闭|开口|是否有盖")

        scale_l4 = self.example_questions(read("kp_s05_scale"))[3]
        for required_text in ("路线", "比例尺", "图上", "实际"):
            self.assertIn(required_text, scale_l4)

        bicycle_questions = "\n".join(self.example_questions(read("kp_s09_bicycle_gearing")))
        for required_text in ("前齿轮", "后齿轮", "不打滑", "车轮周长"):
            self.assertIn(required_text, bicycle_questions)

        pigeonhole = read("kp_s09_pigeonhole_principle")
        for required_text in ("最不利原则", "至少", "构造验证"):
            self.assertIn(required_text, pigeonhole)

    def test_tax_rate_level_four_defines_total_income_scope(self) -> None:
        path = (
            self.MAP_ROOT
            / "specialties"
            / "S02-小数与百分数"
            / "kp_s02_tax_rate.md"
        )
        level_four = path.read_text(encoding="utf-8").split("### 例题 ")[4]
        question = level_four.split("#### 题目", 1)[1].split("#### 难度", 1)[0]
        technique = level_four.split("#### 解题技巧", 1)[1].split(
            "#### 步骤要点", 1
        )[0]
        steps = level_four.split("#### 步骤要点", 1)[1].split(
            "#### 避坑思路", 1
        )[0]
        pitfall = level_four.split("#### 避坑思路", 1)[1].split("#### 答案", 1)[0]
        answer = level_four.split("#### 答案", 1)[1].split("## 常见坑", 1)[0]

        for required in ("全年总收入", "其中", "不计税", "可扣成本"):
            with self.subTest(section="question", required=required):
                self.assertIn(required, question)
        self.assertIn("总收入", technique)
        self.assertIn("80000-15000-5000=60000", steps)
        self.assertIn("80000-2400=77600", steps)
        self.assertIn("补贴已包含在全年总收入", pitfall)
        for expected in ("2400", "77600"):
            self.assertIn(expected, answer)

    def test_percent_application_combines_finance_tax_and_discount_models(self) -> None:
        base = self.MAP_ROOT / "specialties" / "S02-小数与百分数"
        application_text = (base / "kp_s02_percent_application.md").read_text(
            encoding="utf-8"
        )
        discount_text = (base / "kp_s02_discount.md").read_text(encoding="utf-8")
        level_two = application_text.split("### 例题 ")[2]
        level_four = application_text.split("### 例题 ")[4]
        level_two_question = level_two.split("#### 题目", 1)[1].split(
            "#### 难度", 1
        )[0]
        level_four_question = level_four.split("#### 题目", 1)[1].split(
            "#### 难度", 1
        )[0]
        discount_level_four_question = (
            discount_text.split("### 例题 ")[4]
            .split("#### 题目", 1)[1]
            .split("#### 难度", 1)[0]
        )

        for required in ("本金", "年利率", "利息", "折"):
            with self.subTest(level="L2", required=required):
                self.assertIn(required, level_two_question)
        for calculation in (
            "10000×1.8%=180",
            "200×80%=160",
            "180-160=20",
        ):
            with self.subTest(level="L2", calculation=calculation):
                self.assertIn(calculation, level_two)

        for required in (
            "全年总收入",
            "补贴不计税",
            "税率",
            "本金",
            "年利率",
            "八五折",
        ):
            with self.subTest(level="L4", required=required):
                self.assertIn(required, level_four_question)
        for calculation in (
            "100000-20000=80000",
            "80000×5%=4000",
            "100000-4000=96000",
            "30000×2%=600",
            "30000+600=30600",
            "36000×85%=30600",
            "96000+600-30600=66000",
        ):
            with self.subTest(level="L4", calculation=calculation):
                self.assertIn(calculation, level_four)
        self.assertNotEqual(
            level_four_question.strip(), discount_level_four_question.strip()
        )

    def test_task_six_solid_geometry_questions_state_pi_value_locally(self) -> None:
        base = self.MAP_ROOT / "specialties" / "S08-立体图形"
        for kp_id in (
            "kp_s08_cylinder_surface_area",
            "kp_s08_cylinder_volume",
            "kp_s08_cone_volume",
            "kp_s08_composite_solids",
        ):
            text = (base / f"{kp_id}.md").read_text(encoding="utf-8")
            for level, question in enumerate(self.example_questions(text), start=1):
                with self.subTest(kp_id=kp_id, level=f"L{level}"):
                    self.assertIn("π=3.14", question)

    def test_negative_number_meaning_level_two_uses_nonzero_reference(self) -> None:
        path = (
            self.MAP_ROOT
            / "specialties"
            / "S12-负数与综合实践"
            / "kp_s12_negative_numbers_meaning.md"
        )
        level_two = path.read_text(encoding="utf-8").split("### 例题 ")[2]
        question = level_two.split("#### 题目", 1)[1].split("#### 难度", 1)[0]

        for required in ("45 kg", "规定为 `0`", "-2 kg", "实际体重"):
            with self.subTest(required=required):
                self.assertIn(required, question)
        for calculation in ("45-2=43", "49-45=+4"):
            with self.subTest(calculation=calculation):
                self.assertIn(calculation, level_two)

    def test_race_start_level_two_states_complete_lap_assumptions(self) -> None:
        path = (
            self.MAP_ROOT
            / "specialties"
            / "S09-应用题与数量关系"
            / "kp_s09_race_start_compensation.md"
        )
        question = path.read_text(encoding="utf-8").split("### 例题 ")[2].split(
            "#### 难度", 1
        )[0]

        self.assertTrue("一整圈" in question or "360°" in question)
        self.assertIn("直线段等长", question)
        self.assertIn("终点相同", question)

    def test_race_start_level_four_states_partial_arc_assumptions(self) -> None:
        path = (
            self.MAP_ROOT
            / "specialties"
            / "S09-应用题与数量关系"
            / "kp_s09_race_start_compensation.md"
        )
        question = path.read_text(encoding="utf-8").split("### 例题 ")[4].split(
            "#### 难度", 1
        )[0]

        for required in ("同心圆弧", "直线部分等长", "相同总圆心角", "270°", "终点相同"):
            with self.subTest(required=required):
                self.assertIn(required, question)

    def test_water_saving_level_four_states_stratum_representativeness(self) -> None:
        path = (
            self.MAP_ROOT
            / "specialties"
            / "S09-应用题与数量关系"
            / "kp_s09_water_saving_model.md"
        )
        question = path.read_text(encoding="utf-8").split("### 例题 ")[4].split(
            "#### 难度", 1
        )[0]

        self.assertIn("两组样本分别能代表各自小区家庭", question)

    def test_grade_six_upper_review_aggregates_every_active_entry_once(self) -> None:
        grade_index = self.GRADE_INDEX.read_text(encoding="utf-8")
        self.assertIn("### 六上总复习", grade_index)
        aggregate = grade_index.split("### 六上总复习", 1)[1].split("\n### ", 1)[0]
        self.assertNotIn("### 例题", aggregate)

        active_ids = set()
        for path in sorted(self.MAP_ROOT.rglob("kp_*.md")):
            frontmatter = parse_frontmatter(path.read_text(encoding="utf-8"))
            if frontmatter.get("status") != "active":
                continue
            if not any(
                unit.get("grade") == 6 and unit.get("volume") == "上"
                for unit in frontmatter.get("pep_units", [])
            ):
                continue
            active_ids.add(frontmatter["kp_id"])

        self.assertGreater(len(active_ids), 0)
        aggregate_ids = [
            Path(target.split("#", 1)[0].split("?", 1)[0]).stem
            for target in scan_markdown_links(aggregate)
            if Path(target.split("#", 1)[0].split("?", 1)[0]).name.startswith("kp_")
        ]
        self.assertEqual(len(aggregate_ids), len(set(aggregate_ids)))
        self.assertSetEqual(set(aggregate_ids), active_ids)

    def test_sector_and_annulus_are_separate_progressive_entries(self) -> None:
        sector = self.read_task_four_entry("kp_s07_sector_and_ring")
        annulus = self.read_task_four_entry("kp_s07_annulus_area")
        sector_questions = self.example_questions(sector)
        annulus_questions = self.example_questions(annulus)

        self.assertEqual(parse_frontmatter(sector).get("title"), "扇形面积")
        self.assertEqual(parse_frontmatter(annulus).get("title"), "圆环面积")
        self.assertTrue(all("扇形" in question for question in sector_questions))
        self.assertTrue(
            all("圆环" in question or "环形" in question for question in annulus_questions)
        )
        self.assertIn("圆心角是多少", sector_questions[2])
        self.assertIn("分针", sector_questions[3])
        self.assertIn("内圆半径是多少", annulus_questions[2])
        self.assertIn("内圆周长", annulus_questions[3])

    def test_fan_chart_levels_two_and_three_derive_a_share_from_visual_information(self) -> None:
        text = self.read_task_four_entry("kp_s10_fan_chart_reading")
        examples = text.split("### 例题 ")[1:]

        for number in (2, 3):
            with self.subTest(example=number):
                example = examples[number - 1]
                question = example.split("#### 难度", 1)[0]
                chart = re.search(
                    r"\`\`\`mermaid\s+pie(?:\s+showData)?\s+.*?\`\`\`",
                    question,
                    flags=re.DOTALL,
                )
                self.assertIsNotNone(chart, "L2/L3 题目必须内嵌 Mermaid pie 图")
                labels = re.findall(
                    r'^\s*"[^"]+"\s*:\s*\d+(?:\.\d+)?\s*$',
                    chart.group(0),
                    flags=re.MULTILINE,
                )
                self.assertGreaterEqual(len(labels), 3, "饼图必须有多个可读类别标签")

    def test_cross_chart_level_one_uses_two_sources_for_one_inference(self) -> None:
        level_one = self.read_task_four_entry("kp_s10_chart_data_inference").split(
            "### 例题 ", 2
        )[1]

        self.assertIn("统计表", level_one)
        self.assertIn("扇形图", level_one)
        self.assertIn("°", level_one)

    def test_percent_meaning_level_three_compares_multiple_denominators(self) -> None:
        level_three = self.read_task_four_entry("kp_s02_percent_meaning").split(
            "### 例题 ", 4
        )[3]

        self.assertGreaterEqual(level_three.count("%"), 3)
        self.assertTrue("分母" in level_three or "标准量" in level_three)

    def test_grade_six_index_orders_task_three_units(self) -> None:
        grade_index = self.GRADE_INDEX.read_text(encoding="utf-8")
        positions: dict[str, list[int]] = {"分数乘法": [], "分数除法": [], "比": []}

        for _, kp_id, unit in self.TARGETS:
            if unit in positions:
                positions[unit].append(grade_index.index(f"{kp_id}.md"))

        self.assertLess(max(positions["分数乘法"]), min(positions["分数除法"]))
        self.assertLess(max(positions["分数除法"]), min(positions["比"]))


class L4AuditTests(unittest.TestCase):
    MAP_ROOT = Path(__file__).resolve().parents[1] / "docs" / "小学数学地图"
    AUDIT = MAP_ROOT / "_meta" / "L4横向题审计.md"
    SPECIALTY_INDEX = MAP_ROOT / "专项索引.md"
    COLUMNS = (
        "专项",
        "主条目",
        "定位",
        "L3",
        "L4标题",
        "横向标签",
        "适龄说明",
        "引用条目",
    )
    POSITIONS = {"核心", "分班高频", "基础横向"}

    @staticmethod
    def table_cells(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    def setUp(self) -> None:
        self.audit_text = (
            self.AUDIT.read_text(encoding="utf-8") if self.AUDIT.is_file() else ""
        )

    def audit_rows(self) -> list[list[str]]:
        lines = self.audit_text.splitlines()
        header = "| " + " | ".join(self.COLUMNS) + " |"
        self.assertIn(header, lines, "L4 审计表缺少固定的 8 列表头")
        start = lines.index(header)
        rows: list[list[str]] = []
        for line in lines[start + 2 :]:
            if not line.startswith("|"):
                break
            cells = self.table_cells(line)
            self.assertEqual(len(cells), len(self.COLUMNS), f"审计行列数错误：{line}")
            rows.append(cells)
        return rows

    @staticmethod
    def local_link(base: Path, cell: str) -> Path:
        targets = scan_markdown_links(cell)
        if len(targets) != 1:
            raise AssertionError(f"单元格必须恰有一个 Markdown 链接：{cell}")
        target = targets[0].split("#", 1)[0].split("?", 1)[0]
        return (base / target).resolve()

    def test_l4_audit_file_exists(self) -> None:
        self.assertTrue(self.AUDIT.is_file(), f"缺失 L4 审计文件：{self.AUDIT}")

    def test_each_specialty_has_exactly_one_machine_readable_conclusion(self) -> None:
        if not self.AUDIT.is_file():
            self.skipTest("审计文件尚未创建")
        rows = self.audit_rows()
        specialty_ids = [row[0].split(maxsplit=1)[0] for row in rows]

        self.assertEqual(len(rows), 14)
        self.assertEqual(
            specialty_ids,
            [f"S{number:02d}" for number in range(1, 15)],
        )
        self.assertTrue(all(row[2] in self.POSITIONS for row in rows))

    def test_main_l3_and_l4_links_share_one_active_grade_six_entry(self) -> None:
        if not self.AUDIT.is_file():
            self.skipTest("审计文件尚未创建")

        for row in self.audit_rows():
            specialty_id = row[0].split(maxsplit=1)[0]
            with self.subTest(specialty_id=specialty_id):
                main = self.local_link(self.AUDIT.parent, row[1])
                level_three = self.local_link(self.AUDIT.parent, row[3])
                level_four = self.local_link(self.AUDIT.parent, row[4])
                self.assertEqual(main, level_three)
                self.assertEqual(main, level_four)
                self.assertTrue(main.is_file(), f"主条目链接失效：{main}")

                text = main.read_text(encoding="utf-8")
                frontmatter = parse_frontmatter(text)
                self.assertEqual(frontmatter.get("status"), "active")
                self.assertEqual(frontmatter.get("specialty_id"), specialty_id)
                self.assertIn(6, frontmatter.get("grades", []))

    def test_core_and_placement_frequent_rows_have_real_l3_and_l4_examples(self) -> None:
        if not self.AUDIT.is_file():
            self.skipTest("审计文件尚未创建")

        marked_rows = [
            row for row in self.audit_rows() if row[2] in {"核心", "分班高频"}
        ]
        self.assertGreater(len(marked_rows), 0)
        for row in marked_rows:
            specialty_id = row[0].split(maxsplit=1)[0]
            with self.subTest(specialty_id=specialty_id, positioning=row[2]):
                main = self.local_link(self.AUDIT.parent, row[1])
                levels = re.findall(
                    r"^#### 难度\s*\n\s*(L[1-4])\s*$",
                    main.read_text(encoding="utf-8"),
                    re.MULTILINE,
                )
                self.assertIn("L3", levels)
                self.assertIn("L4", levels)

    def test_references_are_active_or_age_reason_is_explicit(self) -> None:
        if not self.AUDIT.is_file():
            self.skipTest("审计文件尚未创建")

        for row in self.audit_rows():
            specialty_id, age_note, reference = row[0].split(maxsplit=1)[0], row[6], row[7]
            with self.subTest(specialty_id=specialty_id):
                if reference == "暂不设置":
                    self.assertTrue(
                        age_note.startswith("适龄：") and len(age_note) > len("适龄："),
                        "暂不设置引用时必须在适龄说明中给出原因",
                    )
                    continue

                self.assertIn("引用", reference)
                target = self.local_link(self.AUDIT.parent, reference)
                self.assertTrue(target.is_file(), f"引用条目链接失效：{target}")
                frontmatter = parse_frontmatter(target.read_text(encoding="utf-8"))
                self.assertEqual(frontmatter.get("status"), "active")

    def test_specialty_index_reports_actual_active_and_l4_counts(self) -> None:
        index_text = self.SPECIALTY_INDEX.read_text(encoding="utf-8")
        summary_rows = {
            cells[0].split(maxsplit=1)[0]: cells
            for line in index_text.splitlines()
            if line.startswith("| S")
            and (cells := self.table_cells(line))
            and re.fullmatch(r"S(?:0[1-9]|1[0-4])", cells[0].split(maxsplit=1)[0])
        }
        self.assertEqual(set(summary_rows), {f"S{number:02d}" for number in range(1, 15)})

        for specialty_id, cells in summary_rows.items():
            with self.subTest(specialty_id=specialty_id):
                reported = re.search(r"(\d+) active / (\d+) L4", cells[-1])
                self.assertIsNotNone(reported, "专项索引必须报告 active / L4 数量")
                paths = sorted(
                    self.MAP_ROOT.glob(f"specialties/{specialty_id}-*/kp_*.md")
                )
                actual_active = 0
                actual_l4 = 0
                for path in paths:
                    text = path.read_text(encoding="utf-8")
                    if parse_frontmatter(text).get("status") != "active":
                        continue
                    actual_active += 1
                    levels = re.findall(
                        r"^#### 难度\s*\n\s*(L[1-4])\s*$", text, re.MULTILINE
                    )
                    actual_l4 += "L4" in levels
                self.assertEqual(
                    tuple(map(int, reported.groups())),
                    (actual_active, actual_l4),
                )

    def test_specialty_index_has_no_task_number_placeholder(self) -> None:
        index_text = self.SPECIALTY_INDEX.read_text(encoding="utf-8")

        self.assertIsNone(re.search(r"待任务|任务\s*[4-7]|任务[4-7]", index_text))

    def test_audit_main_entries_do_not_claim_review_aggregate_as_unit(self) -> None:
        for row in self.audit_rows():
            specialty_id = row[0].split(maxsplit=1)[0]
            with self.subTest(specialty_id=specialty_id):
                main = self.local_link(self.AUDIT.parent, row[1])
                frontmatter = parse_frontmatter(main.read_text(encoding="utf-8"))
                units = [unit.get("unit") for unit in frontmatter.get("pep_units", [])]
                self.assertTrue(set(units).isdisjoint({"总复习", "整理和复习"}))

    def test_s09_audit_main_is_one_progressive_travel_skill(self) -> None:
        s09 = next(row for row in self.audit_rows() if row[0].startswith("S09 "))
        main = self.local_link(self.AUDIT.parent, s09[1])
        text = main.read_text(encoding="utf-8")
        frontmatter = parse_frontmatter(text)
        questions = CoverageTests.example_questions(text)

        self.assertIn("行程", frontmatter.get("title", ""))
        self.assertNotIn("工程", frontmatter.get("title", ""))
        self.assertEqual(len(questions), 4)
        self.assertTrue(
            all(re.search(r"速度|行驶|相遇|追赶|路程", question) for question in questions)
        )
        self.assertTrue(all("工程" not in question for question in questions))

    def test_s14_audit_main_keeps_unit_conversion_as_primary_skill(self) -> None:
        s14 = next(row for row in self.audit_rows() if row[0].startswith("S14 "))
        main = self.local_link(self.AUDIT.parent, s14[1])
        questions = CoverageTests.example_questions(
            main.read_text(encoding="utf-8")
        )
        unit_markers = (
            "m",
            "cm",
            "厘米",
            "小时",
            "分钟",
            "L",
            "mL",
            "m³",
            "升",
            "毫升",
            "立方米",
        )

        self.assertEqual(len(questions), 4)
        for question in questions:
            self.assertGreaterEqual(
                sum(marker in question for marker in unit_markers),
                2,
                f"单位专项题必须显式提供至少两种待统一单位：{question}",
            )
        joined = "\n".join(questions)
        self.assertNotRegex(joined, r"追上|追赶|相遇|速度")


if __name__ == "__main__":
    unittest.main()
