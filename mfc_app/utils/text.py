import html
import re
from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    BLOCK_TAGS = {
        "p", "div", "br", "li", "ul", "ol", "table", "tr", "td", "th",
        "section", "article", "h1", "h2", "h3", "h4", "h5", "h6",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


def clean_html(value) -> str:
    if value is None:
        return ""

    raw = html.unescape(str(value))
    parser = _TextExtractor()
    try:
        parser.feed(raw)
        text = parser.text()
    except Exception:
        text = re.sub(r"<[^>]+>", " ", raw)

    lines = []
    for line in text.splitlines():
        normalized = re.sub(r"[\t \f\v]+", " ", line).strip()
        if normalized:
            lines.append(normalized)

    return "\n".join(lines).strip()


def truncate(value: str, max_chars: int) -> str:
    text = (value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"
