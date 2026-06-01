import re

_TAG_RE = re.compile(r"<[^>]*>")

_LIKE_ESCAPE_CHAR = "\\"


def strip_html_tags(value: str) -> str:
    """Remove HTML/XML tags from a string, keeping the text content."""

    return _TAG_RE.sub("", value)


def escape_like(value: str, escape_char: str = _LIKE_ESCAPE_CHAR) -> str:
    """L1: escapes LIKE wildcards (% and _) and the escape character itself.

    Use with ilike(pattern, escape="\\") - otherwise user input such as "50%"
    matches "50x", "500", and so on.
    """

    return (
        value.replace(escape_char, escape_char * 2)
        .replace("%", escape_char + "%")
        .replace("_", escape_char + "_")
    )
