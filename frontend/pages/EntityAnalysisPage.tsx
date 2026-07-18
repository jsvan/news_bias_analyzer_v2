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
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Autocomplete,
  TextField,
  IconButton,
  Tooltip,
  Chip,
} from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';
import { useData } from '../context/DataContext';
import { statsApi } from '../services/api';
import SentimentChart from '../components/SentimentChart';
import ContestedEntitiesPanel from '../components/ContestedEntitiesPanel';
import DriftFeedPanel from '../components/DriftFeedPanel';
import { EntitySentimentSummary } from '../types';
import { tokens, archetypeColor, archetypeLabel, monoNumber, ArchetypeLabel } from '../theme';

const ARCHETYPES: ArchetypeLabel[] = ['Hero', 'Victim', 'Villain', 'Threat'];

const EntityAnalysisPage: React.FC = () => {
  const { entities } = useData();
  const navigate = useNavigate();
  const [selectedArchetypes, setSelectedArchetypes] = useState<ArchetypeLabel[]>([]);
  const [highlightedEntities, setHighlightedEntities] = useState<EntitySentimentSummary[]>([]);

  useEffect(() => {
    statsApi
      .getTrendingEntities(40)
      .then(setHighlightedEntities)
      .catch(() => setHighlightedEntities([]));
  }, []);

  const filteredHighlighted = selectedArchetypes.length
    ? highlightedEntities.filter((e) => selectedArchetypes.includes(archetypeLabel(e.power_score, e.moral_score)))
    : highlightedEntities;

  // Strongest archetype signal = distance from the neutral origin on the power/moral plane
  const notableEntities = [...filteredHighlighted]
    .sort((a, b) => Math.hypot(b.power_score, b.moral_score) - Math.hypot(a.power_score, a.moral_score))
    .slice(0, 8);

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
              subheader="Power vs. Moral positioning of key entities"
              action={
                <Tooltip title="Entities are positioned based on their average sentiment scores across all analyzed news sources. The quadrants represent different narrative archetypes.">
                  <IconButton>
                    <InfoIcon />
                  </IconButton>
                </Tooltip>
              }
            />
            <CardContent>
              <SentimentChart data={filteredHighlighted} height={500} showLabels={true} />
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
          <Card>
            <CardHeader title="Strongest portrayals" subheader="Furthest from neutral on both axes, all sources combined" />
            <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
              {notableEntities.length === 0 && (
                <Box sx={{ px: 2, py: 3 }}>
                  <Typography variant="body2" sx={{ color: tokens.inkMuted }}>
                    No scored entities yet. This list ranks entities by how far their average
                    portrayal sits from neutral once mentions are analyzed.
                  </Typography>
                </Box>
              )}
              {notableEntities.map((entity, i) => (
                <Box
                  key={entity.entity}
                  onClick={() => entity.id && navigate(`/entities/${entity.id}`)}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1.5,
                    px: 2,
                    py: 1.25,
                    cursor: entity.id ? 'pointer' : 'default',
                    borderTop: i === 0 ? 'none' : `1px solid ${tokens.border}`,
                    '&:hover': entity.id ? { bgcolor: tokens.surfaceSunken } : undefined,
                  }}
                >
                  <Box
                    sx={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      flexShrink: 0,
                      bgcolor: archetypeColor(entity.power_score, entity.moral_score),
                    }}
                  />
                  <Typography variant="body2" sx={{ flex: 1, fontWeight: 500 }}>
                    {entity.entity}
                  </Typography>
                  <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted }}>
                    P {entity.power_score.toFixed(1)} · M {entity.moral_score.toFixed(1)}
                  </Typography>
                  <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted, minWidth: 52, textAlign: 'right' }}>
                    {(entity.mention_count || 0).toLocaleString()}
                  </Typography>
                </Box>
              ))}
            </CardContent>
          </Card>

          <Box sx={{ mt: 3 }}>
            <ContestedEntitiesPanel />
          </Box>

          <Box sx={{ mt: 3 }}>
            <DriftFeedPanel />
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
};

export default EntityAnalysisPage;
