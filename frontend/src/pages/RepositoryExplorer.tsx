import React, { useState, useEffect } from "react";
import {
  FileCode,
  Code2,
  Boxes,
  Search,
  ChevronRight,
} from "lucide-react";
import { FileDetails, Repository } from "../types";
import { listFiles, getFileDetails } from "../services/api";

interface RepositoryExplorerProps {
  activeRepo: Repository;
  initialFile?: string;
  onOpenImpact?: (funcName: string) => void;
}

export const RepositoryExplorer: React.FC<RepositoryExplorerProps> = ({
  activeRepo,
  initialFile,
  onOpenImpact,
}) => {
  const [files, setFiles] = useState<string[]>([]);
  const [fileFilter, setFileFilter] = useState("");
  const [selectedFile, setSelectedFile] = useState<string | null>(initialFile || null);
  const [fileDetails, setFileDetails] = useState<FileDetails | null>(null);
  const [loadingFile, setLoadingFile] = useState(false);
  const [selectedFunc, setSelectedFunc] = useState<string | null>(null);

  useEffect(() => {
    listFiles(activeRepo.id).then((res) => {
      setFiles(res);
      if (!selectedFile && res.length > 0) {
        setSelectedFile(res[0]);
      }
    });
  }, [activeRepo.id]);

  useEffect(() => {
    if (!selectedFile) return;
    setLoadingFile(true);
    getFileDetails(activeRepo.id, selectedFile)
      .then((data) => setFileDetails(data))
      .catch(() => setFileDetails(null))
      .finally(() => setLoadingFile(false));
  }, [selectedFile, activeRepo.id]);

  const filteredFiles = files.filter((f) =>
    f.toLowerCase().includes(fileFilter.toLowerCase())
  );

  return (
    <div className="h-[calc(100vh-112px)] flex overflow-hidden">
      {/* Left Sidebar: File Tree */}
      <div className="w-72 border-r border-slate-800 bg-[#0d1322] flex flex-col shrink-0">
        <div className="p-3 border-b border-slate-800">
          <div className="relative">
            <Search className="h-3.5 w-3.5 absolute left-3 top-2.5 text-slate-500" />
            <input
              type="text"
              placeholder="Filter files..."
              value={fileFilter}
              onChange={(e) => setFileFilter(e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
          {filteredFiles.map((f) => (
            <button
              key={f}
              onClick={() => setSelectedFile(f)}
              className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs font-mono flex items-center space-x-2 transition-colors ${
                selectedFile === f
                  ? "bg-indigo-600/15 text-indigo-300 font-semibold border border-indigo-500/20"
                  : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
              }`}
            >
              <FileCode className="h-3.5 w-3.5 shrink-0 text-slate-500" />
              <span className="truncate">{f}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Center: Source Code Viewer */}
      <div className="flex-1 flex flex-col bg-[#0b0f19] overflow-hidden">
        {selectedFile && (
          <div className="h-10 border-b border-slate-800 px-4 flex items-center justify-between text-xs text-slate-400 bg-slate-900/40">
            <div className="flex items-center space-x-1 font-mono">
              <span>{selectedFile}</span>
              {fileDetails && (
                <span className="text-slate-500">
                  ({fileDetails.total_lines} lines)
                </span>
              )}
            </div>
          </div>
        )}

        <div className="flex-1 overflow-auto p-4 font-mono text-xs">
          {loadingFile ? (
            <div className="text-slate-500 text-center py-12">Loading file contents...</div>
          ) : fileDetails ? (
            <div className="space-y-0.5">
              {fileDetails.source.split("\n").map((line, idx) => {
                const lineNum = idx + 1;
                const isHighlighted =
                  selectedFunc &&
                  fileDetails.functions.some(
                    (fn) =>
                      fn.name === selectedFunc &&
                      lineNum >= fn.start_line &&
                      lineNum <= fn.end_line
                  );

                return (
                  <div
                    key={idx}
                    className={`flex items-start hover:bg-slate-800/30 px-2 rounded ${
                      isHighlighted ? "bg-indigo-950/40 border-l-2 border-indigo-400" : ""
                    }`}
                  >
                    <span className="w-10 shrink-0 text-slate-600 select-none text-right pr-4">
                      {lineNum}
                    </span>
                    <pre className="text-slate-300 whitespace-pre overflow-x-visible">{line || " "}</pre>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-slate-500 text-center py-12">Select a file to view code.</div>
          )}
        </div>
      </div>

      {/* Right Sidebar: AST Symbol Inspector */}
      {fileDetails && (
        <div className="w-80 border-l border-slate-800 bg-[#0d1322] flex flex-col shrink-0 overflow-y-auto p-4 space-y-6">
          {/* Docstring */}
          {fileDetails.docstring && (
            <div className="p-3 bg-slate-900/80 border border-slate-800 rounded-lg text-xs text-slate-300">
              <span className="text-[10px] uppercase font-bold text-slate-500 block mb-1">
                Module Docstring
              </span>
              <p className="italic text-slate-400">{fileDetails.docstring}</p>
            </div>
          )}

          {/* Classes */}
          {fileDetails.classes.length > 0 && (
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2 flex items-center space-x-1.5">
                <Boxes className="h-3.5 w-3.5 text-purple-400" />
                <span>Classes ({fileDetails.classes.length})</span>
              </h3>
              <div className="space-y-2">
                {fileDetails.classes.map((cls) => (
                  <div key={cls.name} className="p-2.5 bg-slate-900/60 border border-slate-800/80 rounded-lg text-xs">
                    <div className="font-bold text-purple-300 font-mono">{cls.name}</div>
                    {cls.bases.length > 0 && (
                      <div className="text-[11px] text-slate-500 mt-0.5">
                        Inherits: {cls.bases.join(", ")}
                      </div>
                    )}
                    <div className="text-[10px] text-slate-500 mt-1">
                      Lines {cls.start_line} - {cls.end_line}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Functions */}
          {fileDetails.functions.length > 0 && (
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2 flex items-center space-x-1.5">
                <Code2 className="h-3.5 w-3.5 text-emerald-400" />
                <span>Functions & Methods ({fileDetails.functions.length})</span>
              </h3>
              <div className="space-y-2">
                {fileDetails.functions.map((fn) => (
                  <div
                    key={fn.name}
                    onClick={() => setSelectedFunc(fn.name === selectedFunc ? null : fn.name)}
                    className={`p-2.5 rounded-lg border text-xs cursor-pointer transition-all ${
                      selectedFunc === fn.name
                        ? "bg-indigo-950/40 border-indigo-500/40"
                        : "bg-slate-900/60 border-slate-800/80 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-emerald-300 font-mono">{fn.name}()</span>
                      <span className="text-[10px] text-slate-500">
                        L{fn.start_line}-{fn.end_line}
                      </span>
                    </div>

                    <div className="text-[11px] font-mono text-slate-400 truncate mt-1">
                      {fn.signature}
                    </div>

                    {fn.calls.length > 0 && (
                      <div className="text-[11px] text-slate-500 mt-1">
                        Calls: {fn.calls.slice(0, 3).join(", ")}
                        {fn.calls.length > 3 && ` +${fn.calls.length - 3}`}
                      </div>
                    )}

                    {onOpenImpact && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onOpenImpact(fn.name);
                        }}
                        className="mt-2 text-[10px] font-semibold text-indigo-400 hover:text-indigo-300 flex items-center space-x-1"
                      >
                        <span>Analyze Change Impact</span>
                        <ChevronRight className="h-3 w-3" />
                      </button>
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
