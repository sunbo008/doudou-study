# 词各部分独立解释（part_explain）

目标：遇到「看起来能拆」的拼写时，**逐段判断有没有独立解释力**——有则讲清；无则明确写「无独立词义」，禁止硬编假词缀。

教学逻辑服务记忆；可借轻量历史事实说明「为何长这样」，但 **≠ 严格词源课**。

---

## 1. 何时必须做

对 lemma 起草时，若出现任一触发，须填写 `part_explain`（并常配一条拼写/构词链）：

| 触发 | 例 |
|------|----|
| 怪拼写块 / 不发音字母 | `-ough`、`-igh`、`kn-`、`wr-`、`mb` |
| 像词缀但可能假拆 | `-er`（比较级 vs 职业）、`-ly`、`un-`、`re-` |
| 同音异形易混 | bough ↔ bow；their / there |
| 复合/黏着外观 | notebook、bookshelf（可拆且有义） |
| 学生会问「这一截是什么意思」 | 任何视觉上可切开的片段 |

无触发可省略 `part_explain`（短词如 `box` 常不必硬拆）。

---

## 2. 判定：独立解释力

对每一截 `segment` 问：**单独拿出来，能否稳定帮助记本词？**

| `power` | 含义 | 写法 |
|---------|------|------|
| `yes` | 有独立解释力（核键 / 真词缀 / 可指认词根） | 写清 `gloss`；相关对比词可进 `contrast` / chains |
| `no` | **无**独立词义（拼写残留、死字母） | `gloss` **必须**含「无独立词义」；给 `contrast` 防误推 |
| `weak` | 弱联想（助记可以，勿当构词真理） | `gloss` 标明「助记，非词缀」 |

**红线**

| 错 | 对 |
|----|----|
| 把 bough 的 `ugh` 编成「某义后缀」 | `ugh`/`ough` → `power: no`，无独立词义 |
| 只写「不规则拼写」了事 | 说明不发音 + 对照 though/through/cough/enough |
| 为拆而拆、拆出与主义无关的碎片 | 只拆对学生记忆有用的段 |
| 用假词源压过核意象 | 核仍是主轴；部分解释是辅链 |

---

## 3. JSON 字段

```json
"part_explain": [
  {
    "segment": "bo",
    "role": "core_key",
    "power": "yes",
    "gloss": "音形键，挂 bo ---- box（盒子）"
  },
  {
    "segment": "ugh",
    "role": "orthographic",
    "power": "no",
    "gloss": "无独立词义；属 -ough 历史拼写残留，现代 /baʊ/ 中 gh 不发音",
    "contrast": ["though", "through", "cough", "enough"]
  }
]
```

| 字段 | 要求 |
|------|------|
| `segment` | 拼写片段（可与相邻段重叠说明，如 `ough` 与 `ugh`） |
| `role` | `core_key` \| `root` \| `affix` \| `orthographic` \| `compound` \| `other` |
| `power` | `yes` \| `no` \| `weak` |
| `gloss` | 中文一句话；`power=no` 必含「无独立词义」 |
| `contrast` | 可选；对照词（单 token），须进入 `map_words` 若要在导图/链里点 |

配套（推荐）：

- `chains` 增加「拼写提醒 / 构词」类链，items 用 `contrast` 里的词
- `notes` 用一句话收束：哪一段有义、哪一段无义
- `content_review.claims.part_explain_summary`：如 `"ugh 无独立词义；bo 为核键"`

---

## 4. 与核 / 链的关系

1. **核键段**（如 `bo`）→ `role: core_key`，`power: yes`，对齐 `core.key`。
2. **无义拼写段** → 勿改 `basic` 主义；主义仍说整词（bough=大树枝）。
3. **有义词缀** → 可开延伸链，但主图仍是整词实物/主义。
4. `map_words`：凡 `contrast` 与构词链里的英文词都要列入（≤24 总上限）。

---

## 5. Checker（内容教研加项）

在 K1–K6 之外，若本词触发了 §1，再勾：

| # | 检查项 | 说明 |
|---|--------|------|
| P1 | 该拆则拆 | 有触发却无 `part_explain` → 驳回补写 |
| P2 | 无义说清 | 任一 `power=no` 的 gloss 含「无独立词义」 |
| P3 | 未假词缀 | 无把 orthographic 段写成语义后缀 |
| P4 | 对照够用 | `power=no` 且易误推时有 `contrast` 或拼写链 |

写入 `content_review.notes` 可点一句，如：`ugh power=no 已标明`。

---

## 6. 范例速查

| lemma | 拆法要点 |
|-------|----------|
| bough | `bo` 核键 yes；`ugh`/`ough` orthographic **no**；对照 though 等；主义=大树枝 |
| bow | 一般不拆 ough；多义在链，主图弓 |
| book | `bo` 核键；整词「装页的盒」；不必拆 -k |
| unhappy | `un-` affix yes「否定」+ `happy`；主图仍整词情绪/场景按页设计 |
| notebook | `note` + `book` compound yes |
