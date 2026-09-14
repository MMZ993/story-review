"""Deterministic rendering: FinalizedReview -> Markdown / PDF.

The document structure is built once (a flat block list) and rendered by
two independent writers, so MD and PDF always agree on structure. PDF
bytes are latin-1 (built-in fonts transliterate lossily — non-latin
text degrades to '?' in PDF while MD keeps full fidelity). Rendering
is a pure function of the FinalizedReview: no timestamps of the render
itself, no random ids — identical input produces byte-identical output
within one pinned fpdf2 version (the /Producer trailer carries that
version). PDF metadata is pinned too: fixed creation date and no /ID
trailer (fpdf2's default `file_id()` is falsy).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from fpdf import FPDF
from review_schemas.facilitator import FinalizedReview

#: Fixed PDF CreationDate — the document's own facts come from the content.
_FIXED_PDF_DATE = datetime(2000, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class Block:
    """One document block: title, heading, paragraph, or list item."""

    kind: str  # "title" | "heading" | "para" | "bullet" | "numbered"
    text: str


def document_blocks(content: FinalizedReview) -> list[Block]:
    """The canonical document structure for one finalized review."""
    catalog = {entry.issue: entry for entry in content.issues}

    def label(issue: str) -> str:
        """Annotate an id with its catalog title when one exists (D19)."""
        entry = catalog.get(issue)
        return f"{issue} — {entry.title}" if entry is not None else issue

    def source_word(source: str) -> str:
        return "from synthesis" if source == "synthesis" else "raised by facilitator"

    blocks = [
        Block("title", f"Story Review Report — {content.story_id}"),
        Block("para", f"Story: {content.story_id}"),
        Block("para", f"Story run: {content.story_run_id}"),
        Block("para", f"Final turn: {content.final_turn_number}"),
        Block("para", f"Finalized at: {content.finalized_at.isoformat()}"),
        Block("heading", "Verdict"),
        Block(
            "para",
            f"PO acceptance: {'accepted' if content.po_accepted else 'not accepted'}",
        ),
        Block("heading", "Issues"),
    ]
    if content.issues:
        for entry in content.issues:
            severity = (
                f", {entry.severity}" if entry.severity is not None else ""
            )
            blocks.append(
                Block(
                    "bullet",
                    f"{entry.issue} — {entry.title} "
                    f"({source_word(entry.source)}{severity}): "
                    f"{entry.description}",
                )
            )
    else:
        blocks.append(Block("para", "None."))
    blocks.append(Block("heading", "Resolutions"))
    if content.resolutions:
        for index, item in enumerate(content.resolutions, start=1):
            blocks.append(
                Block(
                    "numbered",
                    f"{index}. {label(item.issue)} — {item.disposition} "
                    f"(turn {item.turn_number}): {item.explanation}",
                )
            )
    else:
        blocks.append(Block("para", "None."))
    blocks.append(Block("heading", "Remaining open issues"))
    if content.remaining_open_issues:
        blocks.extend(
            Block("bullet", label(issue)) for issue in content.remaining_open_issues
        )
    else:
        blocks.append(Block("para", "None."))
    return blocks


def render_markdown(content: FinalizedReview) -> str:
    """Deterministic Markdown for the finalized review."""
    lines: list[str] = []
    for block in document_blocks(content):
        if block.kind == "title":
            lines += [f"# {block.text}", ""]
        elif block.kind == "heading":
            lines += [f"## {block.text}", ""]
        elif block.kind == "bullet":
            lines += [f"- {block.text}"]
        else:  # para | numbered
            lines += [block.text, ""]
    return "\n".join(lines).rstrip() + "\n"


def render_pdf(content: FinalizedReview) -> bytes:
    """Deterministic PDF for the finalized review (fpdf2, built-in fonts)."""
    blocks = document_blocks(content)
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    # Determinism: pinned CreationDate, and no /ID trailer is emitted
    # (fpdf2's default file_id() returns a falsy value), so nothing time-
    # or host-derived enters the bytes.
    pdf.set_creation_date(_FIXED_PDF_DATE)
    pdf.add_page()
    for block in blocks:
        if block.kind == "title":
            pdf.set_font("helvetica", style="B", size=16)
            pdf.multi_cell(0, 8, _latin1(block.text))
            pdf.ln(2)
        elif block.kind == "heading":
            pdf.set_font("helvetica", style="B", size=12)
            pdf.multi_cell(0, 6, _latin1(block.text))
            pdf.ln(1)
        else:
            pdf.set_font("helvetica", size=10)
            pdf.multi_cell(0, 5, _latin1(block.text))
            pdf.ln(1)
    return bytes(pdf.output())


def render(content: FinalizedReview, fmt: str) -> bytes:
    """Render the finalized review in the requested wire format."""
    if fmt == "md":
        return render_markdown(content).encode("utf-8")
    if fmt == "pdf":
        return render_pdf(content)
    raise ValueError(f"unsupported report format {fmt!r}")


def _latin1(text: str) -> str:
    """Map to the built-in fonts' latin-1 repertoire, lossily but stably.

    The typographic characters the renderer itself emits (the em-dash
    label separator) are transliterated to readable ASCII first — never
    the generic '?' replacement."""
    return (
        text.replace("—", " - ")
        .encode("latin-1", "replace")
        .decode("latin-1")
    )
