import React, { useState } from 'react';
import {
  FileCode,
  FunctionSquare,
  Box,
  Package,
  RefreshCw,
  CheckCircle,
  AlertCircle,
  Clock,
} from 'lucide-react';
import * as api from '@/services/api';
import LoadingSpinner from '@/components/common/LoadingSpinner';
import type { Repository, IngestionResult } from '@/types';

interface OverviewProps {
  repo: Repository;
  onRefresh: () => void;
}

const Overview: React.FC<OverviewProps> = ({ repo, onRefresh }) => {
  const [ingesting, setIngesting] = useState(false);
  const [ingestionResult, setIngestionResult] = useState<IngestionResult | null>(
    repo.last_ingestion ?? null
  );
  const [ingestionError, setIngestionError] = useState<string | null>(null);

  const handleIngest = async () => {
    setIngesting(true);
    setIngestionError(null);
    try {
      const result = await api.ingestRepository(repo.id);
      setIngestionResult(result);
      onRefresh();
    } catch (err: unknown) {
      setIngestionError(err instanceof Error ? err.message : 'Ingestion failed');
    } finally {
      setIngesting(false);
    }
  };

  const stats = [
    {
      label: 'Files',
      value: repo.file_count || 0,
      icon: FileCode,
      color: 'text-green-400',
      bg: 'bg-green-500/10',
    },
    {
      label: 'Functions',
      value: repo.function_count || 0,
      icon: FunctionSquare,
      color: 'text-blue-400',
      bg: 'bg-blue-500/10',
    },
    {
      label: 'Classes',
      value: repo.class_count || 0,
      icon: Box,
      color: 'text-purple-400',
      bg: 'bg-purple-500/10',
    },
    {
      label: 'Modules',
      value: repo.module_count || 0,
      icon: Package,
      color: 'text-yellow-400',
      bg: 'bg-yellow-500/10',
    },
  ];

  return (
    <div className="p-6 max-w-5xl">
      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div
              key={stat.label}
              className="bg-gray-900 border border-gray-800 rounded-xl p-5"
            >
              <div className="flex items-center gap-3">
                <div className={`p-2.5 rounded-lg ${stat.bg}`}>
                  <Icon className={`w-5 h-5 ${stat.color}`} />
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-100">
                    {stat.value.toLocaleString()}
                  </p>
                  <p className="text-xs text-gray-400">{stat.label}</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Ingestion Section */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-100">Ingestion</h3>
          <button
            onClick={handleIngest}
            disabled={ingesting}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${ingesting ? 'animate-spin' : ''}`} />
            {ingesting ? 'Ingesting...' : 'Run Ingestion'}
          </button>
        </div>

        {ingesting && (
          <LoadingSpinner size="sm" message="Processing repository..." />
        )}

        {ingestionError && (
          <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
            <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
            <p className="text-sm text-red-300">{ingestionError}</p>
          </div>
        )}

        {ingestionResult && !ingesting && (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              {ingestionResult.status === 'completed' ? (
                <CheckCircle className="w-5 h-5 text-green-400" />
              ) : (
                <AlertCircle className="w-5 h-5 text-yellow-400" />
              )}
              <span className="text-sm font-medium text-gray-200 capitalize">
                {ingestionResult.status}
              </span>
              {ingestionResult.duration_seconds != null && (
                <span className="flex items-center gap-1 text-xs text-gray-500 ml-2">
                  <Clock className="w-3 h-3" />
                  {ingestionResult.duration_seconds.toFixed(1)}s
                </span>
              )}
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Stat label="Files Processed" value={ingestionResult.files_processed} />
              <Stat label="Functions Found" value={ingestionResult.functions_found} />
              <Stat label="Classes Found" value={ingestionResult.classes_found} />
              <Stat label="Modules Found" value={ingestionResult.modules_found} />
            </div>

            {ingestionResult.errors && ingestionResult.errors.length > 0 && (
              <div className="mt-3">
                <p className="text-sm font-medium text-yellow-400 mb-2">
                  Errors ({ingestionResult.errors.length})
                </p>
                <div className="max-h-40 overflow-auto space-y-1">
                  {ingestionResult.errors.map((err, i) => (
                    <p key={i} className="text-xs text-gray-400 font-mono bg-gray-800 p-2 rounded">
                      {err}
                    </p>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {!ingestionResult && !ingesting && !ingestionError && (
          <p className="text-sm text-gray-500">
            No ingestion has been run yet. Click "Run Ingestion" to analyze this repository.
          </p>
        )}
      </div>

      {/* Repository Details */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h3 className="text-lg font-semibold text-gray-100 mb-4">Details</h3>
        <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Detail label="ID" value={repo.id} mono />
          <Detail label="Path" value={repo.path} mono />
          <Detail label="Status" value={repo.status} />
          <Detail label="Created" value={new Date(repo.created_at).toLocaleString()} />
        </dl>
      </div>
    </div>
  );
};

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-gray-800 rounded-lg p-3">
      <p className="text-lg font-bold text-gray-100">{value.toLocaleString()}</p>
      <p className="text-xs text-gray-400">{label}</p>
    </div>
  );
}

function Detail({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="text-xs text-gray-500 uppercase tracking-wider">{label}</dt>
      <dd className={`text-sm text-gray-200 mt-0.5 ${mono ? 'font-mono' : ''}`}>
        {value}
      </dd>
    </div>
  );
}

export default Overview;
