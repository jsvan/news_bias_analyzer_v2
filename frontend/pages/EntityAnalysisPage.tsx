import React, { useState } from 'react';
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
import SentimentChart from '../components/SentimentChart';
import ContestedEntitiesPanel from '../components/ContestedEntitiesPanel';
import DriftFeedPanel from '../components/DriftFeedPanel';
import { EntitySentimentSummary } from '../types';
import { tokens, archetypeColor, archetypeLabel, monoNumber, ArchetypeLabel } from '../theme';

const ARCHETYPES: ArchetypeLabel[] = ['Hero', 'Victim', 'Villain', 'Threat'];

// No trending/highlighted-entities endpoint exists yet (confirmed in services/api.ts —
// entityApi has no such method); this page is honest about that rather than faking data.
const highlightedEntities: EntitySentimentSummary[] = [];

const EntityAnalysisPage: React.FC = () => {
  const { entities } = useData();
  const navigate = useNavigate();
  const [selectedArchetypes, setSelectedArchetypes] = useState<ArchetypeLabel[]>([]);

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
              <SentimentChart data={filteredHighlighted} entityTypes={{}} height={500} showLabels={true} />
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={5}>
          <Card>
            <CardHeader title="Notable Entities" subheader="Entities with unusual sentiment patterns" />
            <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
              {filteredHighlighted.length === 0 && (
                <Box sx={{ px: 2, py: 3 }}>
                  <Typography variant="body2" sx={{ color: tokens.inkMuted }}>
                    No standout divergence detected yet — this view surfaces entities whose
                    coverage strays furthest from the global baseline once enough sources
                    have been analyzed.
                  </Typography>
                </Box>
              )}
              {filteredHighlighted.slice(0, 8).map((entity, i) => {
                const match = entities.find((e) => e.name === entity.entity);
                return (
                  <Box
                    key={entity.entity}
                    onClick={() => match && navigate(`/entities/${match.id}`)}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1.5,
                      px: 2,
                      py: 1.25,
                      cursor: match ? 'pointer' : 'default',
                      borderTop: i === 0 ? 'none' : `1px solid ${tokens.border}`,
                      '&:hover': match ? { bgcolor: tokens.surfaceSunken } : undefined,
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
                    <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted, minWidth: 44, textAlign: 'right' }}>
                      {entity.global_percentile}%ile
                    </Typography>
                  </Box>
                );
              })}
            </CardContent>
          </Card>

          <Box sx={{ mt: 3 }}>
            <ContestedEntitiesPanel />
          </Box>

          <Box sx={{ mt: 3 }}>
            <DriftFeedPanel />
          </Box>

          <Card sx={{ mt: 3 }}>
            <CardHeader title="Browse all entities" subheader={`${entities.length} tracked, sorted by mention count`} />
            <CardContent sx={{ p: 0, '&:last-child': { pb: 0 }, maxHeight: 360, overflowY: 'auto' }}>
              {entities.slice(0, 40).map((entity, i) => (
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
      </Grid>
    </Box>
  );
};

export default EntityAnalysisPage;
