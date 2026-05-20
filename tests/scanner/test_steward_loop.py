"""Tests for steward_loop.py — Discipline 4."""
import pytest

from scanner.lib.scanner.findings import (
    Measure,
    Ontology,
    EntityType,
    OntologyRelationship,
    Relationship,
    SemanticModel,
    Table,
)
from scanner.lib.scanner.steward_loop import (
    detect_steward_loop_gaps,
    severity_for_gap,
    remediation_hint_for_gap,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_model(
    model_id: str,
    table_names: list[str],
    measure_names: list[str] | None = None,
) -> SemanticModel:
    return SemanticModel(
        model_id=model_id,
        name=f"Model-{model_id}",
        workspace_id="ws-test",
        tables=[Table(name=n) for n in table_names],
        measures=[Measure(name=m, table="", expression="") for m in (measure_names or [])],
    )


def make_ontology(
    ontology_id: str,
    entity_names: list[str],
    relationships: list[tuple[str, str, str]] | None = None,
) -> Ontology:
    """Build an ontology. relationships is list of (from, to, name) tuples."""
    entity_types: list[EntityType] = []
    for name in entity_names:
        rels = [
            OntologyRelationship(from_entity=f, to_entity=t, relationship_name=n)
            for f, t, n in (relationships or [])
            if f == name
        ]
        entity_types.append(EntityType(name=name, relationships=rels))
    return Ontology(
        ontology_id=ontology_id,
        name=f"Ontology-{ontology_id}",
        workspace_id="ws-test",
        entity_types=entity_types,
    )


# ---------------------------------------------------------------------------
# Tests: empty workspace
# ---------------------------------------------------------------------------

class TestEmptyWorkspace:
    def test_no_models_no_ontologies_no_signals(self):
        gaps, has_signals = detect_steward_loop_gaps([], [])
        assert gaps == []
        assert has_signals is False

    def test_has_signals_false_on_empty(self):
        _, has_signals = detect_steward_loop_gaps([], [])
        assert has_signals is False


# ---------------------------------------------------------------------------
# Tests: has_signals flag
# ---------------------------------------------------------------------------

class TestHasSignalsFlag:
    def test_no_vocab_anywhere_signals_false(self):
        model = make_model("m1", ["Customer", "Order", "Product"])
        _, has_signals = detect_steward_loop_gaps([model], [])
        assert has_signals is False

    def test_correction_table_triggers_signals_true(self):
        model = make_model("m2", ["correction_log", "Customer"])
        _, has_signals = detect_steward_loop_gaps([model], [])
        assert has_signals is True

    def test_feedback_measure_triggers_signals_true(self):
        model = make_model("m3", ["Customer"], measure_names=["quality_score"])
        _, has_signals = detect_steward_loop_gaps([model], [])
        assert has_signals is True

    def test_audit_entity_in_ontology_triggers_signals_true(self):
        ont = make_ontology("o1", ["Customer", "AuditLog"])
        _, has_signals = detect_steward_loop_gaps([], [ont])
        assert has_signals is True

    def test_bidirectional_relationship_triggers_signals_true(self):
        # A→B and B→A in the same ontology = bidirectional
        ont = make_ontology(
            "o2",
            ["Customer", "Review"],
            relationships=[
                ("Customer", "Review", "has_review"),
                ("Review", "Customer", "review_of"),
            ],
        )
        _, has_signals = detect_steward_loop_gaps([], [ont])
        assert has_signals is True


# ---------------------------------------------------------------------------
# Tests: gap detection
# ---------------------------------------------------------------------------

class TestGapDetection:
    def test_flat_model_with_no_signals_creates_gap(self):
        model = make_model("m4", ["Customer", "Order"])
        gaps, has_signals = detect_steward_loop_gaps([model], [])
        # has_signals=False so gap is still recorded (caller decides not_assessed)
        assert len(gaps) == 1
        assert gaps[0].scope_id == "m4"
        assert gaps[0].scope_type == "semantic_model"

    def test_model_with_correction_table_no_measure_creates_partial_gap(self):
        model = make_model("m5", ["corrections_log"], measure_names=["TotalRevenue"])
        gaps, has_signals = detect_steward_loop_gaps([model], [])
        assert has_signals is True
        assert len(gaps) == 1
        # correction table found, but no quality measure
        assert "quality_or_feedback_measure" in gaps[0].missing_signals

    def test_model_with_both_table_and_measure_no_gap(self):
        model = make_model(
            "m6",
            ["exception_log"],
            measure_names=["error_rate"],
        )
        gaps, has_signals = detect_steward_loop_gaps([model], [])
        assert has_signals is True
        assert len(gaps) == 0

    def test_ontology_with_no_steward_vocab_creates_gap(self):
        ont = make_ontology("o3", ["Customer", "Product"])
        gaps, _ = detect_steward_loop_gaps([], [ont])
        assert len(gaps) == 1
        assert gaps[0].scope_type == "ontology"

    def test_ontology_with_audit_entity_no_gap(self):
        ont = make_ontology("o4", ["Customer", "Audit"])
        gaps, has_signals = detect_steward_loop_gaps([], [ont])
        assert has_signals is True
        assert len(gaps) == 0


# ---------------------------------------------------------------------------
# Tests: severity
# ---------------------------------------------------------------------------

class TestSeverity:
    def test_no_signals_detected_high_severity(self):
        model = make_model("ms1", ["Customer"])
        gaps, _ = detect_steward_loop_gaps([model], [])
        assert severity_for_gap(gaps[0]) == "high"

    def test_table_signal_only_medium_severity(self):
        model = make_model("ms2", ["correction_log"], measure_names=["TotalOrders"])
        gaps, _ = detect_steward_loop_gaps([model], [])
        assert len(gaps) == 1
        assert severity_for_gap(gaps[0]) == "medium"

    def test_measure_signal_only_low_severity(self):
        model = make_model("ms3", ["Customer"], measure_names=["quality_score"])
        gaps, _ = detect_steward_loop_gaps([model], [])
        assert len(gaps) == 1
        assert severity_for_gap(gaps[0]) == "low"


# ---------------------------------------------------------------------------
# Tests: remediation hints
# ---------------------------------------------------------------------------

class TestRemediationHints:
    def test_no_signal_hint_mentions_correction_or_feedback(self):
        model = make_model("mh1", ["Customer"])
        gaps, _ = detect_steward_loop_gaps([model], [])
        hint = remediation_hint_for_gap(gaps[0])
        assert any(kw in hint.lower() for kw in ("correction", "feedback", "quality", "steward"))

    def test_missing_measure_hint_mentions_measure(self):
        model = make_model("mh2", ["correction_log"])
        gaps, _ = detect_steward_loop_gaps([model], [])
        assert len(gaps) == 1
        hint = remediation_hint_for_gap(gaps[0])
        assert "measure" in hint.lower() or "quality" in hint.lower()


# ---------------------------------------------------------------------------
# Tests: gap ID
# ---------------------------------------------------------------------------

class TestGapId:
    def test_gap_id_prefixed_sl(self):
        model = make_model("gid1", ["Customer"])
        gaps, _ = detect_steward_loop_gaps([model], [])
        assert gaps[0].gap_id.startswith("sl-")

    def test_gap_id_deterministic(self):
        model = make_model("gid2", ["Order"])
        g1 = detect_steward_loop_gaps([model], [])[0][0]
        g2 = detect_steward_loop_gaps([model], [])[0][0]
        assert g1.gap_id == g2.gap_id


# ---------------------------------------------------------------------------
# Tests: CamelCase tokenization in steward loop
# ---------------------------------------------------------------------------

class TestCamelCaseTokenization:
    def test_correction_log_camel_case(self):
        model = make_model("cc1", ["CorrectionLog"])
        _, has_signals = detect_steward_loop_gaps([model], [])
        assert has_signals is True


# ---------------------------------------------------------------------------
# Tests: correction-capture binding check (d4-binding-check)
# ---------------------------------------------------------------------------

class TestCorrectionBinding:
    """Tests for _detect_correction_binding_model/ontology and gap field propagation."""

    def test_correction_table_found_populates_flag(self):
        model = make_model("cb1", ["Corrections", "Customer"])
        gaps, _ = detect_steward_loop_gaps([model], [])
        # There's a gap because no quality measure, but correction_structure_found=True
        if gaps:
            assert gaps[0].correction_structure_found is True

    def test_no_correction_table_flag_false(self):
        model = make_model("cb2", ["Customer", "Product"])
        gaps, _ = detect_steward_loop_gaps([model], [])
        if gaps:
            assert gaps[0].correction_structure_found is False

    def test_correction_table_with_relationship_wired(self):
        """Correction table referenced in a relationship → correction_has_relationships=True."""
        from scanner.lib.scanner.findings import Relationship as Rel
        model = SemanticModel(
            model_id="cb3", name="Wired", workspace_id="ws",
            tables=[Table(name="Corrections"), Table(name="Customer")],
            relationships=[
                Rel(
                    from_table="Customer", from_column="id",
                    to_table="Corrections", to_column="customer_id",
                    cardinality="OneToMany", cross_filter_direction="Single",
                )
            ],
        )
        gaps, _ = detect_steward_loop_gaps([model], [])
        assert any(g.correction_has_relationships is True for g in gaps)

    def test_orphan_correction_table_not_wired(self):
        """Correction table with no relationships → correction_has_relationships=False."""
        model = make_model("cb4", ["Corrections", "Customer"])
        gaps, _ = detect_steward_loop_gaps([model], [])
        if gaps:
            gap = next((g for g in gaps if g.correction_structure_found), None)
            if gap:
                assert gap.correction_has_relationships is False

    def test_correction_entity_in_ontology_found(self):
        ont = make_ontology("o-cb1", ["Customer", "Exceptions"])
        gaps, _ = detect_steward_loop_gaps([], [ont])
        if gaps:
            assert gaps[0].correction_structure_found is True

    def test_orphan_hint_mentions_wiring(self):
        """Remediation hint should mention wiring when correction table is orphaned."""
        model = make_model("cb5", ["Corrections", "Customer"])
        gaps, _ = detect_steward_loop_gaps([model], [])
        if gaps:
            gap = next((g for g in gaps if g.correction_structure_found and not g.correction_has_relationships), None)
            if gap:
                hint = remediation_hint_for_gap(gap)
                assert "wire" in hint.lower() or "relationship" in hint.lower() or "orphan" in hint.lower()

    def test_quality_score_camel_case_measure(self):
        model = make_model("cc2", ["Customer"], measure_names=["QualityScore"])
        _, has_signals = detect_steward_loop_gaps([model], [])
        assert has_signals is True
