import React, { useEffect, useMemo, useState } from 'react';
import { Link as RouterLink, useSearchParams } from 'react-router-dom';
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
  Tabs,
  Tab,
} from '@mui/material';
import { useData } from '../context/DataContext';
import { statsApi } from '../services/api';
import EntityTrendChart from '../components/EntityTrendChart';
import { Entity, TrendPoint } from '../types';
import { tokens, archetypeColor, monoNumber } from '../theme';

const MAX_SELECTED = 4;

const formatScore = (v?: number) => (v == null ? '—' : v.toFixed(2));

const CompareEntitiesPage: React.FC = () => {
  const { entities, getEntityById } = useData();
  const [searchParams, setSearchParams] = useSearchParams();

  const [selectedIds, setSelectedIds] = useState<number[]>(() => {
    const raw = searchParams.get('ids');
    if (!raw) return [];
    return raw
      .split(',')
      .map((v) => Number(v))
      .filter((n) => !Number.isNaN(n))
      .slice(0, MAX_SELECTED);
  });
  const [trendsById, setTrendsById] = useState<Record<number, TrendPoint[]>>({});
  const [loading, setLoading] = useState(false);

  const selectedEntities = useMemo(
    () => selectedIds.map((id) => getEntityById(id)).filter((e): e is Entity => !!e),
    [selectedIds, getEntityById]
  );

  // Keep the URL in sync so a comparison is shareable/bookmarkable.
  useEffect(() => {
    const params = new URLSearchParams(searchParams);
    if (selectedIds.length) params.set('ids', selectedIds.join(','));
    else params.delete('ids');
    setSearchParams(params, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedIds]);

  useEffect(() => {
    if (selectedIds.length === 0) {
      setTrendsById({});
      return;
    }
    let cancelled = false;
    setLoading(true);
    Promise.all(
      selectedIds.map((id) =>
        statsApi
          .getHistoricalSentiment(id, { days: 30 })
          .then((res) => [id, res?.daily_data || []] as const)
          .catch(() => [id, []] as const)
      )
    )
      .then((results) => {
        if (cancelled) return;
        const next: Record<number, TrendPoint[]> = {};
        results.forEach(([id, data]) => {
          next[id] = data;
        });
        setTrendsById(next);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedIds.join(',')]);

  return (
    <Box>
      <Tabs value="entities" sx={{ mb: 3 }}>
        <Tab label="Entities" value="entities" component={RouterLink} to="/compare/entities" />
        <Tab label="Sources" value="sources" component={RouterLink} to="/compare/sources" />
      </Tabs>

      <Typography component="h2" sx={{ fontFamily: '"Newsreader", Georgia, serif', fontStyle: 'italic', fontSize: '2rem', mb: 1 }}>
        Compare Entities
      </Typography>
      <Typography variant="body2" sx={{ color: tokens.inkMuted, mb: 3 }}>
        Each selected entity gets its own chart, side by side, rather than everything overlaid on one axis.
      </Typography>

      <Paper sx={{ p: 2, mb: 4, bgcolor: tokens.surfaceSunken, border: `1px solid ${tokens.border}` }}>
        <Autocomplete
          multiple
          id="compare-entities-select"
          options={entities}
          value={selectedEntities}
          getOptionLabel={(e) => e.name}
          isOptionEqualToValue={(a, b) => a.id === b.id}
          getOptionDisabled={(option) =>
            selectedEntities.length >= MAX_SELECTED && !selectedEntities.some((e) => e.id === option.id)
          }
          onChange={(_, value) => setSelectedIds(value.slice(0, MAX_SELECTED).map((e) => e.id))}
          renderInput={(params) => (
            <TextField
              {...params}
              label="Select up to 4 entities"
              size="small"
              fullWidth
              helperText={`${selectedEntities.length}/${MAX_SELECTED} selected`}
            />
          )}
          limitTags={4}
          disableCloseOnSelect
        />
      </Paper>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress size={28} />
        </Box>
      ) : selectedEntities.length === 0 ? (
        <Box sx={{ textAlign: 'center', py: 8 }}>
          <Typography variant="body1" sx={{ color: tokens.inkMuted }}>
            Select entities above to compare their sentiment trajectories.
          </Typography>
        </Box>
      ) : (
        <>
          <Grid container spacing={3}>
            {selectedEntities.map((entity) => (
              <Grid item xs={12} md={6} key={entity.id}>
                <Card>
                  <CardHeader
                    title={entity.name}
                    subheader={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                        <Chip label={entity.type} size="small" variant="outlined" />
                        <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted }}>
                          {(entity.mention_count || 0).toLocaleString()} mentions
                        </Typography>
                      </Box>
                    }
                  />
                  <CardContent>
                    <Box sx={{ height: 280 }}>
                      <EntityTrendChart entityName={entity.name} data={trendsById[entity.id] || []} height={280} />
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>

          <Card sx={{ mt: 4 }}>
            <CardHeader title="Side by Side" subheader="Latest average scores and mention volume" />
            <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
              {selectedEntities.map((entity, index) => (
                <Box
                  key={entity.id}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1.5,
                    px: 2,
                    py: 1.25,
                    borderTop: index === 0 ? 'none' : `1px solid ${tokens.border}`,
                  }}
                >
                  <Box
                    sx={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      flexShrink: 0,
                      bgcolor:
                        entity.avg_power_score == null || entity.avg_moral_score == null
                          ? tokens.border
                          : archetypeColor(entity.avg_power_score, entity.avg_moral_score),
                    }}
                  />
                  <Typography variant="body2" sx={{ flex: 1, minWidth: 0, fontWeight: 500 }}>
                    {entity.name}
                  </Typography>
                  <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted, flexShrink: 0 }}>
                    P {formatScore(entity.avg_power_score)} &middot; M {formatScore(entity.avg_moral_score)}
                  </Typography>
                  <Typography
                    variant="caption"
                    sx={{ ...monoNumber, color: tokens.inkMuted, minWidth: 96, textAlign: 'right', flexShrink: 0 }}
                  >
                    {(entity.mention_count || 0).toLocaleString()} mentions
                  </Typography>
                </Box>
              ))}
            </CardContent>
          </Card>
        </>
      )}
    </Box>
  );
};

export default CompareEntitiesPage;
