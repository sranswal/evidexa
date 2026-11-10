import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { ReactFlowProvider } from "@xyflow/react";
import { EvidenceGraphNode } from "../components/graph/EvidenceGraphNode";
import { EvidenceGraphEdge } from "../components/graph/EvidenceGraphEdge";
import { GraphControlsBar, GraphFilterState } from "../components/graph/GraphControlsBar";
import { GraphDetailsInspector } from "../components/graph/GraphDetailsInspector";
import { PathExplorationPanel } from "../components/graph/PathExplorationPanel";
import { applyDagreLayout, toReactFlowNode, toReactFlowEdge } from "../components/graph/layout";
import { graphApi } from "../api/graph";
import type { GraphNode, GraphEdge, GraphPathsResult } from "../types/api";

vi.mock("@xyflow/react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@xyflow/react")>();
  return {
    ...actual,
    EdgeLabelRenderer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="edge-label-portal">{children}</div>
    ),
  };
});

vi.mock("../api/graph", () => ({
  graphApi: {
    findPaths: vi.fn(),
  },
}));

describe("Evidence Graph Layout Utility", () => {
  it("applies Dagre hierarchical LR layout to nodes and edges", () => {
    const rawNodes: GraphNode[] = [
      {
        id: "doc-1",
        case_id: "case-123",
        node_type: "DOCUMENT",
        label: "Invoice_2026.pdf",
        source_entity_type: "documents",
        source_entity_id: "doc-1",
        display_attributes: { page_count: 3 },
        provenance: {},
        created_at: "2026-11-09T00:00:00Z",
      },
      {
        id: "org-1",
        case_id: "case-123",
        node_type: "ORGANIZATION",
        label: "Apex Holdings LLC",
        source_entity_type: "entities",
        source_entity_id: "org-1",
        display_attributes: {},
        provenance: {},
        created_at: "2026-11-09T00:00:00Z",
      },
    ];

    const rawEdges: GraphEdge[] = [
      {
        id: "edge-1",
        case_id: "case-123",
        source_node_id: "doc-1",
        target_node_id: "org-1",
        predicate: "ISSUED",
        status: "CONFIRMED",
        status_determination_method: "EVIDENTIARY_RULE",
        score: 1.0,
        explanation: "Invoice mentions Apex Holdings as issuer",
        supporting_evidence_ids: [],
        contradicting_evidence_ids: [],
        source_relationship_id: null,
        metadata: {},
      },
    ];

    const flowNodes = rawNodes.map((n) => toReactFlowNode(n));
    const flowEdges = rawEdges.map((e) => toReactFlowEdge(e));

    const { nodes: layoutNodes, edges: layoutEdges } = applyDagreLayout(
      flowNodes,
      flowEdges,
      "LR"
    );

    expect(layoutNodes).toHaveLength(2);
    expect(layoutEdges).toHaveLength(1);
    expect(layoutNodes[0].position.x).toBeDefined();
    expect(layoutNodes[0].position.y).toBeDefined();
    expect(layoutNodes[1].position.x).toBeGreaterThan(layoutNodes[0].position.x);
  });
});

