import React, { useState } from "react";
import {
  FileCode,
  Code2,
  Boxes,
  Layers,
  Play,
  CheckCircle2,
  FolderOpen,
  RefreshCw,
  AlertCircle,
  FolderGit2,
} from "lucide-react";
import { Repository } from "../types";
import { ingestRepository } from "../services/api";

interface DashboardProps {
  activeRepo: Repository | null;
  repositories: Repository[];
  onSelectRepo: (repo: Repository) => void;
  onRefreshRepos: () => Promise<void>;
  onNavigateToTab: (tab: "explorer" | "graph" | "chat" | "impact") => void;
}

export const Dashboard: React.FC<DashboardProps> = ({
  activeRepo,
  repositories,
  onSelectRepo,
  onRefreshRepos,
  onNavigateToTab,
}) => {
  const [ingesting, setIngesting] = useState(false);
  const [ingestStats, setIngestStats] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleIngest = async () => {
    if (!activeRepo) return;
    setIngesting(true);
    setError(null);
    try {
      const res = await ingestRepository(activeRepo.id);
      setIngestStats(res.stats);
      await onRefreshRepos();
    } catch (err: any) {
      setError(err.message || "Ingestion failed");
    } finally {
      setIngesting(false);
    }
  };

  if (!activeRepo) {
    return (
      <div className="p-12 text-center max-w-lg mx-auto">
        <FolderOpen className="h-12 w-12 text-slate-600 mx-auto mb-4" />
        <h2 className="text-lg font-bold text-slate-200">No Repository Selected</h2>
        <p className="text-xs text-slate-400 mt-1 mb-6">
          Register or select a local Python repository to inspect code structure and knowledge graphs.
        </p>
      </div>
    );
  }

  const statCards = [
    { label: "Python Files", value: activeRepo.total_files, icon: FileCode, color: "text-blue-400" },
    { label: "Functions & Methods", value: activeRepo.total_functions, icon: Code2, color: "text-emerald-400" },
    { label: "Classes Defined", value: activeRepo.total_classes, icon: Boxes, color: "text-purple-400" },
    { label: "Total Code Lines", value: activeRepo.total_lines, icon: Layers, color: "text-amber-400" },
  ];

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-in fade-in duration-200">
      {/* Header Banner */}
      <div className="glass-panel rounded-xl p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-xl font-bold text-white">{activeRepo.name}</h1>
            <span
              className={`px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider ${
                activeRepo.status === "indexed"
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                  : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
              }`}
            >
              {activeRepo.status}
            </span>
          </div>
          <p className="text-xs font-mono text-slate-400 mt-1 flex items-center space-x-1.5">
            <FolderOpen className="h-3.5 w-3.5" />
            <span>{activeRepo.root_path}</span>
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={handleIngest}
            disabled={ingesting}
            className="flex items-center space-x-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shadow-lg shadow-indigo-600/25 transition-all active:scale-95"
          >
            {ingesting ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin" />
                <span>Parsing & Indexing...</span>
              </>
            ) : (
              <>
                <Play className="h-4 w-4 fill-white" />
                <span>{activeRepo.status === "indexed" ? "Re-index Codebase" : "Ingest & Build Graph"}</span>
              </>
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-400 flex items-center space-x-2">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {ingestStats && (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-xs text-emerald-300 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            <span>
              Ingestion complete! Processed {ingestStats.files || activeRepo.total_files} files,{" "}
              {ingestStats.functions || activeRepo.total_functions} functions, and {ingestStats.calls || 0} calls into Neo4j.
            </span>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => onNavigateToTab("explorer")}
              className="text-xs font-semibold underline hover:text-white"
            >
              Explore Code
            </button>
            <span>•</span>
            <button
              onClick={() => onNavigateToTab("graph")}
              className="text-xs font-semibold underline hover:text-white"
            >
              View Graph
            </button>
          </div>
        </div>
      )}

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((stat, idx) => {
          const Icon = stat.icon;
          return (
            <div key={idx} className="glass-panel p-5 rounded-xl flex items-center space-x-4">
              <div className={`p-3 rounded-lg bg-slate-800/80 ${stat.color}`}>
                <Icon className="h-6 w-6" />
              </div>
              <div>
                <span className="text-2xl font-bold text-white block">
                  {stat.value.toLocaleString()}
                </span>
                <span className="text-xs text-slate-400 font-medium">{stat.label}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Quick Access Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div
          onClick={() => onNavigateToTab("explorer")}
          className="glass-panel p-6 rounded-xl cursor-pointer hover:border-indigo-500/40 transition-all group"
        >
          <Code2 className="h-6 w-6 text-indigo-400 mb-3 group-hover:scale-110 transition-transform" />
          <h3 className="text-sm font-bold text-white mb-1">Code Explorer</h3>
          <p className="text-xs text-slate-400">
            Browse AST entities, view exact source code lines, functions, classes, and calls.
          </p>
        </div>

        <div
          onClick={() => onNavigateToTab("graph")}
          className="glass-panel p-6 rounded-xl cursor-pointer hover:border-indigo-500/40 transition-all group"
        >
          <Boxes className="h-6 w-6 text-purple-400 mb-3 group-hover:scale-110 transition-transform" />
          <h3 className="text-sm font-bold text-white mb-1">Knowledge Graph</h3>
          <p className="text-xs text-slate-400">
            Visualize caller-callee neighborhoods, class inheritance, and file dependencies.
          </p>
        </div>

        <div
          onClick={() => onNavigateToTab("impact")}
          className="glass-panel p-6 rounded-xl cursor-pointer hover:border-indigo-500/40 transition-all group"
        >
          <Layers className="h-6 w-6 text-emerald-400 mb-3 group-hover:scale-110 transition-transform" />
          <h3 className="text-sm font-bold text-white mb-1">Impact Analysis</h3>
          <p className="text-xs text-slate-400">
            Select any function to calculate blast radius before making code modifications.
          </p>
        </div>
      </div>

      {/* Registered Repositories List */}
      <div className="glass-panel p-6 rounded-xl space-y-3">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center space-x-1.5">
          <FolderGit2 className="h-4 w-4 text-indigo-400" />
          <span>Registered Repositories ({repositories.length})</span>
        </h3>
        <div className="space-y-2">
          {repositories.map((repo) => (
            <div
              key={repo.id}
              onClick={() => onSelectRepo(repo)}
              className={`p-3 rounded-lg border flex items-center justify-between cursor-pointer transition-colors ${
                repo.id === activeRepo.id
                  ? "bg-indigo-950/40 border-indigo-500/40 text-white"
                  : "bg-slate-900/60 border-slate-800 text-slate-300 hover:border-slate-700"
              }`}
            >
              <div>
                <span className="font-bold text-xs">{repo.name}</span>
                <span className="text-[11px] text-slate-500 block font-mono">{repo.root_path}</span>
              </div>
              <div className="text-right text-[11px] text-slate-400">
                <span>{repo.total_files} files • {repo.total_functions} functions</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
