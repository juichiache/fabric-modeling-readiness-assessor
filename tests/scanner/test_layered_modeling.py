"""Tests for layered_modeling.py — Discipline 3."""
import pytest

from scanner.lib.scanner.findings import SemanticModel, Table, Measure
from scanner.lib.scanner.layered_modeling import (
    detect_layering_gaps,
    severity_for_gap,
    remediation_hint_for_gap,
    LAYER_BUCKETS,
)


def make_model(model_id: str, table_names: list[str], measures: list[str] | None = None) -> SemanticModel:
    return SemanticModel(
        model_id=model_id,
        name=f"Model-{model_id}",
        workspace_id="ws-test",
        tables=[Table(name=n) for n in table_names],
        measures=[Measure(name=m, table="", expression="") for m in (measures or [])],
    )


class TestNoModels:
    def test_empty_list_returns_no_gaps(self):
        gaps = detect_layering_gaps([])
        assert gaps == []


class TestAllThreeLayers:
    def test_bronze_silver_gold_prefix_no_gap(self):
        model = make_model("m1", ["bronze_customer", "silver_customer", "gold_customer"])
        gaps = detect_layering_gaps([model])
        assert gaps == []

    def test_raw_stage_mart_no_gap(self):
        model = make_model("m2", ["raw_orders", "staged_orders", "mart_orders"])
        gaps = detect_layering_gaps([model])
        assert gaps == []

    def test_camel_case_tokens_recognized(self):
        # BronzeCustomer → ["bronze", "customer"]
        model = make_model("m3", ["BronzeCustomer", "SilverCustomer", "GoldCustomer"])
        gaps = detect_layering_gaps([model])
        assert gaps == []

    def test_mixed_synonyms_across_tables(self):
        # Uses synonyms: landing (bronze), prepared (silver), published (gold)
        model = make_model("m4", ["LandingOrders", "PreparedOrders", "PublishedOrders"])
        gaps = detect_layering_gaps([model])
        assert gaps == []


class TestZeroLayers:
    def test_flat_table_names_high_severity_gap(self):
        model = make_model("m5", ["Customer", "Order", "Product"])
        gaps = detect_layering_gaps([model])
        assert len(gaps) == 1
        assert gaps[0].model_id == "m5"
        assert gaps[0].detected_layers == []
        assert sorted(gaps[0].missing_layers) == ["bronze", "gold", "silver"]

    def test_zero_layers_severity_is_high(self):
        model = make_model("m6", ["Customers", "Orders"])
        gaps = detect_layering_gaps([model])
        assert severity_for_gap(gaps[0]) == "high"

    def test_zero_layers_remediation_mentions_staging(self):
        model = make_model("m7", ["Dim_Customer"])
        gaps = detect_layering_gaps([model])
        hint = remediation_hint_for_gap(gaps[0])
        assert "staging" in hint.lower() or "layer" in hint.lower() or "bronze" in hint.lower()


class TestOneLayer:
    def test_gold_only_medium_severity(self):
        model = make_model("m8", ["gold_customer", "SalesReport"])
        gaps = detect_layering_gaps([model])
        assert len(gaps) == 1
        assert gaps[0].detected_layers == ["gold"]
        assert severity_for_gap(gaps[0]) == "medium"

    def test_bronze_only_medium_severity(self):
        model = make_model("m9", ["raw_ingest", "source_data"])
        gaps = detect_layering_gaps([model])
        assert len(gaps) == 1
        assert severity_for_gap(gaps[0]) == "medium"


class TestTwoLayers:
    def test_bronze_gold_low_severity(self):
        model = make_model("m10", ["landing_orders", "mart_orders"])
        gaps = detect_layering_gaps([model])
        assert len(gaps) == 1
        assert sorted(gaps[0].detected_layers) == ["bronze", "gold"]
        assert severity_for_gap(gaps[0]) == "low"

    def test_silver_gold_low_severity(self):
        model = make_model("m11", ["staging_orders", "serving_orders"])
        gaps = detect_layering_gaps([model])
        assert len(gaps) == 1
        assert severity_for_gap(gaps[0]) == "low"


class TestTableCount:
    def test_table_count_reflects_model(self):
        model = make_model("m12", ["t1", "t2", "t3", "t4"])
        gaps = detect_layering_gaps([model])
        assert len(gaps) == 1
        assert gaps[0].table_count == 4


class TestEmptyTablesModel:
    def test_model_with_no_tables_skipped(self):
        model = SemanticModel(model_id="m13", name="Empty", workspace_id="ws", tables=[])
        gaps = detect_layering_gaps([model])
        assert gaps == []


class TestGapId:
    def test_gap_id_is_deterministic(self):
        model = make_model("m14", ["Customer"])
        g1 = detect_layering_gaps([model])[0]
        g2 = detect_layering_gaps([model])[0]
        assert g1.gap_id == g2.gap_id

    def test_gap_id_prefixed_lm(self):
        model = make_model("m15", ["Customer"])
        gap = detect_layering_gaps([model])[0]
        assert gap.gap_id.startswith("lm-")


class TestMultipleModels:
    def test_each_model_assessed_independently(self):
        ok_model = make_model("ok", ["raw_x", "silver_x", "gold_x"])
        bad_model = make_model("bad", ["Customers"])
        gaps = detect_layering_gaps([ok_model, bad_model])
        assert len(gaps) == 1
        assert gaps[0].model_id == "bad"

    def test_all_flat_models_all_gapped(self):
        models = [make_model(f"m{i}", ["Fact", "Dim"]) for i in range(3)]
        gaps = detect_layering_gaps(models)
        assert len(gaps) == 3


class TestLayerVocabBuckets:
    def test_all_buckets_non_empty(self):
        for name, vocab in LAYER_BUCKETS.items():
            assert len(vocab) > 0, f"Bucket {name!r} is empty"

    def test_no_overlap_between_buckets(self):
        all_words: list[tuple[str, str]] = []
        for name, vocab in LAYER_BUCKETS.items():
            for word in vocab:
                all_words.append((word, name))
        seen: dict[str, str] = {}
        for word, bucket in all_words:
            assert word not in seen, (
                f"'{word}' appears in both '{seen[word]}' and '{bucket}' buckets"
            )
            seen[word] = bucket
