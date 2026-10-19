# 实物图规范（词核 / 单词）

核意象与可指认的**实物词**必须配图，帮助学生「看见核」。

**教研门禁（强制）**：见 [`image-review.md`](image-review.md)。未 `approved` 不得交付。

## 何时要图

| 对象 | 要求 |
|------|------|
| 词核 `cores/<id>` | **必须**有 `image`（核的具象物） |
| 单词若本身是实物 | **必须**有 `image` |
| 抽象延伸义为主 | 可只用核图；caption 标明 |

## JSON 字段（完整）

```json
"image": {
  "path": "assets/words/bow.jpg",
  "alt": "一张拉紧弦的木弓",
  "caption": "bow · 弓",
  "source": "generated",
  "prompt": "A single wooden archery bow..., NOT a boat",
  "primary_sense": "archery bow（弓）",
  "must_show": ["木弓", "弓弦", "弯曲弓身"],
  "must_not_show": ["船", "船头", "boat", "hull"],
  "confusable_with": ["boat"],
  "review": {
    "status": "approved",
    "checklist": {
      "primary_object_match": true,
      "must_show_ok": true,
      "must_not_show_ok": true,
      "presentation_ok": true,
      "child_recognizable": true
    },
    "reviewer": "checker",
    "notes": "已目视确认是弓不是船",
    "reviewed_at": "2026-10-19T10:40:00+08:00"
  }
}
```

- `path`：相对 graph 根；文件在 `assets/cores/` 或 `assets/words/`
- `primary_sense` / `must_*` / `review`：**教研必填**

## 获取顺序

1. 本地 `assets/` 已有且已 approved  
2. 公有域准确图 → 本地化 → 走教研  
3. GenerateImage / nano-banana：prompt 含 must_show + NOT confusable → **Read 看图** → Checker 勾选 → approved  

## 发布命令

```bash
python .cursor/skills/logic-english-mindmap/scripts/review_images.py
python .cursor/skills/logic-english-mindmap/scripts/validate_graph.py
```
