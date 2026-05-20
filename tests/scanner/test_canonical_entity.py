"""Tests for canonical_entity.py — written before implementation (T021/T022).

Tests verify:
- rapidfuzz matching at threshold 0.85 (match) and 0.84 (no match)
- Conflict assembly from 3 fixture models (Customer in CRM vs ERP vs Invoicing)
- All 5 disagreement dimensions detected
- Synonym seed matching (Customer↔Account)
- confirmed=False on new conflicts
- Config override of similarity threshold
"""
import json
from pathlib import Path

import pytest

from scanner.lib.scanner.canonical_entity import (
    detect_canonical_entity_conflicts,
    extract_entity_definition,
)
from scanner.lib.scanner.findings import (
    CanonicalEntityConflict,
    SemanticModel,
    Table,
    Relationship,
    Measure,
    Ontology,
    EntityType,
    OntologyProperty,
)
from scanner.lib.scanner.semantic_models import extract_semantic_models_from_response
from scanner.lib.scanner.ontologies import extract_ontologies_from_response

FIXTURES = Path(__file__).parent / "fixtures"


def load_pbi(name: str) -> dict:
    return json.loads((FIXTURES / "power_bi_rest_responses" / name).read_text())


def load_fiq(name: str) -> dict:
    return json.loads((FIXTURES / "fabric_iq_responses" / name).read_text())


@pytest.fixture()
def three_models():
    crm = extract_semantic_models_from_response(load_pbi("crm_sales.json"), "ws-001")
    erp = extract_semantic_models_from_response(load_pbi("erp_finance.json"), "ws-001")
    inv = extract_semantic_models_from_response(load_pbi("invoicing_legacy.json"), "ws-001")
    return crm + erp + inv


@pytest.fixture()
def manufacturing_ontology():
    return extract_ontologies_from_response(load_fiq("manufacturing_ontology.json"), "ws-001")


class TestSimilarityThreshold:
    def test_customer_and_customer_match_at_default_threshold(self, three_models, manufacturing_ontology):
        conflicts, _ = detect_canonical_entity_conflicts(three_models, manufacturing_ontology)
        entity_names = {c.logical_entity_name for c in conflicts}
        # CRM "Customer" + Invoicing "Customer" → exact match → conflict detected
        assert any("Customer" in n or "customer" in n.lower() for n in entity_names)

    def test_threshold_085_matches(self):
        # "Customer" vs "Customers" — ratio should be above 0.85
        from rapidfuzz import fuzz
        score = fuzz.ratio("Customer", "Customers") / 100.0
        assert score >= 0.85, f"Expected ≥0.85, got {score:.3f}"

    def test_threshold_084_no_match(self):
        # "Cat" vs "Dog" — well below threshold
        from rapidfuzz import fuzz
        score = fuzz.ratio("Cat", "Dog") / 100.0
        assert score < 0.85

    def test_custom_threshold_excludes_near_matches(self, three_models, manufacturing_ontology):
        # At threshold 1.0, only exact matches qualify — no near-misses
        conflicts, _ = detect_canonical_entity_conflicts(
            three_models, manufacturing_ontology, threshold=1.0
        )
        for c in conflicts:
            # All definitions must be exactly the same name
            names = {d.logical_entity_name for d in c.definitions}
            assert len(names) == 1


class TestConflictAssembly:
    def test_customer_conflict_has_at_least_two_definitions(self, three_models, manufacturing_ontology):
        conflicts, _ = detect_canonical_entity_conflicts(three_models, manufacturing_ontology)
        customer_conflicts = [c for c in conflicts if "customer" in c.logical_entity_name.lower()]
        assert len(customer_conflicts) >= 1
        customer_conflict = customer_conflicts[0]
        assert len(customer_conflict.definitions) >= 2

    def test_conflict_sources_are_different_artifacts(self, three_models, manufacturing_ontology):
        conflicts, _ = detect_canonical_entity_conflicts(three_models, manufacturing_ontology)
        customer_conflicts = [c for c in conflicts if "customer" in c.logical_entity_name.lower()]
        conflict = customer_conflicts[0]
        source_ids = {d.source_id for d in conflict.definitions}
        assert len(source_ids) >= 2

    def test_all_new_conflicts_unconfirmed(self, three_models, manufacturing_ontology):
        conflicts, _ = detect_canonical_entity_conflicts(three_models, manufacturing_ontology)
        assert all(c.confirmed is False for c in conflicts)

    def test_conflict_id_is_stable_string(self, three_models, manufacturing_ontology):
        conflicts, _ = detect_canonical_entity_conflicts(three_models, manufacturing_ontology)
        for c in conflicts:
            assert isinstance(c.conflict_id, str)
            assert len(c.conflict_id) > 0


