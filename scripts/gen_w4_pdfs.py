#!/usr/bin/env python3
"""Generate W4 有理数数轴应用 PDFs from markdown."""
from pathlib import Path
import math
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Flowable,
)

pdfmetrics.registerFont(TTFont('Heiti', '/System/Library/Fonts/STHeiti Light.ttc', subfontIndex=0))
try:
    pdfmetrics.registerFont(TTFont('HeitiBold', '/System/Library/Fonts/STHeiti Medium.ttc', subfontIndex=1))
    BOLD = 'HeitiBold'
except Exception:
    BOLD = 'Heiti'
pdfmetrics.registerFont(TTFont('Mono', '/System/Library/Fonts/Menlo.ttc', subfontIndex=0))

# Wide glyphs break column alignment in number-line ASCII art → normalize to 1-cell ASCII.
_ASCII_ART_MAP = str.maketrans({
    '─': '-', '━': '-', '—': '-', '–': '-',
    '│': '|', '┃': '|',
    '●': '*', '○': 'o', '◆': '*',
    '←': '<', '→': '>', '↔': '-',
})


class MonoArt(Flowable):
    """Monospace ASCII block so number-line columns stay aligned."""

    def __init__(self, lines, font_size=8.5, left_indent=6):
        super().__init__()
        self.lines = [(ln if ln.strip() else ' ') for ln in lines]
        self.font_size = font_size
        self.left_indent = left_indent
        self.leading = font_size + 2.5
        cw = stringWidth('M', 'Mono', font_size)
        max_cols = max((len(ln) for ln in self.lines), default=1)
        self.width = left_indent + cw * max_cols
        self.height = self.leading * len(self.lines) + 4

    def wrap(self, aw, ah):
        return min(self.width, aw), self.height

    def draw(self):
        c = self.canv
        c.setFont('Mono', self.font_size)
        c.setFillColor(colors.HexColor('#222222'))
        y = self.height - self.leading
        for ln in self.lines:
            c.drawString(self.left_indent, y, ln)
            y -= self.leading


def normalize_ascii_art(line: str) -> str:
    s = line.translate(_ASCII_ART_MAP)
    s = s.replace('⇒', '>').replace('⇐', '<')
    return s


def _parse_num(s: str) -> float:
    s = s.strip().replace('−', '-').replace('—', '-')
    return float(s)


def _fmt_num(v: float) -> str:
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f'{v:g}'


