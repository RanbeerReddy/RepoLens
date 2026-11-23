import {
  ChatResponse,
  FileDetails,
  GraphData,
  ImpactReport,
  Repository,
  SearchResult,
} from "../types";

const API_BASE = "http://localhost:8080/api";

export async function fetchHealth(): Promise<{ neo4j: boolean; llm: boolean }> {
  try {
    const [neo, llm] = await Promise.all([
      fetch("http://localhost:8080/health/neo4j").then((r) => r.json()),
      fetch("http://localhost:8080/health/llm").then((r) => r.json()),
    ]);
    return { neo4j: neo.connected, llm: llm.connected };
  } catch {
    return { neo4j: false, llm: false };
  }
}

export async function listRepositories(): Promise<Repository[]> {
  const res = await fetch(`${API_BASE}/repositories`);
  if (!res.ok) throw new Error("Failed to load repositories");
  return res.json();
}

export async function registerRepository(path: string, name?: string): Promise<Repository> {
  const res = await fetch(`${API_BASE}/repositories`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, name }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Registration failed" }));
    throw new Error(err.detail || "Registration failed");
  }
  return res.json();
}

export async function ingestRepository(repoId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/repositories/${encodeURIComponent(repoId)}/ingest`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Ingestion failed");
  return res.json();
}

export async function listFiles(repoId: string): Promise<string[]> {
  const res = await fetch(`${API_BASE}/repositories/${encodeURIComponent(repoId)}/files`);
  if (!res.ok) return [];
  return res.json();
}

export async function getFileDetails(repoId: string, filePath: string): Promise<FileDetails> {
  const res = await fetch(
    `${API_BASE}/repositories/${encodeURIComponent(repoId)}/files/${encodeURIComponent(filePath)}`
  );
  if (!res.ok) throw new Error("Failed to load file details");
  return res.json();
}

export async function searchCode(
  repoId: string,
  query: string,
  limit = 8
): Promise<SearchResult[]> {
  const res = await fetch(`${API_BASE}/repositories/${encodeURIComponent(repoId)}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, limit }),
  });
  if (!res.ok) return [];
  return res.json();
}

export async function askChat(
  repoId: string,
  query: string,
  top_k = 5
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/repositories/${encodeURIComponent(repoId)}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, top_k }),
  });
  if (!res.ok) throw new Error("Chat request failed");
  return res.json();
}

export async function analyzeImpact(
  repoId: string,
  functionName: string
): Promise<ImpactReport> {
  const res = await fetch(`${API_BASE}/repositories/${encodeURIComponent(repoId)}/impact`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ function_name: functionName }),
  });
  if (!res.ok) throw new Error("Impact analysis failed");
  return res.json();
}

export async function getGraphData(repoId: string, focus?: string): Promise<GraphData> {
  const url = new URL(`${API_BASE}/repositories/${encodeURIComponent(repoId)}/graph`);
  if (focus) url.searchParams.set("focus", focus);
  const res = await fetch(url.toString());
  if (!res.ok) return { nodes: [], edges: [] };
  return res.json();
}
