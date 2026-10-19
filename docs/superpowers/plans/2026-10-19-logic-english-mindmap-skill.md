# Logic English Mindmap Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Project Cursor skill that generates Zhong Ping–style word mindmap HTML with lemma_table-driven bidirectional links, core pages, history, and multi-thread / multi-subagent workflows.

**Architecture:** Word/core JSON is source of truth; `lemma_table.json` inverted index drives O(mentioned_by) relinks; `upsert_word.py` locks table, updates mentions, ThreadPoolExecutor re-renders HTML; Agent drafts JSON then runs scripts.

**Tech Stack:** Python 3 stdlib only; HTML+inline CSS templates; Cursor skill under `.cursor/skills/logic-english-mindmap/`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-10-19-logic-english-mindmap-skill-design.md`
- Graph root default: `docs/逻辑英语/graph`
- Ungenerated lemmas: gray, not clickable
- No hand-edit of HTML as source; no commit unless user asks
- Subagents must not write `lemma_table.json`

## File Map

| Path | Role |
|------|------|
| `.cursor/skills/logic-english-mindmap/SKILL.md` | Agent workflow |
| `.../references/method.md` | 钟平核→链摘要 |
| `.../references/parallel-workflow.md` | 多 subagent 协议 |
| `.../assets/*.html` | Templates |
| `.../scripts/graph_lib.py` | Shared: linkables, table, lock, render |
| `.../scripts/upsert_word.py` | CLI upsert / batch / rebuild-all |
| `.../scripts/upsert_core.py` | Core-only upsert |
| `.../scripts/rebuild_table.py` | Full table rebuild |
| `.../scripts/validate_graph.py` | Consistency checks |
| `docs/逻辑英语/graph/**` | Runtime data (created on first upsert) |
| `tests/logic_english_graph/test_graph_lib.py` | Unit tests |

---

### Task 1: Core library + tests

**Files:**
- Create: `.cursor/skills/logic-english-mindmap/scripts/graph_lib.py`
- Create: `tests/logic_english_graph/test_graph_lib.py`

**Produces:** `linkables()`, `update_lemma_table()`, `render_word_html()`, file lock helpers

- [x] Implement `linkables(doc) -> set[str]`
- [x] Implement table diff update + mentioned_by
- [x] Tests: book mentions bow → bow.mentioned_by contains book; after bow exists, backlinks work
- [x] Run: `python -m pytest tests/logic_english_graph/ -q`

### Task 2: Templates + upsert/validate CLIs

**Files:**
- Create: `assets/word-template.html`, `core-template.html`, `index-template.html` (or string templates in graph_lib)
- Create: `upsert_word.py`, `upsert_core.py`, `rebuild_table.py`, `validate_graph.py`

- [x] `--jobs`, `--batch`, `--rebuild-all`, `--root`
- [x] Thread pool only for HTML writes; serial table/index/history
- [x] Smoke: temp dir upsert book then bow

### Task 3: Skill docs

**Files:**
- Create: `SKILL.md`, `references/method.md`, `references/parallel-workflow.md`

- [x] Trigger description (pushy), workflows 7.1 / 5A, CLI paths

### Task 4: Seed book from existing md

**Files:**
- Create: `docs/逻辑英语/graph/words/book.json` (+ core hezi via script)
- Run upsert book then optionally bow stub verification

- [x] Import content from `docs/逻辑英语/book-核思维导图.md`
- [x] `validate_graph.py` passes
- [x] Open HTML manually sanity check

---

**Plan complete.** Implement tasks in order; skip git commits unless user requests.
