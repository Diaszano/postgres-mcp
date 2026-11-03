"""Shared assertions for narrowing MCP content variants in tests."""

from collections.abc import Sequence


def first_item[T](items: Sequence[T] | None) -> T:
    assert items
    return items[0]


def text_at(contents: Sequence[object], index: int = 0) -> str:
    text = getattr(contents[index], "text", None)
    assert isinstance(text, str)
    return text
