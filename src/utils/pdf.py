"""Markdown-to-PDF conversion using fpdf2 (pure Python, no system deps)."""

from __future__ import annotations

import re
import unicodedata


def markdown_to_pdf(markdown_content: str) -> bytes:
    """Convert a Markdown string to PDF bytes.

    Parses Markdown line-by-line and renders headings, paragraphs, lists,
    code blocks, bold/italic, and horizontal rules. Mermaid blocks become
    labelled code blocks.
    """
    from fpdf import FPDF

    md = _preprocess_mermaid(markdown_content)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Use built-in fonts — need to sanitize unicode chars
    pdf.set_font("Helvetica", size=11)

    in_code_block = False
    code_lines: list[str] = []

    for line in md.split("\n"):
        # Code block fences
        if line.strip().startswith("```"):
            if in_code_block:
                _render_code_block(pdf, code_lines)
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        stripped = line.strip()

        # Empty line
        if not stripped:
            pdf.ln(3)
            continue

        # Horizontal rule
        if re.match(r"^-{3,}$|^\*{3,}$|^_{3,}$", stripped):
            y = pdf.get_y()
            pdf.set_draw_color(180, 180, 180)
            pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
            pdf.ln(5)
            continue

        # Headings
        heading_match = re.match(r"^(#{1,6})\s+(.*)", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2)
            _render_heading(pdf, text, level)
            continue

        # Unordered list items
        list_match = re.match(r"^[\-\*\+]\s+(.*)", stripped)
        if list_match:
            _render_list_item(pdf, list_match.group(1))
            continue

        # Ordered list items
        olist_match = re.match(r"^\d+\.\s+(.*)", stripped)
        if olist_match:
            _render_list_item(pdf, olist_match.group(1), ordered=True)
            continue

        # Table rows (pipe-separated)
        if stripped.startswith("|") and stripped.endswith("|"):
            # Skip separator rows like |---|---|
            if re.match(r"^\|[\s\-:|]+\|$", stripped):
                continue
            _render_table_row(pdf, stripped)
            continue

        # Regular paragraph
        _render_paragraph(pdf, stripped)

    # Flush any unclosed code block
    if code_lines:
        _render_code_block(pdf, code_lines)

    return pdf.output()


def _preprocess_mermaid(md: str) -> str:
    """Replace ```mermaid blocks with labelled code blocks."""
    return re.sub(
        r"```mermaid\s*\n(.*?)```",
        r"Diagrama (fuente Mermaid):\n\n```\n\1```",
        md,
        flags=re.DOTALL,
    )


def _sanitize(text: str) -> str:
    """Replace Unicode characters unsupported by Helvetica with ASCII equivalents."""
    replacements = {
        "\u2018": "'", "\u2019": "'",  # smart single quotes
        "\u201c": '"', "\u201d": '"',  # smart double quotes
        "\u2013": "-", "\u2014": "--",  # en/em dash
        "\u2026": "...",  # ellipsis
        "\u2022": "-",  # bullet
        "\u00a0": " ",  # non-breaking space
        "\u200b": "",  # zero-width space
        "\u2192": "->",  # right arrow
        "\u2190": "<-",  # left arrow
        "\u2194": "<->",  # left-right arrow
        "\u2265": ">=",  # >=
        "\u2264": "<=",  # <=
        "\u2260": "!=",  # !=
        "\u00b7": ".",  # middle dot
        "\u2502": "|",  # box drawing
        "\u251c": "|",  # box drawing
        "\u2500": "-",  # box drawing
        "\u2514": "|",  # box drawing
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)

    # Fallback: replace any remaining non-latin1 chars with closest ASCII
    out = []
    for ch in text:
        try:
            ch.encode("latin-1")
            out.append(ch)
        except UnicodeEncodeError:
            # Try unicode decomposition first
            decomp = unicodedata.normalize("NFKD", ch)
            ascii_chars = decomp.encode("latin-1", errors="ignore").decode("latin-1")
            out.append(ascii_chars if ascii_chars else "?")
    return "".join(out)


def _render_heading(pdf, text: str, level: int) -> None:
    sizes = {1: 20, 2: 16, 3: 13, 4: 12, 5: 11, 6: 11}
    size = sizes.get(level, 11)

    pdf.ln(4 if level <= 2 else 2)
    pdf.set_font("Helvetica", "B", size)
    pdf.multi_cell(0, size * 0.55, _sanitize(_strip_inline(text)))

    if level <= 2:
        y = pdf.get_y()
        pdf.set_draw_color(160, 160, 160)
        pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
        pdf.ln(3)
    else:
        pdf.ln(2)

    pdf.set_font("Helvetica", size=11)


def _render_paragraph(pdf, text: str) -> None:
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 5.5, _sanitize(_strip_inline(text)))
    pdf.ln(1)


def _render_list_item(pdf, text: str, ordered: bool = False) -> None:
    bullet = "  -  " if not ordered else "  *  "
    pdf.set_font("Helvetica", size=11)
    x = pdf.get_x()
    pdf.set_x(x + 5)
    pdf.multi_cell(0, 5.5, bullet + _sanitize(_strip_inline(text)))
    pdf.ln(0.5)


def _render_code_block(pdf, lines: list[str]) -> None:
    pdf.set_font("Courier", size=9)
    pdf.set_fill_color(245, 245, 245)
    code_text = _sanitize("\n".join(lines))
    pdf.multi_cell(0, 4.5, code_text, fill=True)
    pdf.ln(3)
    pdf.set_font("Helvetica", size=11)


def _render_table_row(pdf, row_text: str) -> None:
    """Render a simple pipe-separated table row."""
    cells = [c.strip() for c in row_text.strip("|").split("|")]
    n_cols = len(cells)
    if n_cols == 0:
        return

    usable_w = pdf.w - pdf.l_margin - pdf.r_margin
    col_w = usable_w / n_cols

    pdf.set_font("Helvetica", size=10)
    for cell in cells:
        pdf.cell(col_w, 6, _sanitize(_strip_inline(cell))[:50], border=1)
    pdf.ln()


def _strip_inline(text: str) -> str:
    """Remove Markdown inline formatting (bold, italic, code, links)."""
    text = re.sub(r"\*{3}(.+?)\*{3}", r"\1", text)
    text = re.sub(r"_{3}(.+?)_{3}", r"\1", text)
    text = re.sub(r"\*{2}(.+?)\*{2}", r"\1", text)
    text = re.sub(r"_{2}(.+?)_{2}", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text
