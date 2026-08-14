import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
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
  IconButton,
  Tab,
  Tabs,
  Tooltip,
  Chip,
} from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';
import { useData } from '../context/DataContext';
import { statsApi, narrativeApi } from '../services/api';
import { isStaticMode } from '../services/config/environment';
import SentimentChart from '../components/SentimentChart';
import ContestedEntitiesPanel from '../components/ContestedEntitiesPanel';
import DriftFeedPanel from '../components/DriftFeedPanel';
import { EntitySentimentSummary, NewsSource } from '../types';
import { tokens, archetypeColor, archetypeLabel, monoNumber, ArchetypeLabel } from '../theme';

const ARCHETYPES: ArchetypeLabel[] = ['Hero', 'Victim', 'Villain', 'Wretch'];

const EntityAnalysisPage: React.FC = () => {
  const { entities, sources, meta, availableCountries } = useData();
  const navigate = useNavigate();
  const [selectedArchetypes, setSelectedArchetypes] = useState<ArchetypeLabel[]>([]);
  const [highlightedEntities, setHighlightedEntities] = useState<EntitySentimentSummary[]>([]);

  // Two flavors of the same comparison, as tabs: a country's sphere against the
  // global baseline, or a single newspaper against its country (or the globe).
  const [scatterTab, setScatterTab] = useState(0);

  // The comparison layer: one country's reading of the same entities, drawn
  // against the global baseline instead of replacing it.
  const [overlayCountry, setOverlayCountry] = useState<string | null>(null);
  const [overlayEntities, setOverlayEntities] = useState<EntitySentimentSummary[]>([]);

  // "By newspaper": one paper's reading, drawn against a chosen baseline —
  // its own country by default (the divergence people actually wonder about),
  // or the global average.
  const [selectedSource, setSelectedSource] = useState<NewsSource | null>(null);
  const [sourceBaseline, setSourceBaseline] = useState<string>('Global');
  const [sourceEntities, setSourceEntities] = useState<EntitySentimentSummary[]>([]);
  const [baselineEntities, setBaselineEntities] = useState<EntitySentimentSummary[]>([]);

  // entity name -> cross-country JSD, so contested entities are visually
  // distinct from genuinely neutral ones (both average near the origin).
  const [contested, setContested] = useState<Record<string, number>>({});

  useEffect(() => {
    statsApi
      .getTrendingEntities(40)
      .then(setHighlightedEntities)
      .catch(() => setHighlightedEntities([]));
    narrativeApi
      .getContestedRanking({ days: 30, dimension: 'moral', limit: 100 })
      .then((data) => {
        const map: Record<string, number> = {};
        (data?.entities ?? []).forEach((e: { entity_name: string; divergence: number }) => {
          map[e.entity_name] = e.divergence;
        });
        setContested(map);
      })
      .catch(() => setContested({}));
  }, []);

  useEffect(() => {
    if (!overlayCountry) {
      setOverlayEntities([]);
      return;
    }
    let cancelled = false;
    statsApi
      .getTrendingEntities(40, undefined, overlayCountry)
      .then((data) => {
        if (!cancelled) setOverlayEntities(data);
      })
      .catch(() => {
        if (!cancelled) setOverlayEntities([]);
      });
    return () => {
      cancelled = true;
    };
  }, [overlayCountry]);

  // The paper's own reading. Limit 100 (vs the baseline's 40): per-source
  // coverage is sparse and the chart only draws entities shared with the
  // baseline, so extra overlay rows just improve pairing.
  useEffect(() => {
    if (!selectedSource) {
      setSourceEntities([]);
      return;
    }
    let cancelled = false;
    statsApi
      .getTrendingEntities(100, undefined, undefined, selectedSource.id)
      .then((data) => {
        if (!cancelled) setSourceEntities(data);
      })
      .catch(() => {
        if (!cancelled) setSourceEntities([]);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedSource]);

  useEffect(() => {
    if (sourceBaseline === 'Global') {
      setBaselineEntities([]);
      return;
    }
    let cancelled = false;
    statsApi
      .getTrendingEntities(40, undefined, sourceBaseline)
      .then((data) => {
        if (!cancelled) setBaselineEntities(data);
      })
      .catch(() => {
        if (!cancelled) setBaselineEntities([]);
      });
    return () => {
      cancelled = true;
    };
  }, [sourceBaseline]);

  // Static mode only snapshots papers with enough scored mentions
  // (meta.trending_sources) — offering the rest would give empty overlays.
  const newspaperOptions = useMemo(() => {
    const snapshotted =
      isStaticMode() && meta?.trending_sources ? new Set(meta.trending_sources) : null;
    return sources
      .filter((s) => !snapshotted || snapshotted.has(s.id))
      .slice()
      .sort(
        (a, b) =>
          (a.country || '').localeCompare(b.country || '') || a.name.localeCompare(b.name)
      );
  }, [sources, meta]);

  const handleSourceChange = (s: NewsSource | null) => {
    setSelectedSource(s);
    // Default baseline: the paper's own country when we have data for it
    // (static mode only snapshots some countries), else the global average.
    setSourceBaseline(s && availableCountries.includes(s.country) ? s.country : 'Global');
  };

  const byArchetype = (list: EntitySentimentSummary[]) =>
    selectedArchetypes.length
      ? list.filter((e) => selectedArchetypes.includes(archetypeLabel(e.power_score, e.moral_score)))
      : list;

  const filteredHighlighted = byArchetype(highlightedEntities);
  const newspaperBaseline = sourceBaseline === 'Global' ? highlightedEntities : baselineEntities;

  const toggleArchetype = (a: ArchetypeLabel) => {
    setSelectedArchetypes((prev) => (prev.includes(a) ? prev.filter((x) => x !== a) : [...prev, a]));
  };

  return (
    <Box>
      <Paper sx={{ p: 2, mb: 4, bgcolor: tokens.surfaceSunken, border: `1px solid ${tokens.border}` }}>
        <Grid container spacing={3} alignItems="center">
          <Grid item xs={12} sm={8}>
            <Autocomplete
              id="entity-jump-to"
              options={entities}
              // Includes type so same-named entities of different types (e.g. two
              // "Washington") are distinguishable in the dropdown.
              getOptionLabel={(e) => `${e.name} (${e.type}, ${e.mention_count || 0} mentions)`}
              onChange={(_, value) => value && navigate(`/entities/${value.id}`)}
              renderInput={(params) => (
                <TextField {...params} label="Jump to an entity's profile" size="small" fullWidth />
              )}
            />
          </Grid>
          <Grid item xs={12} sm={4}>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {ARCHETYPES.map((a) => (
                <Chip
                  key={a}
                  label={a}
                  size="small"
                  onClick={() => toggleArchetype(a)}
                  variant={selectedArchetypes.includes(a) ? 'filled' : 'outlined'}
                  sx={{
                    borderColor: archetypeColor(a === 'Hero' || a === 'Villain' ? 1 : -1, a === 'Hero' || a === 'Victim' ? 1 : -1),
                    bgcolor: selectedArchetypes.includes(a)
                      ? archetypeColor(a === 'Hero' || a === 'Villain' ? 1 : -1, a === 'Hero' || a === 'Victim' ? 1 : -1)
                      : 'transparent',
                    color: selectedArchetypes.includes(a) ? '#fff' : tokens.inkMuted,
                  }}
                />
              ))}
            </Box>
          </Grid>
        </Grid>
      </Paper>

      <Grid container spacing={4}>
        <Grid item xs={12} md={7}>
          <Card>
            <CardHeader
              title="Entity Sentiment Analysis"
              subheader={
                scatterTab === 0
                  ? overlayCountry
                    ? `Gray: global baseline. Colored: how ${overlayCountry}'s sources read the same entities.`
                    : 'Power vs. Moral positioning of key entities, all sources combined'
                  : selectedSource
                    ? `Gray: ${sourceBaseline === 'Global' ? 'global baseline' : `${sourceBaseline}'s sources`}. Colored: how ${selectedSource.name} reads the same entities.`
                    : 'Pick a newspaper to see how far it strays from its country — or the world'
              }
              action={
                <Tooltip title="Each dot is an entity's average position across analyzed coverage; the quadrants are narrative archetypes. A dashed ring marks entities whose national spheres disagree most (cross-country Jensen-Shannon divergence) — a ringed dot near the center is an average of conflicting readings, not consensus. Overlay a country against the global baseline, or a single newspaper against its own country's sphere.">
                  <IconButton>
                    <InfoIcon />
                  </IconButton>
                </Tooltip>
              }
            />
            <CardContent>
              <Tabs
                value={scatterTab}
                onChange={(_, v) => setScatterTab(v)}
                sx={{ mb: 1.5, minHeight: 36, '& .MuiTab-root': { minHeight: 36 } }}
              >
                <Tab label="By country" />
                <Tab label="By newspaper" />
              </Tabs>
              {scatterTab === 0 ? (
                <Autocomplete
                  size="small"
                  options={availableCountries}
                  value={overlayCountry}
                  onChange={(_, v) => setOverlayCountry(v)}
                  renderInput={(params) => (
                    <TextField {...params} label="Compare a country against the global baseline" />
                  )}
                  sx={{ maxWidth: 360, mb: 1 }}
                />
              ) : (
                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 1 }}>
                  <Autocomplete
                    size="small"
                    options={newspaperOptions}
                    groupBy={(s) => s.country || 'Other'}
                    getOptionLabel={(s) => s.name}
                    value={selectedSource}
                    onChange={(_, v) => handleSourceChange(v)}
                    renderInput={(params) => <TextField {...params} label="Newspaper" />}
                    sx={{ flex: 1, minWidth: 240, maxWidth: 360 }}
                  />
                  <Autocomplete
                    size="small"
                    disableClearable
                    options={['Global', ...availableCountries]}
                    value={sourceBaseline}
                    onChange={(_, v) => setSourceBaseline(v)}
                    renderInput={(params) => <TextField {...params} label="Compare against" />}
                    sx={{ minWidth: 200 }}
                  />
                </Box>
              )}
              <SentimentChart
                data={scatterTab === 0 ? filteredHighlighted : byArchetype(newspaperBaseline)}
                height={500}
                showLabels={true}
                overlay={
                  scatterTab === 0
                    ? overlayCountry && overlayEntities.length > 0
                      ? { label: overlayCountry, data: overlayEntities }
                      : null
                    : selectedSource && sourceEntities.length > 0
                      ? { label: selectedSource.name, data: sourceEntities }
                      : null
                }
                baselineLabel={scatterTab === 1 && sourceBaseline !== 'Global' ? sourceBaseline : 'Global'}
                contested={contested}
              />
              <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted, px: 2 }}>
                Dashed ring = contested across countries (stronger ring, sharper disagreement).
                {scatterTab === 0
                  ? overlayCountry
                    ? ' Dashed line = the gap between the global baseline and this country’s reading; a gray dot with no partner is an entity this country’s press is largely silent on.'
                    : ' Averages hide contestation — overlay a country to see who disagrees.'
                  : selectedSource
                    ? sourceEntities.length > 0
                      ? ' Dashed line = the gap between the baseline and this paper’s reading; a gray dot with no partner is an entity this paper has barely covered (fewer than 3 scored mentions).'
                      : ` Not enough scored coverage from ${selectedSource.name} yet to draw its reading.`
                    : ' National averages hide the outliers — pick a paper to see how far one newsroom strays from its sphere.'}
              </Typography>
            </CardContent>
          </Card>

          <Card sx={{ mt: 3 }}>
            <CardHeader title="Browse all entities" subheader={`${entities.length} tracked, sorted by mention count`} />
            <CardContent sx={{ p: 0, '&:last-child': { pb: 0 }, maxHeight: 480, overflowY: 'auto' }}>
              {entities.slice(0, 60).map((entity, i) => (
                <Box
                  key={entity.id}
                  onClick={() => navigate(`/entities/${entity.id}`)}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1.5,
                    px: 2,
                    py: 1,
                    cursor: 'pointer',
                    borderTop: i === 0 ? 'none' : `1px solid ${tokens.border}`,
                    '&:hover': { bgcolor: tokens.surfaceSunken },
                  }}
                >
                  <Typography variant="body2" sx={{ flex: 1 }}>
                    {entity.name}
                  </Typography>
                  <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
                    {entity.type}
                  </Typography>
                  <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted, minWidth: 60, textAlign: 'right' }}>
                    {(entity.mention_count || 0).toLocaleString()}
                  </Typography>
                </Box>
              ))}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={5}>
          <ContestedEntitiesPanel />

          <Box sx={{ mt: 3 }}>
            <DriftFeedPanel />
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
};

export default EntityAnalysisPage;