class NumberLine(Flowable):
    """Vector number line with fixed unit scale (same 1-unit length across figures)."""

    # points per number-line unit — keep identical across all diagrams
    UNIT = 11.5

    def __init__(self, points, spans=None, dirs=None, cuts=None, bands=None, pad=1.0):
        super().__init__()
        self.points = list(points)
        self.spans = list(spans or [])   # (v0, v1, mid, bottom)
        self.dirs = list(dirs or [])     # (v_from, v_to, mid, side)
        self.cuts = list(cuts or [])
        self.bands = list(bands or [])
        self.pad = pad
        vals = [v for _, v in self.points] + list(self.cuts)
        for a, b, *_ in self.spans:
            vals.extend([a, b])
        for a, b, *_ in self.dirs:
            vals.extend([a, b])
        if not vals:
            vals = [0, 1]
        self.vmin = min(vals) - self.pad
        self.vmax = max(vals) + self.pad
        self.margin_x = 10
        self.unit = float(self.UNIT)
        span_w = (self.vmax - self.vmin) * self.unit
        self.width = self.margin_x * 2 + span_w + 8  # +8 for axis arrowhead
        self.top_h = 16
        if self.spans:
            self.ann_h = 26 + 22 * len(self.spans)
        elif self.dirs:
            self.ann_h = 26 + 24 * len(self.dirs)
        elif self.bands:
            self.ann_h = 8
        else:
            self.ann_h = 4
        self.axis_y_from_bottom = 8 + self.ann_h
        self.height = self.axis_y_from_bottom + self.top_h + 4

    def wrap(self, aw, ah):
        # keep fixed scale; only shrink if figure would overflow page width
        if self.width > aw:
            self.unit = (aw - self.margin_x * 2 - 8) / max(self.vmax - self.vmin, 1e-6)
            self.width = aw
        return self.width, self.height

    def _x(self, v: float) -> float:
        return self.margin_x + (v - self.vmin) * self.unit

    def _arrowhead(self, c, x, y, direction=1, size=5):
        # direction: +1 right, -1 left
        c.setFillColor(colors.black)
        if direction >= 0:
            path = c.beginPath()
            path.moveTo(x, y)
            path.lineTo(x - size, y + size * 0.45)
            path.lineTo(x - size, y - size * 0.45)
            path.close()
            c.drawPath(path, fill=1, stroke=0)
        else:
            path = c.beginPath()
            path.moveTo(x, y)
            path.lineTo(x + size, y + size * 0.45)
            path.lineTo(x + size, y - size * 0.45)
            path.close()
            c.drawPath(path, fill=1, stroke=0)

    def _draw_bracket(self, c, x0, x1, y, mid_text, bot_text, directed=None):
        """directed: None=both ends (distance), +1=rightward, -1=leftward."""
        lo, hi = (x0, x1) if x0 <= x1 else (x1, x0)
        c.setStrokeColor(colors.HexColor('#333333'))
        c.setLineWidth(1.0)
        c.line(lo, y, hi, y)
        if directed is None:
            c.line(lo, y - 3.5, lo, y + 3.5)
            c.line(hi, y - 3.5, hi, y + 3.5)
            self._arrowhead(c, lo, y, -1, 4)
            self._arrowhead(c, hi, y, +1, 4)
        elif directed > 0:
            # start bar → arrowhead (signed, rightward)
            c.line(lo, y - 3.5, lo, y + 3.5)
            self._arrowhead(c, hi, y, +1, 5.5)
        else:
            c.line(hi, y - 3.5, hi, y + 3.5)
            self._arrowhead(c, lo, y, -1, 5.5)
        mx = (lo + hi) / 2
        c.setFillColor(colors.black)
        c.setFont('Heiti', 8)
        if mid_text:
            tw = stringWidth(mid_text, 'Heiti', 8)
            c.setFillColor(colors.white)
            c.rect(mx - tw / 2 - 2, y - 1, tw + 4, 9, fill=1, stroke=0)
            c.setFillColor(colors.black)
            c.drawCentredString(mx, y + 1, mid_text)
        if bot_text:
            c.setFont('Heiti', 8)
            c.drawCentredString(mx, y - 12, bot_text)

    def draw(self):
        c = self.canv
        y = self.axis_y_from_bottom
        x_left = self._x(self.vmin)
        x_right = self._x(self.vmax)

        # axis
        c.setStrokeColor(colors.black)
        c.setLineWidth(1.2)
        c.line(x_left, y, x_right - 2, y)
        self._arrowhead(c, x_right, y, +1, 6)

        # integer unit ticks (makes equal spacing visually checkable)
        tick0 = math.ceil(self.vmin + 1e-9)
        tick1 = math.floor(self.vmax - 1e-9)
        c.setStrokeColor(colors.HexColor('#666666'))
        c.setLineWidth(0.7)
        for tv in range(tick0, tick1 + 1):
            tx = self._x(tv)
            c.line(tx, y - 3.5, tx, y + 3.5)

        # cuts (partition ticks taller)
        for cv in self.cuts:
            cx = self._x(cv)
            c.setStrokeColor(colors.HexColor('#555555'))
            c.setLineWidth(1.0)
            c.line(cx, y - 8, cx, y + 10)

        # band labels above
        if self.bands and self.cuts:
            ordered = sorted(self.cuts)
            edges = [self.vmin] + ordered + [self.vmax]
            for i, lab in enumerate(self.bands):
                if i + 1 >= len(edges):
                    break
                mx = (self._x(edges[i]) + self._x(edges[i + 1])) / 2
                c.setFont(BOLD, 8)
                c.setFillColor(colors.HexColor('#333333'))
                c.drawCentredString(mx, y + 14, lab)

        # points
        for label, val in self.points:
            x = self._x(val)
            c.setFillColor(colors.black)
            c.circle(x, y, 3.2, fill=1, stroke=0)
            c.setFont(BOLD, 9)
            c.drawCentredString(x, y + 8, label)
            c.setFont('Heiti', 8)
            c.drawCentredString(x, y - 12, _fmt_num(val))

        # undirected spans (distance)
        for i, (v0, v1, mid, bot) in enumerate(self.spans):
            yy = y - 28 - i * 22
            self._draw_bracket(c, self._x(v0), self._x(v1), yy, mid, bot, directed=None)

        # directed segments (signed): mid = magnitude, bottom = equation
        for i, (vf, vt, mid, side) in enumerate(self.dirs):
            yy = y - 28 - i * 24
            d = 1 if vt >= vf else -1
            self._draw_bracket(c, self._x(vf), self._x(vt), yy, mid, side, directed=d)


