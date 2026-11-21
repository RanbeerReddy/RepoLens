import axios from 'axios';
import type {
  Repository,
  IngestionResult,
  SearchResult,
  Symbol,
  GraphData,
  ImpactReport,
  ChatMessage,
  ChatResponse,
  HealthStatus,
} from '@/types';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Health
export async function getHealth(): Promise<HealthStatus> {
  const { data } = await api.get('/health');
  return data;
}

// Repositories
export async function listRepositories(): Promise<Repository[]> {
  const { data } = await api.get('/repositories');
  return data;
}

export async function createRepository(path: string, name: string): Promise<Repository> {
  const { data } = await api.post('/repositories', { path, name });
  return data;
}

export async function getRepository(id: string): Promise<Repository> {
  const { data } = await api.get(`/repositories/${id}`);
  return data;
}

export async function deleteRepository(id: string): Promise<void> {
  await api.delete(`/repositories/${id}`);
}

// Ingestion
export async function ingestRepository(id: string): Promise<IngestionResult> {
  const { data } = await api.post(`/repositories/${id}/ingest`);
  return data;
}

// Search
export async function searchCode(
  id: string,
  query: string,
  limit: number = 20
): Promise<SearchResult[]> {
  const { data } = await api.get(`/repositories/${id}/search`, {
    params: { query, limit },
  });
  return data;
}

// Symbols
export async function getSymbols(
  id: string,
  params?: { entity_type?: string; file_path?: string; limit?: number; offset?: number }
): Promise<Symbol[]> {
  const { data } = await api.get(`/repositories/${id}/symbols`, { params });
  return data;
}

export async function getSymbol(id: string, symbolId: string): Promise<Symbol> {
  const { data } = await api.get(`/repositories/${id}/symbols/${symbolId}`);
  return data;
}

// Graph
export async function getGraph(id: string, limit: number = 100): Promise<GraphData> {
  const { data } = await api.get(`/repositories/${id}/graph`, {
    params: { limit },
  });
  return data;
}

export async function getNeighbors(
  id: string,
  entityId: string,
  depth: number = 1
): Promise<GraphData> {
  const { data } = await api.get(`/repositories/${id}/graph/neighbors/${entityId}`, {
    params: { depth },
  });
  return data;
}

// Impact Analysis
export async function analyzeImpact(
  id: string,
  symbol: string,
  depth: number = 3
): Promise<ImpactReport> {
  const { data } = await api.get(`/repositories/${id}/impact`, {
    params: { symbol, depth },
  });
  return data;
}

// Chat
export async function chat(
  id: string,
  question: string,
  history: ChatMessage[] = []
): Promise<ChatResponse> {
  const { data } = await api.post(`/repositories/${id}/chat`, {
    question,
    history,
  });
  return data;
}
