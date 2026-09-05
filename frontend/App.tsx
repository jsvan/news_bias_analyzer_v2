import React from 'react';
import { HashRouter, Routes, Route, Navigate, useLocation, useParams } from 'react-router-dom';
import { DataProvider } from './context/DataContext';
import Layout from './components/Layout';
import SectionShell from './components/SectionShell';
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
import ShiftsPage from './pages/ShiftsPage';
import MyBubblePage from './pages/MyBubblePage';
import SearchPage from './pages/SearchPage';
import MethodologyPage from './pages/MethodologyPage';
import InfrastructurePage from './pages/InfrastructurePage';

// The pre-section flat routes live on in bookmarks and the Chrome extension;
// each forwards to its section home, keeping params and the query string.
const LegacyRedirect: React.FC<{ to: (params: Record<string, string | undefined>) => string }> = ({ to }) => {
  const params = useParams();
  const { search } = useLocation();
  return <Navigate to={to(params) + search} replace />;
};

const App: React.FC = () => (
  <DataProvider>
    <HashRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<WelcomePage />} />

          {/* What is the press talking about? */}
          <Route path="/coverage" element={<SectionShell section="coverage" />}>
            <Route index element={<Navigate to="countries" replace />} />
            <Route path="countries" element={<CountryEntityPage />} />
            <Route path="newspapers" element={<SourcesIndexPage />} />
            <Route path="newspapers/:name" element={<SourceProfilePage />} />
          </Route>

          {/* How is one thing portrayed? */}
          <Route path="/portrayals" element={<SectionShell section="portrayals" />}>
            <Route index element={<EntityAnalysisPage />} />
            <Route path="side-by-side" element={<CompareEntitiesPage />} />
            <Route path=":id" element={<EntityProfilePage />} />
          </Route>

          {/* How do the newspapers compare? */}
          <Route path="/landscape" element={<SectionShell section="landscape" />}>
            <Route index element={<Navigate to="map" replace />} />
            <Route path="map" element={<SourceSpacePage />} />
            <Route path="diets" element={<CompareSourcesPage />} />
            <Route path="my-bubble" element={<MyBubblePage />} />
          </Route>

          {/* What changed this week? */}
          <Route path="/shifts" element={<ShiftsPage />} />

          <Route path="/stories" element={<StoriesPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/methodology" element={<MethodologyPage />} />
          <Route path="/infrastructure" element={<InfrastructurePage />} />

          {/* Legacy flat routes → section homes */}
          <Route path="/entities" element={<LegacyRedirect to={() => '/portrayals'} />} />
          <Route path="/entities/:id" element={<LegacyRedirect to={(p) => `/portrayals/${p.id}`} />} />
          <Route path="/sources" element={<LegacyRedirect to={() => '/coverage/newspapers'} />} />
          <Route
            path="/sources/:name"
            element={<LegacyRedirect to={(p) => `/coverage/newspapers/${encodeURIComponent(p.name ?? '')}`} />}
          />
          <Route path="/countries" element={<LegacyRedirect to={() => '/coverage/countries'} />} />
          <Route path="/source-space" element={<LegacyRedirect to={() => '/landscape/map'} />} />
          <Route path="/compare" element={<LegacyRedirect to={() => '/portrayals/side-by-side'} />} />
          <Route path="/compare/entities" element={<LegacyRedirect to={() => '/portrayals/side-by-side'} />} />
          <Route path="/compare/sources" element={<LegacyRedirect to={() => '/landscape/diets'} />} />
          <Route path="/my-bubble" element={<LegacyRedirect to={() => '/landscape/my-bubble'} />} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </HashRouter>
  </DataProvider>
);

export default App;
