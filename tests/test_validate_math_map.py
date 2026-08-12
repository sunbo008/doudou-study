from __future__ import annotations

import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from scripts.validate_math_map import main, validate


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


if __name__ == "__main__":
    unittest.main()
