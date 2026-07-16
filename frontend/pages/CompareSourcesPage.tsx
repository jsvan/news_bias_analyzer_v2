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
import { NewsSource, CountryEntityData } from '../types';
import { tokens, archetypeColor, monoNumber } from '../theme';

const MAX_SELECTED = 4;

const CompareSourcesPage: React.FC = () => {
  const { sources, getSourceByName } = useData();
  const [searchParams, setSearchParams] = useSearchParams();

  const [selectedNames, setSelectedNames] = useState<string[]>(() => {
    const raw = searchParams.get('names');
    if (!raw) return [];
    return raw
      .split(',')
      .map((v) => v.trim())
      .filter(Boolean)
      .slice(0, MAX_SELECTED);
  });
  const [entitiesByName, setEntitiesByName] = useState<Record<string, CountryEntityData[]>>({});
  const [loading, setLoading] = useState(false);

  const selectedSources = useMemo(
    () => selectedNames.map((name) => getSourceByName(name)).filter((s): s is NewsSource => !!s),
    [selectedNames, getSourceByName]
  );

  // Keep the URL in sync so a comparison is shareable/bookmarkable.
  useEffect(() => {
    const params = new URLSearchParams(searchParams);
    if (selectedNames.length) params.set('names', selectedNames.join(','));
    else params.delete('names');
    setSearchParams(params, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedNames]);

  useEffect(() => {
    if (selectedNames.length === 0) {
      setEntitiesByName({});
      return;
    }
    let cancelled = false;
    setLoading(true);
    Promise.all(
      selectedNames.map((name) =>
        statsApi
          .getNewspaperTopEntities(name, { days: 30, limit: 8 })
          .then((res) => [name, res?.entities || []] as const)
          .catch(() => [name, []] as const)
      )
    )
      .then((results) => {
        if (cancelled) return;
        const next: Record<string, CountryEntityData[]> = {};
        results.forEach(([name, data]) => {
          next[name] = data;
        });
        setEntitiesByName(next);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedNames.join(',')]);

  return (
    <Box>
      <Tabs value="sources" sx={{ mb: 3 }}>
        <Tab label="Entities" value="entities" component={RouterLink} to="/compare/entities" />
        <Tab label="Sources" value="sources" component={RouterLink} to="/compare/sources" />
      </Tabs>

      <Typography component="h2" sx={{ fontFamily: '"Newsreader", Georgia, serif', fontStyle: 'italic', fontSize: '2rem', mb: 1 }}>
        Compare Sources
      </Typography>
      <Typography variant="body2" sx={{ color: tokens.inkMuted, mb: 3 }}>
        Each selected source gets its own panel of top entities, side by side, rather than everything overlaid on one axis.
      </Typography>

      <Paper sx={{ p: 2, mb: 4, bgcolor: tokens.surfaceSunken, border: `1px solid ${tokens.border}` }}>
        <Autocomplete
          multiple
          id="compare-sources-select"
          options={sources}
          value={selectedSources}
          getOptionLabel={(s) => s.name}
          isOptionEqualToValue={(a, b) => a.name === b.name}
          getOptionDisabled={(option) =>
            selectedSources.length >= MAX_SELECTED && !selectedSources.some((s) => s.name === option.name)
          }
          onChange={(_, value) => setSelectedNames(value.slice(0, MAX_SELECTED).map((s) => s.name))}
          renderInput={(params) => (
            <TextField
              {...params}
              label="Select up to 4 sources"
              size="small"
              fullWidth
              helperText={`${selectedSources.length}/${MAX_SELECTED} selected`}
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
      ) : selectedSources.length === 0 ? (
        <Box sx={{ textAlign: 'center', py: 8 }}>
          <Typography variant="body1" sx={{ color: tokens.inkMuted }}>
            Select sources above to compare which entities they cover most.
          </Typography>
        </Box>
      ) : (
        <Grid container spacing={3}>
          {selectedSources.map((source) => {
            const topEntities = entitiesByName[source.name] || [];
            return (
              <Grid item xs={12} md={6} key={source.name}>
                <Card>
                  <CardHeader
                    title={source.name}
                    subheader={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                        <Chip label={source.country} size="small" variant="outlined" />
                        <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted }}>
                          {topEntities.length} top entities
                        </Typography>
                      </Box>
                    }
                  />
                  <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
                    {topEntities.length === 0 ? (
                      <Box sx={{ px: 2, py: 3, textAlign: 'center' }}>
                        <Typography variant="body2" sx={{ color: tokens.inkMuted }}>
                          No data yet for {source.name}
                        </Typography>
                      </Box>
                    ) : (
                      topEntities.map((entity, index) => (
                        <Box
                          key={entity.entity_name}
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 1.5,
                            px: 2,
                            py: 1.25,
                            borderTop: index === 0 ? 'none' : `1px solid ${tokens.border}`,
                            '&:hover': { bgcolor: tokens.surfaceSunken },
                          }}
                        >
                          <Box
                            sx={{
                              width: 8,
                              height: 8,
                              borderRadius: '50%',
                              flexShrink: 0,
                              bgcolor: archetypeColor(entity.avg_power_score, entity.avg_moral_score),
                            }}
                          />
                          <Typography
                            variant="body2"
                            sx={{ flex: 1, minWidth: 0, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                          >
                            {entity.entity_name}
                          </Typography>
                          <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted, flexShrink: 0 }}>
                            P {entity.avg_power_score.toFixed(2)} &middot; M {entity.avg_moral_score.toFixed(2)}
                          </Typography>
                          <Typography
                            variant="caption"
                            sx={{ ...monoNumber, color: tokens.inkMuted, minWidth: 78, textAlign: 'right', flexShrink: 0 }}
                          >
                            {entity.mention_count} mentions
                          </Typography>
                        </Box>
                      ))
                    )}
                  </CardContent>
                </Card>
              </Grid>
            );
          })}
        </Grid>
      )}
    </Box>
  );
};

export default CompareSourcesPage;
