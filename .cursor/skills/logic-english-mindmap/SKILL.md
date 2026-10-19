---
name: logic-english-mindmap
description: >-
  Generates Zhong Ping (钟平) Logic-English mindmap HTML for any English word with
  core pages (bo ---- box（盒子）), pedagogy gates against 张冠李戴 (content + image
  教研), lemma_table bidirectional links, history.jsonl, and multi-thread /
  multi-subagent updates. Use for 逻辑英语导图, 钟平画词, 实物图, 教研审图/审内容,
  graph 更新单词, 词核页, 双向链接.
---

# Logic English Mindmap

## When to use

- Word **visual** mindmap HTML（本地 Mermaid 明快粉彩导图，可点击；初中生向，勿用灰暗 neutral）
- 词核页：展示 **`bo ---- box（盒子）`**（关键是音形键 bo）
- **内容教研 + 图片教研**（防张冠李戴）
- lemma_table 双向链接；多 subagent 批量补词

## Paths

| Role | Path |
|------|------|
| Graph | `docs/逻辑英语/graph/` |
| Mermaid UMD | `docs/逻辑英语/graph/vendor/mermaid.min.js`（离线本地，勿改回 CDN） |
| Method | `references/method.md` |
| **内容教研** | `references/content-review.md` |
| 图片规范 | `references/images.md` |
| **图片教研** | `references/image-review.md` |
| 并行 | `references/parallel-workflow.md` |

## Single-word workflow（含教研门禁）

1. Read `method.md` + **`content-review.md`** + **`image-review.md`**.
2. Draft `words/<lemma>.json`：`core.key/prototype/name`、`basic`、`chains`、`map_words`.
3. **内容立项**：写清本词主义、核键、不与谁混淆（`content_review.claims`）。
4. **图片**：立项 → 生成 → Checker 看图 → `image.review.status=approved`.
5. **内容 Checker**：按 content-review K1–K6 勾选 → `content_review.status=approved`.
6. 发布：

```bash
python .cursor/skills/logic-english-mindmap/scripts/upsert_word.py <lemma> --jobs 4
python .cursor/skills/logic-english-mindmap/scripts/review_content.py
python .cursor/skills/logic-english-mindmap/scripts/review_images.py
python .cursor/skills/logic-english-mindmap/scripts/validate_graph.py
```

7. 报告：路径、核标签、内容/图片审批状态、`links_updated`.
8. 验收 HTML：**用系统浏览器打开** `words/<lemma>.html`（Cursor 内置预览常不执行本地脚本，会只看到 Mermaid 源码）。Mermaid：中心词→有道；已生成兄弟词→本站词页；词核标签→核页。

**禁止交付**：`content_review` 或 `image.review` 非 `approved`。  
**禁止**手改 HTML 为源；**禁止** subagent 写 `lemma_table.json`。

## 张冠李戴红线

| 错 | 对 |
|----|----|
| 核标题只写「盒子」 | `bo ---- box（盒子）` |
| bow 配船图 | bow 配**弓**图 |
| boat 写成弓的基本义 | boat = 船 / 水上盒 |
| 词挂错音形键 | lemma 与 `core.key` 音形相关 |

## Batch

≥3 词 → `parallel-workflow.md`；草稿 `pending`，Coordinator 审过后 batch upsert + 双门禁。

## Other CLIs

```bash
python .cursor/skills/logic-english-mindmap/scripts/upsert_core.py <core_id>
python .cursor/skills/logic-english-mindmap/scripts/rebuild_table.py
python .cursor/skills/logic-english-mindmap/scripts/review_content.py
python .cursor/skills/logic-english-mindmap/scripts/review_images.py
```
