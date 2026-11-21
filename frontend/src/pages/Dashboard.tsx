import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FolderGit2,
  FileCode,
  FunctionSquare,
  Box,
  Plus,
  ArrowRight,
} from 'lucide-react';
import { useApi } from '@/hooks/useApi';
import * as api from '@/services/api';
import LoadingSpinner from '@/components/common/LoadingSpinner';
import ErrorMessage from '@/components/common/ErrorMessage';
import Modal from '@/components/common/Modal';
import { formatDate } from '@/utils/format';
import type { Repository } from '@/types';

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const {
    data: repositories,
    loading,
    error,
    refetch,
  } = useApi<Repository[]>(() => api.listRepositories(), []);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [repoPath, setRepoPath] = useState('');
  const [repoName, setRepoName] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const totalFiles = repositories?.reduce((s, r) => s + (r.file_count || 0), 0) ?? 0;
  const totalFunctions = repositories?.reduce((s, r) => s + (r.function_count || 0), 0) ?? 0;
  const totalClasses = repositories?.reduce((s, r) => s + (r.class_count || 0), 0) ?? 0;

  const handleCreate = async () => {
    if (!repoPath.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      const repo = await api.createRepository(
        repoPath.trim(),
        repoName.trim() || repoPath.trim().split('/').pop() || 'repo'
      );
      setIsModalOpen(false);
      setRepoPath('');
      setRepoName('');
      navigate(`/repo/${repo.id}`);
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : 'Failed to add repository');
    } finally {
      setCreating(false);
    }
  };

  if (loading) return <LoadingSpinner message="Loading dashboard..." />;
  if (error) return <ErrorMessage message={error} onRetry={refetch} />;

  const stats = [
    {
      label: 'Repositories',
      value: repositories?.length ?? 0,
      icon: FolderGit2,
      color: 'text-blue-400',
      bg: 'bg-blue-500/10',
    },
    {
      label: 'Files',
      value: totalFiles,
      icon: FileCode,
      color: 'text-green-400',
      bg: 'bg-green-500/10',
    },
    {
      label: 'Functions',
      value: totalFunctions,
      icon: FunctionSquare,
      color: 'text-yellow-400',
      bg: 'bg-yellow-500/10',
    },
    {
      label: 'Classes',
      value: totalClasses,
      icon: Box,
      color: 'text-purple-400',
      bg: 'bg-purple-500/10',
    },
  ];

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Dashboard</h1>
          <p className="text-sm text-gray-400 mt-1">
            Overview of your analyzed repositories
          </p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
        >
          <Plus className="w-4 h-4" />
          Add Repository
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div
              key={stat.label}
              className="bg-gray-900 border border-gray-800 rounded-xl p-5"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-400">{stat.label}</p>
                  <p className="text-2xl font-bold text-gray-100 mt-1">
                    {stat.value.toLocaleString()}
                  </p>
                </div>
                <div className={`p-3 rounded-lg ${stat.bg}`}>
                  <Icon className={`w-6 h-6 ${stat.color}`} />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Recent Repositories */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl">
        <div className="px-6 py-4 border-b border-gray-800">
          <h2 className="text-lg font-semibold text-gray-100">
            Repositories
          </h2>
        </div>
        {repositories && repositories.length > 0 ? (
          <div className="divide-y divide-gray-800">
            {repositories.map((repo) => (
              <button
                key={repo.id}
                onClick={() => navigate(`/repo/${repo.id}`)}
                className="w-full flex items-center justify-between px-6 py-4 hover:bg-gray-800/50 transition-colors text-left"
              >
                <div className="flex items-center gap-4">
                  <div className="p-2 bg-blue-500/10 rounded-lg">
                    <FolderGit2 className="w-5 h-5 text-blue-400" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-100">
                      {repo.name}
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5 font-mono">
                      {repo.path}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-6">
                  <div className="text-right hidden sm:block">
                    <p className="text-xs text-gray-400">
                      {repo.file_count} files · {repo.function_count} functions
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {formatDate(repo.updated_at || repo.created_at)}
                    </p>
                  </div>
                  <ArrowRight className="w-4 h-4 text-gray-600" />
                </div>
              </button>
            ))}
          </div>
        ) : (
          <div className="px-6 py-12 text-center">
            <FolderGit2 className="w-10 h-10 text-gray-700 mx-auto mb-3" />
            <p className="text-gray-400 text-sm">No repositories yet</p>
            <p className="text-gray-500 text-xs mt-1">
              Add a repository to get started
            </p>
          </div>
        )}
      </div>

      {/* Add Repository Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setCreateError(null);
        }}
        title="Add Repository"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              Repository Path
            </label>
            <input
              type="text"
              value={repoPath}
              onChange={(e) => setRepoPath(e.target.value)}
              placeholder="/path/to/your/repository"
              className="w-full px-3 py-2.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              Display Name (optional)
            </label>
            <input
              type="text"
              value={repoName}
              onChange={(e) => setRepoName(e.target.value)}
              placeholder="My Project"
              className="w-full px-3 py-2.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          {createError && (
            <p className="text-sm text-red-400">{createError}</p>
          )}
          <div className="flex justify-end gap-3 pt-2">
            <button
              onClick={() => {
                setIsModalOpen(false);
                setCreateError(null);
              }}
              className="px-4 py-2 text-sm text-gray-400 hover:text-gray-100 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleCreate}
              disabled={creating || !repoPath.trim()}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
            >
              {creating ? 'Adding...' : 'Add Repository'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default Dashboard;
