"""Canonical Entity Modeling conflict detection.

Detects candidate canonical entity conflicts across semantic models and ontologies
using configurable name-similarity (rapidfuzz normalized Levenshtein) and a synonym
seed loaded from entity-synonyms.yaml.

FR-005: Detect candidate canonical entity conflicts.
FR-006: Surface specific disagreement dimensions per conflict.
"""
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

import yaml
from rapidfuzz import fuzz

from scanner.lib.scanner.findings import (
    CanonicalEntityConflict,
    Disagreement,
    EntityDefinition,
    Measure,
    Ontology,
    Relationship,
    SemanticModel,
)

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.85
_SYNONYMS_FILE = Path(__file__).parent / "entity-synonyms.yaml"

# Guard against O(n²) fuzzy comparisons on very large workspaces.
# 2 000 candidates → ~2M comparisons, which completes in < 2 s on typical hardware.
# Beyond this threshold the comparison budget is unpredictable; skip and warn.
MAX_CANDIDATES = 2_000

DISAGREEMENT_DIMENSIONS = (
    "primary_key",
    "join_logic",
    "filter_context",
    "measure_definition",
    "source_columns",
)


def _load_synonyms(path: Path = _SYNONYMS_FILE) -> list[frozenset[str]]:
    """Load synonym pairs as frozensets for order-independent lookup."""
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return [frozenset(pair) for pair in (data or {}).get("synonyms", [])]


def _normalize(name: str) -> str:
    return name.strip().lower()


def _are_similar(
    name_a: str,
    name_b: str,
    threshold: float,
    synonyms: list[frozenset[str]],
) -> bool:
    """Return True if two entity names are similar enough to be candidate conflicts."""
    if _normalize(name_a) == _normalize(name_b):
        return True
    # Synonym check — case-insensitive
    pair = frozenset({_normalize(name_a), _normalize(name_b)})
    for syn_pair in synonyms:
        if pair == frozenset(n.lower() for n in syn_pair):
            return True
    # Similarity check
    ratio = fuzz.ratio(name_a, name_b) / 100.0
    return ratio >= threshold


def _conflict_id(entity_name: str, source_ids: list[str]) -> str:
    """Stable, deterministic conflict ID."""
    key = entity_name.lower() + "|" + "|".join(sorted(source_ids))
    return "cem-" + hashlib.sha1(key.encode()).hexdigest()[:8]


def extract_entity_definition(
    source: SemanticModel | Ontology,
    entity_name: str,
) -> EntityDefinition | None:
    """Extract an EntityDefinition for a named entity from a semantic model or ontology.

    Returns None if the entity is not found in the source.
    """
    if isinstance(source, SemanticModel):
        table = next((t for t in source.tables if _normalize(t.name) == _normalize(entity_name)), None)
        if table is None:
            return None
        # Measures belonging to this table
        measure_names = [m.name for m in source.measures if _normalize(m.table) == _normalize(entity_name)]
        # Relationships where this entity is the "to" side (defining side)
        join_rels = [r for r in source.relationships if _normalize(r.to_table) == _normalize(entity_name)]
        return EntityDefinition(
            logical_entity_name=entity_name,
            source_type="semantic_model",
            source_id=source.model_id,
            source_name=source.name,
            primary_key_columns=list(table.primary_key_columns),
            join_relationships=join_rels,
            measure_names=measure_names,
            source_columns=list(table.source_columns),
            confidence=1.0,
        )

    if isinstance(source, Ontology):
        entity_type = next(
            (et for et in source.entity_types if _normalize(et.name) == _normalize(entity_name)),
            None,
        )
        if entity_type is None:
            return None

        # Primary key proxy: properties flagged as source attribution or named with
        # id/key/code tokens are the closest structural equivalent to a PK in an ontology.
        _pk_tokens = {"id", "key", "code", "identifier", "ref", "pk"}
        pk_proxy = [
            p.name for p in entity_type.properties
            if p.is_source_attribution
            or any(tok in _normalize(p.name) for tok in _pk_tokens)
        ]

        # Map OntologyRelationship → Relationship (cardinality unknown for ontologies).
        # Presence of relationships can still fire join_logic and filter_context dimensions.
        from scanner.lib.scanner.findings import Relationship as Rel  # noqa: PLC0415
        join_rels = [
            Rel(
                from_table=r.from_entity,
                from_column="",
                to_table=r.to_entity,
                to_column="",
                cardinality="unknown",
                cross_filter_direction="unknown",
            )
            for r in entity_type.relationships
        ]

        return EntityDefinition(
            logical_entity_name=entity_name,
            source_type="ontology",
            source_id=source.ontology_id,
            source_name=source.name,
            primary_key_columns=pk_proxy,
            join_relationships=join_rels,
            measure_names=[],  # ontologies have no measures
            source_columns=[p.name for p in entity_type.properties],
            confidence=1.0,
        )

    return None


