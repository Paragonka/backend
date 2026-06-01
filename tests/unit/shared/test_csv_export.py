import pytest

from app.shared.csv_export import (
    MAX_EXPORT_ROWS,
    add_custom_columns,
    ensure_export_limit,
    rows_to_csv,
)


class TestRowsToCsv:
    def test_header_and_bom(self):
        result = rows_to_csv([{"a": "1", "b": "x"}], ["a", "b"])
        assert result.startswith("\ufeff")
        assert "a,b\r\n" in result
        assert "1,x\r\n" in result

    def test_escaping_quotes_and_commas(self):
        result = rows_to_csv(
            [{"name": 'Иван, "повар"', "phone": "123"}],
            ["name", "phone"],
        )
        assert '"Иван, ""повар"""' in result

    def test_unicode(self):
        result = rows_to_csv([{"name": "Круассан", "unit": "шт"}], ["name", "unit"])
        assert "Круассан" in result
        assert "шт" in result

    def test_extra_keys_ignored(self):
        result = rows_to_csv([{"a": "1", "b": "2", "c": "3"}], ["a", "b"])
        assert "1,2\r\n" in result
        assert "c" not in result

    def test_empty_rows(self):
        result = rows_to_csv([], ["a", "b"])
        assert result == "\ufeffa,b\r\n"


class TestAddCustomColumns:
    def test_flattens_sorted(self):
        row = add_custom_columns({}, {"b": 2, "a": 1})
        assert row == {"cf_a": 1, "cf_b": 2}

    def test_none_fields(self):
        row = add_custom_columns({"x": 1}, None)
        assert row == {"x": 1}


class TestEnsureExportLimit:
    def test_ok_under_limit(self):
        ensure_export_limit([{}] * (MAX_EXPORT_ROWS - 1))

    def test_exact_limit_ok(self):
        ensure_export_limit([{}] * MAX_EXPORT_ROWS)

    def test_over_limit_raises(self):
        with pytest.raises(ValueError, match="Export exceeds maximum"):
            ensure_export_limit([{}] * (MAX_EXPORT_ROWS + 1))
