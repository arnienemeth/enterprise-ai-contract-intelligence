"""Section-aware text chunking for embeddings + retrieval.

Why chunking is needed
----------------------
1. Model limits: text-embedding-3-large accepts ~8,191 tokens (~30k chars) per
   input. A long contract embedded whole is truncated → lost content.
2. Retrieval quality: one vector for a 40-page contract is a blurry average.
   Splitting into clause-sized pieces lets semantic search surface the exact
   section that answers a question, and lets RAG cite it.

Strategy
--------
Split the text on natural boundaries (blank lines, then numbered clause /
ARTICLE / SECTION headings), then greedily pack those pieces into windows of at
most ``max_chars`` characters. Consecutive windows share ``overlap`` characters
of tail context so a clause split across a boundary is still retrievable from
both sides. A single oversized paragraph is hard-split as a last resort.

Pure functions, no external deps — trivially unit-testable.
"""

import re

# Defaults chosen well under the embedding token limit while keeping chunks
# large enough to preserve clause context. ~4k chars ≈ ~1k tokens.
DEFAULT_MAX_CHARS = 4000
DEFAULT_OVERLAP = 400

# Headings that typically begin a new contract section. Used as *preferred*
# split points so a chunk starts at a clause boundary when possible.
_SECTION_HEADING = re.compile(
    r"(?m)^\s*("
    r"(?:ARTICLE|SECTION|CLAUSE|SCHEDULE|EXHIBIT|APPENDIX|ANNEX)\b.*"  # named
    r"|\d+(?:\.\d+)*\.?\s+\S.*"                                        # 1.  / 2.3
    r")$"
)


def _normalize(text: str) -> str:
    """Standardize newlines and strip trailing whitespace per line."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    # Collapse 3+ blank lines into a paragraph break.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_into_units(text: str) -> list:
    """Break text into small semantic units (paragraphs / clauses).

    First split on blank lines; then, inside each block, start a new unit at a
    section heading so headings begin chunks rather than dangling at the end of
    the previous one.
    """
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]

    units = []
    for block in blocks:
        lines = block.split("\n")
        current = []
        for line in lines:
            if _SECTION_HEADING.match(line) and current:
                units.append("\n".join(current).strip())
                current = [line]
            else:
                current.append(line)
        if current:
            units.append("\n".join(current).strip())

    return [u for u in units if u]


def _hard_split(unit: str, max_chars: int) -> list:
    """Split an over-long unit that has no internal boundaries.

    Prefer sentence breaks; fall back to a hard character cut so nothing exceeds
    the limit.
    """
    pieces = []
    sentences = re.split(r"(?<=[.;!?])\s+", unit)
    buf = ""
    for s in sentences:
        if len(s) > max_chars:
            # A single monster sentence: flush, then slice by characters.
            if buf:
                pieces.append(buf.strip())
                buf = ""
            for i in range(0, len(s), max_chars):
                pieces.append(s[i:i + max_chars].strip())
            continue
        if len(buf) + len(s) + 1 > max_chars:
            if buf:
                pieces.append(buf.strip())
            buf = s
        else:
            buf = f"{buf} {s}".strip()
    if buf:
        pieces.append(buf.strip())
    return [p for p in pieces if p]


def chunk_text(text, max_chars=DEFAULT_MAX_CHARS, overlap=DEFAULT_OVERLAP):
    """Split ``text`` into overlapping, section-aware chunks.

    Args:
        text: the full document text.
        max_chars: maximum characters per chunk.
        overlap: characters of trailing context repeated at the start of the
            next chunk (kept < max_chars).

    Returns:
        list[str] of chunks in document order. Short documents return a single
        chunk; empty input returns [].
    """
    if not text or not text.strip():
        return []

    if overlap < 0:
        overlap = 0
    if overlap >= max_chars:
        overlap = max_chars // 4

    text = _normalize(text)

    # Fast path: short document → one chunk.
    if len(text) <= max_chars:
        return [text]

    units = _split_into_units(text) or [text]

    chunks = []
    current = ""

    for unit in units:
        # A unit bigger than the window must itself be broken down.
        if len(unit) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_hard_split(unit, max_chars))
            continue

        candidate = unit if not current else f"{current}\n\n{unit}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            # Close the current chunk and start a new one carrying overlap.
            chunks.append(current.strip())
            tail = current[-overlap:] if overlap else ""
            current = f"{tail}\n\n{unit}".strip() if tail else unit

    if current.strip():
        chunks.append(current.strip())

    # Drop accidental empties and de-duplicate adjacent identical chunks.
    cleaned = []
    for c in chunks:
        c = c.strip()
        if c and (not cleaned or cleaned[-1] != c):
            cleaned.append(c)

    return cleaned