def parse_numberline(lines):
    """Parse ```numberline DSL into a NumberLine flowable."""
    points = []
    spans = []
    dirs = []
    cuts = []
    bands = []
    name_to_val = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('points '):
            for tok in line[7:].split():
                if '=' not in tok:
                    continue
                name, vs = tok.split('=', 1)
                v = _parse_num(vs)
                points.append((name, v))
                name_to_val[name] = v
        elif line.startswith('span '):
            # span A P 2 PA   OR  span 0 2 2 PA
            parts = line.split()
            a, b, mid = parts[1], parts[2], parts[3]
            bot = parts[4] if len(parts) > 4 else ''
            v0 = name_to_val.get(a, _parse_num(a) if re.match(r'^-?\d', a.replace('−', '-')) else None)
            v1 = name_to_val.get(b, _parse_num(b) if re.match(r'^-?\d', b.replace('−', '-')) else None)
            if v0 is None:
                v0 = _parse_num(a)
            if v1 is None:
                v1 = _parse_num(b)
            spans.append((v0, v1, mid, bot))
        elif line.startswith('dir '):
            # dir A M +3 A->M=+3
            parts = line.split(None, 4)
            a, b, mid = parts[1], parts[2], parts[3]
            side = parts[4] if len(parts) > 4 else ''
            v0 = name_to_val[a]
            v1 = name_to_val[b]
            dirs.append((v0, v1, mid, side))
        elif line.startswith('cut '):
            for tok in line[4:].split():
                cuts.append(name_to_val.get(tok, _parse_num(tok)))
        elif line.startswith('bands '):
            bands = line[6:].split()
    return NumberLine(points, spans=spans, dirs=dirs, cuts=cuts, bands=bands)

ROOT = Path(__file__).resolve().parents[1] / 'practice' / 'W4-有理数数轴应用'
FILES = [
    '技巧与避坑.md',
    'Day01.md',
    'Day02.md',
    'Day03.md',
    '答案.md',
]
C_ROOT = ROOT / 'C专项-距离比'
C_FILES = [
    '00-几何与±法则.md',
    'Day01.md',
    'Day02.md',
    '答案.md',
]

FRAC_RE = re.compile(
    r'(?:'
    r'(\d+)\s+(\d+)\s*/\s*(\d+)'
    r'|'
    r'([□\d]+)\s*/\s*([□\d]+[ⁿn]?)'
    r')'
)


class HFraction(Flowable):
    def __init__(self, numer, denom, font_name='Heiti', font_size=9, whole=None):
        super().__init__()
        self.numer = str(numer)
        self.denom = str(denom)
        self.whole = None if whole is None else str(whole)
        self.font_name = font_name
        self.font_size = font_size
        fs = font_size - 0.5
        self._fs = fs
        nw = stringWidth(self.numer, font_name, fs)
        dw = stringWidth(self.denom, font_name, fs)
        self.frac_w = max(nw, dw, 6) + 3
        self.whole_w = stringWidth(self.whole + ' ', font_name, font_size) if self.whole else 0
        self.width = self.whole_w + self.frac_w
        self.height = fs * 2.4

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        c = self.canv
        fs = self._fs
        y0 = 0.5
        x0 = 0
        if self.whole:
            c.setFont(self.font_name, self.font_size)
            c.drawString(0, fs * 0.55, self.whole)
            x0 = self.whole_w
        c.setFont(self.font_name, fs)
        c.drawCentredString(x0 + self.frac_w / 2, y0 + fs + 2.2, self.numer)
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.7)
        pad = 0.5
        c.line(x0 + pad, y0 + fs + 0.8, x0 + self.frac_w - pad, y0 + fs + 0.8)
        c.drawCentredString(x0 + self.frac_w / 2, y0, self.denom)


def inline_xml(text: str) -> str:
    s = escape(text)
    s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
    s = re.sub(r'`([^`]+)`', r'\1', s)
    s = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', s)
    return s


