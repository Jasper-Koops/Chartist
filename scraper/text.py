"""
Motion text: extracting it from the published XML, and deriving its core.

The full text is stored, as on the official page; the core (what the motion
says, without the fixed formula around it) is derived from it when needed,
so a different cut never needs a new download.
"""

import logging
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

MOTION_START_MARKER: str = "gehoord de beraadslaging"
# Used when a motion omits 'gehoord de beraadslaging'. Compared to the whole
# line, so content lines that merely start with 'De Kamer' do not match.
MOTION_ALT_START_MARKER: str = "de kamer"
# Matched anywhere in the line; some motions drop the leading 'en'.
MOTION_END_MARKER: str = "gaat over tot de orde van de dag"
MOTION_FALLBACK_PREFIXES: tuple[str, ...] = (
    "constaterende",
    "overwegende",
    "verzoekt",
    "spreekt uit",
)


def _key(line: str) -> str:
    """A line lowercased and without closing punctuation, for matching."""
    return line.strip().lower().rstrip(",.;:")


def _list_marker(
    elem: ET.Element, parents: dict[ET.Element, ET.Element]
) -> str:
    """
    The marker of the list item a paragraph opens, e.g. "– " or "1. ".

    Only the first paragraph of a list item gets the marker; anything else
    gets an empty string.
    """
    item = parents.get(elem)
    if item is None or item.tag != "li" or item.find("al") is not elem:
        return ""
    number = item.find("li.nr")
    marker = "".join(number.itertext()).strip() if number is not None else ""
    return f"{marker} " if marker else ""


def _paragraphs(root: ET.Element) -> list[str]:
    """Every non-empty paragraph, list items with their marker."""
    parents = {child: parent for parent in root.iter() for child in parent}
    lines = []
    for elem in root.iter("al"):
        if text := "".join(elem.itertext()).strip():
            lines.append(_list_marker(elem, parents) + text)
    return lines


def _formula_span(lines: list[str]) -> tuple[int, int, int] | None:
    """
    Where the motion formula is: the 'De Kamer,' line (or the start line if
    there is none), the start line ('gehoord de beraadslaging,' or else
    'De Kamer,'), and the end line ('en gaat over tot de orde van de dag.').

    Returns None when the start or the end is missing.
    """
    keys = [_key(line) for line in lines]
    opening = next(
        (i for i, key in enumerate(keys) if key == MOTION_ALT_START_MARKER),
        None,
    )
    start = next(
        (
            i
            for i, key in enumerate(keys)
            if key.startswith(MOTION_START_MARKER)
        ),
        opening,
    )
    if start is None:
        return None
    end = next(
        (
            i
            for i, key in enumerate(keys)
            if MOTION_END_MARKER in key and i > start
        ),
        None,
    )
    if end is None:
        return None
    if opening is None or opening > start:
        opening = start
    return opening, start, end


def extract_motion_text(
    xml_content: bytes, document_id: str | None = None
) -> list[str]:
    """
    Extract the text of a motion from its XML, as on the official page.

    Accepts raw bytes so that ElementTree can read the encoding declaration
    and handle the UTF-8 BOM correctly.

    Motions follow a fixed formula: 'De Kamer, gehoord de beraadslaging,'
    followed by the considerations and operative part, closed by 'en gaat
    over tot de orde van de dag.' and the signatories. Returned are the
    proposal date line ('Voorgesteld 12 oktober 2026') and every line from
    'De Kamer,' up to and including the closing line; the signatories are
    left out. Punctuation is kept, and a sub-point of a list keeps its
    marker, e.g. "– het behoud van veto's".

    If the formula is not found, falls back to keeping only lines starting
    with constaterende, overwegende, verzoekt or spreekt uit.

    Args:
        xml_content (bytes): Raw XML bytes of the motion document.
        document_id (str | None): Optional identifier, used for logging.

    Returns:
        list[str]: The lines of the motion.
    """
    root = ET.fromstring(xml_content)
    lines = _paragraphs(root)
    span = _formula_span(lines)
    if span is not None:
        opening, _, end = span
        date = root.find(".//datumtekst")
        proposed = (
            " ".join("".join(date.itertext()).split())
            if date is not None
            else ""
        )
        return ([proposed] if proposed else []) + lines[opening : end + 1]

    if lines:
        logger.info(
            f"Motion markers not found in {document_id}, using prefix fallback",
            extra={"document_id": document_id},
        )
    return [
        line
        for line in lines
        if _key(line).startswith(MOTION_FALLBACK_PREFIXES)
    ]


def motion_core(lines: list[str]) -> list[str]:
    """
    The core of a motion: the lines between the opening formula ('gehoord de
    beraadslaging,') and the closing line ('en gaat over tot de orde van de
    dag.'), regardless of their wording. Trailing commas are stripped.

    Without the formula (texts extracted by the fallback, or stored before
    the full text was), only lines starting with constaterende, overwegende,
    verzoekt or spreekt uit are kept.

    Args:
        lines (list[str]): The stored text of a motion.

    Returns:
        list[str]: The core lines.
    """
    span = _formula_span(lines)
    if span is not None:
        _, start, end = span
        core = lines[start + 1 : end]
    else:
        core = [
            line
            for line in lines
            if _key(line).startswith(MOTION_FALLBACK_PREFIXES)
        ]
    return [line.rstrip(",") for line in core]