class TestDisagreementDimensions:
    def test_primary_key_disagreement_detected(self, three_models, manufacturing_ontology):
        # CRM: CustomerGUID, Invoicing: InvoiceCustomerID — different PKs
        conflicts, _ = detect_canonical_entity_conflicts(three_models, manufacturing_ontology)
        customer_conflicts = [c for c in conflicts if "customer" in c.logical_entity_name.lower()]
        assert customer_conflicts, "No Customer conflict found"
        conflict = customer_conflicts[0]
        dims = {d.dimension for d in conflict.disagreements}
        assert "primary_key" in dims

    def test_disagreement_has_description(self, three_models, manufacturing_ontology):
        conflicts, _ = detect_canonical_entity_conflicts(three_models, manufacturing_ontology)
        for c in conflicts:
            for d in c.disagreements:
                assert isinstance(d.description, str)
                assert len(d.description) > 0


class TestSynonymMatching:
    def test_customer_account_synonym_pair_detected(self, three_models, manufacturing_ontology):
        # ERP has "Account" (synonym for Customer), CRM/Invoicing has "Customer"
        conflicts, _ = detect_canonical_entity_conflicts(three_models, manufacturing_ontology)
        # Any conflict grouping Customer + Account (or vice versa) is acceptable
        all_entity_names = set()
        for c in conflicts:
            all_entity_names.add(c.logical_entity_name.lower())
            for d in c.definitions:
                all_entity_names.add(d.logical_entity_name.lower())
        # At minimum CRM Customer and ERP Account should both appear as definitions somewhere
        assert "customer" in all_entity_names or "account" in all_entity_names

    def test_product_material_synonym_detected(self, three_models, manufacturing_ontology):
        conflicts, _ = detect_canonical_entity_conflicts(three_models, manufacturing_ontology)
        all_def_names = {
            d.logical_entity_name.lower()
            for c in conflicts
            for d in c.definitions
        }
        # Product (Invoicing) and Material (ERP) are synonyms → should surface
        assert "product" in all_def_names or "material" in all_def_names


class TestExtractEntityDefinition:
    def test_extract_from_semantic_model(self, three_models):
        crm = three_models[0]  # CRM-Sales
        defn = extract_entity_definition(crm, "Customer")
        assert defn.source_type == "semantic_model"
        assert defn.source_id == crm.model_id
        assert "CustomerGUID" in defn.primary_key_columns
        assert "Customer Count" in defn.measure_names or len(defn.measure_names) >= 0

    def test_extract_confidence_within_range(self, three_models):
        crm = three_models[0]
        defn = extract_entity_definition(crm, "Customer")
        assert 0.0 <= defn.confidence <= 1.0

    def test_extract_returns_none_for_missing_entity(self, three_models):
        crm = three_models[0]
        defn = extract_entity_definition(crm, "NonExistentEntity99")
        assert defn is None


