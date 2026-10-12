#!/usr/bin/env python3
"""Generate W4 有理数数轴应用 PDFs from markdown."""
from pathlib import Path
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

ROOT = Path(__file__).resolve().parents[1] / 'practice' / 'W4-有理数数轴应用'
FILES = [
    '技巧与避坑.md',
    'Day01.md',
    'Day02.md',
    'Day03.md',
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


if __name__ == '__main__':
    main()
