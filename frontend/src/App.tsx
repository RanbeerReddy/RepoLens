import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Layout from '@/components/common/Layout';
import Dashboard from '@/pages/Dashboard';
import RepositoryPage from '@/pages/RepositoryPage';

const App: React.FC = () => {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/repo/:id" element={<RepositoryPage />} />
      </Routes>
    </Layout>
  );
};

export default App;
