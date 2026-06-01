import pytest

from app.shared.csv_import import CsvImportResult, parse_bool, parse_csv


class TestParseBool:
    def test_true_values(self):
        for v in ["true", "True", "TRUE", "1", "yes", "y", "t", " yes ", "Y"]:
            assert parse_bool(v) is True

    def test_false_values(self):
        for v in ["false", "False", "FALSE", "0", "no", "n", "", "  no  "]:
            assert parse_bool(v) is False

    def test_none_is_false(self):
        assert parse_bool(None) is False

    def test_unknown_string_is_false(self):
        # Critical: bool("False") == True in Python, parse_bool must not.
        assert parse_bool("False") is False
        assert parse_bool("0") is False


class TestCsvImport:
    def test_parse_csv_success(self):
        content = b"name,surname,phone\nIvan,Ivanov,+7999\nPetr,Petrov,+7888"
        headers, rows = parse_csv(content)
        assert headers == ["name", "surname", "phone"]
        assert len(rows) == 2
        assert rows[0]["name"] == "Ivan"
        assert rows[1]["phone"] == "+7888"

    def test_parse_csv_empty_content(self):
        content = b""
        with pytest.raises(ValueError, match="CSV file has no headers"):
            parse_csv(content)

    def test_csv_import_result(self):
        result = CsvImportResult()
        assert result.imported == 0
        assert result.errors == []
        result.add_error(5, "Invalid name")
        assert len(result.errors) == 1
        assert result.errors[0]["row"] == 5
