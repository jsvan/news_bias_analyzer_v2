import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link as RouterLink } from 'react-router-dom';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardHeader,
  CardContent,
  Paper,
  Autocomplete,
  TextField,
  Chip,
  CircularProgress,
} from '@mui/material';
import { useData } from '../context/DataContext';
import { entityApi, statsApi } from '../services/api';
import EntityTrendChart from '../components/EntityTrendChart';
import SentimentDistributionChart, { layersFromDistributions } from '../components/SentimentDistributionChart';
import MultiSourceTrendChart from '../components/MultiSourceTrendChart';
import EntitySourceScatterPanel from '../components/EntitySourceScatterPanel';
import RelatedEntitiesPanel from '../components/RelatedEntitiesPanel';
import ArchetypeQuadrantPanel from '../components/ArchetypeQuadrantPanel';
import EntityDriftPanel from '../components/EntityDriftPanel';
import TimeRangeSelect, { ALL_TIME, describeTimeRange } from '../components/TimeRangeSelect';
import { NewsSource, SentimentDistributions, TrendPoint } from '../types';
import { tokens, archetypeColor, monoNumber } from '../theme';

const EntityProfilePage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { entities, sources, availableCountries, getEntityById } = useData();
  const entity = getEntityById(Number(id));

  const [selectedTimeRange, setSelectedTimeRange] = useState<number>(ALL_TIME);
  const [selectedCountries, setSelectedCountries] = useState<string[]>([]);
  const [trends, setTrends] = useState<TrendPoint[]>([]);
  const [distribution, setDistribution] = useState<SentimentDistributions | null>(null);
  const [sourcesTrends, setSourcesTrends] = useState<Record<string, TrendPoint[]>>({});
  const [loading, setLoading] = useState(true);

  // The Distribution card's own comparison pickers: overlay one country and/or
  // one source against the always-global baseline.
  const [distCountry, setDistCountry] = useState<string | null>(null);
  const [distSource, setDistSource] = useState<NewsSource | null>(null);

  useEffect(() => {
    if (!entity) return;
    let cancelled = false;
    entityApi
      .getEntityDistribution(entity.id, distCountry ?? undefined, distSource?.id, selectedTimeRange)
      .then((res) => {
        if (!cancelled) setDistribution(res?.distributions ?? null);
      })
      .catch(() => {
        if (!cancelled) setDistribution(null);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entity?.id, selectedTimeRange, distCountry, distSource]);

  const loadForEntity = useCallback(async (entityId: number, days: number, countries: string[]) => {
    setLoading(true);
    try {
      const historicalRes = await statsApi.getHistoricalSentiment(entityId, { days }).catch(() => null);
      setTrends(historicalRes?.daily_data || []);

      const params: any = { days };
      if (countries.length > 0) params.countries = countries;
      try {
        const sourceRes = await statsApi.getSourceHistoricalSentiment(entityId, params);
        const sourceTrends: Record<string, TrendPoint[]> = {};
        if (sourceRes?.sources) {
          Object.entries(sourceRes.sources).forEach(([key, value]: [string, any]) => {
            if (value.daily_data?.length) sourceTrends[key] = value.daily_data;
          });
        }
        setSourcesTrends(sourceTrends);
      } catch {
        setSourcesTrends({});
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (entity) loadForEntity(entity.id, selectedTimeRange, selectedCountries);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entity?.id]);

  const handleTimeRangeChange = (days: number) => {
    setSelectedTimeRange(days);
    if (entity) loadForEntity(entity.id, days, selectedCountries);
  };

  const handleCountriesChange = (countries: string[]) => {
    setSelectedCountries(countries);
    if (entity) loadForEntity(entity.id, selectedTimeRange, countries);
  };

  if (!entity) {
    return (
      <Box sx={{ textAlign: 'center', py: 8 }}>
        <Typography variant="h5" sx={{ color: tokens.inkMuted }}>
          Entity not found
        </Typography>
        <Typography variant="body2" sx={{ color: tokens.inkMuted, mt: 1 }}>
          It may not be among the top {entities.length} tracked entities. Try search instead.
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
        <Typography component="h2" sx={{ fontFamily: '"Newsreader", Georgia, serif', fontStyle: 'italic', fontSize: '2rem' }}>
          {entity.name}
        </Typography>
        <Chip label={entity.type} size="small" variant="outlined" />
        <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted }}>
          {(entity.mention_count || 0).toLocaleString()} mentions
        </Typography>
      </Box>

      <Paper sx={{ p: 2, mb: 4, bgcolor: tokens.surfaceSunken, border: `1px solid ${tokens.border}` }}>
        <Grid container spacing={3} alignItems="center">
          <Grid item xs={12} sm={4}>
            <TimeRangeSelect value={selectedTimeRange} onChange={handleTimeRangeChange} options={[7, 30, 90, 180, 365]} />
          </Grid>
          <Grid item xs={12} sm={8}>
            <Autocomplete
              multiple
              id="country-filter"
              options={availableCountries}
              value={selectedCountries}
              onChange={(_, value) => handleCountriesChange(value)}
              renderInput={(params) => <TextField {...params} label="Filter cross-source view by countries" size="small" fullWidth />}
              limitTags={3}
              disableCloseOnSelect
            />
          </Grid>
        </Grid>
      </Paper>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress size={28} />
        </Box>
      ) : (
        <Grid container spacing={4}>
          <Grid item xs={12} md={7}>
            <Card>
              <CardHeader title="Sentiment Over Time" subheader={`Tracking ${entity.name}'s own trajectory`} />
              <CardContent>
                <Box sx={{ height: 400 }}>
                  <EntityTrendChart entityName={entity.name} data={trends} height={400} />
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={5}>
            <Card>
              <CardHeader title="Distribution" subheader="Global, national, and source-level spread" />
              <CardContent>
                <Grid container spacing={1.5} sx={{ mb: 1.5 }}>
                  <Grid item xs={12} sm={6}>
                    <Autocomplete
                      size="small"
                      options={availableCountries}
                      value={distCountry}
                      onChange={(_, v) => setDistCountry(v)}
                      renderInput={(params) => <TextField {...params} label="Compare a country" />}
                    />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Autocomplete
                      size="small"
                      options={sources}
                      value={distSource}
                      getOptionLabel={(s) => s.name}
                      isOptionEqualToValue={(a, b) => a.id === b.id}
                      onChange={(_, v) => setDistSource(v)}
                      renderInput={(params) => <TextField {...params} label="Compare a source" />}
                    />
                  </Grid>
                </Grid>
                {distribution ? (
                  <SentimentDistributionChart
                    layers={layersFromDistributions(distribution)}
                    entityName={entity.name}
                    height={330}
                  />
                ) : (
                  <Box sx={{ height: 330, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                    <Typography variant="body2" sx={{ color: tokens.inkMuted }}>
                      No distribution data available yet
                    </Typography>
                  </Box>
                )}
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12}>
            <Card>
              <CardHeader
                title={`How Different Sources Portray ${entity.name}`}
                subheader={`Compare ${Object.keys(sourcesTrends).length} news sources over ${describeTimeRange(selectedTimeRange)}`}
              />
              <CardContent>
                {Object.keys(sourcesTrends).length > 0 ? (
                  <Box sx={{ height: 500 }}>
                    <MultiSourceTrendChart entityName={entity.name} sourcesTrends={sourcesTrends} height={500} />
                  </Box>
                ) : (
                  <Box
                    sx={{
                      height: 300,
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'center',
                      alignItems: 'center',
                      bgcolor: tokens.surfaceSunken,
                      borderRadius: 1,
                      border: `1px dashed ${tokens.border}`,
                    }}
                  >
                    <Typography variant="body1" sx={{ color: tokens.inkMuted }}>
                      No source-specific data available for {entity.name} yet
                    </Typography>
                  </Box>
                )}
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12}>
            <EntitySourceScatterPanel entityId={entity.id} entityName={entity.name} />
          </Grid>

          <Grid item xs={12} md={6}>
            <ArchetypeQuadrantPanel entityId={entity.id} />
          </Grid>

          <Grid item xs={12} md={6}>
            <RelatedEntitiesPanel entityId={entity.id} />
          </Grid>

          <Grid item xs={12} md={6}>
            <EntityDriftPanel entityId={entity.id} />
          </Grid>
        </Grid>
      )}

      <Box sx={{ mt: 4 }}>
        <RouterLink to="/entities" style={{ color: tokens.accent, fontSize: '0.875rem' }}>
          &larr; Back to all entities
        </RouterLink>
      </Box>
    </Box>
  );
};

export default EntityProfilePage;
