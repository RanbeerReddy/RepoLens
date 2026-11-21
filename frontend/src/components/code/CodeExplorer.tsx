import React, { useState, useMemo } from 'react';
import {
  ChevronRight,
  ChevronDown,
  FileCode,
  FunctionSquare,
  Box,
  Folder,
  FolderOpen,
} from 'lucide-react';
import { useApi } from '@/hooks/useApi';
import * as api from '@/services/api';
import LoadingSpinner from '@/components/common/LoadingSpinner';
import ErrorMessage from '@/components/common/ErrorMessage';
import Badge from '@/components/common/Badge';
import type { Symbol } from '@/types';

interface CodeExplorerProps {
  repoId: string;
}

interface FileTreeNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  children: FileTreeNode[];
  symbols: Symbol[];
}

function buildFileTree(symbols: Symbol[]): FileTreeNode[] {
  const root: Map<string, FileTreeNode> = new Map();

  const getOrCreateDir = (parts: string[], depth: number): FileTreeNode => {
    const path = parts.slice(0, depth + 1).join('/');
    if (!root.has(path)) {
      root.set(path, {
        name: parts[depth],
        path,
        type: 'directory',
        children: [],
        symbols: [],
      });
    }
    return root.get(path)!;
  };

  symbols.forEach((sym) => {
    const parts = sym.file_path.split('/').filter(Boolean);
    if (parts.length === 0) return;

    // Build directory chain
    for (let i = 0; i < parts.length - 1; i++) {
      const parent = i === 0 ? null : getOrCreateDir(parts, i - 1);
      const dir = getOrCreateDir(parts, i);
      if (parent && !parent.children.find((c) => c.path === dir.path)) {
        parent.children.push(dir);
      }
    }

    // Add file node
    const filePath = sym.file_path;
    if (!root.has(filePath)) {
      root.set(filePath, {
        name: parts[parts.length - 1],
        path: filePath,
        type: 'file',
        children: [],
        symbols: [],
      });
    }
    root.get(filePath)!.symbols.push(sym);

    // Attach file to parent directory
    if (parts.length > 1) {
      const parent = getOrCreateDir(parts, parts.length - 2);
      if (!parent.children.find((c) => c.path === filePath)) {
        parent.children.push(root.get(filePath)!);
      }
    }
  });

  // Return top-level nodes
  const topLevel: FileTreeNode[] = [];
  const allPaths = new Set(root.keys());
  root.forEach((node) => {
    const parts = node.path.split('/').filter(Boolean);
    if (parts.length === 1) {
      topLevel.push(node);
    }
  });

  // Sort: directories first, then alphabetical
  const sortNodes = (nodes: FileTreeNode[]) => {
    nodes.sort((a, b) => {
      if (a.type !== b.type) return a.type === 'directory' ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    nodes.forEach((n) => sortNodes(n.children));
  };
  sortNodes(topLevel);
  return topLevel;
}

const CodeExplorer: React.FC<CodeExplorerProps> = ({ repoId }) => {
  const {
    data: symbols,
    loading,
    error,
    refetch,
  } = useApi<Symbol[]>(() => api.getSymbols(repoId, { limit: 5000 }), [repoId]);

  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set());

  const fileTree = useMemo(() => {
    if (!symbols) return [];
    return buildFileTree(symbols);
  }, [symbols]);

  const selectedSymbols = useMemo(() => {
    if (!symbols || !selectedFile) return [];
    return symbols.filter((s) => s.file_path === selectedFile);
  }, [symbols, selectedFile]);

  const selectedSource = useMemo(() => {
    if (!selectedSymbols.length) return '';
    // Build a combined source view from all symbols in this file
    const sorted = [...selectedSymbols].sort((a, b) => a.line_start - b.line_start);
    return sorted.map((s) => s.source).join('\n\n');
  }, [selectedSymbols]);

  const toggleDir = (path: string) => {
    setExpandedDirs((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  if (loading) return <LoadingSpinner message="Loading code..." />;
  if (error) return <ErrorMessage message={error} onRetry={refetch} />;

  return (
    <div className="flex h-full">
      {/* File tree */}
      <div className="w-72 border-r border-gray-800 overflow-auto flex-shrink-0 bg-gray-900/50">
        <div className="px-3 py-3 border-b border-gray-800">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
            Files
          </p>
        </div>
        <div className="py-1">
          {fileTree.length > 0 ? (
            fileTree.map((node) => (
              <TreeNode
                key={node.path}
                node={node}
                depth={0}
                expandedDirs={expandedDirs}
                selectedFile={selectedFile}
                onToggleDir={toggleDir}
                onSelectFile={setSelectedFile}
              />
            ))
          ) : (
            <p className="text-xs text-gray-500 px-4 py-6 text-center">
              No files found. Run ingestion first.
            </p>
          )}
        </div>
      </div>

      {/* Source view + symbols panel */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Source code */}
        <div className="flex-1 overflow-auto">
          {selectedFile ? (
            <div className="p-0">
              <div className="px-4 py-2 bg-gray-900 border-b border-gray-800 sticky top-0 z-10">
                <p className="text-xs text-gray-400 font-mono">{selectedFile}</p>
              </div>
              <pre className="text-sm font-mono p-4 leading-relaxed">
                {selectedSource ? (
                  selectedSource.split('\n').map((line, i) => (
                    <div key={i} className="flex hover:bg-gray-900/50">
                      <span className="inline-block w-12 text-right pr-4 text-gray-600 select-none flex-shrink-0">
                        {i + 1}
                      </span>
                      <span className="text-gray-200 whitespace-pre-wrap break-all">
                        {line || ' '}
                      </span>
                    </div>
                  ))
                ) : (
                  <span className="text-gray-500">No source available</span>
                )}
              </pre>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <FileCode className="w-10 h-10 text-gray-700 mx-auto mb-3" />
                <p className="text-sm text-gray-500">
                  Select a file from the tree to view its source
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Bottom panel: symbols in selected file */}
        {selectedFile && selectedSymbols.length > 0 && (
          <div className="border-t border-gray-800 max-h-56 overflow-auto bg-gray-900/50 flex-shrink-0">
            <div className="px-4 py-2 border-b border-gray-800 sticky top-0 bg-gray-900 z-10">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                Symbols ({selectedSymbols.length})
              </p>
            </div>
            <div className="divide-y divide-gray-800">
              {selectedSymbols.map((sym) => (
                <div
                  key={sym.id}
                  className="px-4 py-2.5 flex items-center gap-3 hover:bg-gray-800/50"
                >
                  {sym.entity_type === 'function' ? (
                    <FunctionSquare className="w-4 h-4 text-blue-400 flex-shrink-0" />
                  ) : (
                    <Box className="w-4 h-4 text-purple-400 flex-shrink-0" />
                  )}
                  <div className="min-w-0">
                    <p className="text-sm text-gray-200 font-mono truncate">
                      {sym.signature || sym.name}
                    </p>
                    <p className="text-xs text-gray-500">
                      Lines {sym.line_start}–{sym.line_end}
                    </p>
                  </div>
                  <Badge type={sym.entity_type} />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

function TreeNode({
  node,
  depth,
  expandedDirs,
  selectedFile,
  onToggleDir,
  onSelectFile,
}: {
  node: FileTreeNode;
  depth: number;
  expandedDirs: Set<string>;
  selectedFile: string | null;
  onToggleDir: (path: string) => void;
  onSelectFile: (path: string) => void;
}) {
  const isDir = node.type === 'directory';
  const isExpanded = expandedDirs.has(node.path);
  const isSelected = !isDir && selectedFile === node.path;

  return (
    <>
      <button
        className={`w-full flex items-center gap-1.5 px-2 py-1.5 text-left text-sm hover:bg-gray-800/50 transition-colors ${
          isSelected ? 'bg-blue-600/20 text-blue-300' : 'text-gray-300'
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={() => {
          if (isDir) onToggleDir(node.path);
          else onSelectFile(node.path);
        }}
      >
        {isDir ? (
          <>
            {isExpanded ? (
              <ChevronDown className="w-3.5 h-3.5 text-gray-500 flex-shrink-0" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-gray-500 flex-shrink-0" />
            )}
            {isExpanded ? (
              <FolderOpen className="w-4 h-4 text-yellow-500 flex-shrink-0" />
            ) : (
              <Folder className="w-4 h-4 text-yellow-500 flex-shrink-0" />
            )}
          </>
        ) : (
          <>
            <span className="w-3.5 flex-shrink-0" />
            <FileCode className="w-4 h-4 text-gray-500 flex-shrink-0" />
          </>
        )}
        <span className="truncate">{node.name}</span>
      </button>
      {isDir && isExpanded &&
        node.children.map((child) => (
          <TreeNode
            key={child.path}
            node={child}
            depth={depth + 1}
            expandedDirs={expandedDirs}
            selectedFile={selectedFile}
            onToggleDir={onToggleDir}
            onSelectFile={onSelectFile}
          />
        ))}
    </>
  );
}

export default CodeExplorer;
