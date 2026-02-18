from dataclasses import dataclass, field
from typing import List, Optional, Iterable, Sequence
import re


@dataclass
class Section:
    title: Optional[str]       # None for the synthetic root
    level: int                 # 0 for root, 1 for #, 2 for ##, etc.
    lines: List[str] = field(default_factory=list)
    children: List["Section"] = field(default_factory=list)

    def add_child(self, child: "Section") -> None:
        self.children.append(child)

    def iter_depth_first(self) -> Iterable["Section"]:
        """Depth first iterator over this section and all descendants."""
        yield self
        for child in self.children:
            yield from child.iter_depth_first()


class Document:
    """
    Represents a parsed Markdown document as a hierarchy of Sections.

    Usage:
        doc = Document.from_text(markdown_str)
        sec = doc.find_section("GRAPE")
        doc.replace_section_content("Related Reviews", "None")
        new_text = doc.to_markdown()
    """

    _HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")

    def __init__(self, root: Optional[Section] = None) -> None:
        self.root: Section = root if root is not None else Section(
            title=None,
            level=0,
        )

    # ---------- Construction ----------

    @classmethod
    def from_text(cls, text: str) -> "Document":
        """Parse Markdown text into a Document."""
        lines = text.splitlines()
        root = Section(title=None, level=0)
        stack: List[Section] = [root]
        current_section = root

        for line in lines:
            m = cls._HEADING_RE.match(line.strip())

            if m:
                hashes, raw_title = m.groups()
                level = len(hashes)
                title = raw_title

                # Pop until we find a parent with lower level
                while stack and stack[-1].level >= level:
                    stack.pop()

                parent = stack[-1] if stack else root

                new_section = Section(title=title, level=level)
                parent.add_child(new_section)
                stack.append(new_section)
                current_section = new_section
            else:
                current_section.lines.append(line)

        return cls(root=root)

    # ---------- Introspection ----------

    def iter_sections(self) -> Iterable[Section]:
        """Depth first iteration over all sections, including root."""
        yield from self.root.iter_depth_first()

    def find_section(self, title: str, *, case_sensitive: bool = True) -> Optional[Section]:
        """
        Return the first section whose title matches.

        If case_sensitive is False, comparison is done using lower().
        """
        for sec in self.iter_sections():
            if sec.title is None:
                continue
            if case_sensitive:
                if sec.title == title:
                    return sec
            else:
                if sec.title.lower() == title.lower():
                    return sec
        return None

    def find_sections(self, title: str, *, case_sensitive: bool = True) -> List[Section]:
        """
        Return all sections whose title matches.
        """
        matches: List[Section] = []
        for sec in self.iter_sections():
            if sec.title is None:
                continue
            if case_sensitive:
                if sec.title == title:
                    matches.append(sec)
            else:
                if sec.title.lower() == title.lower():
                    matches.append(sec)
        return matches

    # ---------- Mutation helpers ----------

    def replace_section_content(
        self,
        title: str,
        new_text: str,
        *,
        case_sensitive: bool = True,
    ) -> bool:
        """
        Replace the content of the first section with the given title.

        Returns True if a section was replaced, False if not found.
        """
        sec = self.find_section(title, case_sensitive=case_sensitive)
        if sec is None:
            return False
        sec.lines = new_text.splitlines()
        return True

    def set_section_content(self, section: Section, new_text: str) -> None:
        """
        Directly set content of a specific Section object.
        """
        section.lines = new_text.splitlines()

    # ---------- Rendering ----------

    def _render_section(self, sec: Section) -> List[str]:
        """Render a section (and its children) into a list of lines."""
        lines: List[str] = []

        # Root has no heading
        if sec.level > 0 and sec.title is not None:
            heading = "#" * sec.level + " " + sec.title
            lines.append(heading)

        # Body
        lines.extend(sec.lines)

        # Children
        for child in sec.children:
            if lines and lines[-1].strip() != "":
                lines.append("")
            lines.extend(self._render_section(child))

        return lines

    def to_text(self) -> str:
        """Render the whole document back into Markdown text."""
        lines: List[str] = []

        # Root content first (before first heading)
        lines.extend(self.root.lines)

        # Top level sections
        for child in self.root.children:
            if lines and lines[-1].strip() != "":
                lines.append("")
            lines.extend(self._render_section(child))

        return "\n".join(lines).rstrip() + "\n"
