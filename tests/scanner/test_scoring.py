"""Tests for scoring.py — must be written before scoring.py is implemented.

Tests verify:
- All threshold bands produce correct scores
- not_assessed status for Layered Modeling and Steward-Loop Modeling with no signals
- RuntimeError on missing rubric
- RuntimeError on unknown schema_version
"""
import os
import textwrap

import pytest
import yaml

# The module under test — import will succeed once scoring.py exists.
from scanner.lib.scanner.scoring import compute_score, load_rubric


RUBRIC_V1 = {
    "schema_version": "1.0",
    "disciplines": {
        "canonical_entity_modeling": {
            "thresholds": [
                {"max_findings": 0, "score": 4},
                {"max_findings": 2, "score": 3},
                {"max_findings": 5, "score": 2},
                {"max_findings": 10, "score": 1},
                {"score": 0},
            ]
        },
        "field_level_lineage": {
            "thresholds": [
                {"max_findings": 0, "score": 4},
                {"max_findings": 2, "score": 3},
                {"max_findings": 5, "score": 2},
                {"max_findings": 10, "score": 1},
                {"score": 0},
            ]
        },
        "layered_modeling": {
            "thresholds": [
                {"max_findings": 0, "score": 4},
                {"max_findings": 2, "score": 3},
                {"max_findings": 5, "score": 2},
                {"max_findings": 10, "score": 1},
                {"score": 0},
            ]
        },
        "steward_loop_modeling": {
            "thresholds": [
                {"max_findings": 0, "score": 4},
                {"max_findings": 2, "score": 3},
                {"max_findings": 5, "score": 2},
                {"max_findings": 10, "score": 1},
                {"score": 0},
            ]
        },
    },
}


class TestThresholdBands:
    """Verify score assignment for every significant finding count boundary."""

    @pytest.mark.parametrize("finding_count,expected_score", [
        (0, 4),   # exactly 0 findings → top score
        (1, 3),   # 1 finding → band 3
        (2, 3),   # 2 findings → band 3 (inclusive upper bound)
        (3, 2),   # 3 findings → band 2
        (5, 2),   # 5 findings → band 2 (inclusive)
        (6, 1),   # 6 findings → band 1
        (10, 1),  # 10 findings → band 1 (inclusive)
        (11, 0),  # 11 findings → catch-all band
        (99, 0),  # many findings → catch-all band
    ])
    def test_canonical_entity_modeling_bands(self, finding_count, expected_score):
        result = compute_score("canonical_entity_modeling", finding_count, RUBRIC_V1)
        assert result.score == expected_score
        assert result.discipline == "canonical_entity_modeling"
        assert result.assessment_status == "assessed"
        assert result.finding_count == finding_count
        assert result.rubric_version == "1.0"

    @pytest.mark.parametrize("finding_count,expected_score", [
        (0, 4), (1, 3), (2, 3), (3, 2), (5, 2), (6, 1), (10, 1), (11, 0),
    ])
    def test_field_level_lineage_bands(self, finding_count, expected_score):
        result = compute_score("field_level_lineage", finding_count, RUBRIC_V1)
        assert result.score == expected_score
        assert result.assessment_status == "assessed"


class TestNotAssessedDisciplines:
    """Layered Modeling and Steward-Loop Modeling return not_assessed with no signals."""

    def test_layered_modeling_not_assessed_when_no_signals(self):
        result = compute_score("layered_modeling", finding_count=0, rubric=RUBRIC_V1, has_signals=False)
        assert result.assessment_status == "not_assessed"
        assert result.score is None
        assert result.discipline == "layered_modeling"
        assert "not assessed" in result.rationale.lower()

    def test_steward_loop_modeling_not_assessed_when_no_signals(self):
        result = compute_score("steward_loop_modeling", finding_count=0, rubric=RUBRIC_V1, has_signals=False)
        assert result.assessment_status == "not_assessed"
        assert result.score is None

    def test_layered_modeling_assessed_when_signals_present(self):
        result = compute_score("layered_modeling", finding_count=2, rubric=RUBRIC_V1, has_signals=True)
        assert result.assessment_status == "assessed"
        assert result.score == 3

    def test_steward_loop_modeling_assessed_when_signals_present(self):
        result = compute_score("steward_loop_modeling", finding_count=0, rubric=RUBRIC_V1, has_signals=True)
        assert result.assessment_status == "assessed"
        assert result.score == 4


class TestRubricErrors:
    """scoring.py raises RuntimeError on bad rubric inputs."""

    def test_missing_rubric_file_raises(self, tmp_path):
        nonexistent = str(tmp_path / "no-rubric.yaml")
        with pytest.raises(RuntimeError, match="rubric"):
            load_rubric(nonexistent)

    def test_unknown_schema_version_raises(self):
        bad_rubric = {**RUBRIC_V1, "schema_version": "99.0"}
        with pytest.raises(RuntimeError, match="schema_version"):
            compute_score("canonical_entity_modeling", 0, bad_rubric)

    def test_unknown_discipline_raises(self):
        with pytest.raises((RuntimeError, KeyError)):
            compute_score("made_up_discipline", 0, RUBRIC_V1)

    def test_empty_rubric_raises(self):
        with pytest.raises((RuntimeError, KeyError, TypeError)):
            compute_score("canonical_entity_modeling", 0, {})


class TestRubricFileLoading:
    """load_rubric reads a valid YAML file and returns the dict."""

    def test_load_valid_rubric_file(self, tmp_path):
        rubric_file = tmp_path / "scoring-rubric.yaml"
        rubric_file.write_text(yaml.dump(RUBRIC_V1), encoding="utf-8")
        rubric = load_rubric(str(rubric_file))
        assert rubric["schema_version"] == "1.0"
        assert "canonical_entity_modeling" in rubric["disciplines"]
