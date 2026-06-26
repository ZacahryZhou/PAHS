#!/usr/bin/env python3
"""Markdown -> PDF via Pillow image rendering (works in Preview + Google Drive)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
# A4 @ 150 DPI
PAGE_W, PAGE_H = 1240, 1754
MARGIN_L, MARGIN_R, MARGIN_T, MARGIN_B = 72, 72, 72, 88
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R

BOX_CHARS = set("┌┐└┘├┤┬┴┼─│▼▲═║╔╗╚╝╠╣╦╩╬")
REPLACEMENTS = {"→": "->", "←": "<-", "↔": "<->", "▼": "v", "▲": "^"}


def clean(text: str) -> str:
    out: list[str] = []
    for ch in text:
        if ch in BOX_CHARS:
            out.append(" ")
        elif ch in REPLACEMENTS:
            out.append(REPLACEMENTS[ch])
        else:
            out.append(ch)
    return "".join(out)


def is_table_sep(line: str) -> bool:
    return bool(re.match(r"^\|[\s\-:|]+\|$", line.strip()))


def parse_table_cells(line: str) -> list[str] | None:
    s = line.strip()
    if not s.startswith("|") or not s.endswith("|"):
        return None
    return [c.strip().strip("`") for c in s.split("|")[1:-1]]


class PageWriter:
    def __init__(self, footer: str) -> None:
        self.footer = footer
        self.pages: list[Image.Image] = []
        self._new_page()
        self.fonts = {
            "h1": ImageFont.truetype(FONT_PATH, 28),
            "h2": ImageFont.truetype(FONT_PATH, 22),
            "h3": ImageFont.truetype(FONT_PATH, 18),
            "h4": ImageFont.truetype(FONT_PATH, 16),
            "body": ImageFont.truetype(FONT_PATH, 15),
            "small": ImageFont.truetype(FONT_PATH, 13),
            "code": ImageFont.truetype(FONT_PATH, 12),
            "footer": ImageFont.truetype(FONT_PATH, 11),
        }

    def _new_page(self) -> None:
        self.img = Image.new("RGB", (PAGE_W, PAGE_H), "white")
        self.draw = ImageDraw.Draw(self.img)
        self.y = MARGIN_T
        self.page_no = len(self.pages) + 1

    def _line_height(self, font: ImageFont.FreeTypeFont, spacing: float = 1.45) -> int:
        bbox = font.getbbox("测试Ag")
        return int((bbox[3] - bbox[1]) * spacing)

    def _wrap(self, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
        text = clean(text)
        if not text:
            return [""]
        lines: list[str] = []
        for para in text.split("\n"):
            if not para:
                lines.append("")
                continue
            current = ""
            for ch in para:
                trial = current + ch
                w = self.draw.textlength(trial, font=font)
                if w <= max_w:
                    current = trial
                else:
                    if current:
                        lines.append(current)
                    current = ch
            if current:
                lines.append(current)
        return lines or [""]

    def _ensure_space(self, need: int) -> None:
        if self.y + need > PAGE_H - MARGIN_B:
            self._finish_page()
            self._new_page()

    def _finish_page(self) -> None:
        ft = self.fonts["footer"]
        label = f"{self.footer}  |  第 {self.page_no} 页"
        self.draw.text((PAGE_W / 2, PAGE_H - 52), label, fill="#666666", font=ft, anchor="mm")
        self.pages.append(self.img.copy())

    def write_block(self, text: str, *, style: str = "body", gap: int = 6) -> None:
        font = self.fonts[style]
        lh = self._line_height(font)
        for line in self._wrap(text, font, CONTENT_W):
            self._ensure_space(lh + gap)
            self.draw.text((MARGIN_L, self.y), line, fill="black", font=font)
            self.y += lh
        self.y += gap

    def write_lines(self, lines: list[str], *, style: str = "body", gap: int = 4) -> None:
        for line in lines:
            self.write_block(line, style=style, gap=gap)

    def spacer(self, h: int = 12) -> None:
        self._ensure_space(h)
        self.y += h

    def save(self, path: Path) -> None:
        if self.y > MARGIN_T:
            self._finish_page()
        elif not self.pages:
            self._finish_page()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.pages[0].save(
            path,
            "PDF",
            resolution=150,
            save_all=True,
            append_images=self.pages[1:],
        )


def md_to_pdf(md_path: Path, pdf_path: Path, *, footer: str) -> None:
    lines = md_path.read_text(encoding="utf-8").splitlines()
    w = PageWriter(footer=footer)

    in_code = False
    table_header: list[str] | None = None
    table_rows: list[list[str]] = []
    code_buf: list[str] = []

    def flush_code() -> None:
        nonlocal code_buf
        if not code_buf:
            return
        w.spacer(6)
        w.write_block("\n".join(code_buf), style="code", gap=3)
        w.spacer(8)
        code_buf = []

    def flush_table() -> None:
        nonlocal table_header, table_rows
        if not table_rows:
            table_header = None
            return
        header = table_header or table_rows[0]
        data = table_rows[1:] if table_header else table_rows[1:]
        if not table_header:
            header = table_rows[0]
            data = table_rows[1:]
        w.spacer(6)
        ncol = len(header)
        for row in data:
            if ncol >= 4:
                w.write_block(f"【{row[0]}】" if row else "", style="h4", gap=4)
                for h, cell in zip(header, row):
                    w.write_block(f"  {h}：{cell}", style="small", gap=3)
                w.spacer(8)
            elif ncol == 3:
                w.write_block(f"  [{row[0]}] {row[1]}  (合格：{row[2]})", style="small")
            elif ncol == 2:
                w.write_block(f"  {row[0]}  ->  {row[1]}", style="small")
            else:
                w.write_block("  |  ".join(row), style="small")
        w.spacer(8)
        table_header = None
        table_rows = []

    for raw in lines:
        line = raw.rstrip()

        if line.strip().startswith("```"):
            if in_code:
                flush_code()
                in_code = False
            else:
                flush_table()
                in_code = True
            continue
        if in_code:
            code_buf.append(line)
            continue

        cells = parse_table_cells(line)
        if cells is not None:
            if is_table_sep(line):
                continue
            if table_header is None:
                table_header = cells
                table_rows = []
            else:
                table_rows.append(cells)
            continue

        flush_table()

        if not line.strip():
            w.spacer(10)
            continue
        if line.strip() == "---":
            w.spacer(16)
            continue
        if line.startswith("# "):
            w.spacer(20)
            w.write_block(line[2:].strip(), style="h1", gap=10)
            continue
        if line.startswith("## "):
            w.spacer(14)
            w.write_block(line[3:].strip(), style="h2", gap=8)
            continue
        if line.startswith("### "):
            w.spacer(10)
            w.write_block(line[4:].strip(), style="h3", gap=6)
            continue
        if line.startswith("#### "):
            w.spacer(8)
            w.write_block(line[5:].strip(), style="h4", gap=5)
            continue
        if re.match(r"^[-*] ", line):
            w.write_block("  *  " + line[2:].strip(), style="body", gap=4)
            continue
        if re.match(r"^\d+\. ", line):
            w.write_block("  " + line.strip(), style="body", gap=4)
            continue
        w.write_block(line.strip(), style="body", gap=5)

    flush_code()
    flush_table()
    w.save(pdf_path)


def restore_md_sources(root: Path) -> None:
    merged = root / "docs" / "_merged_for_pdf.md"
    if not merged.exists():
        return
    text = merged.read_text(encoding="utf-8")
    marker = "\n---\n\n# 下卷 · 深度学习教程（代码走读详细版）\n\n"
    if marker not in text:
        return
    part1, part2 = text.split(marker, 1)
    (root / "docs" / "PAHS_学习全集_Zachary_Zhou.md").write_text(part1.strip() + "\n", encoding="utf-8")
    detail = "# PAHS 深度学习教程（详细版）\n\n" + part2.strip() + "\n"
    (root / "docs" / "PAHS_深度学习教程_详细版.md").write_text(detail, encoding="utf-8")


def build_merged_md(root: Path) -> Path:
    full = root / "docs" / "PAHS_学习全集_Zachary_Zhou.md"
    detail = root / "docs" / "PAHS_深度学习教程_详细版.md"
    merged_path = root / "docs" / "_merged_for_pdf.md"
    if full.exists() and detail.exists():
        merged = (
            full.read_text(encoding="utf-8").rstrip()
            + "\n\n---\n\n# 下卷 · 深度学习教程（代码走读详细版）\n\n"
            + detail.read_text(encoding="utf-8").split("\n", 1)[1]
        )
        merged_path.write_text(merged, encoding="utf-8")
    return merged_path


def validate_pdf(path: Path, min_kb: int = 200) -> None:
    size = path.stat().st_size
    if size < min_kb * 1024:
        raise RuntimeError(f"{path.name} too small ({size} bytes)")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    restore_md_sources(root)
    merged = build_merged_md(root)

    jobs: list[tuple[Path, str, str, int]] = [
        (merged, "PAHS_完整学习包_Zachary_Zhou.pdf", "PAHS 完整学习包", 400),
        (
            root / "docs" / "PAHS_学习全集_Zachary_Zhou.md",
            "PAHS_学习全集_Zachary_Zhou.pdf",
            "PAHS 学习全集",
            250,
        ),
        (
            root / "docs" / "PAHS_深度学习教程_详细版.md",
            "PAHS_深度学习教程_详细版_Zachary.pdf",
            "PAHS 深度学习教程",
            350,
        ),
    ]

    for md_path, pdf_name, footer, min_kb in jobs:
        if not md_path.exists():
            print(f"SKIP {md_path}", file=sys.stderr)
            continue
        for out_dir in (root / "docs", Path.home() / "Downloads"):
            pdf_path = out_dir / pdf_name
            try:
                md_to_pdf(md_path, pdf_path, footer=footer)
                validate_pdf(pdf_path, min_kb=min_kb)
                print(f"OK  {pdf_path}  ({pdf_path.stat().st_size // 1024} KB)")
            except OSError as e:
                print(f"WARN {pdf_path}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
