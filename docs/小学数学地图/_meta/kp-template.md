# 知识点条目模板

复制下方全文到新文件 `specialties/Sxx-专项名/kp_sXX_short_name.md`，替换占位内容。规范见 [`命名规范.md`](./命名规范.md)。

---

```markdown
---
kp_id: kp_sXX_short_name
title: 
specialty_id: SXX
grades: []
pep_units:
  - { grade: , volume: , unit: "" }
status: draft   # draft | active | deprecated
source_verification: pending  # verified_book | verified_public | pending
practice: 
weak_ref: 
lateral_tags: []
---

# {title}

## 一句话

（该知识点要会什么，一两句话。）

## 典型题型（按难度）

| 难度 | 题型描述 | 状态 |
|---|---|---|
| L1 |  | 待补 |
| L2 |  | 待补 |
| L3 |  | 待补 |
| L4 |  | 待补 |

## 例题

### 例题 1

#### 题目

（完整题干）

#### 难度

L1

#### 解题技巧

（可复用的方法口诀或决策顺序。）

#### 步骤要点

1. 
2. 

#### 避坑思路

（本题最容易错在哪、如何自检。）

#### 答案

（最终结果。）

---

（按需增加例题 2、例题 3……每道均含：题目、难度、解题技巧、步骤要点、避坑思路、答案。）

## 常见坑 / 易混

（知识点级汇总；可与例题避坑互相引用，避免空泛列表。）

## 年级与单元

（与 frontmatter 中 `pep_units` 一致，可补充说明。）

## 思维横向题（L4）

（若本题点有 L4：写「表面像什么 → 实际要先看出什么」、主专项 + 横向标签、完整例题子块。跨专项 L4 正文只维护一处，此处用链接引用。无则写「待补」。）

## 关联

- **相近知识点**：
- **练习材料**：（`practice/` 路径，与 `practice` / `weak_ref` 一致）
- **素质跟踪弱项**：（如 W1 / W2 / W2b）
```
