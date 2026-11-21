import React, { useState, useCallback, useMemo, useEffect } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeMouseHandler,
  MarkerType,
  BackgroundVariant,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Search, X, Layers } from 'lucide-react';
import { useApi } from '@/hooks/useApi';
import * as api from '@/services/api';
import LoadingSpinner from '@/components/common/LoadingSpinner';
import ErrorMessage from '@/components/common/ErrorMessage';
import Badge from '@/components/common/Badge';
import type { GraphData, GraphNode as GNode } from '@/types';

interface GraphExplorerProps {
  repoId: string;
}

function getNodeColor(type: string): string {
  switch (type.toLowerCase()) {
    case 'function': return '#3b82f6';
    case 'class': return '#a855f7';
    case 'file': return '#22c55e';
    case 'module': return '#eab308';
    default: return '#6b7280';
  }
}

function getNodeShape(type: string): { borderRadius: string } {
  switch (type.toLowerCase()) {
    case 'function': return { borderRadius: '12px' };
    case 'class': return { borderRadius: '0px' }; // diamond handled via rotation style
    case 'file': return { borderRadius: '4px' };
    default: return { borderRadius: '8px' };
  }
}

function mapToFlowNodes(graphNodes: GNode[]): Node[] {
  const cols = Math.ceil(Math.sqrt(graphNodes.length));
  return graphNodes.map((gn, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const color = getNodeColor(gn.type);
    const shape = getNodeShape(gn.type);
    return {
      id: gn.id,
      position: { x: col * 220 + Math.random() * 40, y: row * 120 + Math.random() * 30 },
      data: { label: gn.label, entityType: gn.type, filePath: gn.file_path, qualifiedName: gn.qualified_name },
      style: {
        background: `${color}20`,
        border: `2px solid ${color}`,
        color: '#e5e7eb',
        padding: '8px 14px',
        fontSize: '12px',
        fontFamily: 'ui-monospace, monospace',
        ...shape,
      },
    };
  });
}

function mapToFlowEdges(graphEdges: { id: string; source: string; target: string; relationship: string; label?: string }[]): Edge[] {
  return graphEdges.map((ge) => ({
    id: ge.id,
    source: ge.source,
    target: ge.target,
    label: ge.label || ge.relationship,
    type: 'default',
    animated: ge.relationship === 'CALLS',
    style: { stroke: '#4b5563', strokeWidth: 1.5 },
    labelStyle: { fill: '#9ca3af', fontSize: 10, fontFamily: 'ui-monospace, monospace' },
    labelBgStyle: { fill: '#1f2937', fillOpacity: 0.8 },
    labelBgPadding: [4, 2] as [number, number],
    markerEnd: { type: MarkerType.ArrowClosed, color: '#4b5563', width: 15, height: 15 },
  }));
}

const GraphExplorer: React.FC<GraphExplorerProps> = ({ repoId }) => {
  const [limit, setLimit] = useState(100);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedNode, setSelectedNode] = useState<GNode | null>(null);

  const {
    data: graphData,
    loading,
    error,
    refetch,
  } = useApi<GraphData>(() => api.getGraph(repoId, limit), [repoId, limit]);

  const filteredData = useMemo(() => {
    if (!graphData) return null;
    if (!searchTerm.trim()) return graphData;
    const term = searchTerm.toLowerCase();
    const matchingNodes = graphData.nodes.filter(
      (n) =>
        n.label.toLowerCase().includes(term) ||
        n.type.toLowerCase().includes(term) ||
        (n.file_path && n.file_path.toLowerCase().includes(term))
    );
    const nodeIds = new Set(matchingNodes.map((n) => n.id));
    const matchingEdges = graphData.edges.filter(
      (e) => nodeIds.has(e.source) || nodeIds.has(e.target)
    );
    // Include connected nodes
    matchingEdges.forEach((e) => {
      if (!nodeIds.has(e.source)) {
        const n = graphData.nodes.find((n) => n.id === e.source);
        if (n) { matchingNodes.push(n); nodeIds.add(n.id); }
      }
      if (!nodeIds.has(e.target)) {
        const n = graphData.nodes.find((n) => n.id === e.target);
        if (n) { matchingNodes.push(n); nodeIds.add(n.id); }
      }
    });
    return { nodes: matchingNodes, edges: matchingEdges };
  }, [graphData, searchTerm]);

  const initialNodes = useMemo(() => {
    if (!filteredData) return [];
    return mapToFlowNodes(filteredData.nodes);
  }, [filteredData]);

  const initialEdges = useMemo(() => {
    if (!filteredData) return [];
    return mapToFlowEdges(filteredData.edges);
  }, [filteredData]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  const onNodeClick: NodeMouseHandler = useCallback(
    (_, node) => {
      const gNode = graphData?.nodes.find((n) => n.id === node.id);
      setSelectedNode(gNode || null);
    },
    [graphData]
  );

  if (loading) return <LoadingSpinner message="Loading graph..." />;
  if (error) return <ErrorMessage message={error} onRetry={refetch} />;

  return (
    <div className="h-full flex flex-col">
      {/* Controls bar */}
      <div className="px-4 py-3 border-b border-gray-800 flex items-center gap-4 flex-shrink-0 bg-gray-900/50">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Filter nodes..."
            className="w-full pl-9 pr-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-gray-500" />
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value={50}>50 nodes</option>
            <option value={100}>100 nodes</option>
            <option value={200}>200 nodes</option>
            <option value={500}>500 nodes</option>
          </select>
        </div>
        <div className="text-xs text-gray-500">
          {filteredData?.nodes.length ?? 0} nodes · {filteredData?.edges.length ?? 0} edges
        </div>
      </div>

      {/* Graph */}
      <div className="flex-1 relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.1}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
        >
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1f2937" />
          <Controls />
          <MiniMap
            nodeColor={(n) => getNodeColor(n.data?.entityType as string || '')}
            maskColor="rgba(0,0,0,0.6)"
            style={{ backgroundColor: '#111827' }}
          />
        </ReactFlow>

        {/* Selected node details */}
        {selectedNode && (
          <div className="absolute top-4 right-4 w-72 bg-gray-900 border border-gray-700 rounded-xl shadow-xl z-10">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
              <span className="text-sm font-semibold text-gray-100">Node Details</span>
              <button
                onClick={() => setSelectedNode(null)}
                className="p-1 text-gray-400 hover:text-gray-100 hover:bg-gray-800 rounded"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="px-4 py-3 space-y-3">
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider">Name</p>
                <p className="text-sm text-gray-100 font-mono mt-0.5">{selectedNode.label}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider">Type</p>
                <div className="mt-1">
                  <Badge type={selectedNode.type} />
                </div>
              </div>
              {selectedNode.file_path && (
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-wider">File</p>
                  <p className="text-xs text-gray-300 font-mono mt-0.5 break-all">
                    {selectedNode.file_path}
                  </p>
                </div>
              )}
              {selectedNode.qualified_name && (
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-wider">Qualified Name</p>
                  <p className="text-xs text-gray-300 font-mono mt-0.5 break-all">
                    {selectedNode.qualified_name}
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default GraphExplorer;
