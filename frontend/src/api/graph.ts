import { api } from "./client";
import type {
  GraphSnapshot,
  GraphNode,
  GraphEdge,
  GraphNeighborhoodResult,
  GraphPathsResult,
} from "../types/api";

export interface GetGraphOptions {
  node_types?: string[];
  relationship_types?: string[];
  statuses?: string[];
  document_ids?: string[];
  limit?: number;
  offset?: number;
}

export interface GetNeighborhoodOptions {
  max_hops?: number;
  limit?: number;
  relationship_types?: string[];
  statuses?: string[];
}

export interface FindPathsOptions {
  source_node_id: string;
  target_node_id: string;
  max_depth?: number;
  max_paths?: number;
  confirmed_only?: boolean;
  relationship_types?: string[];
}

export interface NodeDetailResponse {
  node: GraphNode;
  incoming_edges: GraphEdge[];
  outgoing_edges: GraphEdge[];
  degree: number;
  in_degree: number;
  out_degree: number;
}

type QueryParamValue = string | number | boolean | Array<string | number> | undefined | null;

export const graphApi = {
  getCaseGraph: (caseId: string, options: GetGraphOptions = {}): Promise<GraphSnapshot> => {
    return api.get<GraphSnapshot>(`/cases/${caseId}/graph`, options as Record<string, QueryParamValue>);
  },

  getNode: (caseId: string, nodeId: string): Promise<NodeDetailResponse> => {
    return api.get<NodeDetailResponse>(`/cases/${caseId}/graph/nodes/${nodeId}`);
  },

  getNeighborhood: (
    caseId: string,
    nodeId: string,
    options: GetNeighborhoodOptions = {}
  ): Promise<GraphNeighborhoodResult> => {
    return api.get<GraphNeighborhoodResult>(
      `/cases/${caseId}/graph/nodes/${nodeId}/neighbors`,
      options as Record<string, QueryParamValue>
    );
  },

  findPaths: (caseId: string, options: FindPathsOptions): Promise<GraphPathsResult> => {
    return api.get<GraphPathsResult>(
      `/cases/${caseId}/graph/paths`,
      options as unknown as Record<string, QueryParamValue>
    );
  },
};
