# W1 心算技巧递进 · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按规格在 `practice/W1-心算技巧递进/` 落地技巧速查卡、Plan0～Plan5 三招日卷（含答案与技巧代号）及 PDF，并更新 README / 素质跟踪链接。

**Architecture:** 用一份 Python 生成器按题型模板构造题库（答案 ≤3 位有限小数，避开既有 200/400/速度巩固表达式），写出 Markdown 后用 reportlab 出 PDF；每日卷固定 招一6 + 招二10 + 招三4。

**Tech Stack:** Python 3、fractions/Decimal、reportlab、STHeiti/PingFang CJK 字体、pypdf（页数校验）

## Global Constraints

- 技巧只认人教五上/六上算法 + 2022 课标；禁止一口清主线
- 答案有限小数且 ≤3 位（估数量级题除外）
- 表达式尽量不与 `心算专项-200题` / `400题` / `400题-速度巩固` 重复
- 学生卷无答案；答案卷标注技巧代号 T1～T10
- 路径：`practice/W1-心算技巧递进/`
- 不自动 git commit（除非用户明确要求）

---

### Task 1: 目录与 README + 技巧速查卡

**Files:**
- Create: `practice/W1-心算技巧递进/README.md`
- Create: `practice/W1-心算技巧递进/00-技巧速查卡.md`
- Create: `practice/W1-心算技巧递进/00-技巧速查卡.pdf`

- [ ] **Step 1:** 创建目录 `practice/W1-心算技巧递进/` 及子目录 `Plan0-摸底` … `Plan5-估验混选`
- [ ] **Step 2:** 写 README：目的、三招用法、过关标准、与旧 200/400 关系、Plan 顺序
- [ ] **Step 3:** 写 `00-技巧速查卡.md`（T1～T10 + 出处 + 一例）
- [ ] **Step 4:** 用 reportlab 生成一页 PDF 速查卡
- [ ] **Step 5:** 目视确认 PDF 含 T1～T10

---

### Task 2: 题库生成器核心

**Files:**
- Create: `scripts/gen_w1_technique_drills.py`

**Interfaces:**
- Produces: `gen_all()` → 写出各 Plan 的 md/pdf；`load_used_exprs()` → set[str]
- Each item: `{"expr": str, "answer": str, "tech": str, "type_id": str, "kind": "compute"|"estimate"|"oral"}`

- [ ] **Step 1:** 实现 `fmt_num` / `is_nice_answer`（≤3 位有限小数）
- [ ] **Step 2:** 实现各题型生成函数：`gen_p1_a` … `gen_p5_*`、`gen_plan0`
- [ ] **Step 3:** 实现 `make_daily_sheet(plan, day, pools)` → 20 题分三招
- [ ] **Step 4:** 从既有三套心算 md 加载 used 集合去重
- [ ] **Step 5:** `python scripts/gen_w1_technique_drills.py --dry-run` 打印各题型数量与 0 overlap

---

### Task 3: Plan0 + Plan1 落盘

**Files:**
- Create: `practice/W1-心算技巧递进/Plan0-摸底/诊断卷.md` + `.pdf` + `错因表.md`
- Create: `practice/W1-心算技巧递进/Plan1-转化百分数/Day01.md` … `Day04.md` + 合订 PDF + `答案.md`

- [ ] **Step 1:** 生成 Plan0：20 题覆盖 D1～D7，答案含技巧；附错因勾选表
- [ ] **Step 2:** 生成 Plan1：4 个 Day，每 Day 20 题；题库满足 P1-A～E 下限
- [ ] **Step 3:** 校验答案手算抽样 10 题
- [ ] **Step 4:** 出 PDF（题目在前，答案在后或分文件）

---

### Task 4: Plan2～Plan5 落盘

**Files:**
- Create: `Plan2-特殊因数凑整/` Days + 答案 + PDF
- Create: `Plan3-除法与百分数除/` …
- Create: `Plan4-运算定律简算/` …
- Create: `Plan5-估验混选/` Days + 混选正式卷 6 套 + PDF
- Create: `practice/W1-心算技巧递进/题库索引.md`

- [ ] **Step 1:** 按规格天数生成 Day 卷（P2:5, P3:5, P4:6, P5:7）
- [ ] **Step 2:** P5 另出 6 套限时混选正式卷（技巧不印在学生卷）
- [ ] **Step 3:** 写 `题库索引.md`（题型 ID ↔ 技巧 ↔ 文件/题号）
- [ ] **Step 4:** overlap 检查 + 抽样验算

---

### Task 5: 链接更新

**Files:**
- Modify: `practice/W1-小数乘除/README.md`
- Modify: `docs/素质跟踪/豆豆/素质跟踪报告.md`

- [ ] **Step 1:** W1 README 增加「心算技巧递进」入口
- [ ] **Step 2:** 素质跟踪 W1 练习材料增加链接；复测记录加一行「启动技巧递进计划」
- [ ] **Step 3:** 列出生成文件树供人工确认

---

## Spec coverage

| Spec 块 | Task |
|---|---|
| T1～T10 速查 | Task 1 |
| Plan0～5 题型与题量 | Task 2–4 |
| 三招日卷结构 | Task 2–4 |
| 去重/≤3 位小数 | Task 2 |
| README/索引/报告链接 | Task 1, 5 |
| 不替代 W2 | README 写明边界 |
