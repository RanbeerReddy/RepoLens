import React from "react";
import {
  LayoutDashboard,
  FolderTree,
  Network,
  MessageSquare,
  GitBranch,
} from "lucide-react";

export type TabType = "dashboard" | "explorer" | "graph" | "chat" | "impact";

interface TabNavigationProps {
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
  hasActiveRepo: boolean;
}

export const TabNavigation: React.FC<TabNavigationProps> = ({
  activeTab,
  onTabChange,
  hasActiveRepo,
}) => {
  const tabs = [
    { id: "dashboard" as TabType, label: "Dashboard", icon: LayoutDashboard },
    { id: "explorer" as TabType, label: "Code Explorer", icon: FolderTree },
    { id: "graph" as TabType, label: "Knowledge Graph", icon: Network },
    { id: "chat" as TabType, label: "AI Codebase Chat", icon: MessageSquare },
    { id: "impact" as TabType, label: "Impact Analysis", icon: GitBranch },
  ];

  return (
    <div className="border-b border-slate-800 bg-[#0d1322] px-6 flex items-center space-x-2">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = activeTab === tab.id;
        const isDisabled = !hasActiveRepo && tab.id !== "dashboard";

        return (
          <button
            key={tab.id}
            onClick={() => !isDisabled && onTabChange(tab.id)}
            disabled={isDisabled}
            className={`flex items-center space-x-2 px-4 py-3 text-xs font-semibold border-b-2 transition-all ${
              isActive
                ? "border-indigo-500 text-indigo-400 bg-indigo-500/5"
                : isDisabled
                ? "border-transparent text-slate-600 cursor-not-allowed"
                : "border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700"
            }`}
          >
            <Icon className="h-4 w-4" />
            <span>{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
};
