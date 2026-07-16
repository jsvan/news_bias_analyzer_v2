import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardContent, Box, Typography, IconButton, Tooltip } from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';
import { tokens, monoNumber } from '../theme';
import { useData } from '../context/DataContext';
import { narrativeApi } from '../services/api';

interface ContestedEntity {
  entity_name: string;
  divergence: number;
}

// "The front line": entities with the sharpest cross-country sentiment disagreement
// (extension/api/narrative_endpoints.py::get_contested_ranking, backed by
// analyzer/narrative_metrics.py::contested_ranking - Jensen-Shannon divergence between
// countries' sentiment histograms for the same entity). Live-API only for now.
const ContestedEntitiesPanel: React.FC = () => {
  const { entities } = useData();
  const navigate = useNavigate();
  const [ranked, setRanked] = useState<ContestedEntity[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    narrativeApi.getContestedRanking({ days: 30, dimension: 'moral', limit: 8 })
      .then((data) => setRanked(data.entities))
      .catch((err) => setError((err as Error).message));
  }, []);

  return (
    <Card>
      <CardHeader
        title="The front line"
        subheader="Entities where countries disagree most on sentiment, last 30 days"
        action={
          <Tooltip title="Divergence = the sharpest Jensen-Shannon divergence between any two countries' sentiment-score histograms for this entity. Computed mechanically, no editorial judgment.">
            <IconButton>
              <InfoIcon />
            </IconButton>
          </Tooltip>
        }
      />
      <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
        {error && (
          <Box sx={{ px: 2, py: 3 }}>
            <Typography variant="body2" sx={{ color: tokens.inkMuted }}>
              {error}
            </Typography>
          </Box>
        )}
        {!error && ranked === null && (
          <Box sx={{ px: 2, py: 3 }}>
            <Typography variant="body2" sx={{ color: tokens.inkMuted }}>
              Loading…
            </Typography>
          </Box>
        )}
        {!error && ranked?.length === 0 && (
          <Box sx={{ px: 2, py: 3 }}>
            <Typography variant="body2" sx={{ color: tokens.inkMuted }}>
              No entities with enough cross-country coverage in this window yet.
            </Typography>
          </Box>
        )}
        {ranked?.map((entry, i) => {
          const match = entities.find((e) => e.name === entry.entity_name);
          return (
            <Box
              key={entry.entity_name}
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
              <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted, minWidth: 20 }}>
                {i + 1}
              </Typography>
              <Typography variant="body2" sx={{ flex: 1, fontWeight: 500 }}>
                {entry.entity_name}
              </Typography>
              <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted }}>
                JSD {entry.divergence.toFixed(2)}
              </Typography>
            </Box>
          );
        })}
      </CardContent>
    </Card>
  );
};

export default ContestedEntitiesPanel;
