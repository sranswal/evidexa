"""Unit tests for Evidence Graph traversal, filtering, and pathfinding algorithms."""

from __future__ import annotations

from document_intelligence.domain.enums import GraphEdgePredicate, GraphNodeType
from document_intelligence.domain.models.graph import (
    GraphEdge,
    GraphNode,
    deterministic_edge_id,
    deterministic_node_id,
)
from document_intelligence.modules.graph.engine import (
    HARD_MAX_HOPS,
    EvidenceGraphEngine,
)
from document_intelligence.modules.graph.projector import ProjectedGraphData


def _build_test_graph() -> ProjectedGraphData:
    """Build a deterministic synthetic test graph with cycles and multi-hop branches.

    Topology:
        (Case)
          | CONTAINS_DOCUMENT
          v
        (Doc1) ---- REFERENCES_PO ----> (Doc2)
          | HAS_EVIDENCE                  | HAS_EVIDENCE
          v                               v
        (Ev1)                           (Ev2)
          ^                               ^
          | SUPPORTED_BY                  | SUPPORTED_BY
        (FF1)                           (CF1)
          |                               |
          +---------- PERTAINS_TO --------+
    """
    case_id = "test-case-c1"
    graph = ProjectedGraphData(case_id=case_id)

    def _add_n(nid: str, ntype: GraphNodeType, label: str) -> str:
        full_id = deterministic_node_id(case_id, ntype, nid)
        graph.add_node(
            GraphNode(
                id=full_id,
                case_id=case_id,
                node_type=ntype,
                source_entity_type=ntype.value,
                source_entity_id=nid,
                label=label,
                provenance={"document_id": nid if "doc" in nid else None},
            )
        )
        return full_id

    def _add_e(src: str, tgt: str, pred: str, status: str = "CONFIRMED") -> str:
        eid = deterministic_edge_id(case_id, src, pred, tgt)
        graph.add_edge(
            GraphEdge(
                id=eid,
                case_id=case_id,
                source_node_id=src,
                target_node_id=tgt,
                predicate=pred,
                status=status,
            )
        )
        return eid

    n_case = _add_n("c1", GraphNodeType.CASE, "Case 1")
    n_doc1 = _add_n("doc1", GraphNodeType.DOCUMENT, "Invoice.pdf")
    n_doc2 = _add_n("doc2", GraphNodeType.DOCUMENT, "PO.pdf")
    n_ev1 = _add_n("ev1", GraphNodeType.EVIDENCE, "Token 1")
    n_ev2 = _add_n("ev2", GraphNodeType.EVIDENCE, "Token 2")
    n_ff1 = _add_n("ff1", GraphNodeType.FORENSIC_FINDING, "Visual Anomaly")
    n_cf1 = _add_n("cf1", GraphNodeType.CONSISTENCY_FINDING, "Overrun Check")

    # Add edges
    _add_e(n_case, n_doc1, GraphEdgePredicate.CONTAINS_DOCUMENT.value, "CONFIRMED")
    _add_e(n_case, n_doc2, GraphEdgePredicate.CONTAINS_DOCUMENT.value, "CONFIRMED")
    _add_e(n_doc1, n_ev1, GraphEdgePredicate.HAS_EVIDENCE.value, "CONFIRMED")
    _add_e(n_doc2, n_ev2, GraphEdgePredicate.HAS_EVIDENCE.value, "CONFIRMED")
    _add_e(n_doc1, n_doc2, "REFERENCES_PURCHASE_ORDER", "CONFIRMED")
    _add_e(n_ff1, n_ev1, GraphEdgePredicate.SUPPORTED_BY.value, "CONFIRMED")
    _add_e(n_cf1, n_ev2, GraphEdgePredicate.SUPPORTED_BY.value, "CONFIRMED")
    _add_e(n_cf1, n_doc1, GraphEdgePredicate.COMPARES_DOCUMENT.value, "CONFIRMED")
    # Candidate edge
    _add_e(n_ff1, n_doc2, "SUSPECTS_COLLUSION", "CANDIDATE")

    return graph


