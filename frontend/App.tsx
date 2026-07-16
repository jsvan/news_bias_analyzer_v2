import React from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import { DataProvider } from './context/DataContext';
import Layout from './components/Layout';
import EntityAnalysisPage from './pages/EntityAnalysisPage';
import EntityProfilePage from './pages/EntityProfilePage';
import SourcesIndexPage from './pages/SourcesIndexPage';
import SourceProfilePage from './pages/SourceProfilePage';
import CountryEntityPage from './pages/CountryEntityPage';
import WorldViewPage from './pages/WorldViewPage';
import CompareEntitiesPage from './pages/CompareEntitiesPage';
import CompareSourcesPage from './pages/CompareSourcesPage';
import IntelligenceInsights from './components/IntelligenceInsights';
import StoriesPage from './pages/StoriesPage';
import MyBubblePage from './pages/MyBubblePage';
import SearchPage from './pages/SearchPage';

const App: React.FC = () => (
  <DataProvider>
    <HashRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/entities" replace />} />
          <Route path="/entities" element={<EntityAnalysisPage />} />
          <Route path="/entities/:id" element={<EntityProfilePage />} />
          <Route path="/sources" element={<SourcesIndexPage />} />
          <Route path="/sources/:name" element={<SourceProfilePage />} />
          <Route path="/countries" element={<CountryEntityPage />} />
          <Route path="/world" element={<WorldViewPage />} />
          <Route path="/compare" element={<Navigate to="/compare/entities" replace />} />
          <Route path="/compare/entities" element={<CompareEntitiesPage />} />
          <Route path="/compare/sources" element={<CompareSourcesPage />} />
          <Route path="/events" element={<IntelligenceInsights />} />
          <Route path="/stories" element={<StoriesPage />} />
          <Route path="/my-bubble" element={<MyBubblePage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="*" element={<Navigate to="/entities" replace />} />
        </Route>
      </Routes>
    </HashRouter>
  </DataProvider>
);

export default App;
