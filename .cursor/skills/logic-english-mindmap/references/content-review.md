# 内容教研机制（防张冠李戴）

覆盖：**词核归属、基本义、延伸链、主图主义、展示文案**。  
图片专项见 `image-review.md`。二者都要通过才能交付。

反例（张冠李戴）：

| 错误 | 应为 |
|------|------|
| 词核标题只写「盒子」 | `bo ---- box（盒子）`，关键是 **bo** |
| bow 主图是船 | bow 主图是**弓**（船头义写在链里） |
| boat 基本义写成「弓」 | boat = 水上的盒子/船 |
| book 挂到无关核 | book 挂 `bo` |

---

## 1. Maker–Checker

| 角色 | 职责 |
|------|------|
| Maker | 起草 JSON：核键、basic、chains、map_words、图立项 |
| Checker | 按清单核对「词↔核↔义↔图」四一致；填 `content_review` |

Maker 不得直接自批 `approved`（至少二次清单 + notes；推荐对立模型 Checker）。

---

## 2. 生成前立项

```json
"content_review": {
  "status": "pending",
  "claims": {
    "core_key": "bo",
    "lemma_fits_key": "book starts with bo",
    "basic_one_liner": "装页的扁平盒",
    "image_primary_sense": "closed book",
    "not_confused_with": ["box", "boat"]
  }
}
```

---

## 3. Checker 清单（全 true 才通过）

| # | 检查项 | 说明 |
|---|--------|------|
| K1 | 核键正确 | `core.id == core.key`；展示为 `key ---- prototype（name）` |
| K2 | 词挂对核 | lemma 与 key 音形相关（通常以 key 开头/含 key）；例外须在 notes 说明 |
| K3 | 基本义匹配 lemma | `basic` 描述的是本词，不是兄弟词 |
| K4 | 主图匹配主义 | `image.primary_sense` 与 `basic`/lemma 一致；不得用兄弟实物图 |
| K5 | 链不串台 | chains/map 里的兄弟词同核合理；多义次要义不抢主图 |
| K6 | 小学生可辨 | 不看英文也能看出主物/主义不颠倒 |

写入：

```json
"content_review": {
  "status": "approved",
  "checklist": {
    "core_key_ok": true,
    "lemma_on_core_ok": true,
    "basic_matches_lemma": true,
    "image_matches_sense": true,
    "chains_coherent": true,
    "child_clear": true
  },
  "reviewer": "checker",
  "notes": "book↔bo↔书图一致",
  "reviewed_at": "ISO-8601"
}
```

---

## 4. 门禁命令

```bash
python .cursor/skills/logic-english-mindmap/scripts/review_content.py
python .cursor/skills/logic-english-mindmap/scripts/review_images.py
python .cursor/skills/logic-english-mindmap/scripts/validate_graph.py
```

任一失败 → 不得交付。

---

## 5. 顺序

1. 内容立项 → 2. 起草 JSON → 3. 图立项+生成+图审 → 4. **内容 Checker** → 5. upsert → 6. `review_content` + `review_images` + `validate`