describe("EvidenceGraphNode Component", () => {
  it("renders a DOCUMENT node with category, icon, and label", () => {
    const nodeProps: any = {
      id: "doc-1",
      data: {
        rawNode: {
          id: "doc-1",
          case_id: "case-123",
          node_type: "DOCUMENT",
          source_entity_type: "documents",
          source_entity_id: "doc-1",
          label: "Wire_Transfer_Confirmation.pdf",
          display_attributes: { page_count: 2 },
          provenance: { document_id: "doc-1", page_number: 1 },
          created_at: "2026-11-09T00:00:00Z",
        },
      },
      selected: false,
    };

    render(
      <ReactFlowProvider>
        <EvidenceGraphNode {...nodeProps} />
      </ReactFlowProvider>
    );

    expect(screen.getByText("DOCUMENT")).toBeInTheDocument();
    expect(screen.getByText("Wire_Transfer_Confirmation.pdf")).toBeInTheDocument();
    expect(screen.getByText("p. 1")).toBeInTheDocument();
  });

  it("renders a masked label for sensitive account numbers", () => {
    const nodeProps: any = {
      id: "acc-1",
      data: {
        rawNode: {
          id: "acc-1",
          case_id: "case-123",
          node_type: "ACCOUNT",
          source_entity_type: "entities",
          source_entity_id: "acc-1",
          label: "1234567890123456",
          display_attributes: {},
          provenance: {},
          created_at: "2026-11-09T00:00:00Z",
        },
      },
      selected: false,
    };

    render(
      <ReactFlowProvider>
        <EvidenceGraphNode {...nodeProps} />
      </ReactFlowProvider>
    );

    expect(screen.getByText("ACCOUNT")).toBeInTheDocument();
    // Verify masking retains last 4 digits
    expect(screen.getByText(/3456/)).toBeInTheDocument();
    expect(screen.queryByText("1234567890123456")).not.toBeInTheDocument();
  });

  it("applies highlighted classes based on path flag", () => {
    const nodeProps: any = {
      id: "org-1",
      data: {
        rawNode: {
          id: "org-1",
          case_id: "case-123",
          node_type: "ORGANIZATION",
          source_entity_type: "entities",
          source_entity_id: "org-1",
          label: "Apex Holdings",
          display_attributes: {},
          provenance: {},
          created_at: "2026-11-09T00:00:00Z",
        },
        isPathHighlighted: true,
      },
      selected: false,
    };

    const { container } = render(
      <ReactFlowProvider>
        <EvidenceGraphNode {...nodeProps} />
      </ReactFlowProvider>
    );

    const nodeElement = container.querySelector(".border-amber-400");
    expect(nodeElement).toBeInTheDocument();
  });
});

describe("EvidenceGraphEdge Component", () => {
  it("renders edge label with predicate and status styling", () => {
    const edgeProps: any = {
      id: "edge-1",
      source: "doc-1",
      target: "org-1",
      sourceX: 100,
      sourceY: 100,
      targetX: 300,
      targetY: 200,
      sourcePosition: "right",
      targetPosition: "left",
      data: {
        rawEdge: {
          id: "edge-1",
          case_id: "case-123",
          source_node_id: "doc-1",
          target_node_id: "org-1",
          predicate: "INVOICED",
          status: "CONFIRMED" as const,
          status_determination_method: "EVIDENTIARY_RULE",
          score: 0.98,
          explanation: "Verified against bank settlement record",
          supporting_evidence_ids: [],
          contradicting_evidence_ids: [],
          source_relationship_id: null,
          metadata: {},
        },
      },
      selected: false,
    };

    render(
      <ReactFlowProvider>
        <div>
          <svg>
            <EvidenceGraphEdge {...edgeProps} />
          </svg>
        </div>
      </ReactFlowProvider>
    );

    expect(screen.getByText("INVOICED")).toBeInTheDocument();
  });
});

