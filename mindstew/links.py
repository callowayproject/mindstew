"""The one shared wikilink resolver (used by show, and later graph, lint and chat)."""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from mindstew.pages import Page

_WIKILINK = re.compile(r"\[\[([^\[\]]*)\]\]")


def _key(name: str) -> str:
    return name.strip().casefold()


def extract_links(body: str) -> list[str]:
    """Return the distinct wikilink targets in ``body`` in order, without ``|display``, ``#heading`` or ``^block``."""
    targets: dict[str, None] = {}
    for raw in _WIKILINK.findall(body):
        target = re.split(r"[|#^]", raw, maxsplit=1)[0].strip()
        if target:
            targets[target] = None
    return list(targets)


class Resolver:
    """Maps wikilink targets to pages, case-insensitively on title, then on frontmatter ``aliases``.

    Duplicates are deterministic: a title beats any alias, and among equals the first page in the given order wins.
    """

    def __init__(self, pages: Iterable[Page]) -> None:
        pages = list(pages)
        self._by_name: dict[str, Page] = {}
        # ponytail: two passes keep "title beats alias" without a priority field
        for names in (lambda p: [p.title] if p.title else [], lambda p: p.aliases):
            for page in pages:
                for name in names(page):
                    self._by_name.setdefault(_key(name), page)

    def resolve(self, target: str) -> Page | None:
        """Return the page ``target`` points at, or None."""
        return self._by_name.get(_key(target))

    def resolve_body(self, body: str) -> list[tuple[str, Page | None]]:
        """Return every link target in ``body`` paired with its page (None if unresolved)."""
        return [(t, self.resolve(t)) for t in extract_links(body)]
