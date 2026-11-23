import React, { useState, useEffect } from "react";
import { Search, Network } from "lucide-react";
import { GraphData, Repository } from "../types";
import { getGraphData } from "../services/api";

interface GraphExplorerProps {
  activeRepo: Repository;
}

export const GraphExplorer: React.FC<GraphExplorerProps> = ({ activeRepo }) => {
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], edges: [] });
  const [focusQuery, setFocusQuery] = useState("");
  const [selectedNode, setSelectedNode] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchGraph = (focus?: string) => {
    setLoading(true);
    getGraphData(activeRepo.id, focus)
      .then((data) => setGraphData(data))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchGraph();
  }, [activeRepo.id]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchGraph(focusQuery.trim() || undefined);
  };

  return (
    <div className="h-[calc(100vh-112px)] flex flex-col overflow-hidden bg-[#0b0f19]">
      {/* Top Search & Filter Bar */}
      <div className="h-14 border-b border-slate-800 bg-[#0d1322] px-6 flex items-center justify-between">
        <form onSubmit={handleSearch} className="flex items-center space-x-3">
          <div className="relative w-72">
            <Search className="h-3.5 w-3.5 absolute left-3 top-2.5 text-slate-500" />
            <input
              type="text"
              placeholder="Focus symbol (e.g. authenticate_user)..."
              value={focusQuery}
              onChange={(e) => setFocusQuery(e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 font-mono"
            />
          </div>
          <button
            type="submit"
            className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow transition-all"
          >
            Center Graph
          </button>
        </form>

        <div className="flex items-center space-x-4 text-xs">
          <span className="flex items-center space-x-1.5 text-blue-400">
            <span className="h-2.5 w-2.5 rounded-full bg-blue-500 inline-block" />
            <span>File</span>
          </span>
          <span className="flex items-center space-x-1.5 text-purple-400">
            <span className="h-2.5 w-2.5 rounded-full bg-purple-500 inline-block" />
            <span>Class</span>
          </span>
          <span className="flex items-center space-x-1.5 text-emerald-400">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 inline-block" />
            <span>Function</span>
          </span>
        </div>
      </div>

      {/* Main Canvas Area */}
      <div className="flex-1 flex overflow-hidden relative">
        <div className="flex-1 p-6 overflow-auto flex items-center justify-center">
          {loading ? (
            <div className="text-slate-500 text-sm">Rendering dependency graph...</div>
          ) : graphData.nodes.length === 0 ? (
            <div className="text-slate-500 text-sm text-center">
              <Network className="h-10 w-10 mx-auto mb-2 opacity-50" />
              <span>No graph nodes available. Ingest the codebase to build relationships.</span>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 max-w-5xl">
              {graphData.nodes.map((node) => {
                const colorMap = {
                  file: "border-blue-500/30 bg-blue-500/10 text-blue-300",
                  class: "border-purple-500/30 bg-purple-500/10 text-purple-300",
                  function: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
                };
                const badgeColor = colorMap[node.type] || "border-slate-700 bg-slate-800 text-slate-300";

                return (
                  <div
                    key={node.id}
                    onClick={() => setSelectedNode(node)}
                    className={`p-3 rounded-lg border cursor-pointer transition-all hover:scale-105 ${badgeColor} ${
                      selectedNode?.id === node.id ? "ring-2 ring-indigo-400" : ""
                    }`}
                  >
                    <span className="text-[10px] font-bold uppercase tracking-wider block opacity-70 mb-0.5">
                      {node.type}
                    </span>
                    <span className="font-mono text-xs font-bold block truncate">{node.label}</span>
                    {node.file_path && (
                      <span className="text-[10px] text-slate-400 block truncate mt-1">
                        {node.file_path}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Selected Node Inspector Drawer */}
        {selectedNode && (
          <div className="w-80 border-l border-slate-800 bg-[#0d1322] p-5 shrink-0 overflow-y-auto">
            <h3 className="text-sm font-bold text-white mb-2">{selectedNode.label}</h3>
            <div className="space-y-3 text-xs">
              <div>
                <span className="text-slate-500 block">Node ID:</span>
                <span className="font-mono text-slate-300 break-all">{selectedNode.id}</span>
              </div>
              <div>
                <span className="text-slate-500 block">Type:</span>
                <span className="font-bold text-slate-300 uppercase">{selectedNode.type}</span>
              </div>
              {selectedNode.file_path && (
                <div>
                  <span className="text-slate-500 block">File:</span>
                  <span className="font-mono text-slate-300">{selectedNode.file_path}</span>
                </div>
              )}

              <div className="pt-4 border-t border-slate-800">
                <span className="text-slate-400 font-semibold block mb-2">Connected Relationships:</span>
                <div className="space-y-1 font-mono text-[11px]">
                  {graphData.edges
                    .filter((e) => e.source === selectedNode.id || e.target === selectedNode.id)
                    .map((e, idx) => (
                      <div key={idx} className="p-1.5 bg-slate-900 rounded text-slate-300">
                        <span className="text-indigo-400">{e.type}</span>:{" "}
                        {e.source === selectedNode.id ? `-> ${e.target}` : `<- ${e.source}`}
                      </div>
                    ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
