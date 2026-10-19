# 逻辑英语思维导图 Skill 设计

**日期**：2026-10-19  
**状态**：已批准并实现（P0–P1）  
**范围**：项目内 Cursor Skill + `docs/逻辑英语/graph/` 产物与脚本

---

## 1. 目标

基于钟平「逻辑英语」方法，对**任一英文单词**生成可浏览的思维导图 HTML，并满足：

1. **可追踪历史**：每次 create / update / link / create_core 追加 `history.jsonl`（HTML 只保留当前版）。
2. **可修改过往**：改源 JSON 后重跑脚本，覆写 HTML，并重算受影响链接。
3. **词间跳转**：导图里凡已生成的英文词均可点击进入对应 HTML。
4. **全图词双向回溯**：不只 `related`；**导图中每一个可链接英文词**都参与回溯（见 §5）。
5. **词核一等公民**：词核有独立 HTML；缺失则创建；`index.html` 可访问全部词核。
6. **高效回溯**：维护 **`lemma_table.json` 单词表**（倒排索引），避免每次全盘扫 `words/*.json`；重渲染支持 **多线程**；批量生成支持 **多 subagent 并行起草 + 单点提交链接**。
7. **实物图教研门禁**：主图须声明 `primary_sense` / `must_show` / `must_not_show`；Maker–Checker 目视验收后 `review.status=approved`；`review_images.py` 未通过不得交付（防 bow 配船图）。
8. **内容教研门禁**：词↔核↔义↔图四一致；核展示 `key ---- prototype（name）`；`content_review.status=approved`；`review_content.py` 未通过不得交付（防张冠李戴）。

**非目标**：严格历史词源学；在线服务；未生成词的可点击占位。

---

## 2. 已确认决策

| 项 | 选择 |
|----|------|
| Skill 位置 | 项目内 `.cursor/skills/logic-english-mindmap/` |
| 产物根目录 | `docs/逻辑英语/graph/` |
| 历史策略 | `history.jsonl` 事件日志；HTML 仅当前版 |
| HTML 形态 | 自包含：本地 Mermaid UMD 思维导图（可点击）+ 下方详情；`vendor/mermaid.min.js`，无 CDN |
| 内容来源 | Agent 按钟平方法自动推断核与链；脚本负责持久化与链接 |
| 未生成词 | **灰色不可点** |
| 架构 | **JSON 源数据 + 渲染脚本**（HTML 为生成物） |
| 回溯范围 | **导图内全部可链接英文词**（非仅 related） |
| 词核 | **独立页**；缺失则创建；index 列出全部词核 |
| 回溯索引 | **`lemma_table.json` 单词表**（权威倒排；O(提及者) 定位） |
| 并行 | 脚本 **多线程**重渲染；Agent **多 subagent**并行起草词 JSON |

---

## 3. 目录结构

```
.cursor/skills/logic-english-mindmap/
  SKILL.md
  references/
    method.md
    parallel-workflow.md      # 多 subagent 协议
  assets/
    word-template.html
    core-template.html
    index-template.html
  scripts/
    upsert_word.py              # 主入口（更新表 + 多线程回溯）
    upsert_core.py
    rebuild_table.py            # 从 words/*.json 全量重建单词表
    validate_graph.py

docs/逻辑英语/graph/
  index.html
  graph.json                    # 核/词节点摘要（给 index 用）
  lemma_table.json              # ★ 单词表：倒排索引（回溯主索引）
  lemma_table.lock              # 进程锁（多进程/多 agent 提交时）
  history.jsonl
  vendor/
    mermaid.min.js              # 本地 UMD（离线渲染）
  assets/
    cores/  words/              # 实物图
  cores/
    <core_id>.json              # 如 bo.json；展示 bo ---- box（盒子）
    <core_id>.html
  words/
    <lemma>.json
    <lemma>.html
  _drafts/                      # 多 subagent 起草区（可选）
    <lemma>.json
```

现有 `docs/逻辑英语/book-核思维导图.md` 保留；已导入为 `words/book.json` + `cores/bo.json`。

---

## 4. 数据模型

### 4.1 词核 `cores/<core_id>.json`

```json
{
  "id": "hezi",
  "name": "盒子",
  "def": "有边界、能装东西的空间",
  "members": ["book", "box", "boat", "bow", "bowl"],
  "updated_at": "2026-10-19T10:00:00+08:00"
}
```

规则：

- `id` / `key`：音形键（小写，如 `bo`、`throw`）；展示为 `bo ---- box（盒子）`。由 Agent 在首次出现该核时确定；之后复用。
- `members`：**由脚本维护**（所有 `core.id == 此核` 的 lemma 集合）。
- 词核页展示：核名、定义、成员词（已生成可点 / 未生成灰色）。

