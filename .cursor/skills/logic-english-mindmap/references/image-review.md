# 实物图教研机制（强制）

目标：杜绝「词是 A、图是近邻 B」类错误（反例：`bow` 配成船图）。

**未通过教研的图不得标 `approved`，不得作为最终发布图。**

---

## 1. 角色（Maker–Checker）

| 角色 | 职责 | 禁令 |
|------|------|------|
| **Maker** | 定 `primary_sense`、写 prompt、生成/下载图、填 `must_show`/`must_not_show` | 自己给自己 `approved` |
| **Checker** | 打开图片做视觉验收、勾 checklist、写 `review` | 改 prompt 后不重审就通过 |

同一次会话里若 Maker 与主 Agent 为同一人：必须另开 **Checker 步骤**（换模型子代理更佳，见 `maker-checker-model-mutex`），或至少用下方清单做二次自检并留下 `review.notes`。

推荐：Maker 用当前模型生成 → Checker 用对立模型族 Task，prompt 只给 lemma + image path + must_*，输出通过/驳回。

---

## 2. 生成前（教研立项）

在写文件 / 调 GenerateImage **之前**，JSON 里先写好（可无 path）：

```json
"image": {
  "primary_sense": "archery bow（弓）",
  "must_show": ["单张木弓", "弓弦", "弯曲弓身"],
  "must_not_show": ["船", "船头", "hull", "水面行船", "整艘 boat"],
  "confusable_with": ["boat", "bowl"],
  "review": { "status": "pending" }
}
```

规则：

1. **`primary_sense` 唯一主义**：多义词只选**本页主图**对应的一个义项；其它义项写在 `chains`，不要抢主图。
2. **`must_not_show` 必含易混兄弟**：同核 `related`/`map_words` 里易混实物都要列（bow↔boat，bowl↔box 等）。
3. Prompt 必须显式加入：`must_show` 英文描述 + `NOT a <confusable>`。

### 易混登记（持续扩充）

| lemma | primary_sense（推荐主图） | must_not_show（至少） |
|-------|---------------------------|------------------------|
| bow | archery bow / 弓 | boat, ship, hull, 船头 |
| boat | small watercraft / 小船 | bow-as-weapon, 弓 |
| bowl | open ceramic bowl / 碗 | box, carton |
| box | closed carton/box / 箱盒 | bowl, book |
| book | closed book / 书 | box-only without pages |
| boot | footwear boot / 靴 | bottle |
| bottle | bottle / 瓶 | boot |

---

## 3. 生成后（视觉教研 · 必做）

1. 用 Read 工具打开图片文件（看图，不只看文件名）。
2. 逐项回答（全为「是」才能通过）：

| # | 检查项 | 失败即 |
|---|--------|--------|
| C1 | 画面主语是否 = `primary_sense`？ | 驳回 |
| C2 | `must_show` 是否可见？ | 驳回 |
| C3 | `must_not_show` / `confusable_with` 是否**未**出现？ | 驳回 |
| C4 | 是否单主物、浅底、无水印无文字？ | 驳回 |
| C5 | 小学生能否不看英文也认出是该物？ | 驳回 |

3. 写入 `review`：

```json
"review": {
  "status": "approved",
  "checklist": {
    "primary_object_match": true,
    "must_show_ok": true,
    "must_not_show_ok": true,
    "presentation_ok": true,
    "child_recognizable": true
  },
  "reviewer": "checker-agent",
  "notes": "确认是弓不是船",
  "reviewed_at": "ISO-8601"
}
```

驳回：`status: rejected`，换 prompt 重生成，**重新走 §3**。

---

## 4. 发布门禁

```bash
python .cursor/skills/logic-english-mindmap/scripts/review_images.py
python .cursor/skills/logic-english-mindmap/scripts/validate_graph.py
```

- `review_images.py`：缺字段 / `pending` / `rejected` / checklist 未全 true → **失败**
- `validate_graph.py`：图文件缺失 → 失败；并调用同一套教研字段检查

**禁止**：`review.status != approved` 时把该图当最终页交付（除非用户明确要求草稿预览）。

---

## 5. 与 upsert 的顺序

1. 立项字段 → 2. 生成图 → 3. Checker 视觉验收 → 4. `status=approved` → 5. `upsert_word.py` → 6. `review_images.py` + `validate_graph.py`
