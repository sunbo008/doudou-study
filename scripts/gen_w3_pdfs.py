#!/usr/bin/env python3
"""Regenerate W3 practice PDFs with horizontal (stacked) fractions."""
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

ROOT = Path(__file__).resolve().parents[1] / 'practice' / 'W3-小学分数全题型启发式'
FILES = [
    '00-分数意义底层逻辑.md',
    '试题01-认识与意义.md',
    '试题02-约分通分与加减.md',
    '试题03-乘法.md',
    '试题04-除法.md',
    '试题05-总复习.md',
    '学后总结-技巧与避坑.md',
    '答案.md',
    '覆盖清单.md',
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


styles = {
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


def line_to_flowables(text: str, style_name='inline'):
    text = text.replace('`', '')
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
            widths2.append(max(stringWidth(val, 'Heiti', 9.5) + 1, 2))
        else:
            cells2.append(val)
            widths2.append(val.width + 2)
    t = Table([cells2], colWidths=widths2)
    t.hAlign = 'LEFT'  # 避免窄表在页面居中，看起来像「靠右飘」
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
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


def cell_flowables(text: str, bold=False):
    st = 'cell_b' if bold else 'cell'
    return line_to_flowables(text, st)[0]


def md_to_story(md: str):
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
            story.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#555555'), spaceAfter=6))
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
            story.append(Spacer(1, 2 * mm))
            story.append(HRFlowable(width='100%', thickness=0.4, color=colors.HexColor('#bbbbbb'), spaceBefore=2, spaceAfter=4))
            i += 1
            continue
        if line.startswith('>'):
            qs = []
            while i < len(lines) and lines[i].startswith('>'):
                qs.append(lines[i].lstrip('> ').rstrip())
                i += 1
            for f in line_to_flowables(' '.join(qs), 'quote'):
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
                data.append([cell_flowables(c, bold=(ridx == 0)) for c in row])
            ncols = max(len(r) for r in data)
            for r in data:
                while len(r) < ncols:
                    r.append(Paragraph('', styles['cell']))
            usable = 180 * mm
            col_w = [usable / ncols] * ncols
            t = Table(data, colWidths=col_w, repeatRows=1)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EEEEEE')),
                ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#999999')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            story.append(t)
            story.append(Spacer(1, 3 * mm))
            continue
        story.extend(line_to_flowables(line.strip(), 'body'))
        story.append(Spacer(1, 1.2 * mm))
        i += 1
    return story


def build_pdf(md_path: Path, pdf_path: Path):
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=md_path.stem,
        author='doudou-study',
    )
    doc.build(md_to_story(md_path.read_text(encoding='utf-8')))
    print(f'OK {pdf_path.name}')


def main():
    for name in FILES:
        md_path = ROOT / name
        build_pdf(md_path, ROOT / f'{md_path.stem}.pdf')


if __name__ == '__main__':
    main()
