import React from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import { DataProvider } from './context/DataContext';
import Layout from './components/Layout';
import WelcomePage from './pages/WelcomePage';
import EntityAnalysisPage from './pages/EntityAnalysisPage';
import EntityProfilePage from './pages/EntityProfilePage';
import SourcesIndexPage from './pages/SourcesIndexPage';
import SourceSpacePage from './pages/SourceSpacePage';
import SourceProfilePage from './pages/SourceProfilePage';
import CountryEntityPage from './pages/CountryEntityPage';
import CompareEntitiesPage from './pages/CompareEntitiesPage';
import CompareSourcesPage from './pages/CompareSourcesPage';
import StoriesPage from './pages/StoriesPage';
import MyBubblePage from './pages/MyBubblePage';
import SearchPage from './pages/SearchPage';
import MethodologyPage from './pages/MethodologyPage';
import InfrastructurePage from './pages/InfrastructurePage';

const App: React.FC = () => (
  <DataProvider>
    <HashRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<WelcomePage />} />
          <Route path="/entities" element={<EntityAnalysisPage />} />
          <Route path="/entities/:id" element={<EntityProfilePage />} />
          <Route path="/sources" element={<SourcesIndexPage />} />
          <Route path="/source-space" element={<SourceSpacePage />} />
          <Route path="/sources/:name" element={<SourceProfilePage />} />
          <Route path="/countries" element={<CountryEntityPage />} />
          <Route path="/compare" element={<Navigate to="/compare/entities" replace />} />
          <Route path="/compare/entities" element={<CompareEntitiesPage />} />
          <Route path="/compare/sources" element={<CompareSourcesPage />} />
          <Route path="/stories" element={<StoriesPage />} />
          <Route path="/my-bubble" element={<MyBubblePage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/methodology" element={<MethodologyPage />} />
          <Route path="/infrastructure" element={<InfrastructurePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </HashRouter>
  </DataProvider>
);

export default App;
