import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { entityApi, sourcesApi, metaApi } from '../services/api';
import { isStaticMode } from '../services/config/environment';
import { Entity, NewsSource, SnapshotMeta } from '../types';

interface DataContextValue {
  entities: Entity[];
  sources: NewsSource[];
  meta: SnapshotMeta | null;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  availableCountries: string[];
  getEntityById: (id: number) => Entity | undefined;
  getSourceByName: (name: string) => NewsSource | undefined;
}

const DataContext = createContext<DataContextValue | undefined>(undefined);

export const DataProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [sources, setSources] = useState<NewsSource[]>([]);
  const [meta, setMeta] = useState<SnapshotMeta | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (isRefresh: boolean) => {
    isRefresh ? setRefreshing(true) : setLoading(true);
    setError(null);

    // Freshness metadata is informational only - never let it block or fail the core load.
    metaApi.getMeta().then(setMeta).catch(() => setMeta(null));

    try {
      const [sourcesData, entitiesData] = await Promise.all([
        sourcesApi.getSources(),
        entityApi.getEntities({ limit: 200 }),
      ]);
      setSources(sourcesData);
      setEntities(entitiesData);
    } catch (err) {
      const message = (err as Error).message;
      if (message.includes('API unavailable')) {
        setError('Backend server required for accurate news analysis.\n\nThis system requires real data - no mock data is provided for reliability.\n\nTo use the dashboard:\n- Run locally: `python server/dashboard_api.py`\n- Or set VITE_API_BASE_URL to your hosted API');
      } else {
        setError('Failed to connect to the news analysis API. Please ensure the backend server is running and accessible.');
      }
    } finally {
      isRefresh ? setRefreshing(false) : setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(false);
  }, [load]);

  const refresh = useCallback(() => load(true), [load]);

  // Static mode: only meta.countries have country snapshots — offering the full
  // source-country list would give pickers entries with no data behind them.
  const availableCountries = isStaticMode() && meta?.countries?.length
    ? [...meta.countries].sort()
    : [...new Set(sources.map((s) => s.country).filter(Boolean))].sort();

  const getEntityById = useCallback((id: number) => entities.find((e) => e.id === id), [entities]);
  const getSourceByName = useCallback((name: string) => sources.find((s) => s.name === name), [sources]);

  return (
    <DataContext.Provider
      value={{ entities, sources, meta, loading, refreshing, error, refresh, availableCountries, getEntityById, getSourceByName }}
    >
      {children}
    </DataContext.Provider>
  );
};

export const useData = (): DataContextValue => {
  const ctx = useContext(DataContext);
  if (!ctx) throw new Error('useData must be used within a DataProvider');
  return ctx;
};
