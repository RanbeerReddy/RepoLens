import React, { useState, useEffect } from "react";
import { Navbar } from "./components/Navbar";
import { TabNavigation, TabType } from "./components/TabNavigation";
import { RegisterModal } from "./components/RegisterModal";
import { Dashboard } from "./pages/Dashboard";
import { RepositoryExplorer } from "./pages/RepositoryExplorer";
import { GraphExplorer } from "./pages/GraphExplorer";
import { ChatView } from "./pages/ChatView";
import { ImpactView } from "./pages/ImpactView";
import { Repository } from "./types";
import { fetchHealth, listRepositories, registerRepository } from "./services/api";

export const App: React.FC = () => {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [activeRepo, setActiveRepo] = useState<Repository | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>("dashboard");
  const [isRegisterOpen, setIsRegisterOpen] = useState(false);
  const [health, setHealth] = useState({ neo4j: false, llm: false });

  const [explorerTargetFile, setExplorerTargetFile] = useState<string | undefined>(undefined);
  const [impactTargetFunc, setImpactTargetFunc] = useState<string | undefined>(undefined);

  const loadData = async () => {
    try {
      const [h, repos] = await Promise.all([fetchHealth(), listRepositories()]);
      setHealth(h);
      setRepositories(repos);
      if (repos.length > 0 && !activeRepo) {
        setActiveRepo(repos[0]);
      }
    } catch {
      // Fallback
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleRegister = async (path: string, name?: string) => {
    const created = await registerRepository(path, name);
    await loadData();
    setActiveRepo(created);
    setActiveTab("dashboard");
  };

  const handleNavigateToFile = (filePath: string) => {
    setExplorerTargetFile(filePath);
    setActiveTab("explorer");
  };

  const handleOpenImpact = (funcName: string) => {
    setImpactTargetFunc(funcName);
    setActiveTab("impact");
  };

  return (
    <div className="min-h-screen bg-[#0b0f19] text-slate-100 flex flex-col">
      <Navbar
        repositories={repositories}
        activeRepo={activeRepo}
        onSelectRepo={(r) => setActiveRepo(r)}
        onOpenRegister={() => setIsRegisterOpen(true)}
        health={health}
      />

      <TabNavigation
        activeTab={activeTab}
        onTabChange={(t) => setActiveTab(t)}
        hasActiveRepo={!!activeRepo}
      />

      <main className="flex-1 overflow-auto">
        {activeTab === "dashboard" && (
          <Dashboard
            activeRepo={activeRepo}
            repositories={repositories}
            onSelectRepo={(r) => setActiveRepo(r)}
            onRefreshRepos={loadData}
            onNavigateToTab={(t) => setActiveTab(t)}
          />
        )}

        {activeTab === "explorer" && activeRepo && (
          <RepositoryExplorer
            activeRepo={activeRepo}
            initialFile={explorerTargetFile}
            onOpenImpact={handleOpenImpact}
          />
        )}

        {activeTab === "graph" && activeRepo && (
          <GraphExplorer activeRepo={activeRepo} />
        )}

        {activeTab === "chat" && activeRepo && (
          <ChatView
            activeRepo={activeRepo}
            onNavigateToFile={handleNavigateToFile}
          />
        )}

        {activeTab === "impact" && activeRepo && (
          <ImpactView
            activeRepo={activeRepo}
            initialFunction={impactTargetFunc}
          />
        )}
      </main>

      <RegisterModal
        isOpen={isRegisterOpen}
        onClose={() => setIsRegisterOpen(false)}
        onRegister={handleRegister}
      />
    </div>
  );
};
