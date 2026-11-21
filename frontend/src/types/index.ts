export interface Repository {
  id: string;
  name: string;
  path: string;
  status: string;
  created_at: string;
  updated_at: string;
  file_count: number;
  function_count: number;
  class_count: number;
  module_count: number;
  last_ingestion: IngestionResult | null;
}

export interface IngestionResult {
  repository_id: string;
  status: string;
  files_processed: number;
  functions_found: number;
  classes_found: number;
  modules_found: number;
  errors: string[];
  duration_seconds: number;
  started_at: string;
  completed_at: string;
}

export interface SearchResult {
  entity_id: string;
  name: string;
  qualified_name: string;
  entity_type: string;
  file_path: string;
  line_start: number;
  line_end: number;
  source: string;
  score: number;
  docstring: string | null;
}

export interface Symbol {
  id: string;
  name: string;
  qualified_name: string;
  entity_type: string;
  file_path: string;
  line_start: number;
  line_end: number;
  source: string;
  signature: string | null;
  docstring: string | null;
  decorators: string[];
  is_method: boolean;
  is_async: boolean;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  file_path?: string;
  qualified_name?: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relationship: string;
  label?: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface ImpactReport {
  target: {
    name: string;
    qualified_name: string;
    entity_type: string;
    file_path: string;
  };
  direct_dependents: Array<{
    name: string;
    qualified_name: string;
    entity_type: string;
    file_path: string;
    relationship: string;
  }>;
  indirect_dependents: Array<{
    name: string;
    qualified_name: string;
    entity_type: string;
    file_path: string;
    depth: number;
  }>;
  affected_files: string[];
  dependency_paths: Array<{
    path: string[];
    relationships: string[];
  }>;
  summary: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: Array<{
    name: string;
    file_path: string;
    entity_type: string;
    relevance: number;
  }>;
}

export interface ChatResponse {
  answer: string;
  sources: Array<{
    name: string;
    file_path: string;
    entity_type: string;
    relevance: number;
  }>;
}

export interface HealthStatus {
  status: string;
  neo4j: string;
  version: string;
}
