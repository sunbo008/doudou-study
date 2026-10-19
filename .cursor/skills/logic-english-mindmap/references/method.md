# 钟平逻辑英语 · 核 → 链（Agent 起草用）

## 公理

1. 一词不是孤点，是推理链上的节点；多条链相交成导图。
2. 先立**核意象**（具象、可看见），再推基本义与延伸义。
3. 教学逻辑服务记忆；≠ 历史词源。页面注明边界。
4. 禁止用「固定搭配」结束思考——要能说清「为什么」。

## 起草清单

对 lemma `W`：

1. **核**（关键是音形键）：
   - `core.id` = `core.key` = 音形键（如 `bo`）
   - `core.prototype` = 意象锚点词（如 `box`）
   - `core.name` = 中文意象（如 `盒子`）
   - 展示格式固定：`bo ---- box（盒子）`  
   - `def`：一句话操作定义
2. **内容教研**：按 **`content-review.md`**，保证词↔核↔义↔图一致（防张冠李戴）；`content_review.status=approved`。
3. **实物图 + 图审**：按 `images.md` / **`image-review.md`**；`image.review.status=approved`。
4. **基本义** `basic`：用核解释 W（必须说本词，不是兄弟词）。
5. **chains**：延伸链；兄弟词用**单 token**。
6. **map_words**：导图里每一个英文单词节点。
7. **related**：同核兄弟精简列表（≤12）。
8. **examples**：每条重要链至少 1 句英文。
9. **notes**：可选；提醒教学逻辑。

## 示例核

- `bo ---- box（盒子）`：关键 **bo**；box 为意象锚点；def = 有边界、能装东西的空间  
  成员：book / boat / bowl / bow / box / bottle / boot …

## 质量门

- `review_content.py` + `review_images.py` + `validate_graph.py` 全过
- map_words 与导图单词节点一致
- map_words ≤ 24；related ≤ 12
- 多词短语整段展示，不自动拆链；要链的词写入 map_words
