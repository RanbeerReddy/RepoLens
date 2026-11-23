import React from "react";
import { FolderGit2, Plus, Database, Cpu } from "lucide-react";
import { Repository } from "../types";

interface NavbarProps {
  repositories: Repository[];
  activeRepo: Repository | null;
  onSelectRepo: (repo: Repository) => void;
  onOpenRegister: () => void;
  health: { neo4j: boolean; llm: boolean };
}

export const Navbar: React.FC<NavbarProps> = ({
  repositories,
  activeRepo,
  onSelectRepo,
  onOpenRegister,
  health,
}) => {
  return (
    <header className="h-16 border-b border-slate-800 bg-[#0f172a]/80 backdrop-blur px-6 flex items-center justify-between sticky top-0 z-40">
      {/* Brand */}
      <div className="flex items-center space-x-3">
        <div className="h-9 w-9 rounded-lg bg-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-500/25">
          <FolderGit2 className="h-5 w-5 text-white" />
        </div>
        <div>
          <span className="font-bold text-lg bg-gradient-to-r from-white via-slate-200 to-indigo-300 bg-clip-text text-transparent">
            RepoLens
          </span>
          <span className="ml-2 text-xs font-semibold px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            Intelligence
          </span>
        </div>
      </div>

      {/* Center: Repository Selector */}
      <div className="flex items-center space-x-3">
        <div className="flex items-center bg-slate-900/90 border border-slate-800 rounded-lg px-3 py-1.5 focus-within:border-indigo-500 transition-colors">
          <span className="text-xs text-slate-400 mr-2 font-medium">Repo:</span>
          <select
            className="bg-transparent text-sm text-slate-200 font-medium focus:outline-none cursor-pointer pr-4"
            value={activeRepo?.id || ""}
            onChange={(e) => {
              const selected = repositories.find((r) => r.id === e.target.value);
              if (selected) onSelectRepo(selected);
            }}
          >
            {repositories.length === 0 && <option value="">No repositories registered</option>}
            {repositories.map((repo) => (
              <option key={repo.id} value={repo.id} className="bg-slate-900 text-slate-200">
                {repo.name} ({repo.status})
              </option>
            ))}
          </select>
        </div>

        <button
          onClick={onOpenRegister}
          className="flex items-center space-x-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-sm transition-all active:scale-95"
        >
          <Plus className="h-3.5 w-3.5" />
          <span>Add Repo</span>
        </button>
      </div>

      {/* Right: Service Status Badges */}
      <div className="flex items-center space-x-3 text-xs font-medium">
        <div
          className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full border ${
            health.neo4j
              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
              : "bg-slate-800 border-slate-700 text-slate-400"
          }`}
          title={health.neo4j ? "Neo4j Connected" : "Neo4j Offline (Using in-memory engine)"}
        >
          <Database className="h-3.5 w-3.5" />
          <span>Neo4j: {health.neo4j ? "Online" : "Offline"}</span>
        </div>

        <div
          className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full border ${
            health.llm
              ? "bg-indigo-500/10 border-indigo-500/30 text-indigo-400"
              : "bg-slate-800 border-slate-700 text-slate-400"
          }`}
          title={health.llm ? "vLLM Inference Online" : "vLLM Offline (Using evidence extraction fallback)"}
        >
          <Cpu className="h-3.5 w-3.5" />
          <span>vLLM: {health.llm ? "Online" : "Offline"}</span>
        </div>
      </div>
    </header>
  );
};