def _build_disagreements(definitions: list[EntityDefinition]) -> list[Disagreement]:
    """Detect disagreement dimensions across two or more EntityDefinitions."""
    if len(definitions) < 2:
        return []

    disagreements: list[Disagreement] = []
    first = definitions[0]

    # primary_key — report both "keys differ" and "some definitions missing keys"
    pk_sets = [frozenset(d.primary_key_columns) for d in definitions if d.primary_key_columns]
    if len(pk_sets) >= 2 and len(set(pk_sets)) > 1:
        pk_desc = "; ".join(
            f"{d.source_name}: [{', '.join(d.primary_key_columns) or 'none'}]"
            for d in definitions
            if d.primary_key_columns
        )
        disagreements.append(Disagreement(
            dimension="primary_key",
            description=f"Primary keys differ across definitions: {pk_desc}",
        ))
    if any(not d.primary_key_columns for d in definitions):
        disagreements.append(Disagreement(
            dimension="primary_key",
            description=(
                "Some definitions declare no primary key: "
                + "; ".join(d.source_name for d in definitions if not d.primary_key_columns)
            ),
        ))

    # join_logic — detect when relationship cardinalities differ
    cardinalities = {
        frozenset(r.cardinality for r in d.join_relationships)
        for d in definitions
    }
    if len(cardinalities) > 1:
        disagreements.append(Disagreement(
            dimension="join_logic",
            description="Join relationship cardinalities differ across definitions.",
        ))

    # filter_context — detect when cross-filter directions differ
    cross_filters = {
        frozenset(r.cross_filter_direction for r in d.join_relationships)
        for d in definitions
        if d.join_relationships
    }
    if len(cross_filters) > 1:
        disagreements.append(Disagreement(
            dimension="filter_context",
            description="Cross-filter directions differ across definitions.",
        ))

    # measure_definition — detect measure name set differences
    measure_sets = [frozenset(d.measure_names) for d in definitions]
    if len(set(measure_sets)) > 1:
        disagreements.append(Disagreement(
            dimension="measure_definition",
            description=(
                "Measure definitions differ across artifact definitions for this entity: "
                + "; ".join(f"{d.source_name}: [{', '.join(sorted(d.measure_names)) or 'none'}]" for d in definitions)
            ),
        ))

    # source_columns — detect when column sets differ significantly
    col_sets = [frozenset(_normalize(c) for c in d.source_columns) for d in definitions if d.source_columns]
    if len(col_sets) >= 2:
        all_cols = set.union(*[set(s) for s in col_sets])
        shared = set.intersection(*[set(s) for s in col_sets])
        if len(all_cols) > 0 and len(shared) / len(all_cols) < 0.5:
            disagreements.append(Disagreement(
                dimension="source_columns",
                description="Source column overlap is less than 50% across definitions — likely different underlying tables.",
            ))

    return disagreements


def _structural_similarity(defn_a: EntityDefinition, defn_b: EntityDefinition) -> float:
    """Return a 0.0–1.0 score measuring how structurally similar two EntityDefinitions are.

    Computes a weighted combination of:
    - Primary-key column overlap (weight 0.5) — strongest signal of same concept
    - Source-column Jaccard similarity (weight 0.3)
    - Measure-name Jaccard similarity (weight 0.2)

    Returns 1.0 when all three dimensions are identical; 0.0 when none overlap.
    """
    def _jaccard(a: set, b: set) -> float:
        union = a | b
        return len(a & b) / len(union) if union else 0.0

    pk_a = {_normalize(c) for c in defn_a.primary_key_columns}
    pk_b = {_normalize(c) for c in defn_b.primary_key_columns}
    pk_score = _jaccard(pk_a, pk_b) if (pk_a or pk_b) else 0.0

    col_a = {_normalize(c) for c in defn_a.source_columns}
    col_b = {_normalize(c) for c in defn_b.source_columns}
    col_score = _jaccard(col_a, col_b) if (col_a or col_b) else 0.0

    meas_a = {_normalize(m) for m in defn_a.measure_names}
    meas_b = {_normalize(m) for m in defn_b.measure_names}
    meas_score = _jaccard(meas_a, meas_b) if (meas_a or meas_b) else 0.0

    return 0.5 * pk_score + 0.3 * col_score + 0.2 * meas_score


