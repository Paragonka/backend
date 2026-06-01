"""Unit tests for shared sanitization helpers."""

from app.shared.sanitization import escape_like, strip_html_tags


class TestEscapeLike:
    def test_percent_is_escaped(self):
        assert escape_like("50%") == r"50\%"

    def test_underscore_is_escaped(self):
        assert escape_like("a_b") == r"a\_b"

    def test_escape_char_itself_is_escaped_first(self):
        assert escape_like("100\\") == "100\\\\"
        # Order matters: the escape character is escaped before % and _
        assert escape_like("\\%") == "\\\\\\%"

    def test_plain_text_unchanged(self):
        assert escape_like("Anna Kowalska") == "Anna Kowalska"

    def test_empty_string(self):
        assert escape_like("") == ""


class TestStripHtmlTags:
    def test_removes_tags(self):
        assert strip_html_tags("<b>hi</b>") == "hi"

    def test_plain_text_passthrough(self):
        assert strip_html_tags("plain") == "plain"
