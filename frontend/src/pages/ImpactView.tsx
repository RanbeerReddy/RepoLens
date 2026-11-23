import React, { useState } from "react";
import {
  GitBranch,
  FileCode,
  ArrowRight,
  Search,
} from "lucide-react";
import { ImpactReport, Repository } from "../types";
import { analyzeImpact } from "../services/api";

interface ImpactViewProps {
  activeRepo: Repository;
  initialFunction?: string;
}

export const ImpactView: React.FC<ImpactViewProps> = ({
  activeRepo,
  initialFunction,
}) => {
  const [functionName, setFunctionName] = useState(initialFunction || "");
  const [report, setReport] = useState<ImpactReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!functionName.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const res = await analyzeImpact(activeRepo.id, functionName.trim());
      setReport(res);
    } catch (err: any) {
      setError(err.message || "Impact analysis failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-[calc(100vh-112px)] overflow-y-auto p-8 max-w-5xl mx-auto space-y-6">
      {/* Header and Input */}
      <div className="glass-panel p-6 rounded-xl space-y-4">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center space-x-2">
            <GitBranch className="h-5 w-5 text-indigo-400" />
            <span>Change Impact Blast-Radius Analysis</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Identify all direct callers, transitive dependents, and potentially affected test suites before modifying code.
          </p>
        </div>

        <form onSubmit={handleAnalyze} className="flex items-center space-x-3">
          <div className="relative flex-1">
            <Search className="h-4 w-4 absolute left-3 top-3 text-slate-500" />
            <input
              type="text"
              placeholder="Enter function name (e.g. authenticate_user, verify_password)..."
              value={functionName}
              onChange={(e) => setFunctionName(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 font-mono"
            />
          </div>
          <button
            type="submit"
            disabled={loading || !functionName.trim()}
            className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shadow transition-all active:scale-95 shrink-0"
          >
            {loading ? "Analyzing..." : "Analyze Impact"}
          </button>
        </form>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-400">
          {error}
        </div>
      )}

      {/* Impact Report Card */}
      {report && (
        <div className="space-y-6 animate-in fade-in duration-200">
          {/* Target Overview & Badge */}
          <div className="glass-panel p-6 rounded-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                Target Analyzed
              </span>
              <div className="text-lg font-bold font-mono text-white mt-0.5">
                {report.target_function}()
              </div>
              <div className="text-xs text-slate-400 font-mono mt-0.5">
                {report.target_file_path}
              </div>
            </div>

            <div className="text-right">
              <span
                className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider inline-block ${
                  report.impact_level === "LOW"
                    ? "badge-low"
                    : report.impact_level === "MEDIUM"
                    ? "badge-medium"
                    : "badge-high"
                }`}
              >
                {report.impact_level} IMPACT
              </span>
              <span className="text-[11px] text-slate-400 block mt-1">
                {report.heuristic_rationale}
              </span>
            </div>
          </div>

          {/* AI Risk Assessment Card */}
          <div className="glass-panel p-5 rounded-xl border-l-4 border-l-indigo-500 bg-slate-900/60">
            <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-400 block mb-1">
              Architecture Impact Assessment
            </span>
            <p className="text-xs text-slate-200 leading-relaxed font-sans">
              {report.analysis_summary}
            </p>
            <p className="text-[10px] text-slate-500 mt-2 italic">
              {report.disclaimer}
            </p>
          </div>

          {/* Callers & Affected Files Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Direct Callers */}
            <div className="glass-panel p-5 rounded-xl space-y-3">
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Direct Dependents ({report.direct_callers.length})
              </h3>
              {report.direct_callers.length === 0 ? (
                <div className="text-xs text-slate-500 italic">No direct upstream callers detected.</div>
              ) : (
                <div className="space-y-1.5 font-mono text-xs">
                  {report.direct_callers.map((c) => (
                    <div
                      key={c.id}
                      className="p-2 bg-slate-900/80 rounded border border-slate-800 flex items-center justify-between"
                    >
                      <span className="text-emerald-400 font-semibold">{c.name}()</span>
                      <span className="text-slate-500 text-[10px]">
                        {c.file_path}:{c.start_line}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Affected Files & Tests */}
            <div className="glass-panel p-5 rounded-xl space-y-3">
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Affected Files ({report.affected_files.length})
              </h3>
              <div className="space-y-1.5 font-mono text-xs">
                {report.affected_files.map((file) => {
                  const isTest = report.relevant_tests.includes(file);
                  return (
                    <div
                      key={file}
                      className={`p-2 rounded border flex items-center justify-between ${
                        isTest
                          ? "bg-amber-500/10 border-amber-500/20 text-amber-300"
                          : "bg-slate-900/80 border-slate-800 text-slate-300"
                      }`}
                    >
                      <div className="flex items-center space-x-2">
                        <FileCode className="h-3.5 w-3.5" />
                        <span>{file}</span>
                      </div>
                      {isTest && (
                        <span className="text-[10px] font-bold uppercase tracking-wider bg-amber-500/20 px-1.5 py-0.5 rounded text-amber-400">
                          Test Suite
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Dependency Chains */}
          {report.dependency_paths.length > 0 && (
            <div className="glass-panel p-5 rounded-xl space-y-3">
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Execution Chains ({report.dependency_paths.length})
              </h3>
              <div className="space-y-1 font-mono text-xs">
                {report.dependency_paths.map((path, idx) => (
                  <div key={idx} className="p-2 bg-slate-950/60 rounded text-slate-300 flex items-center space-x-2">
                    <ArrowRight className="h-3.5 w-3.5 text-indigo-400 shrink-0" />
                    <span>{path}</span>
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