# Minimum weighted structural similarity to flag two unlike-named entities as twins.
# 0.7 requires strong PK overlap OR broad column overlap — avoids false positives
# from entities that happen to share a small number of common column names.
STRUCTURAL_TWIN_THRESHOLD = 0.7


def _find_structural_twins(
    candidates: list[tuple[str, SemanticModel | Ontology]],
    unclaimed: list[bool],
    synonyms: list[frozenset[str]],
    threshold: float,
) -> list[list[tuple[str, SemanticModel | Ontology]]]:
    """Second pass: cluster structurally similar but unlike-named entities.

    Runs only over candidates that were not already clustered in the first (name)
    pass — i.e., singletons after name-similarity grouping.  For each remaining
    unclustered entity, extracts its EntityDefinition and compares structurally
    with other unclustered entities from *different* source artifacts.

    Only pairs with meaningful structural content (≥1 PK column or ≥3 source
    columns) are compared; empty definitions are skipped to avoid phantom clusters
    of empty entities.
    """
    unvisited_indices = [i for i, eligible in enumerate(unclaimed) if eligible]
    structural_clusters: list[list[tuple[str, SemanticModel | Ontology]]] = []
    struct_visited = [False] * len(unvisited_indices)

    # Pre-compute EntityDefinitions for all unvisited candidates
    defns: list[EntityDefinition | None] = []
    for idx in unvisited_indices:
        name, source = candidates[idx]
        defns.append(extract_entity_definition(source, name))

    for i, pos_i in enumerate(unvisited_indices):
        if struct_visited[i]:
            continue
        defn_i = defns[i]
        # Skip if definition is empty (no PK and fewer than 3 columns)
        if defn_i is None or (
            not defn_i.primary_key_columns and len(defn_i.source_columns) < 3
        ):
            continue

        name_i, source_i = candidates[pos_i]
        sid_i = source_i.model_id if isinstance(source_i, SemanticModel) else source_i.ontology_id
        cluster: list[tuple[str, SemanticModel | Ontology]] = [(name_i, source_i)]
        struct_visited[i] = True

        for j, pos_j in enumerate(unvisited_indices):
            if j <= i or struct_visited[j]:
                continue
            defn_j = defns[j]
            if defn_j is None or (
                not defn_j.primary_key_columns and len(defn_j.source_columns) < 3
            ):
                continue
            name_j, source_j = candidates[pos_j]
            sid_j = source_j.model_id if isinstance(source_j, SemanticModel) else source_j.ontology_id
            if sid_i == sid_j:
                continue  # same artifact can't twin with itself
            # Skip if names are similar — already covered by name-similarity pass
            if _are_similar(name_i, name_j, threshold, synonyms):
                continue
            if _structural_similarity(defn_i, defn_j) >= STRUCTURAL_TWIN_THRESHOLD:
                cluster.append((name_j, source_j))
                struct_visited[j] = True

        if len(cluster) >= 2:
            structural_clusters.append(cluster)

    return structural_clusters


