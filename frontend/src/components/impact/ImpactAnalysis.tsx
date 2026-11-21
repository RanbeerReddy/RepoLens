import React, { useState } from 'react';
import { Zap, ChevronRight, FileCode, AlertTriangle } from 'lucide-react';
import * as api from '@/services/api';
import LoadingSpinner from '@/components/common/LoadingSpinner';
import ErrorMessage from '@/components/common/ErrorMessage';
import Badge from '@/components/common/Badge';
import type { ImpactReport } from '@/types';

interface ImpactAnalysisProps {
  repoId: string;
}

const ImpactAnalysis: React.FC<ImpactAnalysisProps> = ({ repoId }) => {
  const [symbolName, setSymbolName] = useState('');
  const [depth, setDepth] = useState(3);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ImpactReport | null>(null);

  const handleAnalyze = async () => {
    const name = symbolName.trim();
    if (!name) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.analyzeImpact(repoId, name, depth);
      setReport(result);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
      setReport(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-5xl">
      {/* Input Controls */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
        <h3 className="text-lg font-semibold text-gray-100 mb-4 flex items-center gap-2">
          <Zap className="w-5 h-5 text-yellow-400" />
          Impact Analysis
        </h3>
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <label className="block text-sm text-gray-400 mb-1.5">
              Function or Class Name
            </label>
            <input
              type="text"
              value={symbolName}
              onChange={(e) => setSymbolName(e.target.value)}
              placeholder="e.g., parse_file, MyClass"
              onKeyDown={(e) => { if (e.key === 'Enter') handleAnalyze(); }}
              className="w-full px-3 py-2.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono"
            />
          </div>
          <div className="w-full sm:w-48">
            <label className="block text-sm text-gray-400 mb-1.5">
              Depth: {depth}
            </label>
            <input
              type="range"
              min={1}
              max={5}
              value={depth}
              onChange={(e) => setDepth(Number(e.target.value))}
              className="w-full accent-blue-500 mt-2"
            />
            <div className="flex justify-between text-xs text-gray-600 mt-1">
              <span>1</span>
              <span>2</span>
              <span>3</span>
              <span>4</span>
              <span>5</span>
            </div>
          </div>
          <div className="flex items-end">
            <button
              onClick={handleAnalyze}
              disabled={loading || !symbolName.trim()}
              className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors whitespace-nowrap"
            >
              Analyze
            </button>
          </div>
        </div>
      </div>

      {loading && <LoadingSpinner message="Analyzing impact..." />}
      {error && <ErrorMessage message={error} />}

      {/* Results */}
      {report && !loading && (
        <div className="space-y-6">
          {/* Target Info */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <h4 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
              Target
            </h4>
            <div className="flex items-center gap-3">
              <Badge type={report.target.entity_type} />
              <span className="text-gray-100 font-mono text-sm">
                {report.target.qualified_name || report.target.name}
              </span>
              <span className="text-xs text-gray-500 font-mono">
                {report.target.file_path}
              </span>
            </div>
          </div>

          {/* Summary */}
          {report.summary && (
            <div className="bg-yellow-500/5 border border-yellow-500/20 rounded-xl p-5">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-sm font-semibold text-yellow-300 mb-1">Summary</h4>
                  <p className="text-sm text-gray-300 leading-relaxed">{report.summary}</p>
                </div>
              </div>
            </div>
          )}

          {/* Direct Dependents */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <h4 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
              Direct Dependents ({report.direct_dependents.length})
            </h4>
            {report.direct_dependents.length > 0 ? (
              <div className="space-y-2">
                {report.direct_dependents.map((dep, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-3 px-3 py-2 bg-gray-800 rounded-lg"
                  >
                    <Badge type={dep.entity_type} />
                    <span className="text-sm text-gray-200 font-mono">
                      {dep.qualified_name || dep.name}
                    </span>
                    <span className="text-xs text-gray-500 ml-auto">
                      {dep.relationship}
                    </span>
                    <span className="text-xs text-gray-600 font-mono">
                      {dep.file_path}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500">No direct dependents found.</p>
            )}
          </div>

          {/* Indirect Dependents */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <h4 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
              Indirect Dependents ({report.indirect_dependents.length})
            </h4>
            {report.indirect_dependents.length > 0 ? (
              <div className="space-y-2">
                {report.indirect_dependents.map((dep, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-3 px-3 py-2 bg-gray-800 rounded-lg"
                  >
                    <Badge type={dep.entity_type} />
                    <span className="text-sm text-gray-200 font-mono">
                      {dep.qualified_name || dep.name}
                    </span>
                    <span className="text-xs text-gray-500 ml-auto">
                      depth {dep.depth}
                    </span>
                    <span className="text-xs text-gray-600 font-mono">
                      {dep.file_path}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500">No indirect dependents found.</p>
            )}
          </div>

          {/* Affected Files */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <h4 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
              Affected Files ({report.affected_files.length})
            </h4>
            {report.affected_files.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {report.affected_files.map((file, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 px-3 py-2 bg-gray-800 rounded-lg"
                  >
                    <FileCode className="w-4 h-4 text-green-400 flex-shrink-0" />
                    <span className="text-xs text-gray-300 font-mono truncate">
                      {file}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500">No affected files.</p>
            )}
          </div>

          {/* Dependency Paths */}
          {report.dependency_paths && report.dependency_paths.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <h4 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
                Dependency Paths ({report.dependency_paths.length})
              </h4>
              <div className="space-y-3">
                {report.dependency_paths.map((dp, i) => (
                  <div key={i} className="bg-gray-800 rounded-lg p-3">
                    <div className="flex flex-wrap items-center gap-1">
                      {dp.path.map((step, si) => (
                        <React.Fragment key={si}>
                          <span className="text-xs text-gray-200 font-mono bg-gray-700 px-2 py-1 rounded">
                            {step}
                          </span>
                          {si < dp.path.length - 1 && (
                            <ChevronRight className="w-3 h-3 text-gray-600" />
                          )}
                        </React.Fragment>
                      ))}
                    </div>
                    {dp.relationships && dp.relationships.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {dp.relationships.map((rel, ri) => (
                          <span
                            key={ri}
                            className="text-[10px] text-gray-500 bg-gray-700/50 px-1.5 py-0.5 rounded"
                          >
                            {rel}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ImpactAnalysis;
