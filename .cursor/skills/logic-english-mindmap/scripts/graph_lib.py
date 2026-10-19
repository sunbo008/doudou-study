#!/usr/bin/env python3
"""Logic-English graph: lemma table, linkables, render, lock."""

from __future__ import annotations

import html
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

TOKEN_RE = re.compile(r"^[a-z][a-z0-9-]*$")
DEFAULT_ROOT = Path("docs/逻辑英语/graph")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def ensure_dirs(root: Path) -> None:
    for sub in ("words", "cores", "_drafts", "assets/words", "assets/cores"):
        (root / sub).mkdir(parents=True, exist_ok=True)


def image_block(image: dict[str, Any] | None, *, rel_prefix: str = "../") -> str:
    """Render an object image card from JSON image field."""
    if not image:
        return ""
    path = str(image.get("path") or "").strip()
    if not path:
        return ""
    # paths in JSON are relative to graph root, e.g. assets/words/book.png
    src = html.escape(f"{rel_prefix}{path.lstrip('/')}")
    alt = html.escape(str(image.get("alt") or "实物图"))
    source = html.escape(str(image.get("source") or ""))
    caption = html.escape(str(image.get("caption") or alt))
    source_note = f'<span class="img-source">{source}</span>' if source else ""
    return (
        f'<figure class="thing-image">'
        f'<img src="{src}" alt="{alt}" loading="lazy"/>'
        f"<figcaption>{caption} {source_note}</figcaption>"
        f"</figure>"
    )


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


class TableLock:
    """Simple exclusive lock file for lemma_table / graph writes."""

    def __init__(self, root: Path, timeout: float = 30.0) -> None:
        self.path = root / "lemma_table.lock"
        self.timeout = timeout
        self._fd: int | None = None

    def __enter__(self) -> "TableLock":
        deadline = time.time() + self.timeout
        while True:
            try:
                self._fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self._fd, str(os.getpid()).encode())
                return self
            except FileExistsError:
                if time.time() >= deadline:
                    raise TimeoutError(f"Could not acquire lock: {self.path}")
                time.sleep(0.05)

    def __exit__(self, *args: Any) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass


