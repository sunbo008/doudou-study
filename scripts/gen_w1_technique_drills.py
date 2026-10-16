#!/usr/bin/env python3
"""Generate W1 mental-math technique progressive drills (Plan0–Plan5)."""
from __future__ import annotations

import argparse
import random
import re
from collections import Counter, defaultdict
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
W1 = ROOT / "practice" / "W1-小数乘除"
OUT = ROOT / "practice" / "W1-心算技巧递进"
SEED = 20260908

SPECIAL_PCT = {
    25: Fraction(1, 4),
    50: Fraction(1, 2),
    75: Fraction(3, 4),
    20: Fraction(1, 5),
    40: Fraction(2, 5),
    60: Fraction(3, 5),
    80: Fraction(4, 5),
    125: Fraction(5, 4),  # as percent of 100 → 1.25? wait 125%=5/4
    12.5: Fraction(1, 8),
    37.5: Fraction(3, 8),
    62.5: Fraction(5, 8),
    87.5: Fraction(7, 8),
}

# Use percent ints that are special: 12.5 written as 12.5
SPECIAL_PCT_KEYS = [12.5, 20, 25, 37.5, 50, 62.5, 75, 80, 87.5]


def fmt_num(x: Fraction | int | float | Decimal) -> str:
    if isinstance(x, Fraction):
        d = Decimal(x.numerator) / Decimal(x.denominator)
    else:
        d = Decimal(str(x))
    s = format(d.normalize(), "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"


def is_nice(ans: Fraction, max_places: int = 3, max_abs: float = 2000) -> bool:
    if ans < 0:
        return False
    den = ans.denominator
    while den % 2 == 0:
        den //= 2
    while den % 5 == 0:
        den //= 5
    if den != 1:
        return False
    s = fmt_num(ans)
    if "." in s and len(s.split(".")[1]) > max_places:
        return False
    if ans > max_abs:
        return False
    return True


def load_used() -> set[str]:
    used: set[str] = set()
    for rel in [
        "心算专项-200题/心算专项-200题.md",
        "心算专项-400题/心算专项-400题.md",
        "心算专项-400题-速度巩固/心算专项-400题-速度巩固.md",
    ]:
        p = W1 / rel
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8").split("## 答案")[0]
        used |= set(re.findall(r"`(.+?) = ______`", text))
    return used


class Bank:
    def __init__(self, used: set[str]):
        self.prior_used = set(used)
        self.used = set(used)  # exprs claimed as new compute items (vs prior sets)
        self.by_type: dict[str, list[dict]] = defaultdict(list)
        self._seen_in_type: dict[str, set[str]] = defaultdict(set)
        self.rng = random.Random(SEED)

    def add(
        self,
        type_id: str,
        expr: str,
        answer: str,
        tech: str,
        kind: str = "compute",
        *,
        reuse: bool = False,
    ) -> bool:
        """Add item. New items must not collide with prior 200/400 sets.
        reuse=True copies an existing bank expr into another type_id."""
        if expr in self._seen_in_type[type_id]:
            return False
        if not reuse:
            if expr in self.prior_used or expr in self.used:
                return False
            self.used.add(expr)
        self._seen_in_type[type_id].add(expr)
        item = {"expr": expr, "answer": answer, "tech": tech, "type_id": type_id, "kind": kind}
        self.by_type[type_id].append(item)
        return True

    def copy_into(
        self, type_id: str, src: dict, tech: str | None = None, kind: str | None = None
    ) -> bool:
        return self.add(
            type_id,
            src["expr"],
            src["answer"],
            tech or src["tech"],
            kind or src["kind"],
            reuse=True,
        )

    def need(self, type_id: str, n: int) -> None:
        if len(self.by_type[type_id]) < n:
            raise RuntimeError(f"{type_id} only {len(self.by_type[type_id])}/{n}")


def frac_from_dec(s: str) -> Fraction:
    return Fraction(str(Decimal(s)))


def build_bank(used: set[str]) -> Bank:
    b = Bank(used)
    r = b.rng

    # ---- P1-A percent to decimal (oral fill) ----
    pcts = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 16, 18, 24, 28, 30, 32, 35, 36, 45, 48, 55, 64, 70, 72, 85, 90, 96, 100]
    for p in pcts:
        expr = f"{p}% = ?"
        ans = fmt_num(Fraction(p, 100))
        b.add("P1-A", expr, ans, "T1", "convert")

    # ---- P1-B decimal × percent ----
    for _ in range(400):
        if len(b.by_type["P1-B"]) >= 35:
            break
        a = Fraction(r.randint(1, 99), 10)
        p = r.choice([5, 8, 10, 12, 15, 16, 18, 20, 24, 30, 35, 40, 45, 60])
        ans = a * Fraction(p, 100)
        if not is_nice(ans):
            continue
        b.add("P1-B", f"{fmt_num(a)} × {p}%", fmt_num(ans), "T1")

    # ---- P1-C integer × special percent ----
    for _ in range(500):
        if len(b.by_type["P1-C"]) >= 35:
            break
        p = r.choice([20, 25, 50, 75, 12.5, 37.5, 62.5])
        # choose integer divisible for nice answer via fraction
        frac = SPECIAL_PCT[p]
        # a * p% = a * frac
        # pick a multiple of denominator
        den = frac.denominator
        k = r.randint(1, 20)
        a = den * k
        if a > 120:
            continue
        ans = Fraction(a) * frac
        if not is_nice(ans):
            continue
        ps = fmt_num(p) if isinstance(p, float) else str(int(p)) if float(p) == int(p) else str(p)
        if p == 12.5:
            ps = "12.5"
        elif p in (37.5, 62.5, 87.5):
            ps = str(p)
        else:
            ps = str(int(p))
        b.add("P1-C", f"{a} × {ps}%", fmt_num(ans), "T2")

    # ---- P1-D decimal × special percent ----
    for _ in range(500):
        if len(b.by_type["P1-D"]) >= 25:
            break
        p = r.choice([20, 25, 50, 75, 12.5])
        frac = SPECIAL_PCT[p]
        a = Fraction(r.randint(1, 40), 2)  # .0 or .5
        ans = a * frac
        if not is_nice(ans) or a == int(a):
            # allow some integers too but prefer decimals
            if a == int(a) and r.random() < 0.5:
                continue
            if not is_nice(ans):
                continue
        ps = "12.5" if p == 12.5 else str(int(p))
        b.add("P1-D", f"{fmt_num(a)} × {ps}%", fmt_num(ans), "T2")

    # ---- P1-E estimate magnitude for ÷% ----
    est_pairs = [
        ("2.8 ÷ 6%", "四十多", "T1+T10"),
        ("1.5 ÷ 5%", "30 左右", "T1+T10"),
        ("4.8 ÷ 12%", "40 左右", "T1+T10"),
        ("0.6 ÷ 3%", "20 左右", "T1+T10"),
        ("3.6 ÷ 8%", "四十多", "T1+T10"),
        ("2.4 ÷ 4%", "60 左右", "T1+T10"),
        ("0.9 ÷ 9%", "10 左右", "T1+T10"),
        ("1.2 ÷ 6%", "20 左右", "T1+T10"),
        ("7.2 ÷ 9%", "80 左右", "T1+T10"),
        ("0.48 ÷ 12%", "4 左右", "T1+T10"),
        ("5 ÷ 25%", "20", "T1+T10"),
        ("8 ÷ 16%", "50", "T1+T10"),
        ("3 ÷ 15%", "20", "T1+T10"),
        ("9 ÷ 30%", "30", "T1+T10"),
        ("6 ÷ 8%", "75", "T1+T10"),
        ("1 ÷ 4%", "25", "T1+T10"),
        ("2 ÷ 8%", "25", "T1+T10"),
        ("0.5 ÷ 5%", "10", "T1+T10"),
    ]
    for expr, ans, tech in est_pairs:
        b.add("P1-E", expr + "（估数量级）", ans, tech, "estimate")

    # ---- P2-A ×0.5 / 0.25 / 0.125 ----
    for _ in range(600):
        if len(b.by_type["P2-A"]) >= 35:
            break
        f = r.choice([Fraction(1, 2), Fraction(1, 4), Fraction(1, 8)])
        # a such that a*f nice
        if f == Fraction(1, 2):
            a = Fraction(r.randint(1, 40), 2)
        elif f == Fraction(1, 4):
            a = Fraction(r.randint(1, 80), 2)
        else:
            a = Fraction(r.randint(1, 80), 1)
        ans = a * f
        if not is_nice(ans):
            continue
        b.add("P2-A", f"{fmt_num(a)} × {fmt_num(f)}", fmt_num(ans), "T4")

    # ---- P2-B single pair ----
    pairs = [
        (Fraction(1, 4), 4),
        (Fraction(5, 4), 8),
        (Fraction(25, 2), 8),  # 12.5×8
        (Fraction(1, 8), 8),
    ]
    for _ in range(400):
        if len(b.by_type["P2-B"]) >= 35:
            break
        left, right = r.choice(pairs)
        # either left×right or (k×left)×right via showing left×right only when left is the special
        mode = r.choice(["direct", "scaled"])
        if mode == "direct":
            expr = f"{fmt_num(left)} × {right}"
            ans = left * right
        else:
            k = Fraction(r.randint(1, 15), r.choice([1, 2, 5, 10]))
            # (k) × left × right shown as k × left with implied? Better: show special × (right*k/k)
            # Use: special × n where n multiple of 4 or 8
            if right == 4:
                n = 4 * r.randint(1, 12)
                expr = f"{fmt_num(left)} × {n}"
                ans = left * n
            else:
                n = 8 * r.randint(1, 9)
                expr = f"{fmt_num(left)} × {n}"
                ans = left * n
        if not is_nice(ans):
            continue
        b.add("P2-B", expr, fmt_num(ans), "T5")

    # ---- P2-C three-factor ----
    for _ in range(800):
        if len(b.by_type["P2-C"]) >= 35:
            break
        kind = r.choice(["025_4", "125_8", "0125_8", "125_8b"])
        mid = Fraction(r.randint(1, 40), r.choice([1, 2, 4, 5, 10]))
        if kind == "025_4":
            factors = [Fraction(1, 4), mid, 4]
        elif kind == "125_8":
            factors = [Fraction(5, 4), mid, 8]
        elif kind == "0125_8":
            factors = [Fraction(1, 8), mid, 8]
        else:
            factors = [Fraction(25, 2), mid, Fraction(4, 5)]  # 12.5 × mid × 0.8
        r.shuffle(factors)
        ans = factors[0] * factors[1] * factors[2]
        if not is_nice(ans):
            continue
        expr = f"{fmt_num(factors[0])} × {fmt_num(factors[1])} × {fmt_num(factors[2])}"
        b.add("P2-C", expr, fmt_num(ans), "T5")

    # ---- P2-D ×1.5 / ×2.5 ----
    for _ in range(400):
        if len(b.by_type["P2-D"]) >= 30:
            break
        m = r.choice([Fraction(3, 2), Fraction(5, 2)])
        a = Fraction(r.randint(1, 40), r.choice([1, 2, 5, 10]))
        ans = a * m
        if not is_nice(ans):
            continue
        b.add("P2-D", f"{fmt_num(a)} × {fmt_num(m)}", fmt_num(ans), "T6")

    # ---- P2-E normal decimal mul ----
    for _ in range(500):
        if len(b.by_type["P2-E"]) >= 25:
            break
        a = Fraction(r.randint(11, 95), 10)
        b2 = Fraction(r.randint(11, 95), 10)
        ans = a * b2
        if not is_nice(ans) or ans > 100:
            continue
        b.add("P2-E", f"{fmt_num(a)} × {fmt_num(b2)}", fmt_num(ans), "T3")

    # ---- P3-A div one-decimal ----
    for _ in range(600):
        if len(b.by_type["P3-A"]) >= 35:
            break
        div = Fraction(r.randint(1, 9), 10)
        if div == 0:
            continue
        quot = Fraction(r.randint(1, 30), r.choice([1, 2, 5]))
        dividend = quot * div
        if not is_nice(dividend) or not is_nice(quot):
            continue
        b.add("P3-A", f"{fmt_num(dividend)} ÷ {fmt_num(div)}", fmt_num(quot), "T7")

    # ---- P3-B two-decimal divisor ----
    for _ in range(600):
        if len(b.by_type["P3-B"]) >= 30:
            break
        div = Fraction(r.randint(1, 25), 100) * r.choice([1, 5])  # .05 .1 etc
        div = Fraction(r.choice([5, 15, 25, 35, 4, 8, 12, 16, 24]), 100)
        quot = Fraction(r.randint(2, 40), r.choice([1, 2, 5]))
        dividend = quot * div
        if not is_nice(dividend) or not is_nice(quot) or not is_nice(div):
            continue
        b.add("P3-B", f"{fmt_num(dividend)} ÷ {fmt_num(div)}", fmt_num(quot), "T7")

    # ---- P3-C ÷ percent ----
    for _ in range(800):
        if len(b.by_type["P3-C"]) >= 45:
            break
        p = r.choice([4, 5, 6, 8, 10, 12, 15, 16, 20, 24, 25, 30, 40, 50])
        quot = Fraction(r.randint(2, 80), r.choice([1, 2, 4, 5]))
        a = quot * Fraction(p, 100)
        if not is_nice(a) or not is_nice(quot) or a > 50:
            continue
        b.add("P3-C", f"{fmt_num(a)} ÷ {p}%", fmt_num(quot), "T8")

    # ---- P3-D ÷ special percent ----
    for _ in range(500):
        if len(b.by_type["P3-D"]) >= 30:
            break
        p = r.choice([20, 25, 50, 75, 12.5])
        frac = SPECIAL_PCT[p]
        # a ÷ (p%) = a / frac = a * 1/frac
        quot = Fraction(r.randint(2, 40), r.choice([1, 2, 4]))
        a = quot * frac
        if not is_nice(a) or not is_nice(quot):
            continue
        ps = "12.5" if p == 12.5 else str(int(p))
        b.add("P3-D", f"{fmt_num(a)} ÷ {ps}%", fmt_num(quot), "T2+T8")

    # ---- P3-E trap pairs oral ----
    traps = [
        ("2.8 ÷ 6 与 2.8 ÷ 6% 哪个商更大？", "2.8 ÷ 6% 更大", "T8+T10"),
        ("1.5 ÷ 5 与 1.5 ÷ 5% 哪个商更大？", "1.5 ÷ 5% 更大", "T8+T10"),
        ("4.8 ÷ 12 与 4.8 ÷ 12% 哪个商更大？", "4.8 ÷ 12% 更大", "T8+T10"),
        ("3 ÷ 25 与 3 ÷ 25% 哪个商更大？", "3 ÷ 25% 更大", "T8+T10"),
        ("0.6 ÷ 3 与 0.6 ÷ 3% 哪个商更大？", "0.6 ÷ 3% 更大", "T8+T10"),
        ("2.4 ÷ 8 与 2.4 ÷ 8% 哪个商更大？", "2.4 ÷ 8% 更大", "T8+T10"),
        ("6 ÷ 4 与 6 ÷ 4% 哪个商更大？", "6 ÷ 4% 更大", "T8+T10"),
        ("9 ÷ 9 与 9 ÷ 9% 哪个商更大？", "9 ÷ 9% 更大", "T8+T10"),
        ("1 ÷ 2 与 1 ÷ 2% 哪个商更大？", "1 ÷ 2% 更大", "T8+T10"),
        ("5 ÷ 10 与 5 ÷ 10% 哪个商更大？", "5 ÷ 10% 更大", "T8+T10"),
        ("7.2 ÷ 8 与 7.2 ÷ 8% 哪个商更大？", "7.2 ÷ 8% 更大", "T8+T10"),
        ("0.9 ÷ 9 与 0.9 ÷ 9% 哪个商更大？", "0.9 ÷ 9% 更大", "T8+T10"),
        ("4 ÷ 16 与 4 ÷ 16% 哪个商更大？", "4 ÷ 16% 更大", "T8+T10"),
        ("3.6 ÷ 6 与 3.6 ÷ 6% 哪个商更大？", "3.6 ÷ 6% 更大", "T8+T10"),
        ("8 ÷ 20 与 8 ÷ 20% 哪个商更大？", "8 ÷ 20% 更大", "T8+T10"),
    ]
    for expr, ans, tech in traps:
        b.add("P3-E", expr, ans, tech, "oral")

    # ---- P4-A three-factor continue ----
    for item in b.by_type["P2-C"][:40]:
        # clone into P4-A with new exprs by reshuffling unused
        pass
    for _ in range(600):
        if len(b.by_type["P4-A"]) >= 30:
            break
        mid = Fraction(r.randint(1, 36), r.choice([1, 2, 4, 5, 10]))
        factors = [Fraction(25, 2), mid, Fraction(4, 5)]
        r.shuffle(factors)
        ans = factors[0] * factors[1] * factors[2]
        if not is_nice(ans):
            continue
        expr = f"{fmt_num(factors[0])} × {fmt_num(factors[1])} × {fmt_num(factors[2])}"
        b.add("P4-A", expr, fmt_num(ans), "T5")

    # ---- P4-B distributive extract ----
    for _ in range(500):
        if len(b.by_type["P4-B"]) >= 35:
            break
        # a% × m + a% × n = a% × (m+n)
        a = r.choice([15, 20, 25, 30, 35, 38, 40, 45, 50, 60, 75])
        m = r.randint(10, 70)
        n = 100 - m if r.random() < 0.5 else r.randint(10, 70)
        ans = Fraction(a, 100) * (m + n)
        if not is_nice(ans):
            continue
        expr = f"{a}% × {m} + {a}% × {n}"
        b.add("P4-B", expr, fmt_num(ans), "T9")

    # ---- P4-C near integer ----
    for _ in range(500):
        if len(b.by_type["P4-C"]) >= 35:
            break
        a = Fraction(r.randint(15, 95), 10)
        mode = r.choice(["101", "99", "1.01", "0.99"])
        if mode == "101":
            expr = f"{fmt_num(a)} × 101"
            ans = a * 101
        elif mode == "99":
            expr = f"{fmt_num(a)} × 99"
            ans = a * 99
        elif mode == "1.01":
            expr = f"{fmt_num(a)} × 1.01"
            ans = a * Fraction(101, 100)
        else:
            expr = f"{fmt_num(a)} × 0.99"
            ans = a * Fraction(99, 100)
        if not is_nice(ans):
            continue
        b.add("P4-C", expr, fmt_num(ans), "T9")

    # ---- P4-D split ----
    for _ in range(400):
        if len(b.by_type["P4-D"]) >= 30:
            break
        a = Fraction(r.choice([2, 4, 5, 8]), 10)  # 0.2 0.4 0.5 0.8
        base = r.choice([10, 100])
        delta = Fraction(r.randint(1, 9), 10)
        # a × (base + delta)
        whole = base + delta
        ans = a * whole
        if not is_nice(ans):
            continue
        b.add("P4-D", f"{fmt_num(a)} × {fmt_num(whole)}", fmt_num(ans), "T9")

    # ---- P4-E can you simplify? ----
    judgments = [
        ("3.6 × 1.5 + 3.6 × 8.5，能用分配律吗？并计算", "能；=3.6×10=36", "T9+T10"),
        ("2.5 × 1.25 × 0.32，能用结合律凑整吗？并计算", "能；先 1.25×0.32 或 2.5×0.32", "T5+T10"),
        ("4.2 + 3.5 × 2，能先把 4.2 与 3.5 加起来再乘吗？", "不能；先乘后加", "T10"),
        ("0.25 × 4.8 × 4，建议怎么算？并求值", "先 0.25×4=1，再×4.8=4.8", "T5+T10"),
        ("7.2 ÷ 0.8 × 0.5，能改成 7.2 ÷ (0.8×0.5) 吗？", "不能；连续乘除从左到右", "T10"),
        ("5.6 × 99，怎么拆？并求值", "5.6×100−5.6=560−5.6=554.4", "T9+T10"),
        ("12% × 50 + 12% × 50，等于？", "12%×100=12", "T9+T10"),
        ("1.25 × 8.8 × 0.8，建议怎么算？并求值", "先 1.25×0.8=1，再×8.8=8.8", "T5+T10"),
        ("9.9 × 3.5，怎么拆？并求值", "10×3.5−0.1×3.5=35−0.35=34.65", "T9+T10"),
        ("6 ÷ 25% × 4，先算谁？并求值", "先 6÷25%=24，再×4=96", "T8+T10"),
        ("0.8 × 100.1，怎么拆？并求值", "0.8×100+0.8×0.1=80.08", "T9+T10"),
        ("2.4 × 3 + 2.4，等于？", "2.4×4=9.6", "T9+T10"),
        ("15% × 40 − 15% × 20，等于？", "15%×20=3", "T9+T10"),
        ("3.5 × 2.4 ÷ 0.7，能否先约？并求值", "可；约后=12", "T7+T10"),
        ("4.8 × 25% ÷ 0.4，等于？", "1.2÷0.4=3", "T2+T7+T10"),
    ]
    for expr, ans, tech in judgments:
        b.add("P4-E", expr, ans, tech, "oral")

    # ---- P5-A estimate only ----
    for item in b.by_type["P1-E"]:
        b.copy_into("P5-A", item, tech="T10", kind="estimate")
    extra_est = [
        ("9.6 × 0.25（估）", "约 2.4", "T10"),
        ("1.25 × 8（估）", "10", "T10"),
        ("48 × 12.5%（估）", "6", "T10"),
        ("7.2 ÷ 0.9（估）", "8", "T10"),
    ]
    for expr, ans, tech in extra_est:
        b.add("P5-A", expr, ans, tech, "estimate")

    # ---- P5-B compute + note verify ----
    for src in ["P1-B", "P2-A", "P3-A", "P3-C"]:
        for item in b.by_type[src][:8]:
            b.add(
                "P5-B",
                item["expr"] + "（算完用逆运算验）",
                item["answer"],
                "T10",
                "compute",
            )

    # ---- P5-D double technique ----
    for _ in range(400):
        if len(b.by_type["P5-D"]) >= 35:
            break
        # 25% × mid × 4
        mid = Fraction(r.randint(1, 40), r.choice([1, 2, 5, 10]))
        factors = [Fraction(1, 4), mid, 4]  # as 25%, mid, 4
        r.shuffle(factors)
        # present one as percent if it's 1/4
        parts = []
        for f in factors:
            if f == Fraction(1, 4) and r.random() < 0.7:
                parts.append("25%")
            else:
                parts.append(fmt_num(f))
        ans = Fraction(1, 4) * mid * 4
        if not is_nice(ans):
            continue
        expr = " × ".join(parts)
        b.add("P5-D", expr, fmt_num(ans), "T1+T5")

    # Plan0 types as aliases / dedicated
    for item in b.by_type["P1-B"][:8]:
        b.copy_into("D1", item, tech="T1")
    for item in b.by_type["P1-C"][:6]:
        b.copy_into("D2", item, tech="T2")
    for item in b.by_type["P2-B"][:6]:
        b.copy_into("D3", item, tech="T5")
    for item in b.by_type["P2-C"][:4]:
        b.copy_into("D3", item, tech="T5")
    for item in b.by_type["P3-A"][:6]:
        b.copy_into("D4", item, tech="T7")
    for item in b.by_type["P3-C"][:6]:
        b.copy_into("D5", item, tech="T8")
    for item in b.by_type["P4-B"][:5]:
        b.copy_into("D6", item, tech="T9")
    for item in b.by_type["P1-E"][:5]:
        b.copy_into("D7", item, tech="T10", kind="estimate")

    # P5-C pool = mix of compute types
    for tid in [
        "P1-B",
        "P1-C",
        "P1-D",
        "P2-A",
        "P2-B",
        "P2-C",
        "P2-D",
        "P3-A",
        "P3-B",
        "P3-C",
        "P3-D",
        "P4-A",
        "P4-B",
        "P4-C",
        "P4-D",
    ]:
        for item in b.by_type[tid]:
            b.copy_into("P5-C", item)

    mins = {
        "P1-A": 30,
        "P1-B": 30,
        "P1-C": 30,
        "P1-D": 20,
        "P1-E": 15,
        "P2-A": 30,
        "P2-B": 30,
        "P2-C": 30,
        "P2-D": 25,
        "P2-E": 20,
        "P3-A": 30,
        "P3-B": 25,
        "P3-C": 40,
        "P3-D": 25,
        "P3-E": 15,
        "P4-A": 25,
        "P4-B": 30,
        "P4-C": 30,
        "P4-D": 25,
        "P4-E": 15,
        "P5-A": 20,
        "P5-B": 20,
        "P5-C": 100,
        "P5-D": 30,
    }
    for k, n in mins.items():
        b.need(k, n)
    return b


