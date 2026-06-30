"""Tests for the exact-"phrase" search matcher (search mode C).

The whole-word boundary is the crux: searching "software engineer" must NOT
return "Software Engineering Manager", even though it's a substring.
"""
from app.routers.jobs import _phrase_pattern


def _hit(query: str, text: str) -> bool:
    pat = _phrase_pattern(query)
    assert pat is not None
    return bool(pat.search(text.lower()))


class TestPhrasePattern:
    def test_matches_exact_phrase(self):
        assert _hit("software engineer", "Software Engineer")

    def test_matches_phrase_within_longer_title(self):
        assert _hit("software engineer", "Senior Software Engineer")
        assert _hit("software engineer", "Software Engineer II")

    def test_excludes_engineering_manager(self):
        # The whole point: "engineer" must not match inside "engineering".
        assert not _hit("software engineer", "Software Engineering Manager")

    def test_excludes_unrelated(self):
        assert not _hit("software engineer", "Software Developer")

    def test_punctuation_is_a_word_boundary(self):
        assert _hit("software engineer", "Software Engineer, Backend")
        assert _hit("software engineer", "Software Engineer / Architect")

    def test_tolerates_irregular_spacing(self):
        assert _hit("software engineer", "software   engineer")

    def test_single_word_is_whole_word(self):
        assert _hit("manager", "Engineering Manager")
        assert not _hit("manager", "Management Consultant")

    def test_case_insensitive(self):
        assert _hit("Staff Engineer", "staff engineer")

    def test_empty_query_yields_no_pattern(self):
        assert _phrase_pattern("") is None
        assert _phrase_pattern("   ") is None