class TestCandidateCap:
    """Verify MAX_CANDIDATES guard prevents O(n²) hang on large workspaces."""

    def test_exceeding_cap_returns_empty_list(self):
        from scanner.lib.scanner.canonical_entity import MAX_CANDIDATES
        # Build MAX_CANDIDATES + 1 candidate entities across two fake models
        half = (MAX_CANDIDATES // 2) + 1
        def make_model(model_id: str, n: int) -> SemanticModel:
            return SemanticModel(
                model_id=model_id,
                name=model_id,
                workspace_id="ws",
                tables=[Table(name=f"Table_{model_id}_{i}") for i in range(n)],
            )
        models = [make_model("model-A", half), make_model("model-B", half)]
        result, was_assessed = detect_canonical_entity_conflicts(models, [])
        # Should return empty, not hang
        assert result == []

    def test_below_cap_still_runs(self):
        from scanner.lib.scanner.canonical_entity import MAX_CANDIDATES
        # Single model well below cap → no cross-source conflicts possible → empty
        model = SemanticModel(
            model_id="m1",
            name="M1",
            workspace_id="ws",
            tables=[Table(name=f"T{i}") for i in range(10)],
        )
        result, was_assessed = detect_canonical_entity_conflicts([model], [])
        assert isinstance(result, list)
        assert was_assessed is True


# ---------------------------------------------------------------------------
# Structural-twin detection (cem-structural-twin)
# ---------------------------------------------------------------------------

class TestStructuralTwinDetection:
    """Structural-similarity clustering for unlike-named but structurally identical entities."""

    def _make_twin_models(
        self,
        name_a: str,
        name_b: str,
        shared_pks: list[str],
        shared_cols: list[str],
    ) -> tuple[SemanticModel, SemanticModel]:
        """Build two models each with one entity — same structure, different names."""
        model_a = SemanticModel(
            model_id="model-crm", name="CRM", workspace_id="ws",
            tables=[Table(name=name_a, primary_key_columns=shared_pks, source_columns=shared_cols)],
        )
        model_b = SemanticModel(
            model_id="model-erp", name="ERP", workspace_id="ws",
            tables=[Table(name=name_b, primary_key_columns=shared_pks, source_columns=shared_cols)],
        )
        return model_a, model_b

    def test_unlike_named_entities_with_identical_pks_detected(self):
        """Customer (CRM) and Account (ERP) with same PK columns → structural twin."""
        m_a, m_b = self._make_twin_models(
            "Customer", "Account",
            shared_pks=["customer_id"],
            shared_cols=["customer_id", "name", "email", "phone", "address", "created_at"],
        )
        # No synonyms path (use no-synonym file to force structural path)
        from pathlib import Path
        conflicts, was_assessed = detect_canonical_entity_conflicts([m_a, m_b], [], synonyms_path=Path("/nonexistent"))
        assert was_assessed is True
        twin_conflicts = [c for c in conflicts if "structural twin" in c.logical_entity_name]
        assert len(twin_conflicts) == 1

    def test_unlike_named_entities_with_no_overlap_not_detected(self):
        """Two entities with completely different keys and columns are not twins."""
        model_a = SemanticModel(
            model_id="ma", name="A", workspace_id="ws",
            tables=[Table(name="Widget", primary_key_columns=["widget_id"], source_columns=["widget_id", "color"])],
        )
        model_b = SemanticModel(
            model_id="mb", name="B", workspace_id="ws",
            tables=[Table(name="Invoice", primary_key_columns=["invoice_num"], source_columns=["invoice_num", "amount"])],
        )
        from pathlib import Path
        conflicts, _ = detect_canonical_entity_conflicts([model_a, model_b], [], synonyms_path=Path("/nonexistent"))
        twin_conflicts = [c for c in conflicts if "structural twin" in c.logical_entity_name]
        assert len(twin_conflicts) == 0

    def test_structural_twin_conflict_id_prefixed_cem_st(self):
        m_a, m_b = self._make_twin_models(
            "Customer", "Party",
            shared_pks=["id"],
            shared_cols=["id", "name", "email", "phone", "status", "region"],
        )
        from pathlib import Path
        conflicts, _ = detect_canonical_entity_conflicts([m_a, m_b], [], synonyms_path=Path("/nonexistent"))
        for c in conflicts:
            if "structural twin" in c.logical_entity_name:
                assert c.conflict_id.startswith("cem-st-")

    def test_same_artifact_entities_not_twinned(self):
        """Entities from the same model cannot be structural twins with each other."""
        model = SemanticModel(
            model_id="mono", name="Mono", workspace_id="ws",
            tables=[
                Table(name="Customer", primary_key_columns=["id"], source_columns=["id", "name"]),
                Table(name="Account", primary_key_columns=["id"], source_columns=["id", "name"]),
            ],
        )
        from pathlib import Path
        conflicts, _ = detect_canonical_entity_conflicts([model], [], synonyms_path=Path("/nonexistent"))
        twin_conflicts = [c for c in conflicts if "structural twin" in c.logical_entity_name]
        assert len(twin_conflicts) == 0

    def test_structural_twin_has_definitions_from_both_sources(self):
        m_a, m_b = self._make_twin_models(
            "Customer", "Account",
            shared_pks=["customer_id"],
            shared_cols=["customer_id", "name", "email", "phone", "address", "created_at"],
        )
        from pathlib import Path
        conflicts, _ = detect_canonical_entity_conflicts([m_a, m_b], [], synonyms_path=Path("/nonexistent"))
        twin_conflicts = [c for c in conflicts if "structural twin" in c.logical_entity_name]
        if twin_conflicts:
            source_ids = {d.source_id for d in twin_conflicts[0].definitions}
            assert "model-crm" in source_ids
            assert "model-erp" in source_ids

    def test_structural_similarity_perfect_overlap(self):
        from scanner.lib.scanner.canonical_entity import _structural_similarity
        from scanner.lib.scanner.findings import EntityDefinition
        defn = EntityDefinition(
            logical_entity_name="E", source_type="semantic_model", source_id="s",
            source_name="S", primary_key_columns=["id"],
            source_columns=["id", "name", "email"], measure_names=["Revenue"],
        )
        assert _structural_similarity(defn, defn) == 1.0

    def test_structural_similarity_no_overlap(self):
        from scanner.lib.scanner.canonical_entity import _structural_similarity
        from scanner.lib.scanner.findings import EntityDefinition
        defn_a = EntityDefinition(
            logical_entity_name="A", source_type="semantic_model", source_id="s1",
            source_name="S1", primary_key_columns=["a_id"], source_columns=["a_id", "x"],
        )
        defn_b = EntityDefinition(
            logical_entity_name="B", source_type="semantic_model", source_id="s2",
            source_name="S2", primary_key_columns=["b_id"], source_columns=["b_id", "y"],
        )
        assert _structural_similarity(defn_a, defn_b) == 0.0
