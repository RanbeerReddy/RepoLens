import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { LayoutDashboard, FolderGit2, Telescope } from 'lucide-react';

interface LayoutProps {
  children: React.ReactNode;
}

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/', label: 'Repositories', icon: FolderGit2 },
];

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const location = useLocation();

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col flex-shrink-0">
        {/* Logo */}
        <div className="h-16 flex items-center px-6 border-b border-gray-800">
          <Telescope className="w-7 h-7 text-blue-500 mr-3" />
          <span className="text-xl font-bold text-gray-100 tracking-tight">
            RepoLens
          </span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              item.label === 'Dashboard'
                ? location.pathname === '/'
                : location.pathname !== '/' && item.label === 'Repositories';

            return (
              <NavLink
                key={item.label}
                to={item.to}
                className={`flex items-center px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-600/20 text-blue-400'
                    : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800'
                }`}
              >
                <Icon className="w-5 h-5 mr-3" />
                {item.label}
              </NavLink>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-800">
          <p className="text-xs text-gray-500">RepoLens v0.1.0</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-gray-950">
        <div className="h-full">{children}</div>
      </main>
    </div>
  );
};

export default Layout;
