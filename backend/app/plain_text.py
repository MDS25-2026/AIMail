"""HTML to readable text, for the few stored bodies that are still markup (#108)."""

from html.parser import HTMLParser

# Their contents are code, not prose.
_SKIPPED = frozenset({"script", "style", "head"})
_BLOCKS = frozenset({"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "table", "blockquote"})


class _TextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIPPED:
            self._skip_depth += 1
        elif tag in _BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIPPED and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)


def plain_text(body: str) -> str:
    """The body as prose. Text without markup comes back unchanged."""
    if "<" not in body:
        return body
    collector = _TextCollector()
    collector.feed(body)
    lines = (line.strip() for line in "".join(collector.parts).splitlines())
    return "\n".join(line for line in lines if line)