def take(pool: list[dict], n: int, rng: random.Random, used_local: set[str]) -> list[dict]:
    cand = [x for x in pool if x["expr"] not in used_local]
    rng.shuffle(cand)
    out = cand[:n]
    for x in out:
        used_local.add(x["expr"])
    return out


def make_day_sheet(
    plan: str,
    day: int,
    warm: list[dict],
    focus: list[dict],
    challenge: list[dict],
) -> dict:
    assert len(warm) == 6 and len(focus) == 10 and len(challenge) == 4
    return {
        "plan": plan,
        "day": day,
        "warm": warm,
        "focus": focus,
        "challenge": challenge,
        "all": warm + focus + challenge,
    }


def render_sheet_md(title: str, sheet: dict, show_tech_on_student: bool) -> str:
    lines = [
        f"# {title}",
        "",
        "> 每日三招：招一温习约 60s · 招二新招约 150s · 招三挑战约 90s（合计约 5 分钟）",
        "> 不用计算器。做完口述 1 题：今天新招是什么、为什么用它。",
        "",
        "姓名：________　日期：________　用时：________　对题：____ / 20",
        "",
    ]

    def block(name: str, items: list[dict], start: int) -> int:
        lines.append(f"## {name}")
        lines.append("")
        i = start
        for it in items:
            tech = f"（{it['tech']}）" if show_tech_on_student else ""
            if it["kind"] == "estimate":
                lines.append(f"{i}. `{it['expr']}`{tech} → 数量级：________")
            elif it["kind"] in ("oral", "convert"):
                if it["type_id"] == "P1-A" or it["kind"] == "convert":
                    lines.append(f"{i}. `{it['expr']}`{tech} → ________")
                else:
                    lines.append(f"{i}. {it['expr']}{tech}")
                    lines.append("")
                    lines.append("   答：________________________________")
            else:
                lines.append(f"{i}. `{it['expr']} = ______`{tech}")
            i += 1
        lines.append("")
        return i

    n = 1
    n = block("招一 · 温习（6 题）", sheet["warm"], n)
    n = block("招二 · 新招（10 题）", sheet["focus"], n)
    block("招三 · 挑战（4 题）", sheet["challenge"], n)
    return "\n".join(lines)


