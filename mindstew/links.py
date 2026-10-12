"""The one shared wikilink resolver (used by show, and later graph, lint and chat)."""

import re
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Iterable

    from mindstew.pages import Page


class Link(NamedTuple):
    """A wikilink target and the page it resolves to (None if unresolved)."""

    target: str
    page: Page | None


_WIKILINK = re.compile(r"\[\[([^\[\]]*)\]\]")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_INLINE_CODE = re.compile(r"(?<!`)(`+)(?!`).+?(?<!`)\1(?!`)", re.DOTALL)


def _key(name: str) -> str:
    """Return the case-insensitive lookup key for a name."""
    return name.strip().casefold()


def _strip_code(body: str) -> str:
    """Return ``body`` without fenced blocks and inline code spans; an unterminated fence runs to the end."""
    prose: list[str] = []
    fence = ""
    for line in body.split("\n"):
        m = _FENCE.match(line)
        if fence:
            if m and m[1][0] == fence[0] and len(m[1]) >= len(fence) and not m[2].strip():
                fence = ""
        elif m and not (m[1][0] == "`" and "`" in m[2]):
            fence = m[1]
        else:
            prose.append(line)
    return _INLINE_CODE.sub("", "\n".join(prose))


def _anchorless(text: str) -> str:
    """Return ``text`` cut at the first ``#`` or ``^``, stripped."""
    return re.split(r"[#^]", text, maxsplit=1)[0].strip()


def extract_links(body: str) -> list[str]:
    r"""Return the distinct raw wikilink targets in prose, in order: the text before ``|display``.

    ``\\|`` counts as ``|``. Links in code spans and fenced blocks are ignored, as are targets that are
    empty once ``#heading`` and ``^block`` are removed.
    """
    targets: dict[str, None] = {}
    for raw in _WIKILINK.findall(_strip_code(body)):
        target = raw.replace("\\|", "|").split("|", 1)[0].strip()
        if _anchorless(target):
            targets[target] = None
    return list(targets)


class Resolver:
    """Maps wikilink targets to pages, case-insensitively, by filename stem, then title, then ``aliases``.

    A target is tried as written, then cut at the first ``#`` or ``^``; each text goes through every tier first.
    Duplicates are deterministic: within a tier the first page in the given order wins.
    """

    def __init__(self, pages: Iterable[Page]) -> None:
        self._tiers: tuple[dict[str, Page], ...] = ({}, {}, {})  # stem, title, alias
        stems, titles, aliases = self._tiers
        for page in pages:
            stems.setdefault(_key(page.path.stem), page)
            if page.title:
                titles.setdefault(_key(page.title), page)
            for alias in page.aliases:
                aliases.setdefault(_key(alias), page)

    def resolve(self, target: str) -> Page | None:
        """Return the page ``target`` points at, or None."""
        for text in dict.fromkeys((target, _anchorless(target))):
            if not text.strip():
                continue
            for tier in self._tiers:
                if page := tier.get(_key(text)):
                    return page
        return None

    def resolve_body(self, body: str) -> list[Link]:
        """Return every link in ``body`` with its resolved page (None if unresolved)."""
        return [Link(t, self.resolve(t)) for t in extract_links(body)]