### 4.2 单词 `words/<lemma>.json`

```json
{
  "lemma": "book",
  "core": {
    "id": "hezi",
    "name": "盒子",
    "def": "有边界、能装东西的空间"
  },
  "basic": "装页/字的扁平盒；合上是盒，打开是页",
  "chains": [
    {
      "id": "A",
      "title": "装进名册",
      "items": ["book a room", "fully booked"]
    },
    {
      "id": "R",
      "title": "同核兄弟",
      "items": ["box", "boat", "bow", "bowl"]
    }
  ],
  "related": ["box", "boat", "bow", "bowl"],
  "map_words": ["box", "boat", "bow", "bowl", "booklet", "bookmark"],
  "backlinks": [],
  "examples": ["Please book a room."],
  "notes": "教学逻辑 ≠ 词源",
  "part_explain": [
    {
      "segment": "bo",
      "role": "core_key",
      "power": "yes",
      "gloss": "音形键，挂盒子核"
    }
  ],
  "updated_at": "2026-10-19T10:00:00+08:00"
}
```

规则：

- `core.id` / `core.name` / `core.def`：写词时必填；upsert 时若 `cores/<id>` 不存在则创建。
- **`part_explain`**（触发则必填）：词各部分独立解释力；`power=no` 的 gloss 须含「无独立词义」。见 skill `references/part-explain.md`。
- `related`：同核兄弟等（建议子集）。
- **`map_words`**：导图中所有需要参与链接/回溯的英文 lemma 显式列表（Agent 维护，**应覆盖导图里每一个单词节点**）。
- **可链接集合 `linkables(W)`**（脚本计算，用于渲染与回溯）=

  ```
  set(W.map_words)
  ∪ set(W.related)
  ∪ { item.lower() | item in 任意 chains[].items 且 item 为单 token（无空格，匹配 ^[a-z][a-z0-9-]*$）}
  ```

  - 多词短语（如 `book a room`）**整段不作为链接目标**；不拆词回溯（避免误链 a/the）。
  - 若希望短语里的某词可链，Agent 须把该 lemma 写入 `map_words` 或作为单独导图节点（单 token item）。
- `backlinks`：由脚本维护。`L ∈ W.backlinks` 当且仅当 `W ∈ linkables(L)`。

### 4.3 `lemma_table.json`（单词表 · 回溯主索引）

权威倒排表。回溯时**只查表，不扫全库**（除非 `--rebuild-table`）。

```json
{
  "version": 1,
  "updated_at": "2026-10-19T10:14:00+08:00",
  "lemmas": {
    "book": {
      "exists": true,
      "path": "words/book.html",
      "json": "words/book.json",
      "core_id": "hezi",
      "mentions": ["box", "boat", "bow", "bowl", "booklet", "bookmark"],
      "mentioned_by": []
    },
    "bow": {
      "exists": false,
      "path": null,
      "json": null,
      "core_id": null,
      "mentions": [],
      "mentioned_by": ["book"]
    }
  }
}
```

字段：

| 字段 | 含义 |
|------|------|
| `exists` | 是否已有正式 `words/<lemma>.json`+`.html` |
| `mentions` | 该词导图 `linkables` 指向的 lemma 列表 |
| `mentioned_by` | **倒排**：哪些已存在词的导图提到了本 lemma（回溯直接读此列表） |

维护规则：

1. upsert `W` 时：写入/更新 `lemmas[W]`（`exists=true`，`mentions=linkables(W)`）。
2. 对每个 `t ∈ mentions(W)`：确保 `lemmas[t]` 条目存在；把 `W` 加入 `lemmas[t].mentioned_by`（去重排序）。
3. 若 `W` 的 `mentions` 相对旧版有删除：从被删目标的 `mentioned_by` 中移除 `W`。
4. `W.backlinks` ← 直接取 `lemmas[W].mentioned_by`（仅保留 `exists=true` 的项，或渲染时再过滤）。
5. 写盘：持有 `lemma_table.lock`（`fcntl`/`msvcrt` 或 lock 文件），`tmp + os.replace` 原子更新。
6. `rebuild_table.py`：全量扫 `words/*.json` 重建表（校验/修复用）。

### 4.4 `graph.json`

```json
{
  "cores": {
    "hezi": { "name": "盒子", "path": "cores/hezi.html", "updated_at": "..." }
  },
  "nodes": {
    "book": { "path": "words/book.html", "core_id": "hezi", "updated_at": "..." }
  },
  "edges": [
    { "from": "book", "to": "bow", "kind": "map" }
  ]
}
```

