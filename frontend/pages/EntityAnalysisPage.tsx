import React, { useEffect, useState } from 'react';
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
  Tooltip,
  Chip,
} from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';
import { useData } from '../context/DataContext';
import { statsApi, narrativeApi } from '../services/api';
import SentimentChart from '../components/SentimentChart';
import ContestedEntitiesPanel from '../components/ContestedEntitiesPanel';
import DriftFeedPanel from '../components/DriftFeedPanel';
import { EntitySentimentSummary } from '../types';
import { tokens, archetypeColor, archetypeLabel, monoNumber, ArchetypeLabel } from '../theme';

const ARCHETYPES: ArchetypeLabel[] = ['Hero', 'Victim', 'Villain', 'Threat'];

const EntityAnalysisPage: React.FC = () => {
  const { entities, availableCountries } = useData();
  const navigate = useNavigate();
  const [selectedArchetypes, setSelectedArchetypes] = useState<ArchetypeLabel[]>([]);
  const [highlightedEntities, setHighlightedEntities] = useState<EntitySentimentSummary[]>([]);

  // The comparison layer: one country's reading of the same entities, drawn
  // against the global baseline instead of replacing it.
  const [overlayCountry, setOverlayCountry] = useState<string | null>(null);
  const [overlayEntities, setOverlayEntities] = useState<EntitySentimentSummary[]>([]);

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

  const filteredHighlighted = selectedArchetypes.length
    ? highlightedEntities.filter((e) => selectedArchetypes.includes(archetypeLabel(e.power_score, e.moral_score)))
    : highlightedEntities;

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
                overlayCountry
                  ? `Gray: global baseline. Colored: how ${overlayCountry}'s sources read the same entities.`
                  : 'Power vs. Moral positioning of key entities, all sources combined'
              }
              action={
                <Tooltip title="Each dot is an entity's average position across analyzed coverage; the quadrants are narrative archetypes. A dashed ring marks entities whose national spheres disagree most (cross-country Jensen-Shannon divergence) — a ringed dot near the center is an average of conflicting readings, not consensus. Pick a country to overlay its reading against the global baseline.">
                  <IconButton>
                    <InfoIcon />
                  </IconButton>
                </Tooltip>
              }
            />
            <CardContent>
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
              <SentimentChart
                data={filteredHighlighted}
                height={500}
                showLabels={true}
                overlay={
                  overlayCountry && overlayEntities.length > 0
                    ? { country: overlayCountry, data: overlayEntities }
                    : null
                }
                contested={contested}
              />
              <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted, px: 2 }}>
                Dashed ring = contested across countries (stronger ring, sharper disagreement).
                {overlayCountry
                  ? ' Dashed line = the gap between the global baseline and this country’s reading; a gray dot with no partner is an entity this country’s press is largely silent on.'
                  : ' Averages hide contestation — overlay a country to see who disagrees.'}
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