def render_answers_md(title: str, sheets: list[dict]) -> str:
    lines = [f"# {title}", "", "> 家长用。每题含技巧代号。", ""]
    for sh in sheets:
        lines.append(f"## Day {sh['day']:02d}")
        lines.append("")
        i = 1
        for section, key in [("招一", "warm"), ("招二", "focus"), ("招三", "challenge")]:
            lines.append(f"### {section}")
            lines.append("")
            for it in sh[key]:
                lines.append(
                    f"{i}. `{it['expr']}` = **{it['answer']}**　`{it['tech']}`　[{it['type_id']}]"
                )
                i += 1
            lines.append("")
    return "\n".join(lines)


def register_font() -> str:
    for p in [
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
    ]:
        if Path(p).exists():
            pdfmetrics.registerFont(TTFont("CJK", p, subfontIndex=0))
            return "CJK"
    raise SystemExit("No CJK font")


def write_tech_card_pdf(pdf_path: Path) -> None:
    """One-page quick-ref with a real bordered table (not markdown pipes)."""
    font = register_font()
    left = right = 11 * mm
    top = bottom = 10 * mm
    usable_w = A4[0] - left - right
    usable_h = A4[1] - top - bottom

    title_s = ParagraphStyle(
        "card_t", fontName=font, fontSize=15, leading=19, alignment=TA_CENTER, spaceAfter=3
    )
    meta_s = ParagraphStyle(
        "card_m", fontName=font, fontSize=8.5, leading=11.5, alignment=TA_CENTER, spaceAfter=1.5
    )
    foot_s = ParagraphStyle(
        "card_f", fontName=font, fontSize=10, leading=13, alignment=TA_LEFT, spaceBefore=5
    )
    th = ParagraphStyle("th", fontName=font, fontSize=9.5, leading=12, textColor=colors.white, alignment=TA_CENTER)
    td = ParagraphStyle("td", fontName=font, fontSize=9, leading=12)
    td_code = ParagraphStyle(
        "tdc",
        fontName=font,
        fontSize=11,
        leading=13,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1a365d"),
    )

    rows_data = [
        ("代号", "技巧", "做法", "例子"),
        ("T1", "百分数→小数", "去 %，小数点左移两位", "6%=0.06"),
        (
            "T2",
            "特殊百分数→分数",
            "25%=1/4，75%=3/4，12.5%=1/8，20%=1/5，50%=1/2",
            "36×25%=9",
        ),
        ("T3", "小数乘法定点", "先按整数乘，再数小数位总和定点", "4.2×3.5→42×35 再点 2 位"),
        ("T4", "×0.5 / 0.25 / 0.125", "当作 ÷2 / ÷4 / ÷8", "7.6×0.25=1.9"),
        (
            "T5",
            "凑整对",
            "0.25×4=1；1.25×8=10；12.5×8=100；0.125×8=1；三因数用结合律",
            "0.25×7.2×4=7.2",
        ),
        ("T6", "×1.5 / ×2.5", "×1 再加一半；或 ×5÷2", "5.6×1.5=8.4"),
        ("T7", "除法齐搬家", "除数变整数，被除数同扩（商不变）", "2.8÷0.7=28÷7=4"),
        ("T8", "÷百分数四步", "先 T1 → 改写 → T7 → 估验", "2.8÷6%=2.8÷0.06"),
        (
            "T9",
            "分配律（及逆）",
            "a×b+a×c=a(b+c)；近整拆 ×99=×100−×1",
            "3.8×1.01=3.8+0.038",
        ),
        ("T10", "先估后算 / 逆验", "看数量级；乘除互验", "÷6% 的商应远大于 ÷6"),
    ]

    table_data = []
    for i, (a, b, c, d) in enumerate(rows_data):
        if i == 0:
            table_data.append(
                [Paragraph(a, th), Paragraph(b, th), Paragraph(c, th), Paragraph(d, th)]
            )
        else:
            table_data.append(
                [
                    Paragraph(a, td_code),
                    Paragraph(b, td),
                    Paragraph(c, td),
                    Paragraph(d, td),
                ]
            )

    # header ~22mm + footer ~14mm + gaps ~8mm → table gets the rest, split across 11 rows
    header_block = 22 * mm
    footer_block = 16 * mm
    table_h = usable_h - header_block - footer_block
    row_h = table_h / 11.0
    row_heights = [row_h] * 11

    col_w = [16 * mm, 36 * mm, usable_w - 16 * mm - 36 * mm - 46 * mm, 46 * mm]
    tbl = Table(table_data, colWidths=col_w, rowHeights=row_heights, repeatRows=1)
    header_bg = colors.HexColor("#2c5282")
    stripe = colors.HexColor("#edf2f7")
    line = colors.HexColor("#718096")
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.7, line),
        ("BOX", (0, 0), (-1, -1), 1.4, header_bg),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, header_bg),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for r in range(1, len(table_data)):
        if r % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, r), (-1, r), stripe))
    tbl.setStyle(TableStyle(style_cmds))

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=left,
        rightMargin=right,
        topMargin=top,
        bottomMargin=bottom,
        title="心算技巧速查卡",
    )
    story = [
        Paragraph("心算技巧速查卡（T1～T10）", title_s),
        Paragraph(
            "出处：人教版五上小数乘除与运算定律、六上百分数；《义务教育数学课程标准（2022）》运算能力",
            meta_s,
        ),
        Paragraph("非「一口清」表演速算 · 读懂题后少在心算上翻车", meta_s),
        Spacer(1, 3 * mm),
        tbl,
        Paragraph(
            "<b>一句话：</b>有 % 先转化；能凑整先凑整；除法齐搬家；算完估一估。",
            foot_s,
        ),
    ]
    doc.build(story)


