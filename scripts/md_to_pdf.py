#!/usr/bin/env python3
"""Convert PAHS learning markdown to PDF with proper table handling."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from fpdf import FPDF

FONT = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
BOX_CHARS = set("┌┐└┘├┤┬┴┼─│▼▲→←↔═║╔╗╚╝╠╣╦╩╬")


def is_table_sep(line: str) -> bool:
    return bool(re.match(r"^\|[\s\-:|]+\|$", line.strip()))


def parse_table_cells(line: str) -> list[str] | None:
    s = line.strip()
    if not s.startswith("|") or not s.endswith("|"):
        return None
    return [c.strip().strip("`") for c in s.split("|")[1:-1]]


def format_table_row(cells: list[str], header: list[str] | None = None) -> str:
    if header and len(header) == len(cells):
        parts = [f"{h}：{c}" for h, c in zip(header, cells) if c]
        return "；".join(parts)
    if len(cells) == 2:
        return f"• {cells[0]} → {cells[1]}"
    if len(cells) == 3:
        return f"• [{cells[0]}] {cells[1]}（合格：{cells[2]}）"
    return "• " + " | ".join(cells)


def safe(s: str) -> str:
    return "".join(c if c not in BOX_CHARS else " " for c in s)


class HandbookPDF(FPDF):
    def footer(self):
        self.set_y(-12)
        self.set_font("ZH", size=8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, f"PAHS 深度学习教程 详细版 · 第 {self.page_no()} 页", align="C")


def md_to_pdf(md_path: Path, pdf_path: Path) -> None:
    text = md_path.read_text(encoding="utf-8")
    pdf = HandbookPDF(format="A4")
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    pdf.add_font("ZH", "", FONT)
    pdf.add_font("ZH", "B", FONT)
    w = pdf.epw

    in_code = False
    table_header: list[str] | None = None

    def write_para(content: str, *, bold: bool = False, size: float = 10) -> None:
        pdf.set_font("ZH", "B" if bold else "", size)
        pdf.multi_cell(w, 5.2, safe(content))
        pdf.set_font("ZH", size=10)

    for raw in text.splitlines():
        line = raw.rstrip()

        if line.strip().startswith("```"):
            in_code = not in_code
            table_header = None
            continue

        cells = parse_table_cells(line) if not in_code else None
        if cells is not None:
            if is_table_sep(line):
                continue
            if table_header is None:
                table_header = cells
                continue
            write_para(format_table_row(cells, table_header), size=9.5)
            continue
        else:
            table_header = None

        if not line.strip():
            pdf.ln(2)
            continue
        if line.startswith("---"):
            pdf.ln(2)
            continue

        if line.startswith("# "):
            pdf.ln(4)
            write_para(line[2:].strip(), bold=True, size=15)
            continue
        if line.startswith("## "):
            pdf.ln(3)
            write_para(line[3:].strip(), bold=True, size=12)
            continue
        if line.startswith("### "):
            pdf.ln(2)
            write_para(line[4:].strip(), bold=True, size=11)
            continue
        if line.startswith("#### "):
            pdf.ln(1)
            write_para(line[5:].strip(), bold=True, size=10.5)
            continue

        if line.startswith("- ") or line.startswith("* "):
            write_para("• " + line[2:].strip(), size=9.5 if in_code else 10)
            continue

        write_para(line.strip(), size=8 if in_code else 10)

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(pdf_path))


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    md = root / "docs" / "PAHS_深度学习教程_详细版.md"
    outs = [
        root / "docs" / "PAHS_深度学习教程_详细版_Zachary.pdf",
        Path.home() / "Downloads" / "PAHS_深度学习教程_详细版_Zachary.pdf",
    ]
    for out in outs:
        md_to_pdf(md, out)
        print(f"Wrote {out} ({out.stat().st_size // 1024} KB)")