class TestEvidenceGraphEngine:
    """Validate query, filtering, neighborhood, and path algorithms."""

    def test_query_filtering_by_node_type(self) -> None:
        """Filtering by node type must strictly limit returned nodes."""
        engine = EvidenceGraphEngine()
        graph = _build_test_graph()

        snapshot = engine.query_graph(
            graph=graph,
            node_types={GraphNodeType.DOCUMENT},
        )

        assert snapshot.total_nodes == 2
        for n in snapshot.nodes:
            assert n.node_type == GraphNodeType.DOCUMENT

        # Edges between those documents should be included
        assert len(snapshot.edges) == 1
        assert snapshot.edges[0].predicate == "REFERENCES_PURCHASE_ORDER"

    def test_query_filtering_by_status(self) -> None:
        """Filtering by edge status must isolate confirmed vs candidate connections."""
        engine = EvidenceGraphEngine()
        graph = _build_test_graph()

        # Confirmed-only query
        snap_conf = engine.query_graph(graph=graph, statuses={"CONFIRMED"})
        for e in snap_conf.edges:
            assert e.status == "CONFIRMED"

        # Candidate-only query
        snap_cand = engine.query_graph(graph=graph, statuses={"CANDIDATE"})
        for e in snap_cand.edges:
            assert e.status == "CANDIDATE"

    def test_query_pagination_and_truncation(self) -> None:
        """Setting small limits must report truncated=True accurately."""
        engine = EvidenceGraphEngine()
        graph = _build_test_graph()

        snapshot = engine.query_graph(graph=graph, limit=3, offset=0)
        assert len(snapshot.nodes) == 3
        assert snapshot.total_nodes == 7
        assert snapshot.truncated is True

    def test_get_neighborhood_expansion(self) -> None:
        """1-hop and 2-hop neighborhood expansion around Doc1."""
        engine = EvidenceGraphEngine()
        graph = _build_test_graph()

        doc1_id = deterministic_node_id("test-case-c1", GraphNodeType.DOCUMENT, "doc1")

        # 1-hop from Doc1
        n1 = engine.get_neighborhood(graph=graph, center_node_id=doc1_id, max_hops=1)
        node_labels_1 = {n.label for n in n1.nodes}
        assert "Invoice.pdf" in node_labels_1
        assert "Case 1" in node_labels_1
        assert "PO.pdf" in node_labels_1
        assert "Token 1" in node_labels_1
        assert n1.hops == 1
        assert n1.truncated is False

        # 2-hop from Doc1 should reach Token 2 (via PO.pdf) and Visual Anomaly (via Token 1)
        n2 = engine.get_neighborhood(graph=graph, center_node_id=doc1_id, max_hops=2)
        node_labels_2 = {n.label for n in n2.nodes}
        assert "Token 2" in node_labels_2
        assert "Visual Anomaly" in node_labels_2

    def test_get_neighborhood_hard_caps(self) -> None:
        """Passing extreme max_hops must be capped at HARD_MAX_HOPS."""
        engine = EvidenceGraphEngine()
        graph = _build_test_graph()
        doc1_id = deterministic_node_id("test-case-c1", GraphNodeType.DOCUMENT, "doc1")

        result = engine.get_neighborhood(graph=graph, center_node_id=doc1_id, max_hops=999)
        assert result.hops == HARD_MAX_HOPS

    def test_find_paths_direct_and_multihop(self) -> None:
        """Path search between Case and Token 1."""
        engine = EvidenceGraphEngine()
        graph = _build_test_graph()

        case_id = deterministic_node_id("test-case-c1", GraphNodeType.CASE, "c1")
        ev1_id = deterministic_node_id("test-case-c1", GraphNodeType.EVIDENCE, "ev1")

        res = engine.find_paths(graph=graph, source_node_id=case_id, target_node_id=ev1_id)
        assert res.total_paths_found >= 1

        path = res.paths[0]
        assert path.nodes[0].id == case_id
        assert path.nodes[-1].id == ev1_id
        assert path.length == 2  # Case -> Doc1 -> Ev1
        assert path.is_confirmed_only is True

    def test_find_paths_confirmed_only_filters_candidate_edges(self) -> None:
        """Path search requiring confirmed_only=True must ignore candidate edges."""
        engine = EvidenceGraphEngine()
        graph = _build_test_graph()

        ff1_id = deterministic_node_id("test-case-c1", GraphNodeType.FORENSIC_FINDING, "ff1")
        doc2_id = deterministic_node_id("test-case-c1", GraphNodeType.DOCUMENT, "doc2")

        # Without confirmed_only: direct candidate edge ff1 -> doc2 is found
        res_all = engine.find_paths(
            graph=graph, source_node_id=ff1_id, target_node_id=doc2_id, confirmed_only=False
        )
        assert res_all.total_paths_found >= 1
        assert any(not p.is_confirmed_only for p in res_all.paths)

        # With confirmed_only=True: candidate edge must NOT be traversed
        res_conf = engine.find_paths(
            graph=graph, source_node_id=ff1_id, target_node_id=doc2_id, confirmed_only=True
        )
        # There is no directed confirmed path from FF1 to Doc2
        assert res_conf.total_paths_found == 0

    def test_cycle_safety_prevents_infinite_loop(self) -> None:
        """A directed cycle (A -> B -> C -> A) must not cause an infinite recursion."""
        case_id = "test-cycle"
        graph = ProjectedGraphData(case_id=case_id)

        # Add 3 nodes in a triangle cycle
        na = deterministic_node_id(case_id, GraphNodeType.DOCUMENT, "a")
        nb = deterministic_node_id(case_id, GraphNodeType.DOCUMENT, "b")
        nc = deterministic_node_id(case_id, GraphNodeType.DOCUMENT, "c")

        for nid, lbl in [(na, "A"), (nb, "B"), (nc, "C")]:
            graph.add_node(
                GraphNode(
                    id=nid,
                    case_id=case_id,
                    node_type=GraphNodeType.DOCUMENT,
                    source_entity_type="Document",
                    source_entity_id=lbl,
                    label=lbl,
                )
            )

        # Edges forming cycle: A -> B -> C -> A
        e1 = deterministic_edge_id(case_id, na, "LINKS", nb)
        e2 = deterministic_edge_id(case_id, nb, "LINKS", nc)
        e3 = deterministic_edge_id(case_id, nc, "LINKS", na)

        for eid, s, t in [(e1, na, nb), (e2, nb, nc), (e3, nc, na)]:
            graph.add_edge(
                GraphEdge(
                    id=eid,
                    case_id=case_id,
                    source_node_id=s,
                    target_node_id=t,
                    predicate="LINKS",
                    status="CONFIRMED",
                )
            )

        engine = EvidenceGraphEngine()

        # Path from A to C should be found with length 2 without looping
        res = engine.find_paths(graph=graph, source_node_id=na, target_node_id=nc, max_depth=5)
        assert res.total_paths_found == 1
        assert res.paths[0].length == 2  # A -> B -> C

    def test_nonexistent_path_returns_empty_cleanly(self) -> None:
        """When two nodes are disconnected, path query returns 0 paths without error."""
        engine = EvidenceGraphEngine()
        graph = _build_test_graph()

        ev1_id = deterministic_node_id("test-case-c1", GraphNodeType.EVIDENCE, "ev1")
        case_id = deterministic_node_id("test-case-c1", GraphNodeType.CASE, "c1")

        # Ev1 has no outgoing path back to Case
        res = engine.find_paths(graph=graph, source_node_id=ev1_id, target_node_id=case_id)
        assert res.total_paths_found == 0
        assert res.truncated is False
