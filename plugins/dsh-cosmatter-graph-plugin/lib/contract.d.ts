export interface GraphNode {
    node_id: string;
    node_type: 'Mission' | 'Paper' | 'Entity' | 'Condition' | 'EvidenceCard';
    label: string;
    attributes: Record<string, unknown>;
}
export interface GraphEdge {
    edge_id: string;
    source_id: string;
    target_id: string;
    relation: 'supports' | 'contradicts' | 'conditions' | 'mentions' | 'derived_from';
}
export interface GraphSnapshot {
    schema_version: '1.0';
    graph_id: string;
    mission_id: string;
    trust_status: 'accepted_evidence_projection_not_scientific_conclusion';
    source_artifact_hashes: string[];
    nodes: GraphNode[];
    edges: GraphEdge[];
    page?: {
        node_types: GraphNode['node_type'][];
        offset: number;
        limit: number;
        node_total: number;
        edge_count: number;
        truncated: boolean;
        empty_result_meaning: string;
    };
}
export declare function assertGraphSnapshot(value: unknown): asserts value is GraphSnapshot;
