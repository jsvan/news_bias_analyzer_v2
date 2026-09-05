import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardContent, Box, Typography, IconButton, Tooltip } from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';
import { tokens, monoNumber } from '../theme';
import { useData } from '../context/DataContext';
import { narrativeApi } from '../services/api';

interface ContestedSphere {
  country: string;
  n: number;
  hist: number[];
}

interface ContestedEntity {
  entity_name: string;
  divergence: number;
  // The two countries whose histograms produced the (max-pairwise) divergence;
  // sphere_a is the friendlier reading. Absent in pre-2026-09 snapshots.
  sphere_a?: ContestedSphere | null;
  sphere_b?: ContestedSphere | null;
}

// Paired sentiment histograms as a sparkline: sphere_a in hero green,
// sphere_b in villain red, overlaid bar-for-bar across the 8 bins (-2 left,
// +2 right). Where the colors separate is where the two presses live in
// different stories.
const PairedHistogram: React.FC<{ a: ContestedSphere; b: ContestedSphere }> = ({ a, b }) => {
  const W = 84;
  const H = 24;
  const bins = Math.max(a.hist.length, b.hist.length);
  const bw = W / bins;
  const peak = Math.max(...a.hist, ...b.hist, 0.01);
  const bar = (hist: number[], color: string) =>
    hist.map((v, i) => {
      const h = (v / peak) * (H - 2);
      return (
        <rect
          key={i}
          x={i * bw + 0.5}
          y={H - h}
          width={bw - 1}
          height={h}
          fill={color}
          fillOpacity={0.55}
        />
      );
    });
  return (
    <svg width={W} height={H} style={{ flexShrink: 0 }} aria-hidden>
      <line x1={W / 2} x2={W / 2} y1={0} y2={H} stroke={tokens.border} />
      {bar(a.hist, tokens.hero)}
      {bar(b.hist, tokens.villain)}
    </svg>
  );
};

// "The front line": entities with the sharpest cross-country sentiment disagreement
// (server/routers/narrative_endpoints.py::get_contested_ranking, backed by
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
        subheader="Entities where countries disagree most on sentiment, last 30 days of coverage"
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
          const a = entry.sphere_a;
          const b = entry.sphere_b;
          return (
            <Box
              key={entry.entity_name}
              onClick={() => match && navigate(`/portrayals/${match.id}`)}
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
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography variant="body2" sx={{ fontWeight: 500 }}>
                  {entry.entity_name}
                </Typography>
                {a && b && (
                  <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
                    <Box component="span" sx={{ color: tokens.hero, fontWeight: 600 }}>
                      {a.country}
                    </Box>
                    {' vs '}
                    <Box component="span" sx={{ color: tokens.villain, fontWeight: 600 }}>
                      {b.country}
                    </Box>
                  </Typography>
                )}
              </Box>
              {a && b && <PairedHistogram a={a} b={b} />}
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
