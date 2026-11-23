export interface Repository {
  id: string;
  name: string;
  root_path: string;
  status: string;
  total_files: number;
  total_functions: number;
  total_classes: number;
  total_lines: number;
}

export interface FileDetails {
  file_path: string;
  total_lines: number;
  docstring: string | null;
  source: string;
  imports: Array<{
    module: string | null;
    names: string[];
    alias_map: Record<string, string>;
    start_line: number;
  }>;
  classes: Array<{
    name: string;
    start_line: number;
    end_line: number;
    bases: string[];
    docstring: string | null;
  }>;
  functions: Array<{
    name: string;
    qualified_name: string;
    signature: string;
    docstring: string | null;
    start_line: number;
    end_line: number;
    calls: string[];
    is_method: boolean;
    class_name: string | null;
  }>;
}

export interface SearchResult {
  id: string;
  name: string;
  qualified_name: string;
  file_path: string;
  start_line: number;
  end_line: number;
  signature: string;
  docstring: string | null;
  source: string;
  final_score: number;
  reasons: string[];
}

export interface ChatSource {
  file_path: string;
  start_line: number;
  end_line: number;
  qualified_name: string;
  relevance_score: number;
  citation: string;
}

export interface ChatResponse {
  query: string;
  answer: string;
  sources: ChatSource[];
  retrieved_count: number;
  llm_used: boolean;
}

export interface DependentEntity {
  id: string;
  name: string;
  qualified_name: string;
  file_path: string;
  start_line: number;
  end_line: number;
  depth: number;
  is_method: boolean;
}

export interface ImpactReport {
  target_function: string;
  target_qualified_name: string;
  target_file_path: string;
  impact_level: "LOW" | "MEDIUM" | "HIGH";
  heuristic_rationale: string;
  direct_callers: DependentEntity[];
  indirect_callers: DependentEntity[];
  callees: DependentEntity[];
  affected_files: string[];
  relevant_tests: string[];
  dependency_paths: string[];
  analysis_summary: string;
  llm_used: boolean;
  disclaimer: string;
}

export interface GraphNode {
  id: string;
  label: string;
  type: "file" | "class" | "function";
  file_path?: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}
