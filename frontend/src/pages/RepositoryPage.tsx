import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Info,
  Code,
  GitFork,
  Search,
  MessageSquare,
  Zap,
  ArrowLeft,
  Trash2,
} from 'lucide-react';
import { useApi } from '@/hooks/useApi';
import * as api from '@/services/api';
import LoadingSpinner from '@/components/common/LoadingSpinner';
import ErrorMessage from '@/components/common/ErrorMessage';
import Overview from '@/components/repository/Overview';
import CodeExplorer from '@/components/code/CodeExplorer';
import GraphExplorer from '@/components/graph/GraphExplorer';
import SearchPanel from '@/components/repository/SearchPanel';
import ChatInterface from '@/components/chat/ChatInterface';
import ImpactAnalysis from '@/components/impact/ImpactAnalysis';
import type { Repository } from '@/types';

const tabs = [
  { id: 'overview', label: 'Overview', icon: Info },
  { id: 'explorer', label: 'Explorer', icon: Code },
  { id: 'graph', label: 'Graph', icon: GitFork },
  { id: 'search', label: 'Search', icon: Search },
  { id: 'chat', label: 'Chat', icon: MessageSquare },
  { id: 'impact', label: 'Impact', icon: Zap },
] as const;

type TabId = (typeof tabs)[number]['id'];

const RepositoryPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [deleting, setDeleting] = useState(false);

  const {
    data: repo,
    loading,
    error,
    refetch,
  } = useApi<Repository>(() => api.getRepository(id!), [id]);

  const handleDelete = async () => {
    if (!id || !confirm('Are you sure you want to delete this repository?')) return;
    setDeleting(true);
    try {
      await api.deleteRepository(id);
      navigate('/');
    } catch {
      setDeleting(false);
    }
  };

  if (loading) return <LoadingSpinner message="Loading repository..." />;
  if (error) return <ErrorMessage message={error} onRetry={refetch} />;
  if (!repo) return <ErrorMessage message="Repository not found" />;

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return <Overview repo={repo} onRefresh={refetch} />;
      case 'explorer':
        return <CodeExplorer repoId={repo.id} />;
      case 'graph':
        return <GraphExplorer repoId={repo.id} />;
      case 'search':
        return <SearchPanel repoId={repo.id} />;
      case 'chat':
        return <ChatInterface repoId={repo.id} />;
      case 'impact':
        return <ImpactAnalysis repoId={repo.id} />;
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-800 bg-gray-900/50 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/')}
              className="p-1.5 text-gray-400 hover:text-gray-100 hover:bg-gray-800 rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-xl font-bold text-gray-100">{repo.name}</h1>
              <p className="text-xs text-gray-500 font-mono mt-0.5">
                {repo.path}
              </p>
            </div>
          </div>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="p-2 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
            title="Delete repository"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mt-4 -mb-[1px]">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-t-lg border transition-colors ${
                  activeTab === tab.id
                    ? 'bg-gray-950 text-blue-400 border-gray-800 border-b-gray-950'
                    : 'text-gray-400 border-transparent hover:text-gray-200 hover:bg-gray-800/50'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto">{renderTabContent()}</div>
    </div>
  );
};

export default RepositoryPage;