def make_styles(compact: bool):
    if compact:
        return {
            'h1': ParagraphStyle('h1', fontName=BOLD, fontSize=13, leading=16, alignment=TA_CENTER, spaceAfter=2, spaceBefore=0),
            'h2': ParagraphStyle('h2', fontName=BOLD, fontSize=10, leading=13, spaceBefore=4, spaceAfter=1),
            'h3': ParagraphStyle('h3', fontName=BOLD, fontSize=9, leading=12, spaceBefore=3, spaceAfter=1),
            'body': ParagraphStyle('body', fontName='Heiti', fontSize=8.5, leading=12, spaceAfter=0),
            'quote': ParagraphStyle('quote', fontName='Heiti', fontSize=8, leading=11, leftIndent=6, textColor=colors.HexColor('#333333'), spaceAfter=1),
            'cell': ParagraphStyle('cell', fontName='Heiti', fontSize=7.5, leading=10),
            'cell_b': ParagraphStyle('cell_b', fontName=BOLD, fontSize=7.5, leading=10),
            'inline': ParagraphStyle('inline', fontName='Heiti', fontSize=8.5, leading=12),
        }
    return {
        'h1': ParagraphStyle('h1', fontName=BOLD, fontSize=16, leading=22, alignment=TA_CENTER, spaceAfter=8, spaceBefore=4),
        'h2': ParagraphStyle('h2', fontName=BOLD, fontSize=12, leading=17, spaceBefore=10, spaceAfter=4),
        'h3': ParagraphStyle('h3', fontName=BOLD, fontSize=10.5, leading=15, spaceBefore=8, spaceAfter=3),
        'body': ParagraphStyle('body', fontName='Heiti', fontSize=9.5, leading=16, spaceAfter=2),
        'quote': ParagraphStyle('quote', fontName='Heiti', fontSize=9, leading=14, leftIndent=8, textColor=colors.HexColor('#333333'), spaceAfter=4),
        'cell': ParagraphStyle('cell', fontName='Heiti', fontSize=8, leading=12),
        'cell_b': ParagraphStyle('cell_b', fontName=BOLD, fontSize=8, leading=12),
        'inline': ParagraphStyle('inline', fontName='Heiti', fontSize=9.5, leading=16),
    }


def make_frac(m: re.Match) -> HFraction:
    if m.group(1) is not None:
        return HFraction(m.group(2), m.group(3), whole=m.group(1))
    return HFraction(m.group(4), m.group(5))


def line_to_flowables(text: str, styles, style_name='inline', compact=False):
    text = text.replace('`', '')
    fs = 8.5 if compact else 9.5
    parts = []
    pos = 0
    for m in FRAC_RE.finditer(text):
        if m.start() > pos:
            parts.append(('t', text[pos:m.start()]))
        parts.append(('f', make_frac(m)))
        pos = m.end()
    if pos < len(text):
        parts.append(('t', text[pos:]))
    if not parts:
        return [Paragraph('', styles[style_name])]
    if all(k == 't' for k, _ in parts):
        return [Paragraph(inline_xml(''.join(t for _, t in parts)), styles[style_name])]

    cells2, widths2 = [], []
    for kind, val in parts:
        if kind == 't':
            if not val:
                continue
            cells2.append(Paragraph(inline_xml(val), styles[style_name]))
            widths2.append(max(stringWidth(val, 'Heiti', fs) + 1, 2))
        else:
            cells2.append(val)
            widths2.append(val.width + 2)
    t = Table([cells2], colWidths=widths2)
    t.hAlign = 'LEFT'
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0 if compact else 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0 if compact else 1),
    ]))
    return [t]


def parse_table(lines):
    rows = []
    for line in lines:
        if re.match(r'^[\|\s:\-]+$', line):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        rows.append(cells)
    return rows


def cell_flowables(text: str, styles, bold=False, compact=False):
    st = 'cell_b' if bold else 'cell'
    return line_to_flowables(text, styles, st, compact=compact)[0]


