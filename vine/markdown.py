from dataclasses import dataclass
from typing import List, Optional, Iterable


@dataclass
class Section:
    level: int              # 0 for pre-heading content, otherwise number of '#' chars
    title: Optional[str]    # None for level 0, otherwise heading text
    lines: List[str]        # lines exclusively in this section (excluding nested subsections)


def parse_markdown_sections(text: str) -> List[Section]:
    """
    Parse a markdown document into a flat list of sections.

    Rules:
    - A heading is a line that starts with one or more '#' followed by at least one space.
    - level = number of '#' characters.
    - Section content is all lines until the next heading of the same or lower level.
    - Content under a deeper heading belongs to that deeper section, not the parent.
    - Text before the first heading is a level 0 section with title=None.
    """
    lines = text.splitlines()
    n = len(lines)

    sections: List[Section] = []

    # Helper to detect heading
    def parse_heading(line: str):
        # Line must start with at least one '#' then a space
        if not line.startswith("#"):
            return None
        i = 0
        while i < len(line) and line[i] == "#":
            i += 1
        if i == 0 or i == len(line) or line[i] != " ":
            return None
        level = i
        title = line[i + 1 :].rstrip()
        return level, title

    # First pass: find all headings with their indices
    headings = []
    for idx, line in enumerate(lines):
        parsed = parse_heading(line)
        if parsed is not None:
            level, title = parsed
            headings.append((idx, level, title))

    # Handle pre-heading content (level 0) if any
    if not headings:
        # Whole document is a single level 0 section
        sections.append(
            Section(
                level=0,
                title=None,
                lines=lines.copy(),
            )
        )
        return sections

    first_heading_idx = headings[0][0]
    if first_heading_idx > 0:
        # Preamble section before the first heading
        sections.append(
            Section(
                level=0,
                title=None,
                lines=lines[0:first_heading_idx],
            )
        )

    # For each heading, we need to find the range of lines that belong to this section,
    # excluding content of subsections.
    num_headings = len(headings)

    for i, (idx, level, title) in enumerate(headings):
        # Determine the tentative end of this section's entire span
        if i + 1 < num_headings:
            next_heading_idx = headings[i + 1][0]
        else:
            next_heading_idx = n  # until the end of the document

        # Now we must trim off content that belongs to deeper subsections:
        #   from idx+1 until the first heading with level <= this level
        #   but we already know next heading's index; the deeper ones are inside
        # So we scan forward to find first heading at level <= current,
        #   and that defines logical end of this section (including all deeper subsections).
        logical_end = n
        for j in range(i + 1, num_headings):
            h_idx, h_level, _ = headings[j]
            if h_level <= level:
                logical_end = h_idx
                break

        # Now we want lines that are exclusively in this section:
        # from idx+1 up to the first child heading at level = level+1 or higher,
        # but not including lines that belong to nested headings.
        # Simplest approach: content lines end at the first heading with level > level,
        #   or logical_end, whichever comes first.
        exclusive_end = logical_end
        for j in range(i + 1, num_headings):
            h_idx, h_level, _ = headings[j]
            if h_level > level:
                exclusive_end = min(exclusive_end, h_idx)
                break

        body_start = idx + 1
        body_end = exclusive_end

        section_lines = lines[body_start:body_end]

        sections.append(
            Section(
                level=level,
                title=title,
                lines=section_lines,
            )
        )

    return sections


def sections_to_markdown(sections: Iterable[Section]) -> str:
    """
    Reconstruct markdown from sections.
    This assumes sections are in the original document order,
    and that level 0 is preamble, other levels have headings.
    """
    out_lines: List[str] = []
    for section in sections:
        if section.level == 0:
            # Preamble, no heading
            out_lines.extend(section.lines)
        else:
            heading_line = "#" * section.level + " " + (section.title or "")
            out_lines.append(heading_line)
            out_lines.extend(section.lines)
    return "\n".join(out_lines)


def get_section_by_title(
    sections: List["Section"],
    title: str,
    level: Optional[int] = None,
) -> Optional["Section"]:
    """
    Return the first Section whose title matches `title`.

    If `level` is provided, only sections with that level are considered.
    If no matching section is found, return None.
    """
    for s in sections:
        if s.title != title:
            continue
        if level is not None and s.level != level:
            continue
        return s
    return None