def linkables(doc: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for key in ("map_words", "related"):
        for item in doc.get(key) or []:
            s = str(item).strip().lower()
            if TOKEN_RE.match(s):
                out.add(s)
    for chain in doc.get("chains") or []:
        for item in chain.get("items") or []:
            s = str(item).strip().lower()
            if TOKEN_RE.match(s):
                out.add(s)
    lemma = str(doc.get("lemma", "")).strip().lower()
    out.discard(lemma)
    return out


def empty_table() -> dict[str, Any]:
    return {"version": 1, "updated_at": now_iso(), "lemmas": {}}


def empty_graph() -> dict[str, Any]:
    return {"cores": {}, "nodes": {}, "edges": []}


def empty_lemma_entry() -> dict[str, Any]:
    return {
        "exists": False,
        "path": None,
        "json": None,
        "core_id": None,
        "mentions": [],
        "mentioned_by": [],
    }


def load_word(root: Path, lemma: str) -> dict[str, Any]:
    path = root / "words" / f"{lemma}.json"
    if not path.exists():
        raise FileNotFoundError(path)
    return load_json(path, {})


def save_word(root: Path, doc: dict[str, Any]) -> Path:
    lemma = doc["lemma"].strip().lower()
    doc["lemma"] = lemma
    path = root / "words" / f"{lemma}.json"
    atomic_write_json(path, doc)
    return path


def load_core(root: Path, core_id: str) -> dict[str, Any] | None:
    path = root / "cores" / f"{core_id}.json"
    if not path.exists():
        return None
    return load_json(path, {})


def save_core(root: Path, doc: dict[str, Any]) -> Path:
    core_id = doc["id"].strip().lower()
    doc["id"] = core_id
    path = root / "cores" / f"{core_id}.json"
    atomic_write_json(path, doc)
    return path


def apply_mentions_diff(
    table: dict[str, Any],
    lemma: str,
    new_mentions: set[str],
    *,
    exists: bool,
    core_id: str | None,
) -> None:
    lemmas: dict[str, Any] = table.setdefault("lemmas", {})
    entry = lemmas.setdefault(lemma, empty_lemma_entry())
    old = set(entry.get("mentions") or [])
    entry["exists"] = exists
    entry["path"] = f"words/{lemma}.html" if exists else None
    entry["json"] = f"words/{lemma}.json" if exists else None
    entry["core_id"] = core_id
    entry["mentions"] = sorted(new_mentions)
    entry.setdefault("mentioned_by", [])

    for t in new_mentions - old:
        te = lemmas.setdefault(t, empty_lemma_entry())
        mb = set(te.get("mentioned_by") or [])
        mb.add(lemma)
        te["mentioned_by"] = sorted(mb)

    for t in old - new_mentions:
        te = lemmas.get(t)
        if not te:
            continue
        mb = set(te.get("mentioned_by") or [])
        mb.discard(lemma)
        te["mentioned_by"] = sorted(mb)

    table["updated_at"] = now_iso()


def backlinks_from_table(table: dict[str, Any], lemma: str) -> list[str]:
    entry = (table.get("lemmas") or {}).get(lemma) or {}
    out = []
    for src in entry.get("mentioned_by") or []:
        src_e = (table.get("lemmas") or {}).get(src) or {}
        if src_e.get("exists"):
            out.append(src)
    return sorted(out)


def rebuild_table_from_words(root: Path) -> dict[str, Any]:
    table = empty_table()
    words_dir = root / "words"
    if not words_dir.exists():
        return table
    docs: list[dict[str, Any]] = []
    for path in sorted(words_dir.glob("*.json")):
        docs.append(load_json(path, {}))
    for doc in docs:
        lemma = str(doc.get("lemma", "")).strip().lower()
        if not lemma:
            continue
        core = doc.get("core") or {}
        apply_mentions_diff(
            table,
            lemma,
            linkables(doc),
            exists=True,
            core_id=core.get("id"),
        )
    return table


def sync_graph_from_table(root: Path, table: dict[str, Any]) -> dict[str, Any]:
    graph = load_json(root / "graph.json", empty_graph())
    nodes: dict[str, Any] = {}
    edges: list[dict[str, str]] = []
    for lemma, entry in sorted((table.get("lemmas") or {}).items()):
        if not entry.get("exists"):
            continue
        nodes[lemma] = {
            "path": entry.get("path") or f"words/{lemma}.html",
            "core_id": entry.get("core_id"),
            "updated_at": now_iso(),
        }
        for t in entry.get("mentions") or []:
            edges.append({"from": lemma, "to": t, "kind": "map"})
    graph["nodes"] = nodes
    graph["edges"] = edges
    # preserve cores; refresh members from nodes
    cores = graph.setdefault("cores", {})
    members_by_core: dict[str, list[str]] = {}
    for lemma, n in nodes.items():
        cid = n.get("core_id")
        if cid:
            members_by_core.setdefault(cid, []).append(lemma)
    for cid, members in members_by_core.items():
        if cid in cores:
            cores[cid]["updated_at"] = now_iso()
        core_doc = load_core(root, cid)
        if core_doc is not None:
            core_doc["members"] = sorted(members)
            save_core(root, core_doc)
            cores[cid] = {
                "key": core_doc.get("key") or cid,
                "prototype": core_doc.get("prototype") or "",
                "name": core_doc.get("name", cid),
                "label": core_display_label(core_doc),
                "path": f"cores/{cid}.html",
                "updated_at": now_iso(),
            }
    atomic_write_json(root / "graph.json", graph)
    return graph


def append_history(root: Path, event: dict[str, Any]) -> None:
    path = root / "history.jsonl"
    event = dict(event)
    event.setdefault("ts", now_iso())
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def word_chip(lemma: str, table: dict[str, Any], *, rel_prefix: str = "") -> str:
    entry = (table.get("lemmas") or {}).get(lemma) or {}
    label = html.escape(lemma)
    if entry.get("exists"):
        href = html.escape(f"{rel_prefix}{lemma}.html")
        return f'<a class="linked" href="{href}">{label}</a>'
    return f'<span class="pending" title="尚未生成">{label}</span>'


def core_display_label(core: dict[str, Any]) -> str:
    """Canonical display: bo ---- box（盒子）. Key is primary; prototype+gloss secondary."""
    key = str(core.get("key") or core.get("id") or "").strip()
    prototype = str(core.get("prototype") or "").strip()
    name = str(core.get("name") or "").strip()
    if key and prototype and name:
        return f"{key} ---- {prototype}（{name}）"
    if key and name:
        return f"{key} ---- （{name}）"
    if key and prototype:
        return f"{key} ---- {prototype}"
    return key or name or prototype or "?"


def youdao_url(lemma: str) -> str:
    """有道词典查询页（英）."""
    from urllib.parse import quote

    return f"https://www.youdao.com/result?word={quote(lemma)}&lang=en"


def mermaid_boot_scripts(*, mindmap: bool = True) -> str:
    """Local UMD Mermaid + click wiring. Place just before </body> (not in <head>)."""
    # 初中生向：明亮粉彩，深色字；避免 neutral 灰暗大块
    # 词页/核页均为 mindmap：加大 padding，减少节点挤叠
    _ = mindmap  # retained for call-site clarity
    mindmap_opt = ", mindmap: { padding: 64, maxNodeWidth: 120 }"
    init = f"""mermaid.initialize({{
    startOnLoad: false,
    theme: "base",
    themeVariables: {{
      darkMode: false,
      background: "#fffef8",
      primaryColor: "#FFE566",
      primaryTextColor: "#1a2a4a",
      primaryBorderColor: "#F4A261",
      lineColor: "#6BB3D9",
      secondaryColor: "#B8E0D2",
      tertiaryColor: "#FFD6E0",
      mainBkg: "#FFE566",
      nodeBorder: "#5B8DEF",
      fontFamily: "Iowan Old Style, Palatino Linotype, Palatino, Georgia, serif",
      fontSize: "18px",
      git0: "#FFE566",
      gitBranchLabel0: "#1a2a4a",
      cScale0: "#FFE566",
      cScale1: "#FF8FAB",
      cScale2: "#72D5C8",
      cScale3: "#7EB8FF",
      cScale4: "#C9A0FF",
      cScale5: "#FFB347",
      cScale6: "#98D8AA",
      cScale7: "#F7A8C4",
      cScale8: "#A8D8FF",
      cScale9: "#FFE07A",
      cScale10: "#B5EAD7",
      cScale11: "#FFDAC1",
      cScaleLabel0: "#1a2a4a",
      cScaleLabel1: "#1a2a4a",
      cScaleLabel2: "#1a2a4a",
      cScaleLabel3: "#1a2a4a",
      cScaleLabel4: "#1a2a4a",
      cScaleLabel5: "#1a2a4a",
      cScaleLabel6: "#1a2a4a",
      cScaleLabel7: "#1a2a4a",
      cScaleLabel8: "#1a2a4a",
      cScaleLabel9: "#1a2a4a",
      cScaleLabel10: "#1a2a4a",
      cScaleLabel11: "#1a2a4a"
    }}{mindmap_opt}
  }});"""
    return f"""<script src="../vendor/mermaid.min.js"></script>
<script>
(async function () {{
  function showFail(msg) {{
    var panel = document.querySelector(".mermaid-panel, .card");
    var tip = document.createElement("p");
    tip.className = "mermaid-fail";
    tip.style.cssText = "color:#b00020;background:#fff0f0;padding:.75rem 1rem;border-radius:10px;";
    tip.textContent = msg;
    if (panel) panel.appendChild(tip);
    console.error(msg);
  }}
  if (!window.mermaid) {{
    showFail("本地 Mermaid 未加载（../vendor/mermaid.min.js）。请用浏览器打开本 HTML，勿依赖禁用脚本的预览。");
    return;
  }}
  try {{
    const mermaid = window.mermaid;
    {init}
    const map = JSON.parse(document.getElementById("mm-click-map").textContent);
    const keys = Object.keys(map).sort(function (a, b) {{ return b.length - a.length; }});
    function resolveHref(raw) {{
      if (!raw) return null;
      if (map[raw]) return map[raw];
      var low = raw.toLowerCase();
      if (map[low]) return map[low];
      // 只精确匹配，避免 bo 误匹配 boat/boot
      for (var i = 0; i < keys.length; i++) {{
        var k = keys[i];
        if (!k) continue;
        if (raw === k || low === k.toLowerCase()) return map[k];
      }}
      return null;
    }}
    function nodeLabelText(g) {{
      var label = g.querySelector(":scope > .label .nodeLabel, :scope > .label foreignObject p, :scope > .label foreignObject span, :scope > foreignObject p");
      if (label) return (label.textContent || "").replace(/\\s+/g, " ").trim();
      return "";
    }}
    function wobbleOnce(g) {{
      if (g.dataset.wobbling === "1") return;
      g.dataset.wobbling = "1";
      var base = g.getAttribute("transform") || "";
      var frames = [0, -3, 3, -2, 2, -1, 0];
      var i = 0;
      var timer = setInterval(function () {{
        g.setAttribute("transform", base + " rotate(" + frames[i] + ")");
        i += 1;
        if (i >= frames.length) {{
          clearInterval(timer);
          g.setAttribute("transform", base);
          delete g.dataset.wobbling;
        }}
      }}, 40);
    }}
    function wireClicks(root) {{
      root.querySelectorAll("svg g.mindmap-node, svg g.node").forEach(function (g) {{
        var raw = nodeLabelText(g);
        var href = resolveHref(raw);
        if (!href) return;
        g.style.cursor = "pointer";
        g.classList.add("mm-clickable");
        g.setAttribute("role", "link");
        g.addEventListener("mouseenter", function () {{ wobbleOnce(g); }});
        g.addEventListener("click", function (e) {{
          e.preventDefault();
          e.stopPropagation();
          if (href.indexOf("http") === 0) window.open(href, "_blank", "noopener");
          else window.location.href = href;
        }});
      }});
    }}
    var nodes = Array.prototype.slice.call(document.querySelectorAll("pre.mermaid"));
    for (var i = 0; i < nodes.length; i++) {{
      var node = nodes[i];
      var code = node.textContent || "";
      var id = "mmd-" + Math.random().toString(36).slice(2);
      var out = await mermaid.render(id, code);
      node.outerHTML = '<div class="mermaid-svg">' + out.svg + "</div>";
    }}
    document.querySelectorAll(".mermaid-svg").forEach(wireClicks);
  }} catch (err) {{
    showFail("Mermaid 渲染失败: " + (err && err.message ? err.message : String(err)));
  }}
}})();
</script>"""


def _mm_escape(text: str) -> str:
    """Escape text for Mermaid mindmap node labels."""
    return (
        str(text)
        .replace('"', "'")
        .replace("\n", " ")
        .replace("(", "（")
        .replace(")", "）")
        .replace("[", "【")
        .replace("]", "】")
    )


def _shown_lemmas_on_map(doc: dict[str, Any]) -> set[str]:
    """Lemmas already appearing on mindmap branches (exclude backlinks)."""
    shown = set(linkables(doc))
    for chain in doc.get("chains") or []:
        for item in chain.get("items") or []:
            s = str(item).strip().lower()
            if TOKEN_RE.match(s):
                shown.add(s)
    return shown


def unique_backlinks(doc: dict[str, Any], backlinks: list[str] | None = None) -> list[str]:
    """Backlinks not already covered by 同核兄弟/chains — avoid duplicate branches."""
    shown = _shown_lemmas_on_map(doc)
    backs = backlinks if backlinks is not None else list(doc.get("backlinks") or [])
    return [b for b in backs if str(b).lower() not in shown]


def _chain_items_deduped(
    chain: dict[str, Any], seen_tokens: set[str]
) -> list[str]:
    items: list[str] = []
    for item in chain.get("items") or []:
        raw = str(item).strip()
        if not raw:
            continue
        low = raw.lower()
        if TOKEN_RE.match(low):
            if low in seen_tokens:
                continue
            seen_tokens.add(low)
        items.append(raw)
    return items


def build_mermaid_mindmap(doc: dict[str, Any]) -> tuple[str, list[tuple[str, list[str]]]]:
    """Build a sparse Mermaid mindmap + deferred chains (avoid overlaps).

    On-map (固定少支): 词核 / 基本义 / 同核兄弟(≤5) / 至多 2 条其它短链。
    其余链条返回 deferred，由页面下方列表展示。
    """
    lemma = _mm_escape(doc.get("lemma", ""))
    core = doc.get("core") or {}
    core_label = _mm_escape(core_display_label(core))
    basic_raw = str(doc.get("basic", "")).strip()
    basic = _mm_escape(basic_raw[:32] + ("…" if len(basic_raw) > 32 else ""))
    lines = [
        "mindmap",
        f"  root(({lemma}))",
        "    词核",
        f"      {core_label}",
        "    基本义",
        f"      {basic}",
    ]
    seen_tokens: set[str] = {str(doc.get("lemma", "")).strip().lower()}
    chains = list(doc.get("chains") or [])

    def is_sibling_chain(ch: dict[str, Any]) -> bool:
        t = str(ch.get("title") or ch.get("id") or "")
        return "同核" in t or str(ch.get("id") or "").upper() == "R"

    siblings = next((c for c in chains if is_sibling_chain(c)), None)
    others = [c for c in chains if c is not siblings]
    deferred: list[tuple[str, list[str]]] = []

    if siblings:
        items = _chain_items_deduped(siblings, seen_tokens)
        title = str(siblings.get("title") or "同核兄弟")
        on_map, rest = items[:4], items[4:]
        if on_map:
            lines.append(f"    {_mm_escape(title)}")
            for item in on_map:
                lines.append(f"      {_mm_escape(item)}")
        if rest:
            deferred.append((f"{title}·更多", rest))

    extra_hubs = 0
    for chain in others:
        title = str(chain.get("title") or chain.get("id") or "链")
        items = _chain_items_deduped(chain, seen_tokens)
        if not items:
            continue
        if extra_hubs < 2 and len(items) <= 4:
            lines.append(f"    {_mm_escape(title)}")
            for item in items:
                lines.append(f"      {_mm_escape(item)}")
            extra_hubs += 1
        else:
            deferred.append((title, items))

    # 回溯不进导图（下方详情已有），避免再挤一支
    return "\n".join(lines), deferred


def render_word_html(doc: dict[str, Any], table: dict[str, Any]) -> str:
    lemma = doc["lemma"]
    core = doc.get("core") or {}
    core_id = html.escape(str(core.get("id") or core.get("key") or ""))
    core_label = html.escape(core_display_label(core))
    core_def = html.escape(str(core.get("def", "")))
    basic = html.escape(str(doc.get("basic", "")))
    notes = html.escape(str(doc.get("notes", "")))
    updated = html.escape(str(doc.get("updated_at", "")))
    backlinks = doc.get("backlinks") or backlinks_from_table(table, lemma)

    mm_src, deferred_chains = build_mermaid_mindmap(doc)
    mermaid_src = html.escape(mm_src)
    back_html = "".join(f"<li>{word_chip(w, table)}</li>" for w in backlinks) or "<li><em>暂无</em></li>"
    examples = "".join(f"<li>{html.escape(str(ex))}</li>" for ex in (doc.get("examples") or []))
    thing_img = image_block(doc.get("image"), rel_prefix="../")
    more_blocks: list[str] = []
    for title, items in deferred_chains:
        chips = "".join(
            f'<span class="chip">{word_chip(it, table) if TOKEN_RE.match(it.lower()) else html.escape(it)}</span>'
            for it in items
        )
        more_blocks.append(
            f'<div class="chain-block"><div class="chain-title">{html.escape(title)}</div>'
            f'<div class="chips">{chips}</div></div>'
        )
    more_html = "".join(more_blocks)
    part_rows: list[str] = []
    for part in doc.get("part_explain") or []:
        if not isinstance(part, dict):
            continue
        seg = html.escape(str(part.get("segment") or ""))
        role = html.escape(str(part.get("role") or ""))
        power = str(part.get("power") or "").strip().lower()
        gloss = html.escape(str(part.get("gloss") or ""))
        power_label = {"yes": "有独立解释力", "no": "无独立词义", "weak": "弱助记"}.get(power, power)
        contrast = part.get("contrast") or []
        contrast_html = ""
        if contrast:
            chips = "".join(
                f'<span class="chip">{word_chip(str(c), table) if TOKEN_RE.match(str(c).lower()) else html.escape(str(c))}</span>'
                for c in contrast
            )
            contrast_html = f'<div class="chips" style="margin-top:.35rem">{chips}</div>'
        part_rows.append(
            f'<div class="chain-block"><div class="chain-title">'
            f'<code>{seg}</code> · {role} · {html.escape(power_label)}</div>'
            f'<div>{gloss}</div>{contrast_html}</div>'
        )
    parts_html = (
        f'<h2>词各部分解释</h2>{"".join(part_rows)}' if part_rows else ""
    )

    # Mermaid 点击：已生成同核/回溯词 → 本站词页；中心词 → 有道；词核标签 → 核页
    click_map: dict[str, str] = {}
    for w, entry in (table.get("lemmas") or {}).items():
        if entry.get("exists") and w != lemma:
            click_map[w] = f"../words/{w}.html"
    click_map[lemma] = youdao_url(lemma)
    core_key = str(core.get("id") or core.get("key") or "")
    if core_key:
        click_map[core_display_label(core)] = f"../cores/{core_key}.html"
        click_map[core_key] = f"../cores/{core_key}.html"
    click_json = json.dumps(click_map, ensure_ascii=False).replace("</", "<\\/")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{html.escape(lemma)} · 逻辑英语思维导图</title>
<script type="application/json" id="mm-click-map">{click_json}</script>
<style>
:root {{ --ink:#1a1a1a; --muted:#666; --pending:#999; --accent:#0b5fff; --card:#fff; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
  color:var(--ink); background:radial-gradient(circle at 15% 0%,#fff9e8,#e8f7ff 45%,#f3e8ff 100%); min-height:100vh; }}
header {{ padding:1rem 1.5rem; }}
header h1 {{ margin:0 0 .35rem; font-size:1.75rem; }}
header .core a {{ color:var(--accent); text-decoration:none; font-weight:700; }}
header .meta a {{ color:var(--muted); }}
.mm-wrap {{ padding:0 1rem 1rem; }}
.mermaid-panel {{ background:linear-gradient(180deg,#fffefb,#ffffff); border-radius:16px; padding:1rem; overflow:auto;
  box-shadow:0 10px 40px rgba(80,120,200,.12); border:1px solid rgba(100,160,220,.18); }}
.mermaid-panel h2 {{ margin:0 0 .5rem; font-size:1.1rem; }}
.mermaid-hint {{ margin:0 0 .75rem; color:var(--muted); font-size:.9rem; }}
.mermaid-svg {{ overflow:auto; }}
.mermaid-svg .mm-clickable {{ cursor:pointer; }}
.mermaid-svg .mm-clickable:hover {{ filter:brightness(1.08); }}
.mermaid-svg .mm-clickable:hover .nodeLabel,
.mermaid-svg .mm-clickable:hover p,
.mermaid-svg .mm-clickable:hover span {{ color:#0b5fff !important; text-decoration:underline; }}
.detail {{ display:grid; grid-template-columns:1fr 1fr; gap:1rem; padding:0 1rem 2rem; }}
@media (max-width:900px) {{ .detail {{ grid-template-columns:1fr; }} }}
.panel {{ background:linear-gradient(180deg,#fffefb,#ffffff); border-radius:14px; padding:1rem 1.2rem;
  box-shadow:0 8px 28px rgba(80,120,200,.1); border:1px solid rgba(100,160,220,.15); }}
.linked {{ color:var(--accent); }} .pending {{ color:var(--pending); }}
.thing-image img {{ width:100%; max-height:220px; object-fit:contain; background:#fff6e8; border-radius:10px; }}
.thing-image figcaption {{ font-size:.85rem; color:var(--muted); }}
.chain-block {{ margin-bottom:.75rem; }}
.chain-title {{ font-weight:700; color:#3a4a6a; margin-bottom:.35rem; }}
.chips {{ display:flex; flex-wrap:wrap; gap:.4rem; }}
.chip {{ background:#eef6ff; border-radius:999px; padding:.2rem .65rem; font-size:.92rem; }}
footer {{ padding:0 1.5rem 2rem; color:var(--muted); font-size:.9rem; }}
</style>
</head>
<body>
<header>
  <div class="meta"><a href="../index.html">← 总览 index</a></div>
  <h1>{html.escape(lemma)} · 思维导图</h1>
  <div class="core">词核：<a href="../cores/{core_id}.html">{core_label}</a>
  <div style="color:var(--muted);font-size:.95rem;margin-top:.25rem">{core_def}</div></div>
</header>

<section class="mm-wrap">
  <div class="mermaid-panel" aria-label="可点击思维导图">
    <h2>思维导图</h2>
    <p class="mermaid-hint">点中心词查有道；点彩色兄弟词进本站；点词核进核页。导图只放主干，更多链条见下方。</p>
    <pre class="mermaid">{mermaid_src}</pre>
  </div>
</section>

<section class="detail">
  <div class="panel">
    <h2>实物图</h2>
    {thing_img or "<p><em>无图</em></p>"}
    <p><strong>基本义</strong>：{basic}</p>
    {f'<h2>更多链条</h2>{more_html}' if more_html else ''}
  </div>
  <div class="panel">
    <h2>谁链到我 · backlinks</h2>
    <ul>{back_html}</ul>
    {parts_html}
    <h2>验收造句</h2>
    <ul>{examples}</ul>
    <p class="notes">{notes}</p>
  </div>
</section>
<footer>updated_at: {updated} · 中心是单词，分支是核/义/链 · 教学逻辑 ≠ 词源 · 可拆则拆、无义说无</footer>
{mermaid_boot_scripts(mindmap=True)}
</body>
</html>
"""


def render_core_html(core: dict[str, Any], table: dict[str, Any]) -> str:
    core_id = html.escape(str(core.get("id") or core.get("key") or ""))
    label = html.escape(core_display_label(core))
    key_raw = str(core.get("key") or core.get("id") or "")
    name_raw = str(core.get("name") or "")
    key = html.escape(key_raw)
    prototype = html.escape(str(core.get("prototype") or ""))
    name = html.escape(name_raw)
    definition = html.escape(str(core.get("def", "")))
    members = sorted({str(m).strip().lower() for m in (core.get("members") or []) if str(m).strip()})
    member_list = "".join(
        f"<li>{word_chip(m, table, rel_prefix='../words/')}</li>" for m in members
    ) or "<li><em>暂无成员</em></li>"
    core_img = image_block(core.get("image"), rel_prefix="../")
    # 中心短标签；成员作为 root 直接子节点沿四周展开（勿再套一层长标签）
    root_label = _mm_escape(f"{key_raw} · {name_raw}" if name_raw else key_raw)
    mm_lines = ["mindmap", f"  root(({root_label}))"]
    for m in members:
        mm_lines.append(f"    {_mm_escape(m)}")
    mermaid_src = html.escape("\n".join(mm_lines))
    click_map: dict[str, str] = {}
    for m in members:
        if (table.get("lemmas") or {}).get(m, {}).get("exists"):
            click_map[m] = f"../words/{m}.html"
    core_href = f"{core.get('id') or key_raw}.html"
    click_map[key_raw] = core_href
    if name_raw:
        click_map[f"{key_raw} · {name_raw}"] = core_href
    click_map[core_display_label(core)] = core_href
    click_json = json.dumps({k: v for k, v in click_map.items() if k}, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>词核 · {label}</title>
<script type="application/json" id="mm-click-map">{click_json}</script>
<style>
body {{ margin:0; font-family:Georgia,serif; background:radial-gradient(circle at 30% 0%,#fff9e8,#e8f7ff 55%,#f3e8ff); color:#1a1a1a; }}
header, main, footer {{ padding:1.25rem 1.5rem; }}
.linked {{ color:#0b5fff; text-decoration:none; font-weight:600; }} .pending {{ color:#999; }}
.card {{ background:linear-gradient(180deg,#fffefb,#ffffff); border-radius:16px; padding:1rem 1.2rem; margin-bottom:1rem;
  box-shadow:0 8px 28px rgba(80,120,200,.12); border:1px solid rgba(100,160,220,.18); }}
.thing-image img {{ width:100%; max-height:280px; object-fit:contain; background:#efece4; border-radius:10px; }}
.mermaid-svg {{ overflow:auto; min-height:480px; }}
.mermaid-svg svg {{ max-width:100%; height:auto; }}
.mermaid-svg .mm-clickable {{ cursor:pointer; }}
.mermaid-svg .mm-clickable:hover {{ filter:brightness(1.08); }}
.mermaid-svg .mm-clickable:hover text {{ fill:#0b5fff !important; }}
.mermaid-svg .mm-clickable:hover .nodeLabel,
.mermaid-svg .mm-clickable:hover p,
.mermaid-svg .mm-clickable:hover span {{ color:#0b5fff !important; text-decoration:underline; }}
.muted {{ color:#666; }}
.hint {{ color:#666; font-size:.9rem; }}
</style>
</head>
<body>
<header>
  <a href="../index.html">← 总览 index</a>
  <h1>词核思维导图：{label}</h1>
  <p>音形键 <strong>{key}</strong> · 原型词 <strong>{prototype}</strong> · 意象 <strong>{name}</strong></p>
  <p class="muted">{definition}</p>
  <p class="hint">Mermaid 节点可点：成员词 → 词页。请用浏览器打开。</p>
</header>
<main>
  <div class="card" aria-label="可点击思维导图">
    <h2>思维导图</h2>
    <pre class="mermaid">{mermaid_src}</pre>
  </div>
  <div class="card">
    <h2>同核成员</h2>
    <ul>{member_list}</ul>
  </div>
  <div class="card">{core_img}</div>
</main>
<footer>关键是音形键（如 bo），原型词（如 box）只是意象锚点 · 教学逻辑 ≠ 词源</footer>
{mermaid_boot_scripts(mindmap=True)}
</body>
</html>
"""


def render_index_html(root: Path, graph: dict[str, Any], table: dict[str, Any]) -> str:
    cores = graph.get("cores") or {}
    core_blocks = []
    for cid, meta in sorted(cores.items(), key=lambda x: (x[1].get("key") or x[0], x[0])):
        core_doc = load_core(root, cid) or {"id": cid, "members": []}
        label = html.escape(str(meta.get("label") or core_display_label(core_doc)))
        members = core_doc.get("members") or []
        mhtml = "".join(
            f"<li>{word_chip(m, table, rel_prefix='words/')}</li>" for m in members
        )
        core_blocks.append(
            f"<section class='core'><h2><a class='linked' href='cores/{html.escape(cid)}.html'>{label}</a></h2>"
            f"<ul>{mhtml}</ul></section>"
        )
    flat = "".join(
        f"<li>{word_chip(lemma, table, rel_prefix='words/')}</li>"
        for lemma, e in sorted((table.get("lemmas") or {}).items())
        if e.get("exists")
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>逻辑英语 · 词核总览</title>
<style>
body {{ margin:0; font-family:"Iowan Old Style",Palatino,Georgia,serif;
  background:radial-gradient(circle at 15% 0%,#fff9e8,#e8f7ff 45%,#f3e8ff 100%); color:#1a2a4a; }}
header {{ padding:1.5rem 1.5rem .5rem; }}
header h1 {{ margin:0 0 .4rem; font-size:1.9rem; }}
header p {{ margin:0; color:#556; }}
main {{ padding:1rem 1.5rem 2rem; display:grid; gap:1rem; }}
h2 {{ margin:.5rem 0; font-size:1.15rem; color:#3a4a6a; }}
.core, .flat {{ background:linear-gradient(180deg,#fffefb,#ffffff); border-radius:16px; padding:1rem 1.25rem;
  box-shadow:0 8px 28px rgba(80,120,200,.12); border:1px solid rgba(100,160,220,.18); }}
.core h2 {{ margin-top:0; }}
.core ul, .flat ul {{ display:flex; flex-wrap:wrap; gap:.5rem .75rem; list-style:none; padding:0; margin:.5rem 0 0; }}
.core li, .flat li {{ background:#eef6ff; border-radius:999px; padding:.25rem .7rem; }}
.linked {{ color:#0b5fff; text-decoration:none; font-weight:600; }}
.linked:hover {{ text-decoration:underline; }}
.pending {{ color:#999; }}
code {{ background:#fff3c4; padding:.1rem .35rem; border-radius:6px; }}
</style>
</head>
<body>
<header>
  <h1>逻辑英语图谱</h1>
  <p>词核按<strong>音形键</strong>组织，如 <code>bo ---- box（盒子）</code> · 关键是 bo · 点词进导图</p>
</header>
<main>
  <h2>词核目录</h2>
  {''.join(core_blocks) or '<p>暂无词核</p>'}
  <section class="flat">
    <h2>全部已生成单词</h2>
    <ul>{flat or '<li><em>暂无</em></li>'}</ul>
  </section>
</main>
</body>
</html>
"""


def ensure_core_from_word(root: Path, doc: dict[str, Any], graph: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    core = doc.get("core") or {}
    # id == sound/letter key (bo); prototype anchors meaning (box); name is Chinese gloss
    core_id = str(core.get("id") or core.get("key") or "").strip().lower()
    if not core_id:
        raise ValueError(f"{doc.get('lemma')}: core.id (音形键, e.g. bo) required")
    key = str(core.get("key") or core_id).strip().lower()
    prototype = str(core.get("prototype") or "").strip().lower()
    name = str(core.get("name", "")).strip() or key
    definition = str(core.get("def", "")).strip()
    existing = load_core(root, core_id)
    created = existing is None
    if existing is None:
        existing = {
            "id": core_id,
            "key": key,
            "prototype": prototype,
            "name": name,
            "def": definition,
            "members": [],
            "updated_at": now_iso(),
        }
        if core.get("image"):
            existing["image"] = core["image"]
    else:
        existing["key"] = key or existing.get("key") or core_id
        if prototype:
            existing["prototype"] = prototype
        if name:
            existing["name"] = name
        if definition:
            existing["def"] = definition
        if core.get("image") and not existing.get("image"):
            existing["image"] = core["image"]
        existing["updated_at"] = now_iso()
    # keep word.core in sync for display
    doc.setdefault("core", {})
    doc["core"]["id"] = core_id
    doc["core"]["key"] = existing.get("key") or key
    doc["core"]["prototype"] = existing.get("prototype") or prototype
    doc["core"]["name"] = existing.get("name") or name
    doc["core"]["def"] = existing.get("def") or definition
    save_core(root, existing)
    graph.setdefault("cores", {})[core_id] = {
        "key": existing.get("key") or key,
        "prototype": existing.get("prototype") or prototype,
        "name": existing.get("name") or name,
        "label": core_display_label(existing),
        "path": f"cores/{core_id}.html",
        "updated_at": now_iso(),
    }
    return existing, created


def rerender_set(table: dict[str, Any], lemma: str, mentions: set[str]) -> set[str]:
    entry = (table.get("lemmas") or {}).get(lemma) or {}
    out = {lemma}
    for src in entry.get("mentioned_by") or []:
        if ((table.get("lemmas") or {}).get(src) or {}).get("exists"):
            out.add(src)
    for t in mentions:
        if ((table.get("lemmas") or {}).get(t) or {}).get("exists"):
            out.add(t)
    return out


def render_one_word(root: Path, lemma: str, table: dict[str, Any]) -> str:
    doc = load_word(root, lemma)
    doc["backlinks"] = backlinks_from_table(table, lemma)
    doc["updated_at"] = doc.get("updated_at") or now_iso()
    # persist backlinks
    save_word(root, doc)
    html_text = render_word_html(doc, table)
    atomic_write_text(root / "words" / f"{lemma}.html", html_text)
    return lemma


def render_words_parallel(root: Path, lemmas: Iterable[str], table: dict[str, Any], jobs: int) -> list[str]:
    lemmas = sorted(set(lemmas))
    if not lemmas:
        return []
    if jobs <= 1 or len(lemmas) == 1:
        return [render_one_word(root, lem, table) for lem in lemmas]
    done: list[str] = []
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        futs = {ex.submit(render_one_word, root, lem, table): lem for lem in lemmas}
        for fut in as_completed(futs):
            done.append(fut.result())
    return sorted(done)


def upsert_words(
    root: Path,
    lemmas: list[str],
    *,
    jobs: int = 4,
) -> dict[str, Any]:
    ensure_dirs(root)
    cores_created: list[str] = []
    with TableLock(root):
        table = load_json(root / "lemma_table.json", empty_table())
        graph = load_json(root / "graph.json", empty_graph())
        all_rerender: set[str] = set()
        core_ids: set[str] = set()
        for lemma in lemmas:
            lemma = lemma.strip().lower()
            doc = load_word(root, lemma)
            doc["lemma"] = lemma
            doc["updated_at"] = now_iso()
            core_doc, created = ensure_core_from_word(root, doc, graph)
            if created:
                cores_created.append(core_doc["id"])
            core_ids.add(core_doc["id"])
            mentions = linkables(doc)
            apply_mentions_diff(
                table,
                lemma,
                mentions,
                exists=True,
                core_id=core_doc["id"],
            )
            doc["backlinks"] = backlinks_from_table(table, lemma)
            save_word(root, doc)
            all_rerender |= rerender_set(table, lemma, mentions)
            all_rerender.add(lemma)

        atomic_write_json(root / "lemma_table.json", table)
        graph = sync_graph_from_table(root, table)
        # refresh core members already done in sync; render
        updated = render_words_parallel(root, all_rerender, table, jobs)
        for cid in core_ids:
            core_doc = load_core(root, cid)
            if core_doc:
                atomic_write_text(
                    root / "cores" / f"{cid}.html",
                    render_core_html(core_doc, table),
                )
        atomic_write_text(root / "index.html", render_index_html(root, graph, table))
        event = {
            "op": "create" if len(lemmas) == 1 else "batch",
            "word": lemmas[0] if len(lemmas) == 1 else ",".join(lemmas),
            "cores_created": cores_created,
            "links_updated": updated,
            "workers": jobs,
            "summary": f"upsert {','.join(lemmas)}; rerender {len(updated)} pages",
        }
        append_history(root, event)
        return event


def upsert_core_only(root: Path, core_id: str) -> dict[str, Any]:
    ensure_dirs(root)
    with TableLock(root):
        table = load_json(root / "lemma_table.json", empty_table())
        graph = load_json(root / "graph.json", empty_graph())
        core = load_core(root, core_id)
        if core is None:
            raise FileNotFoundError(core_id)
        members = sorted(
            lem
            for lem, e in (table.get("lemmas") or {}).items()
            if e.get("exists") and e.get("core_id") == core_id
        )
        core["members"] = members
        core["updated_at"] = now_iso()
        save_core(root, core)
        graph.setdefault("cores", {})[core_id] = {
            "name": core.get("name", core_id),
            "path": f"cores/{core_id}.html",
            "updated_at": now_iso(),
        }
        atomic_write_json(root / "graph.json", graph)
        atomic_write_text(root / "cores" / f"{core_id}.html", render_core_html(core, table))
        atomic_write_text(root / "index.html", render_index_html(root, graph, table))
        event = {"op": "update_core", "core_id": core_id, "summary": f"refresh core {core_id}"}
        append_history(root, event)
        return event
