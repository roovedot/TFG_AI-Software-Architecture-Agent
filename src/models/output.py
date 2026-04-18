"""Pydantic model for Markdown report output."""

from __future__ import annotations

from pydantic import BaseModel


class MarkdownReport(BaseModel):
    """A complete architecture analysis report as a Markdown document."""

    markdown_content: str
