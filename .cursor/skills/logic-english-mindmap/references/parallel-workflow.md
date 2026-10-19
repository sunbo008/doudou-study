# 多 Subagent 并行协议

## 何时用

待生成 **≥ 3** 个互不覆盖的 lemma（例如补齐 book 图上灰色的 bow/bowl/boat）。

## 角色

| 角色 | 可写 | 不可写 |
|------|------|--------|
| Coordinator | `_drafts` 分配、移入 `words/`、跑 upsert、读表 | — |
| Content Subagent | 仅 `_drafts/<自己的lemma>.json` | `lemma_table.json`、他人草稿、`.html`、`graph.json` |

## 阶段

### A · 规划（Coordinator）

1. 读 `lemma_table.json`，列出 pending（`exists:false` 且被 mentioned）或用户点名列表。
2. 去重 lemma；同一新核先由 Coordinator 定好 `core.id/name/def`（或先 `upsert_core` 占位成员为空）。
3. 派发：每个 subagent 一个 lemma + 核信息 + 邻居 exists 快照。

### B · 并行起草（Subagents）

输出路径：`docs/逻辑英语/graph/_drafts/<lemma>.json`  
内容须符合 `method.md` 与词 JSON schema（含完整 `map_words`）。

### C · 串行提交（Coordinator）

```bash
# 校验后移动
mv docs/逻辑英语/graph/_drafts/bow.json docs/逻辑英语/graph/words/bow.json
# ...

python .cursor/skills/logic-english-mindmap/scripts/upsert_word.py --batch bow,bowl,boat --jobs 4
python .cursor/skills/logic-english-mindmap/scripts/validate_graph.py
```

脚本：主线程锁表、差分 mentions；线程池只渲染 HTML。

### D · 报告

新建核、新建词、`links_updated`、表中 lemma 数。

## 冲突

- 禁止两 agent 起草同一 lemma
- 新核只由 Coordinator 创建一次
- 表文件仅 upsert 脚本在锁内写入
