"""Tests for Chapter 2, Exercise 2 — docstring parsing."""

from chapters.ch02_tools.exercises.exercise_2_docstring import parse_docstring


class TestEmpty:
    def test_none(self):
        assert parse_docstring(None) == ("", {})

    def test_empty_string(self):
        assert parse_docstring("") == ("", {})


class TestSummaryOnly:
    def test_one_liner(self):
        assert parse_docstring("Add two numbers.") == ("Add two numbers.", {})

    def test_multi_paragraph(self):
        summary, params = parse_docstring(
            """Short line.

            Longer explanation.
            """
        )
        assert summary.startswith("Short line.")
        assert "Longer explanation." in summary
        assert params == {}


class TestArgs:
    DOC = '''Look up the weather.

    More detail here.

    Args:
        city: City name, e.g. "Delhi".
        unit (str): Temperature unit. Defaults to
            celsius if omitted.
        days: Forecast length.

    Returns:
        A description of the weather.
    '''

    def test_summary_stops_before_args(self):
        summary, _ = parse_docstring(self.DOC)
        assert summary.startswith("Look up the weather.")
        assert "More detail here." in summary
        assert "city" not in summary
        assert "Returns" not in summary

    def test_extracts_params(self):
        _, params = parse_docstring(self.DOC)
        assert set(params) == {"city", "unit", "days"}

    def test_keeps_inline_punctuation(self):
        _, params = parse_docstring(self.DOC)
        assert params["city"] == 'City name, e.g. "Delhi".'

    def test_strips_the_type_annotation_in_parens(self):
        _, params = parse_docstring(self.DOC)
        assert params["unit"].startswith("Temperature unit.")
        assert "(str)" not in params["unit"]

    def test_joins_continuation_lines(self):
        _, params = parse_docstring(self.DOC)
        assert params["unit"] == "Temperature unit. Defaults to celsius if omitted."

    def test_returns_section_ends_the_block(self):
        _, params = parse_docstring(self.DOC)
        assert "A description of the weather." not in params.values()


class TestVariants:
    def test_parameters_header(self):
        _, params = parse_docstring("Do it.\n\nParameters:\n    x: the x\n")
        assert params == {"x": "the x"}

    def test_arguments_header(self):
        _, params = parse_docstring("Do it.\n\nArguments:\n    x: the x\n")
        assert params == {"x": "the x"}

    def test_strips_stars_from_names(self):
        _, params = parse_docstring("Do it.\n\nArgs:\n    *args: extras\n")
        assert "args" in params

    def test_raises_section_ends_the_block(self):
        _, params = parse_docstring(
            "Do it.\n\nArgs:\n    x: the x\n\nRaises:\n    ValueError: nope\n"
        )
        assert set(params) == {"x"}