`edges` 可自 `lemma_table` 的 `mentions` 导出；index 优先读 `graph.json` + 词核列表。

### 4.5 `history.jsonl`

```json
{
  "ts": "2026-10-19T10:14:00+08:00",
  "op": "create|update|relink|create_core|update_core|rebuild_table",
  "word": "bow",
  "core_id": "hezi",
  "map_words": ["boat", "book"],
  "links_updated": ["book"],
  "cores_created": [],
  "workers": 4,
  "summary": "create bow; table backlink → re-render book"
}
```

---

## 5. 全图词双向回溯算法（表驱动）

输入：刚 upsert 的词 `W`。

### 5.1 确保词核

1. 读 `W.core.id`。
2. 若核不存在 → 创建 `cores/<id>.json` + HTML；记 `create_core`。
3. 核 `members` 由「所有 `core_id` 匹配且 `exists` 的 lemma」从单词表/词 JSON 汇总。

### 5.2 更新单词表（O(mentions)，非 O(全库)）

1. 计算 `linkables(W)`。
2. 加锁，读 `lemma_table.json`。
3. 差分更新 `mentions` / 各目标 `mentioned_by`（见 §4.3）。
4. 原子写回表；更新 `graph.nodes` / `edges`。

### 5.3 确定重渲染集合

```
rerender_words = {W}
  ∪ { L | L ∈ lemma_table[W].mentioned_by 且 exists }
  ∪ { T | T ∈ linkables(W) 且 exists }   # 对方页 backlinks 区可能变化
rerender_cores = { W.core_id }
```

