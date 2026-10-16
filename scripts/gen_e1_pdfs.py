#!/usr/bin/env python3
"""Generate E1 野史英语 PDFs from markdown (小朋友版 / 正史卡等)."""
from pathlib import Path
import re
import sys
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable,
)

ROOT = Path(__file__).resolve().parents[1]
E1 = ROOT / 'practice' / 'E1-野史英语'

pdfmetrics.registerFont(TTFont('Heiti', '/System/Library/Fonts/STHeiti Light.ttc', subfontIndex=0))
try:
    pdfmetrics.registerFont(TTFont('HeitiBold', '/System/Library/Fonts/STHeiti Medium.ttc', subfontIndex=1))
    BOLD = 'HeitiBold'
except Exception:
    BOLD = 'Heiti'


def inline_xml(text: str) -> str:
    s = escape(text)
    s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
    s = re.sub(r'\*(.+?)\*', r'<i>\1</i>', s)
    s = re.sub(r'`([^`]+)`', r'\1', s)
    s = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', s)
    return s


styles = {
    'h1': ParagraphStyle('h1', fontName=BOLD, fontSize=16, leading=22, alignment=TA_CENTER, spaceAfter=8, spaceBefore=4),
    'h2': ParagraphStyle('h2', fontName=BOLD, fontSize=12, leading=17, spaceBefore=10, spaceAfter=4),
    'h3': ParagraphStyle('h3', fontName=BOLD, fontSize=10.5, leading=15, spaceBefore=8, spaceAfter=3),
    'body': ParagraphStyle('body', fontName='Heiti', fontSize=9.5, leading=16, spaceAfter=2),
    'quote': ParagraphStyle('quote', fontName='Heiti', fontSize=9, leading=14, leftIndent=10, rightIndent=6,
                            textColor=colors.HexColor('#222222'), spaceAfter=5, spaceBefore=2),
    'cell': ParagraphStyle('cell', fontName='Heiti', fontSize=8.5, leading=13),
    'cell_b': ParagraphStyle('cell_b', fontName=BOLD, fontSize=8.5, leading=13),
}


def parse_table(lines):
    rows = []
    for line in lines:
        if re.match(r'^[\|\s:\-]+$', line):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        rows.append(cells)
    return rows


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
            while i < len(lines) and (lines[i].startswith('>') or lines[i].strip() == ''):
                if lines[i].startswith('>'):
                    txt = lines[i].lstrip('> ').rstrip()
                    if txt:
                        story.append(Paragraph(inline_xml(txt), styles['quote']))
                i += 1
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
                data.append([Paragraph(inline_xml(c), styles['cell_b' if ridx == 0 else 'cell']) for c in row])
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
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(t)
            story.append(Spacer(1, 3 * mm))
            continue
        story.append(Paragraph(inline_xml(line.strip()), styles['body']))
        story.append(Spacer(1, 1.2 * mm))
        i += 1
    return story


def build_pdf(md_path: Path, pdf_path: Path | None = None):
    pdf_path = pdf_path or md_path.with_suffix('.pdf')
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
    print(f'OK {pdf_path}')
    return pdf_path


def main():
    targets = sys.argv[1:]
    if not targets:
        targets = [
            str(E1 / 'Unit02-夏商周/E05-商鞅变法/E05-商鞅变法-小朋友版.md'),
        ]
    for t in targets:
        p = Path(t)
        if not p.is_absolute():
            p = ROOT / p
        build_pdf(p)


if __name__ == '__main__':
    main()