def format_q_line(n: int, it: dict, show_tech: bool) -> str:
    tech = f" <font color='#718096'>({it['tech']})</font>" if show_tech else ""
    expr = it["expr"].replace("<", "&lt;").replace(">", "&gt;")
    if it["kind"] == "estimate":
        return f"{n}. {expr}{tech} → 数量级：______"
    if it["kind"] == "convert":
        return f"{n}. {expr}{tech} → ______"
    if it["kind"] == "oral":
        return f"{n}. {expr}{tech}"
    return f"{n}. {expr} = ______{tech}"


def write_sheets_pdf(
    pdf_path: Path,
    doc_title: str,
    sheets: list[dict],
    page_titles: list[str],
    answer_md: str | None,
    show_tech: bool,
) -> None:
    """Two-column day sheets that fill the page; answers appended."""
    font = register_font()
    left = right = 11 * mm
    top = bottom = 9 * mm
    usable_w = A4[0] - left - right
    usable_h = A4[1] - top - bottom

    title_s = ParagraphStyle(
        "st", fontName=font, fontSize=12, leading=15, alignment=TA_CENTER, spaceAfter=2
    )
    meta_s = ParagraphStyle(
        "sm", fontName=font, fontSize=7.5, leading=9.5, alignment=TA_CENTER, spaceAfter=1
    )
    sec_s = ParagraphStyle(
        "ss",
        fontName=font,
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#2c5282"),
        spaceBefore=2,
        spaceAfter=2,
    )
    q_s = ParagraphStyle("sq", fontName=font, fontSize=9, leading=11)
    ans_h = ParagraphStyle("ah", fontName=font, fontSize=10, leading=12, spaceBefore=3, spaceAfter=2)
    ans_b = ParagraphStyle("ab", fontName=font, fontSize=8, leading=10)

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=left,
        rightMargin=right,
        topMargin=top,
        bottomMargin=bottom,
        title=doc_title,
    )
    story: list = []

    for si, sh in enumerate(sheets):
        if si:
            story.append(PageBreak())
        story.append(Paragraph(page_titles[si], title_s))
        story.append(
            Paragraph(
                "每日三招：温习≈60s · 新招≈150s · 挑战≈90s · 不用计算器 · 做完口述 1 题",
                meta_s,
            )
        )
        story.append(
            Paragraph(
                "姓名：________　日期：________　用时：________　对题：____ / 20",
                meta_s,
            )
        )
        story.append(Spacer(1, 2 * mm))

        header_h = 18 * mm
        q_area = usable_h - header_h
        sec_budget = 7 * mm
        rows_h = (q_area - 3 * sec_budget) / 10.0
        row_h = max(11.0, min(rows_h, 18.0))

        n = 1
        for sec_name, key in [
            ("招一 · 温习（6 题）", "warm"),
            ("招二 · 新招（10 题）", "focus"),
            ("招三 · 挑战（4 题）", "challenge"),
        ]:
            story.append(Paragraph(sec_name, sec_s))
            items = sh[key]
            rows = []
            row: list = []
            for it in items:
                row.append(Paragraph(format_q_line(n, it, show_tech), q_s))
                n += 1
                if len(row) == 2:
                    rows.append(row)
                    row = []
            if row:
                row.append(Paragraph("", q_s))
                rows.append(row)
            t = Table(
                rows,
                colWidths=[usable_w / 2, usable_w / 2],
                rowHeights=[row_h] * len(rows),
            )
            t.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 2),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 1),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e0")),
                        ("LINEBELOW", (0, 0), (-1, -2), 0.3, colors.HexColor("#e2e8f0")),
                    ]
                )
            )
            story.append(t)
            story.append(Spacer(1, 1.5 * mm))

    if answer_md:
        story.append(PageBreak())
        story.append(Paragraph("答案（家长用）· 含技巧代号", title_s))
        for line in answer_md.splitlines():
            if line.startswith("# "):
                continue
            if line.startswith("## "):
                story.append(Paragraph(line[3:], ans_h))
            elif line.startswith("### "):
                story.append(Paragraph(line[4:], sec_s))
            elif line.startswith(">"):
                story.append(Paragraph(line.lstrip("> ").strip(), meta_s))
            elif line.strip() == "":
                story.append(Spacer(1, 1))
            else:
                story.append(Paragraph(line.replace("`", "").replace("**", ""), ans_b))

    doc.build(story)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_plans(b: Bank) -> None:
    rng = random.Random(SEED + 1)
    OUT.mkdir(parents=True, exist_ok=True)

    # README
    readme = """# W1 · 心算技巧递进

读懂题后少在心算上翻车：用「三招过关」每日流程，技巧只认人教教材算法 + 2022 课标。

设计规格：`docs/superpowers/specs/2026-09-08-w1-mental-math-technique-plan-design.md`

## 怎么用

1. 先读 [00-技巧速查卡](./00-技巧速查卡.md)（或 PDF）。
2. 做 [Plan0 摸底](./Plan0-摸底/)，勾错因。
3. 按 Plan1 → Plan5 顺序，每天 1 卷（约 5 分钟），过关再进入下一 Plan。
4. 旧心算 200/400/速度巩固：每周最多 1 组维持，不再当主练。
5. Plan5 过关后隔 3 天做 W1 练习卷 03；通过后把时间交给 W2/W2b。

## 过关

- Plan1～4：连续 2 天 ≥ 18/20
- Plan5：混选 ≤2.5 分钟且 ≥18/20，连续 3 天

## 目录

| 文件夹 | 内容 |
|---|---|
| [00-技巧速查卡](./00-技巧速查卡.md) | T1～T10 |
| [Plan0-摸底](./Plan0-摸底/) | 诊断卷 |
| [Plan1-转化百分数](./Plan1-转化百分数/) | 4 天 |
| [Plan2-特殊因数凑整](./Plan2-特殊因数凑整/) | 5 天 |
| [Plan3-除法与百分数除](./Plan3-除法与百分数除/) | 5 天 |
| [Plan4-运算定律简算](./Plan4-运算定律简算/) | 6 天 |
| [Plan5-估验混选](./Plan5-估验混选/) | 7 天 + 6 套正式混选 |
| [题库索引](./题库索引.md) | 题型 ↔ 技巧 |
"""
    write_text(OUT / "README.md", readme)

    # 速查卡
    card = """# 心算技巧速查卡（T1～T10）

> 出处：人教版五上小数乘除与运算定律、六上百分数；《义务教育数学课程标准（2022）》运算能力。  
> 非「一口清」表演速算。

| 代号 | 技巧 | 做法 | 例子 |
|---|---|---|---|
| T1 | 百分数→小数 | 去 `%`，小数点左移两位 | `6%=0.06` |
| T2 | 特殊百分数→分数 | `25%=1/4`，`75%=3/4`，`12.5%=1/8`，`20%=1/5`，`50%=1/2` | `36×25%=9` |
| T3 | 小数乘法定点 | 先按整数乘，再数小数位总和定点 | `4.2×3.5`→`42×35`再点 2 位 |
| T4 | ×0.5/0.25/0.125 | 当作 ÷2 / ÷4 / ÷8 | `7.6×0.25=1.9` |
| T5 | 凑整对 | `0.25×4=1`，`1.25×8=10`，`12.5×8=100`，`0.125×8=1`；三因数用结合律 | `0.25×7.2×4=7.2` |
| T6 | ×1.5 / ×2.5 | ×1 再加一半；或 ×5÷2 | `5.6×1.5=8.4` |
| T7 | 除法齐搬家 | 除数变整数，被除数同扩（商不变） | `2.8÷0.7=28÷7=4` |
| T8 | ÷百分数四步 | 先 T1 → 改写 → T7 → 估验 | `2.8÷6%=2.8÷0.06` |
| T9 | 分配律（及逆） | `a×b+a×c=a(b+c)`；近整拆 `×99=×100−×1` | `3.8×1.01=3.8+0.038` |
| T10 | 先估后算 / 逆验 | 看数量级；乘除互验 | `÷6%` 商应远大于 `÷6` |

**一句话：** 有 `%` 先转化；能凑整先凑整；除法齐搬家；算完估一估。
"""
    write_text(OUT / "00-技巧速查卡.md", card)

    # Plan0
    p0_dir = OUT / "Plan0-摸底"
    used_local: set[str] = set()
    p0_items = []
    for tid, n in [("D1", 3), ("D2", 3), ("D3", 3), ("D4", 3), ("D5", 3), ("D6", 3), ("D7", 2)]:
        p0_items.extend(take(b.by_type[tid], n, rng, used_local))
    rng.shuffle(p0_items)
    # force 20
    p0_items = p0_items[:20]
    sheet0 = {
        "plan": "Plan0",
        "day": 0,
        "warm": p0_items[:6],
        "focus": p0_items[6:16],
        "challenge": p0_items[16:20],
        "all": p0_items,
    }
    # Actually Plan0 is one diagnostic - use flat 20 without claiming 三招 mastery; still use 三招 layout for habit
    md0 = render_sheet_md("Plan0 · 摸底诊断卷（会算还是会选招）", sheet0, show_tech_on_student=False)
    write_text(p0_dir / "诊断卷.md", md0)
    ans0 = render_answers_md("Plan0 答案", [sheet0])
    write_text(p0_dir / "答案.md", ans0)
    err = """# Plan0 错因表（家长勾选）

对每一错题勾一项主因：

| 题号 | 不会转化 | 不会凑整 | 移位漏移 | 当÷整数 | 分配漏乘 | 估错未查 | 纯笔误 | 备注 |
|---|---|---|---|---|---|---|---|---|
""" + "\n".join(
        f"| {i} | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |  |" for i in range(1, 21)
    )
    write_text(p0_dir / "错因表.md", err)
    write_sheets_pdf(
        p0_dir / "诊断卷.pdf",
        "Plan0 摸底",
        [sheet0],
        ["Plan0 · 摸底诊断卷（会算还是会选招）"],
        ans0,
        show_tech=False,
    )

    def gen_plan_days(
        plan_name: str,
        folder: str,
        n_days: int,
        warm_types: list[str],
        focus_types: list[str],
        challenge_types: list[str],
        show_tech: bool = False,
    ) -> list[dict]:
        d = OUT / folder
        d.mkdir(parents=True, exist_ok=True)
        sheets = []
        local: set[str] = set()
        page_titles: list[str] = []
        for day in range(1, n_days + 1):
            warm_pool = []
            for t in warm_types:
                warm_pool.extend(b.by_type[t])
            focus_pool = []
            for t in focus_types:
                focus_pool.extend(b.by_type[t])
            chal_pool = []
            for t in challenge_types:
                chal_pool.extend(b.by_type[t])
            warm = take(warm_pool, 6, rng, local)
            focus = take(focus_pool, 10, rng, local)
            chal = take(chal_pool, 4, rng, local)
            # refill if short
            while len(warm) < 6:
                warm += take(warm_pool, 6 - len(warm), rng, set())
                warm = warm[:6]
            while len(focus) < 10:
                focus += take(focus_pool, 10 - len(focus), rng, set())
                focus = focus[:10]
            while len(chal) < 4:
                chal += take(chal_pool, 4 - len(chal), rng, set())
                chal = chal[:4]
            sh = make_day_sheet(plan_name, day, warm, focus, chal)
            sheets.append(sh)
            title = f"{plan_name} · Day {day:02d}"
            page_titles.append(title)
            md = render_sheet_md(title, sh, show_tech_on_student=show_tech)
            write_text(d / f"Day{day:02d}.md", md)
        ans = render_answers_md(f"{plan_name} 答案", sheets)
        write_text(d / "答案.md", ans)
        write_sheets_pdf(
            d / f"{plan_name}.pdf",
            plan_name,
            sheets,
            page_titles,
            ans,
            show_tech=show_tech,
        )
        readme_p = f"# {plan_name}\n\n每天 1 份 Day 卷；答案见 `答案.md` / PDF 后部。\n"
        write_text(d / "README.md", readme_p)
        return sheets

    # Plan1: warm convert/easy; focus B/C; challenge D/E
    # For day1 warm use P1-A
    gen_plan_days(
        "Plan1 转化与特殊百分数",
        "Plan1-转化百分数",
        4,
        warm_types=["P1-A", "P1-B"],
        focus_types=["P1-B", "P1-C"],
        challenge_types=["P1-D", "P1-E"],
        show_tech=True,
    )
    gen_plan_days(
        "Plan2 特殊因数凑整",
        "Plan2-特殊因数凑整",
        5,
        warm_types=["P1-C", "P1-B"],
        focus_types=["P2-A", "P2-B", "P2-C"],
        challenge_types=["P2-D", "P2-E"],
        show_tech=True,
    )
    gen_plan_days(
        "Plan3 除法与÷百分数",
        "Plan3-除法与百分数除",
        5,
        warm_types=["P2-A", "P1-C"],
        focus_types=["P3-A", "P3-C"],
        challenge_types=["P3-D", "P3-E", "P3-B"],
        show_tech=True,
    )
    gen_plan_days(
        "Plan4 运算定律简算",
        "Plan4-运算定律简算",
        6,
        warm_types=["P2-C", "P3-C"],
        focus_types=["P4-B", "P4-C"],
        challenge_types=["P4-D", "P4-E", "P4-A"],
        show_tech=True,
    )

    # Plan5 days
    p5_sheets = gen_plan_days(
        "Plan5 估验与见题选招",
        "Plan5-估验混选",
        7,
        warm_types=["P3-C", "P4-B", "P2-C"],
        focus_types=["P5-C"],
        challenge_types=["P5-D", "P5-A", "P5-B"],
        show_tech=False,
    )

    # Plan5 formal mixed 6 sets
    p5 = OUT / "Plan5-估验混选"
    formal_sheets = []
    formal_titles = []
    local2: set[str] = set()
    for i in range(1, 7):
        items = take(b.by_type["P5-C"], 16, rng, local2)
        items += take(b.by_type["P5-D"], 2, rng, local2)
        items += take(b.by_type["P5-A"], 2, rng, local2)
        rng.shuffle(items)
        sh = make_day_sheet("Plan5正式", i, items[:6], items[6:16], items[16:20])
        formal_sheets.append(sh)
        title = f"Plan5 正式混选卷 {i}（不标注技巧 · 限时 2.5 分钟）"
        formal_titles.append(title)
        md = render_sheet_md(title, sh, show_tech_on_student=False)
        write_text(p5 / f"正式混选-{i:02d}.md", md)
    fans = render_answers_md("Plan5 正式混选答案", formal_sheets)
    write_text(p5 / "正式混选-答案.md", fans)
    write_sheets_pdf(
        p5 / "正式混选合订.pdf",
        "Plan5 正式混选",
        formal_sheets,
        formal_titles,
        fans,
        show_tech=False,
    )

    # index
    idx = ["# 题库索引", "", "| 题型 ID | 技巧 | 题量 | 主要出现 |", "|---|---|---|---|"]
    for tid in sorted(b.by_type.keys()):
        techs = Counter(x["tech"] for x in b.by_type[tid])
        tech_s = ", ".join(f"{k}×{v}" for k, v in techs.most_common(3))
        idx.append(f"| {tid} | {tech_s} | {len(b.by_type[tid])} | 见各 Plan Day / 答案 |")
    write_text(OUT / "题库索引.md", "\n".join(idx) + "\n")

    # card pdf — real table layout
    write_tech_card_pdf(OUT / "00-技巧速查卡.pdf")

    print("type counts:")
    for k in sorted(b.by_type.keys()):
        print(f"  {k}: {len(b.by_type[k])}")
    print("wrote", OUT)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    used = load_used()
    print("prior used", len(used))
    b = build_bank(used)
    if args.dry_run:
        for k in sorted(b.by_type.keys()):
            print(f"{k}: {len(b.by_type[k])}")
        return
    build_plans(b)


if __name__ == "__main__":
    main()
