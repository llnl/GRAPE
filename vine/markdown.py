from dataclasses import dataclass, field
from typing import List, Optional, Iterable
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

    def iter_breadth_first(self) -> Iterable["Section"]:
        """Breadth first iterator over this section and all descendants."""
        queue: deque[Section] = deque([self])
        while queue:
            section = queue.popleft()
            yield section
            queue.extend(section.children)


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

    def find_section(self, path: str) -> Optional[Section]:
        """
        Resolve a '/' separated path of section titles.

        Examples:
            "GRAPE/Related Reviews"
            "GRAPE/Review Rules/Code Review/test"

        The lookup is done among children at each level using exact title match.
        Returns None if any segment cannot be resolved.
        """
        # Split and strip whitespace around each segment
        parts = [p.strip() for p in path.split("/") if p.strip()]

        if not parts:
            return self.root

        # If the first part is the root title, skip it so paths can be
        # written either as "GRAPE/..." or "Review Rules/..."
        idx = 0

        if self.root.title is not None and parts[0] == self.root.title:
            idx = 1

            if idx >= len(parts):
                return self.root

        current = self.root

        while idx < len(parts):
            name = parts[idx]

            for child in current.children:
                if child.title == name:
                    current = child
                    break
            else:
                # No child with this name
                return None

            idx += 1

        return current

    def iter_sections(self) -> Iterable[Section]:
        """Depth first iteration over all sections, including root."""
        yield from self.root.iter_depth_first()