def md_to_story(md: str, compact: bool = False):
    styles = make_styles(compact)
    body_gap = 0.4 * mm if compact else 1.2 * mm
    hr_after_title = 2 if compact else 6
    table_pad = 1 if compact else 3
    table_gap = 1.5 * mm if compact else 3 * mm
    rule_gap = 0.8 * mm if compact else 2 * mm
    usable = 186 * mm if compact else 180 * mm

    story = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith('# '):
            story.append(Paragraph(inline_xml(line[2:].strip()), styles['h1']))
            story.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#555555'), spaceAfter=hr_after_title))
            i += 1
            continue
        if line.startswith('## '):
            story.append(Paragraph(inline_xml(line[3:].strip()), styles['h2']))
            i += 1
            continue
        if line.startswith('### '):
            story.append(Paragraph(inline_xml(line[4:].strip()), styles['h3']))
            i += 1
            continue
        if line.strip() == '---':
            story.append(Spacer(1, rule_gap))
            story.append(HRFlowable(width='100%', thickness=0.4, color=colors.HexColor('#bbbbbb'), spaceBefore=1, spaceAfter=2 if compact else 4))
            i += 1
            continue
        if line.strip().startswith('```'):
            fence = line.strip()[3:].strip().lower()
            i += 1
            block = []
            while i < len(lines) and not lines[i].strip().startswith('```'):
                block.append(lines[i].rstrip('\n'))
                i += 1
            if i < len(lines) and lines[i].strip().startswith('```'):
                i += 1
            if fence.startswith('numberline'):
                story.append(parse_numberline(block))
            else:
                art = [normalize_ascii_art(x) for x in block]
                fs = 7.5 if compact else 8.5
                story.append(MonoArt(art, font_size=fs, left_indent=4 if compact else 8))
            story.append(Spacer(1, body_gap))
            continue
        if line.startswith('>'):
            qs = []
            while i < len(lines) and lines[i].startswith('>'):
                qs.append(lines[i].lstrip('> ').rstrip())
                i += 1
            for f in line_to_flowables(' '.join(qs), styles, 'quote', compact=compact):
                story.append(f)
            continue
        if line.strip().startswith('|') and '|' in line.strip()[1:]:
            tbl_lines = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                tbl_lines.append(lines[i])
                i += 1
            rows = parse_table(tbl_lines)
            if not rows:
                continue
            data = []
            for ridx, row in enumerate(rows):
                data.append([cell_flowables(c, styles, bold=(ridx == 0), compact=compact) for c in row])
            ncols = max(len(r) for r in data)
            for r in data:
                while len(r) < ncols:
                    r.append(Paragraph('', styles['cell']))
            col_w = [usable / ncols] * ncols
            t = Table(data, colWidths=col_w, repeatRows=1)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EEEEEE')),
                ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#999999')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), table_pad),
                ('RIGHTPADDING', (0, 0), (-1, -1), table_pad),
                ('TOPPADDING', (0, 0), (-1, -1), table_pad),
                ('BOTTOMPADDING', (0, 0), (-1, -1), table_pad),
            ]))
            story.append(t)
            story.append(Spacer(1, table_gap))
            continue
        if line.strip().startswith('- ['):
            story.extend(line_to_flowables(line.strip(), styles, 'body', compact=compact))
            story.append(Spacer(1, body_gap))
            i += 1
            continue
        story.extend(line_to_flowables(line.strip(), styles, 'body', compact=compact))
        story.append(Spacer(1, body_gap))
        i += 1
    return story


def build_pdf(md_path: Path, pdf_path: Path, compact: bool = False):
    margin = 10 * mm if compact else 14 * mm
    vmargin = 8 * mm if compact else 12 * mm
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=vmargin,
        bottomMargin=vmargin,
        title=md_path.stem,
        author='doudou-study',
    )
    doc.build(md_to_story(md_path.read_text(encoding='utf-8'), compact=compact))
    print(f'OK {pdf_path.name}')


def main():
    for name in FILES:
        md_path = ROOT / name
        if not md_path.exists():
            raise SystemExit(f'missing {md_path}')
        compact = name.startswith('Day')
        build_pdf(md_path, ROOT / f'{md_path.stem}.pdf', compact=compact)

    for name in C_FILES:
        md_path = C_ROOT / name
        if not md_path.exists():
            raise SystemExit(f'missing {md_path}')
        compact = name.startswith('Day')
        build_pdf(md_path, C_ROOT / f'{md_path.stem}.pdf', compact=compact)


if __name__ == '__main__':
    main()
