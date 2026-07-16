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
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Autocomplete,
  TextField,
  Chip,
  CircularProgress,
} from '@mui/material';
import { useData } from '../context/DataContext';
import { entityApi, statsApi } from '../services/api';
import EntityTrendChart from '../components/EntityTrendChart';
import SentimentDistributionChart from '../components/SentimentDistributionChart';
import MultiSourceTrendChart from '../components/MultiSourceTrendChart';
import RelatedEntitiesPanel from '../components/RelatedEntitiesPanel';
import EntityDriftPanel from '../components/EntityDriftPanel';
import { SentimentDistributions, TrendPoint } from '../types';
import { tokens, archetypeColor, monoNumber } from '../theme';

const EntityProfilePage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { entities, availableCountries, getEntityById } = useData();
  const entity = getEntityById(Number(id));

  const [selectedTimeRange, setSelectedTimeRange] = useState<number>(30);
  const [selectedCountries, setSelectedCountries] = useState<string[]>([]);
  const [trends, setTrends] = useState<TrendPoint[]>([]);
  const [distribution, setDistribution] = useState<SentimentDistributions | null>(null);
  const [sourcesTrends, setSourcesTrends] = useState<Record<string, TrendPoint[]>>({});
  const [loading, setLoading] = useState(true);

  const loadForEntity = useCallback(async (entityId: number, days: number, countries: string[]) => {
    setLoading(true);
    try {
      const [distributionRes, historicalRes] = await Promise.all([
        entityApi.getEntityDistribution(entityId).catch(() => null),
        statsApi.getHistoricalSentiment(entityId, { days }).catch(() => null),
      ]);
      setDistribution(distributionRes);
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
            <FormControl fullWidth size="small">
              <InputLabel id="time-range-label">Time Range</InputLabel>
              <Select
                labelId="time-range-label"
                value={selectedTimeRange}
                label="Time Range"
                onChange={(e) => handleTimeRangeChange(e.target.value as number)}
              >
                <MenuItem value={7}>Last 7 days</MenuItem>
                <MenuItem value={30}>Last 30 days</MenuItem>
                <MenuItem value={90}>Last 3 months</MenuItem>
                <MenuItem value={180}>Last 6 months</MenuItem>
                <MenuItem value={365}>Last year</MenuItem>
              </Select>
            </FormControl>
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
                {distribution ? (
                  <SentimentDistributionChart distributions={distribution} entityName={entity.name} height={330} />
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
                subheader={`Compare ${Object.keys(sourcesTrends).length} news sources over ${selectedTimeRange} days`}
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
