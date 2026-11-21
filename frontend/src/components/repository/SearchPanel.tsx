import React, { useState, useCallback } from 'react';
import { Search, Filter } from 'lucide-react';
import * as api from '@/services/api';
import LoadingSpinner from '@/components/common/LoadingSpinner';
import ErrorMessage from '@/components/common/ErrorMessage';
import Badge from '@/components/common/Badge';
import type { SearchResult } from '@/types';

interface SearchPanelProps {
  repoId: string;
}

const entityTypes = [
  { value: '', label: 'All Types' },
  { value: 'function', label: 'Functions' },
  { value: 'class', label: 'Classes' },
  { value: 'file', label: 'Files' },
  { value: 'module', label: 'Modules' },
];

const SearchPanel: React.FC<SearchPanelProps> = ({ repoId }) => {
  const [query, setQuery] = useState('');
  const [entityType, setEntityType] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = useCallback(async () => {
    const q = query.trim();
    if (!q) return;
    setLoading(true);
    setError(null);
    setHasSearched(true);
    try {
      let searchResults = await api.searchCode(repoId, q, 50);
      if (entityType) {
        searchResults = searchResults.filter(
          (r) => r.entity_type.toLowerCase() === entityType
        );
      }
      setResults(searchResults);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Search failed');
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [repoId, query, entityType]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch();
  };

  const getSourcePreview = (source: string): string => {
    const lines = source.split('\n').slice(0, 3);
    return lines.join('\n');
  };

  return (
    <div className="p-6 max-w-5xl">
      {/* Search Controls */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search code symbols, functions, classes..."
              className="w-full pl-10 pr-4 py-2.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <div className="flex gap-3">
            <div className="relative">
              <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 pointer-events-none" />
              <select
                value={entityType}
                onChange={(e) => setEntityType(e.target.value)}
                className="pl-9 pr-8 py-2.5 bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 appearance-none"
              >
                {entityTypes.map((et) => (
                  <option key={et.value} value={et.value}>
                    {et.label}
                  </option>
                ))}
              </select>
            </div>
            <button
              onClick={handleSearch}
              disabled={loading || !query.trim()}
              className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
            >
              Search
            </button>
          </div>
        </div>
      </div>

      {/* Results */}
      {loading && <LoadingSpinner message="Searching..." />}
      {error && <ErrorMessage message={error} />}

      {!loading && !error && hasSearched && (
        <>
          <p className="text-sm text-gray-400 mb-4">
            {results.length} result{results.length !== 1 ? 's' : ''} found
          </p>
          <div className="space-y-3">
            {results.map((result) => (
              <div
                key={result.entity_id}
                className="bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-gray-700 transition-colors"
              >
                <div className="flex items-start justify-between gap-4 mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <Badge type={result.entity_type} />
                    <span className="text-sm font-semibold text-gray-100 truncate">
                      {result.name}
                    </span>
                  </div>
                  <span className="text-xs text-gray-500 flex-shrink-0">
                    Score: {(result.score * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="flex items-center gap-2 text-xs text-gray-400 mb-3">
                  <span className="font-mono truncate">{result.file_path}</span>
                  <span className="text-gray-600">·</span>
                  <span>
                    L{result.line_start}–{result.line_end}
                  </span>
                </div>
                {result.source && (
                  <pre className="text-xs font-mono text-gray-400 bg-gray-800 rounded-lg p-3 overflow-x-auto leading-relaxed">
                    {getSourcePreview(result.source)}
                  </pre>
                )}
              </div>
            ))}

            {results.length === 0 && (
              <div className="text-center py-12">
                <Search className="w-10 h-10 text-gray-700 mx-auto mb-3" />
                <p className="text-sm text-gray-500">No results found</p>
                <p className="text-xs text-gray-600 mt-1">
                  Try a different query or entity type filter
                </p>
              </div>
            )}
          </div>
        </>
      )}

      {!hasSearched && !loading && (
        <div className="text-center py-16">
          <Search className="w-10 h-10 text-gray-700 mx-auto mb-3" />
          <p className="text-sm text-gray-400">Search for code symbols</p>
          <p className="text-xs text-gray-600 mt-1">
            Find functions, classes, and modules by name or semantic similarity
          </p>
        </div>
      )}
    </div>
  );
};

export default SearchPanel;
