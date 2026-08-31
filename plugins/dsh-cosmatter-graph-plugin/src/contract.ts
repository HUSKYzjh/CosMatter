export interface GraphNode {
  node_id: string
  node_type: 'Mission' | 'Paper' | 'Entity' | 'Condition' | 'EvidenceCard'
  label: string
  attributes: Record<string, unknown>
}

export interface GraphEdge {
  edge_id: string
  source_id: string
  target_id: string
  relation: 'supports' | 'contradicts' | 'conditions' | 'mentions' | 'derived_from'
}

export interface GraphSnapshot {
  schema_version: '1.0'
  graph_id: string
  mission_id: string
  trust_status: 'accepted_evidence_projection_not_scientific_conclusion'
  source_artifact_hashes: string[]
  nodes: GraphNode[]
  edges: GraphEdge[]
  page?: { node_types: GraphNode['node_type'][]; offset: number; limit: number; node_total: number; edge_count: number; truncated: boolean; empty_result_meaning: string }
}

const identifier = /^[a-z_]+:[a-f0-9]{16,64}$/
const hash = /^[a-f0-9]{64}$/
const forbiddenKey = /quote|excerpt|content|path|token|secret|authorization|password/i

export function assertGraphSnapshot(value: unknown): asserts value is GraphSnapshot {
  if (!isObject(value) || value.schema_version !== '1.0' || typeof value.graph_id !== 'string' || !identifier.test(value.graph_id)
    || typeof value.mission_id !== 'string' || !value.mission_id.trim()
    || value.trust_status !== 'accepted_evidence_projection_not_scientific_conclusion'
    || !Array.isArray(value.source_artifact_hashes) || !value.source_artifact_hashes.every(item => typeof item === 'string' && hash.test(item))
    || !Array.isArray(value.nodes) || !Array.isArray(value.edges)) {
    throw new Error('CosMatter returned an invalid graph snapshot envelope')
  }
  const nodeIds = new Set<string>()
  for (const node of value.nodes) {
    if (!isObject(node) || typeof node.node_id !== 'string' || !identifier.test(node.node_id)
      || !isGraphNodeType(node.node_type) || typeof node.label !== 'string' || node.label.length > 300
      || !isObject(node.attributes) || nodeIds.has(node.node_id)) {
      throw new Error('CosMatter returned an invalid graph node')
    }
    assertMinimizedAttributes(node.attributes)
    if (node.node_type === 'EvidenceCard' && (node.attributes.review_status !== 'accepted'
      || typeof node.attributes.claim_digest !== 'string' || typeof node.attributes.provenance_digest !== 'string')) {
      throw new Error('CosMatter returned an unreviewed or non-minimized evidence node')
    }
    nodeIds.add(node.node_id)
  }
  if (!value.page && (!value.nodes.some(node => node.node_type === 'Mission') || !value.nodes.some(node => node.node_type === 'EvidenceCard'))) {
    throw new Error('CosMatter graph must contain mission and accepted evidence nodes')
  }
  if (value.page !== undefined) {
    if (!isObject(value.page) || !Array.isArray(value.page.node_types) || !value.page.node_types.every(isGraphNodeType)
      || !isNonNegativeInteger(value.page.offset) || !isPositiveInteger(value.page.limit) || value.page.limit > 100
      || !isNonNegativeInteger(value.page.node_total) || !isNonNegativeInteger(value.page.edge_count)
      || typeof value.page.truncated !== 'boolean' || typeof value.page.empty_result_meaning !== 'string' || value.page.empty_result_meaning.length > 500) {
      throw new Error('CosMatter returned an invalid bounded graph page')
    }
  }
  const edgeIds = new Set<string>()
  for (const edge of value.edges) {
    if (!isObject(edge) || typeof edge.edge_id !== 'string' || !identifier.test(edge.edge_id)
      || !isGraphRelation(edge.relation) || typeof edge.source_id !== 'string' || typeof edge.target_id !== 'string'
      || !nodeIds.has(edge.source_id) || !nodeIds.has(edge.target_id) || edge.source_id === edge.target_id || edgeIds.has(edge.edge_id)) {
      throw new Error('CosMatter returned an invalid graph edge')
    }
    edgeIds.add(edge.edge_id)
  }
}

function assertMinimizedAttributes(attributes: Record<string, unknown>): void {
  for (const [key, item] of Object.entries(attributes)) {
    if (forbiddenKey.test(key) || (typeof item === 'string' && (item.length > 500 || /[A-Za-z]:[\\/]|\.private|case-data/i.test(item)))) {
      throw new Error('CosMatter graph contains forbidden raw content')
    }
    if (Array.isArray(item) && item.some(child => typeof child === 'object' && child !== null)) {
      throw new Error('CosMatter graph attributes must remain shallow')
    }
    if (isObject(item)) assertMinimizedAttributes(item)
  }
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isGraphNodeType(value: unknown): value is GraphNode['node_type'] {
  return value === 'Mission' || value === 'Paper' || value === 'Entity' || value === 'Condition' || value === 'EvidenceCard'
}

function isGraphRelation(value: unknown): value is GraphEdge['relation'] {
  return value === 'supports' || value === 'contradicts' || value === 'conditions' || value === 'mentions' || value === 'derived_from'
}

function isNonNegativeInteger(value: unknown): value is number { return typeof value === 'number' && Number.isInteger(value) && value >= 0 }
function isPositiveInteger(value: unknown): value is number { return isNonNegativeInteger(value) && value > 0 }
