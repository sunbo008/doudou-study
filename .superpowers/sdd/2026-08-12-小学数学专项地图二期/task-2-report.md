# Task 2 实施报告：六年级教材基线与一期校正

## 状态

已完成并待后续 Task 3～6 创建六年级细知识点覆盖入口。

## 修改文件

- 新增 `docs/小学数学地图/_meta/教材目录基线.md`：固定八列表；共 19 行，六上为 8 个正式单元、1 个复习聚合、2 个综合实践，六下为 5 个正式单元、1 个复习聚合、2 个综合实践；所有目录行均为 `verified_book` 并链接相应实书目录图片。
- 更新 `scripts/validate_math_map.py`：解析固定目录表，并对正式单元、综合实践的空/占位/断链覆盖入口报 `catalog-entry-uncovered`；复习聚合不要求细知识点正文。
- 更新 `tests/test_validate_math_map.py`：覆盖空入口、占位、断链和复习聚合年级索引锚点。
- 更新 `docs/小学数学地图/_meta/人教版对齐说明.md`、`docs/小学数学地图/年级索引.md`：写入六年级上下册实书校正，改为「位置与方向（二）」，移除六下独立「统计」。
- 更新四个一期样板：补 `source_verification: verified_book`；两项 S06 初中衔接样板改挂「数学广角——数与形 / 分班衔接」，正文明确不是六上课内方程单元。

## RED / GREEN

- RED：`python3 -m unittest tests.test_validate_math_map.CatalogTests -v`，3 个断言失败，原因均为尚未实现 `catalog-entry-uncovered`。
- GREEN：`python3 -m unittest tests.test_validate_math_map -v`，17 tests，全部通过。

## 全量校验剩余错误

`python3 scripts/validate_math_map.py docs/小学数学地图` 当前仅报 17 个 `catalog-entry-uncovered`，均为 Task 3～6 尚未创建的六年级正式单元或综合实践入口；无一期样板缺少 `source_verification`、无虚构六下「统计」错误。

## 裁决记录

用户裁决：保留「复习聚合」类型。六上目录总项为 9（8 个正式单元 + 1 个复习聚合），六下目录总项为 6（5 个正式单元 + 1 个复习聚合）；两类复习项只链接 `年级索引.md#六年级`，不生成重复知识正文。

## 提交哈希

`871c3b0`（`docs: 建立六年级教材目录基线`）

## 自检

- 目录解析结果：19 行；六上 `official=8, practice=2, review=1`，六下 `official=5, practice=2, review=1`，全部为 `verified_book`。
- `git diff --check` 通过。
- 四个既有 `kp_*.md` 样板均有 `source_verification: verified_book`。

## Concerns

全量校验在后续正文落地前预期非零；不得为提前通过校验而放宽正式单元和综合实践的覆盖规则。

---

## Fix round 1/5：目录校验收紧

### 状态

已完成。未修改用户裁决、19 行目录内容或复习聚合口径。

### 根因与修复

- 原覆盖检查仅验证链接目标存在，故年级索引或 README 也可能被误当作正式单元/综合实践覆盖。现仅接受存在的本地 `kp_*.md` 正文。
- 原复习聚合不验证锚点。现必须链接本地 `年级索引.md#六年级`，并验证目标 Markdown 存在对应标题。
- 原目录解析会静默跳过表头、列数和未知类型问题。现显式报告 `catalog-header-invalid`、`catalog-row-column-count`、`catalog-entry-type-invalid`、`catalog-entry-grade-invalid`、`catalog-entry-volume-invalid`、`catalog-entry-verification-invalid`、`catalog-entry-evidence-invalid`；本期严格要求年级 6、册次上/下、核验 `verified_book` 和存在的本地图片证据。
- 对齐说明已将目录表口径修正为“目录条目的核验值均为 `verified_book`”，不再误称为 `source_verification`。

### RED / GREEN

- RED：`python3 -m unittest tests.test_validate_math_map.CatalogTests -v`，9 个测试中 10 个子断言失败，分别复现错误接受 README/年级索引、未验证复习锚点及静默跳过目录格式/元数据错误。
- GREEN：同一命令 9 tests 全部通过；`python3 -m unittest tests.test_validate_math_map -v`，23 tests 全部通过。

### 全量校验

`python3 scripts/validate_math_map.py docs/小学数学地图` 仍仅报 17 个预期的 `catalog-entry-uncovered`（Task 3～6 尚未创建的六年级细知识点），无其他目录或一期错误。

### 提交哈希

`08a7ad8`（`fix: 收紧教材目录覆盖校验`）