**禁止**再「打开每一个 words/*.json 扫描是否包含 W」。

### 5.4 多线程重渲染

```bash
python upsert_word.py bow --jobs 4
```

- 使用 `concurrent.futures.ThreadPoolExecutor(max_workers=jobs)`。
- 每个 worker：**只读**该词 JSON + **只读** lemma_table 快照 → 写自己的 `.html`。
- **禁止**多线程同时写 `lemma_table.json` / `graph.json` / `history.jsonl` / `index.html`（这些在线程池前后由主线程串行完成）。
- 词核页、`index.html` 在词页线程池结束后由主线程渲染一次。
- 默认 `--jobs` = `min(8, cpu_count)`；`--jobs 1` 关闭并行便于调试。

### 5.5 收尾

主线程追加 `history.jsonl`（含 `links_updated`、`workers`）。

---

## 5A. 多 Subagent 并行协议

目标：一次生成/补全多个词（如 book 图上 pending 的 bow/bowl/boat）时，**内容起草并行**，**提交与表更新串行可控**。

### 5A.1 角色

| 角色 | 职责 |
|------|------|
| Coordinator（当前会话） | 读 `lemma_table`；划分子任务；合并草稿；加锁调用脚本；汇报 |
| Content Subagent × N | 只生成**互不依赖**的词之 JSON 草稿（核、链、map_words）；**不**跑 upsert、**不**改表 |
| （可选）Linker | 不单独需要；由 Coordinator 调 `upsert_word.py` 批量完成 |

### 5A.2 阶段

```
Phase A  规划（Coordinator）
  - 读 lemma_table，列出待生成 lemma 与已有 core_id
  - 同核词可共享核定义；新核由 Coordinator 先 upsert_core 或指定 core 草稿

Phase B  并行起草（Subagents，可同时跑）
  - 每个 subagent 输出到 docs/逻辑英语/graph/_drafts/<lemma>.json
  - 约束：只写自己的 lemma 文件；禁止改 lemma_table / 他人草稿
  - prompt 自带：method 摘要、核 id/名/义、map_words 下限、表中已存在邻居列表

Phase C  串行提交（Coordinator，持锁）
  - 校验草稿 → 移入 words/<lemma>.json
  - python upsert_word.py --batch l1,l2,l3 --jobs 4
      · 主线程按批更新 lemma_table（一次加锁写完所有 mentions 差分）
      · 再多线程渲染全部受影响 HTML
  - 清 _drafts；validate_graph；写 history

Phase D  报告
  - 新建核、新建词、重渲染列表、表行数
```

### 5A.3 冲突规则

- **同一 lemma**：禁止两个 subagent 同时起草；Coordinator 去重分配。
- **同一新核**：Coordinator 先创建核页，再派发成员词 subagent。
- **表文件**：仅 Coordinator / `upsert_word.py` 可写；subagent 只读表快照。
- 若 subagent 需要「别人是否已存在」：以派发时的 `lemma_table` 快照为准，不在中途重读脏写。

### 5A.4 Skill 触发文案示例

- 「用多 agent 把 book 上未生成的同核词全部补齐」→ Coordinator 走 5A。
- 「只生成 bow」→ 单词路径，不强制 subagent。

---

## 6. HTML 页面结构

### 6.1 词页 `words/<lemma>.html`

- Header：lemma；词核名（链到词核页）；回 `../index.html`
- 左栏：全图树（核 → 基本义 → chains → map 词节点）
- 右栏：推理表、造句、**回溯来源 backlinks**
- 样式：`.linked` / `.pending`（灰、不可点）

### 6.2 词核页 `cores/<core_id>.html`

- 核名、定义
- 成员词列表（已生成可点 / 未生成灰）
- 回 index；可列出「同核延伸说明」短注（来自核 JSON 可选 `notes`）

### 6.3 总览 `index.html`

必须包含：

1. **词核目录**：所有 `graph.cores` 的链接（名 + 链到 `cores/<id>.html`）。
2. **按核分组的单词**：每个核下挂 members（已生成可点）。
3. **扁平词表**（可选区）：全部 `nodes` 字母序。

---

## 7. Skill 工作流（Agent）

触发：用户提及「逻辑英语导图 / 生成 xxx 思维导图 HTML / 钟平方法画词 / 更新 graph / 补齐未生成词 / 多 agent 生成」等。

### 7.1 单词路径

1. 读 `SKILL.md`、`references/method.md`；读 **`lemma_table.json`**（无则空表）。
2. 起草/修改 `words/<lemma>.json`（`map_words` 覆盖导图全部单词节点）。
3. `python .../upsert_word.py <lemma> --jobs 4`  
   顺序：**锁表 → 确保词核 → 差分更新单词表 → 算 rerender 集 → 多线程渲染词页 → 主线程渲染核/index → history → 解锁**。
4. 报告路径、`mentioned_by` 命中、重渲染列表。
5. `validate_graph.py`（含表与 JSON 一致性）。

### 7.2 批量 / 多 Subagent 路径

见 §5A 与 `references/parallel-workflow.md`：Phase A–D。  
判定：待生成 ≥ 3 个独立 lemma 时，**默认**走多 subagent；更少则单词路径。

禁止手改 HTML 作为源；禁止 subagent 直接写 `lemma_table.json`。

---

## 8. 脚本 CLI

```bash
python .../upsert_word.py book --jobs 4
python .../upsert_word.py --batch bow,bowl,boat --jobs 4
python .../upsert_core.py hezi
python .../rebuild_table.py                 # 全量重建单词表
python .../upsert_word.py --rebuild-all --jobs 8
python .../validate_graph.py
```

依赖：仅 Python 3 标准库（`concurrent.futures` 做线程池）。

---

## 9. 成功标准

- [ ] 生成 `book` 后存在词核页、词页；**`lemma_table.json` 含 book，且 bow 等为 `exists:false` 但 `mentioned_by` 含 book**。
- [ ] 生成 `bow` 时**不**全盘扫词库；仅按表中 `mentioned_by`/`mentions` 重渲染；`book.html` 中 bow 可点。
- [ ] `--jobs 4` 下批量重渲染结果与 `--jobs 1` 一致（validate 通过）。
- [ ] 多 subagent：三个草稿并行写入 `_drafts` 后，一次 `--batch` 提交，表与链接正确。
- [ ] index 列出全部词核；新核自动出现。
- [ ] `history.jsonl` 记录 workers / links_updated。

---

## 10. 实现分期

| 期 | 交付 |
|----|------|
| P0 | Skill + method + templates + lemma_table + upsert（含锁与 --jobs）+ validate |
| P1 | 导入 book；生成 bow 验证表驱动回溯；index 词核目录 |
| P2 | `--batch` + `_drafts` + parallel-workflow.md；多 subagent 补齐同核词 |
| P3（可选） | history 时间线；核合并；表损坏自动 rebuild |

---

## 11. 风险与边界

- 表与 JSON 不一致 → `validate_graph` 失败并提示 `rebuild_table.py`。
- 多线程只渲染、主线程写表，避免竞态。
- 多 subagent 只并行「无共享写入」的起草；提交必须 Coordinator 持锁。
- `map_words` 漏列 → 表倒排缺失 → Skill/validate 警告。
- related ≤ 12、map_words ≤ 24；锁超时（如 30s）报错重试。

---

## 12. 审阅检查清单（self-review）

- [x] 全图 `linkables` 回溯
- [x] 词核独立页 + index 全核入口
- [x] **`lemma_table.json` 倒排**，回溯 O(提及者)
- [x] **多线程**重渲染 + 主线程串行写表
- [x] **多 subagent** 起草 / 串行提交协议
- [x] 未生成词灰色不可点
- [x] 不自动 commit（待批准后实现）
