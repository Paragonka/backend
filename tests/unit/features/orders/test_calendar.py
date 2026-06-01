from app.shared.templates import format_time


class TestFormatTime:
    def test_format_time_extracts_hh_mm(self):
        assert format_time("2026-06-08 14:30:00") == "14:30"

    def test_format_time_none(self):
        assert format_time(None) == ""

    def test_format_time_short(self):
        assert format_time("2026-06") == "2026-06"

    def test_format_time_empty(self):
        assert format_time("") == ""

    def test_format_time_midnight(self):
        assert format_time("2026-06-08 00:00:00") == "00:00"