def detect_canonical_entity_conflicts(
    models: list[SemanticModel],
    ontologies: list[Ontology],
    threshold: float = DEFAULT_THRESHOLD,
    synonyms_path: Path = _SYNONYMS_FILE,
) -> tuple[list[CanonicalEntityConflict], bool]:
    """Detect candidate canonical entity conflicts across all source artifacts.

    Args:
        models: Semantic models from the workspace.
        ontologies: Fabric IQ ontologies from the workspace.
        threshold: Similarity threshold (0.0–1.0); default 0.85.
        synonyms_path: Path to the entity-synonyms.yaml file.

    Returns:
        A tuple of (conflicts, was_assessed) where was_assessed=False means the
        scan was skipped (candidate count exceeded MAX_CANDIDATES) — the caller
        must pass has_signals=False to the scorer so the workspace does not
        receive a false Excellent score.
    """
    synonyms = _load_synonyms(synonyms_path)

    # Collect all (entity_name, source) pairs
    candidates: list[tuple[str, SemanticModel | Ontology]] = []
    for model in models:
        for table in model.tables:
            candidates.append((table.name, model))
    for ontology in ontologies:
        for entity_type in ontology.entity_types:
            candidates.append((entity_type.name, ontology))

    if not candidates:
        return [], True

    if len(candidates) > MAX_CANDIDATES:
        logger.warning(
            "Candidate entity count (%d) exceeds MAX_CANDIDATES (%d). "
            "Canonical entity conflict detection skipped to avoid O(n²) budget overrun. "
            "Consider narrowing the scan scope or increasing MAX_CANDIDATES if appropriate.",
            len(candidates),
            MAX_CANDIDATES,
        )
        return [], False  # was_assessed=False → caller must pass has_signals=False

    # Group candidates by similarity / synonym clusters
    # Each cluster is a list of (entity_name, source) pairs
    visited: list[bool] = [False] * len(candidates)
    # claimed tracks which candidates actually joined a multi-member name conflict cluster
    claimed: set[int] = set()
    conflicts: list[CanonicalEntityConflict] = []

    for i in range(len(candidates)):
        if visited[i]:
            continue
        cluster_name, cluster_source = candidates[i]
        cluster: list[tuple[str, SemanticModel | Ontology]] = [(cluster_name, cluster_source)]
        visited[i] = True

        for j in range(i + 1, len(candidates)):
            if visited[j]:
                continue
            other_name, other_source = candidates[j]
            # Skip if same source artifact — can't conflict with itself
            source_id_i = cluster_source.model_id if isinstance(cluster_source, SemanticModel) else cluster_source.ontology_id
            source_id_j = other_source.model_id if isinstance(other_source, SemanticModel) else other_source.ontology_id
            if source_id_i == source_id_j:
                continue
            if _are_similar(cluster_name, other_name, threshold, synonyms):
                cluster.append((other_name, other_source))
                visited[j] = True

        if len(cluster) < 2:
            continue  # Singleton — eligible for structural-twin pass

        # Mark all cluster members as claimed (won't be re-examined structurally)
        for ent_name, source in cluster:
            src_id = source.model_id if isinstance(source, SemanticModel) else source.ontology_id
            for idx, (n, s) in enumerate(candidates):
                s_id = s.model_id if isinstance(s, SemanticModel) else s.ontology_id
                if n == ent_name and s_id == src_id:
                    claimed.add(idx)

        # Build EntityDefinitions for each cluster member
        definitions: list[EntityDefinition] = []
        for ent_name, source in cluster:
            defn = extract_entity_definition(source, ent_name)
            if defn is not None:
                defn.logical_entity_name = cluster_name  # Normalize to cluster representative
                definitions.append(defn)

        if len(definitions) < 2:
            continue

        disagreements = _build_disagreements(definitions)
        source_ids = [d.source_id for d in definitions]

        conflicts.append(
            CanonicalEntityConflict(
                conflict_id=_conflict_id(cluster_name, source_ids),
                logical_entity_name=cluster_name,
                definitions=definitions,
                disagreements=disagreements,
                confirmed=False,
            )
        )

    # Second pass: structural-twin detection for unclaimed (singleton) entities
    unclaimed_mask = [i not in claimed for i in range(len(candidates))]
    structural_clusters = _find_structural_twins(candidates, unclaimed_mask, synonyms, threshold)
    for cluster in structural_clusters:
        if len(cluster) < 2:
            continue
        # Use the first entity name as the cluster representative label
        cluster_name = cluster[0][0]
        definitions = []
        for ent_name, source in cluster:
            defn = extract_entity_definition(source, ent_name)
            if defn is not None:
                definitions.append(defn)
        if len(definitions) < 2:
            continue
        disagreements = _build_disagreements(definitions)
        # Mark as structural twin in description via a special conflict_id prefix
        source_ids = [d.source_id for d in definitions]
        twin_id = "cem-st-" + hashlib.sha1(
            "|".join(d.logical_entity_name + d.source_id for d in definitions).encode()
        ).hexdigest()[:8]
        conflicts.append(
            CanonicalEntityConflict(
                conflict_id=twin_id,
                logical_entity_name=f"{cluster_name} [structural twin]",
                definitions=definitions,
                disagreements=disagreements,
                confirmed=False,
            )
        )

    return conflicts, True


# ---------------------------------------------------------------------------
# Ceiling note (honest communication of detection limits)
# ---------------------------------------------------------------------------

CEILING_NOTE = (
    "Canonical Entity Modeling uses two clustering paths. "
    "Primary path: name-similarity and synonym pairs — detects conflicts among consistently-named entities. "
    "Secondary path: structural-twin detection — clusters entities with near-identical key/column shapes "
    "even when names differ (e.g., 'Customer' vs 'Account' with shared primary-key columns). "
    "Entities with unlike names AND no structural overlap (no shared keys or columns) "
    "cannot be detected automatically; the synonym file should be extended for known cross-system aliases. "
    "A low conflict count is a prompt to ask: 'do you call the same business concept different names "
    "in different systems?' — not a verdict that canonical entity conflicts do not exist."
)