describe("GraphControlsBar Component", () => {
  const initialFilter: GraphFilterState = {
    searchQuery: "",
    selectedNodeTypes: new Set(),
    selectedStatuses: new Set(),
    selectedPredicate: null,
  };

  const sampleNodes: GraphNode[] = [
    {
      id: "node-1",
      case_id: "c-1",
      node_type: "DOCUMENT",
      source_entity_type: "documents",
      source_entity_id: "node-1",
      label: "Contract_Alpha.pdf",
      display_attributes: {},
      provenance: {},
      created_at: "2026-11-09T00:00:00Z",
    },
    {
      id: "node-2",
      case_id: "c-1",
      node_type: "PERSON",
      source_entity_type: "entities",
      source_entity_id: "node-2",
      label: "John Doe",
      display_attributes: {},
      provenance: {},
      created_at: "2026-11-09T00:00:00Z",
    },
  ];

  it("renders filter bar, search input, and action triggers", () => {
    const onFiltersChange = vi.fn();
    const onFitView = vi.fn();
    const onReLayout = vi.fn();
    const onOpenPathFinder = vi.fn();
    const onSelectNode = vi.fn();

    render(
      <GraphControlsBar
        filters={initialFilter}
        onFiltersChange={onFiltersChange}
        nodes={sampleNodes}
        totalNodesCount={2}
        totalEdgesCount={1}
        onFitView={onFitView}
        onReLayout={onReLayout}
        onOpenPathFinder={onOpenPathFinder}
        onSelectNode={onSelectNode}
      />
    );

    expect(screen.getByPlaceholderText(/Search nodes in graph/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Explore Paths/i })).toBeInTheDocument();
    expect(screen.getByTitle("Re-run hierarchical Dagre layout")).toBeInTheDocument();
    expect(screen.getByTitle("Fit graph to view")).toBeInTheDocument();

    // Trigger action buttons
    fireEvent.click(screen.getByRole("button", { name: /Explore Paths/i }));
    expect(onOpenPathFinder).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByTitle("Re-run hierarchical Dagre layout"));
    expect(onReLayout).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByTitle("Fit graph to view"));
    expect(onFitView).toHaveBeenCalledTimes(1);
  });
});

describe("GraphDetailsInspector Component", () => {
  const sampleNode: GraphNode = {
    id: "finding-42",
    case_id: "c-1",
    node_type: "FORENSIC_FINDING",
    label: "Font Substitution Detected",
    source_entity_type: "forensic_findings",
    source_entity_id: "finding-42",
    display_attributes: {
      rule_id: "PDF-STRUCT-004",
      confidence: 0.94,
    },
    provenance: {
      document_id: "doc-123",
      page_number: 2,
    },
    created_at: "2026-11-09T00:00:00Z",
  };

  it("renders node details with metadata, provenance, and expand neighborhood button", () => {
    const onExpandNeighborhood = vi.fn();
    const onSelectNode = vi.fn();
    const onSelectEdge = vi.fn();
    const onSetPathSource = vi.fn();
    const onSetPathTarget = vi.fn();

    render(
      <MemoryRouter>
        <GraphDetailsInspector
          selectedNode={sampleNode}
          selectedEdge={null}
          allNodes={[sampleNode]}
          caseId="c-1"
          onClose={vi.fn()}
          onSelectNode={onSelectNode}
          onSelectEdge={onSelectEdge}
          onExpandNeighborhood={onExpandNeighborhood}
          onSetPathSource={onSetPathSource}
          onSetPathTarget={onSetPathTarget}
        />
      </MemoryRouter>
    );

    expect(screen.getByText("Node Details")).toBeInTheDocument();
    expect(screen.getByText("Font Substitution Detected")).toBeInTheDocument();
    expect(screen.getByText("PDF-STRUCT-004")).toBeInTheDocument();
    expect(screen.getByText("View in Doc")).toBeInTheDocument();

    const expandBtn = screen.getByRole("button", { name: /Expand 2 Hops/i });
    fireEvent.click(expandBtn);
    expect(onExpandNeighborhood).toHaveBeenCalledWith("finding-42");
  });

  it("renders edge details with status, score, and explanation", () => {
    const sampleEdge: GraphEdge = {
      id: "edge-77",
      case_id: "c-1",
      source_node_id: "doc-1",
      target_node_id: "org-1",
      predicate: "PURCHASED_FROM",
      status: "CANDIDATE",
      status_determination_method: "FUZZY_NAME_MATCH",
      score: 0.72,
      explanation: "Fuzzy name similarity of 0.88 with known shell entity",
      supporting_evidence_ids: ["ev-1", "ev-2"],
      contradicting_evidence_ids: [],
      source_relationship_id: "rel-1",
      metadata: {},
    };

    render(
      <MemoryRouter>
        <GraphDetailsInspector
          selectedNode={null}
          selectedEdge={sampleEdge}
          allNodes={[]}
          caseId="c-1"
          onClose={vi.fn()}
          onSelectNode={vi.fn()}
          onSelectEdge={vi.fn()}
          onExpandNeighborhood={vi.fn()}
          onSetPathSource={vi.fn()}
          onSetPathTarget={vi.fn()}
        />
      </MemoryRouter>
    );

    expect(screen.getByText("Relationship Semantics")).toBeInTheDocument();
    expect(screen.getByText("PURCHASED FROM")).toBeInTheDocument();
    expect(screen.getByText("CANDIDATE")).toBeInTheDocument();
    expect(screen.getByText(/Fuzzy name similarity/i)).toBeInTheDocument();
    expect(screen.getByText("0.72")).toBeInTheDocument();
  });
});

describe("PathExplorationPanel Component", () => {
  const sampleNodes: GraphNode[] = [
    {
      id: "node-a",
      case_id: "c-1",
      node_type: "DOCUMENT",
      source_entity_type: "documents",
      source_entity_id: "node-a",
      label: "Invoice_A.pdf",
      display_attributes: {},
      provenance: {},
      created_at: "2026-11-09T00:00:00Z",
    },
    {
      id: "node-b",
      case_id: "c-1",
      node_type: "BANK",
      source_entity_type: "entities",
      source_entity_id: "node-b",
      label: "Bank of Zurich",
      display_attributes: {},
      provenance: {},
      created_at: "2026-11-09T00:00:00Z",
    },
  ];

  it("executes path exploration and allows path selection", async () => {
    const mockPathsResult: GraphPathsResult = {
      case_id: "c-1",
      source_node_id: "node-a",
      target_node_id: "node-b",
      max_depth: 4,
      paths: [
        {
          nodes: [sampleNodes[0], sampleNodes[1]],
          edges: [
            {
              id: "edge-1",
              case_id: "c-1",
              source_node_id: "node-a",
              target_node_id: "node-b",
              predicate: "INVOICED",
              status: "CONFIRMED",
              status_determination_method: "EVIDENTIARY_RULE",
              score: 1.0,
              explanation: "Direct invoice wire reference",
              supporting_evidence_ids: [],
              contradicting_evidence_ids: [],
              source_relationship_id: null,
              metadata: {},
            },
          ],
          length: 1,
          is_confirmed_only: true,
        },
      ],
    };

    vi.mocked(graphApi.findPaths).mockResolvedValueOnce(mockPathsResult);

    const onHighlightPath = vi.fn();
    const onClose = vi.fn();

    render(
      <PathExplorationPanel
        isOpen={true}
        onClose={onClose}
        caseId="c-1"
        allNodes={sampleNodes}
        initialSourceId="node-a"
        initialTargetId="node-b"
        onHighlightPath={onHighlightPath}
      />
    );

    expect(screen.getByText("Bounded Path Exploration")).toBeInTheDocument();

    const searchBtn = screen.getByRole("button", { name: /Find Paths/i });
    fireEvent.click(searchBtn);

    await waitFor(() => {
      expect(graphApi.findPaths).toHaveBeenCalledWith("c-1", {
        source_node_id: "node-a",
        target_node_id: "node-b",
        max_depth: 4,
        max_paths: 10,
        confirmed_only: false,
      });
    });

    await waitFor(() => {
      expect(screen.getByText(/Discovered 1 directed paths/i)).toBeInTheDocument();
      expect(screen.getByText("Path #1")).toBeInTheDocument();
    });

    // Click path to highlight
    fireEvent.click(screen.getByText("Path #1"));
    expect(onHighlightPath).toHaveBeenCalledWith(mockPathsResult.paths[0]);
  });
});
