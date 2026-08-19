import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardContent, Box, Typography, IconButton, Tooltip } from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';
import { tokens, monoNumber } from '../theme';
import { useData } from '../context/DataContext';
import { driftApi } from '../services/api';
import { isStaticMode } from '../services/config/environment';

interface DriftFeedEntry {
  entity_id: number;
  entity_name: string;
  source_id: number | null;
  source_name: string | null;
  dimension: string;
  week_start: string;
  statistic: number;
  p_value: number;
  mean_before: number;
  mean_after: number;
}

// Precomputed weekly feed (analyzer/drift_detection.py) of the most statistically
// significant sentiment shifts across the whole corpus - the automated, always-on
// version of the kind of finding ("negative polarization spike for Trump around Jan 6")
// this project's author already found once by hand.
const DriftFeedPanel: React.FC = () => {
  const { entities } = useData();
  const navigate = useNavigate();
  const [entries, setEntries] = useState<DriftFeedEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isStaticMode()) return;
    driftApi.getDriftFeed({ dimension: 'moral', scope: 'all', limit: 10 })
      .then((data) => setEntries(data.events))
      .catch((err) => setError((err as Error).message));
  }, []);

  // The drift feed isn't snapshotted (and the entity_drift_events table can't
  // have events until ~8 weeks of corpus accumulate - pettitt_test's floor), so
  // on the static site render nothing rather than a permanent error box.
  if (isStaticMode()) return null;

  return (
    <Card>
      <CardHeader
        title="Significant shifts"
        subheader="Sentiment changepoints the pipeline flagged on its own, ranked by significance"
        action={
          <Tooltip title="Each row is a statistically significant Pettitt-test changepoint in an entity's sentiment trajectory - either the whole corpus moving together (GLOBAL) or a single source moving alone, beyond what the global trend explains.">
            <IconButton>
              <InfoIcon />
            </IconButton>
          </Tooltip>
        }
      />
      <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
        {error && (
          <Box sx={{ px: 2, py: 3 }}>
            <Typography variant="body2" sx={{ color: tokens.inkMuted }}>{error}</Typography>
          </Box>
        )}
        {!error && entries === null && (
          <Box sx={{ px: 2, py: 3 }}>
            <Typography variant="body2" sx={{ color: tokens.inkMuted }}>Loading…</Typography>
          </Box>
        )}
        {!error && entries?.length === 0 && (
          <Box sx={{ px: 2, py: 3 }}>
            <Typography variant="body2" sx={{ color: tokens.inkMuted }}>
              No significant shifts detected yet.
            </Typography>
          </Box>
        )}
        {entries?.map((e, i) => {
          const match = entities.find((ent) => ent.name === e.entity_name);
          const scope = e.source_name ? e.source_name : 'GLOBAL';
          return (
            <Box
              key={`${e.entity_id}-${e.source_id ?? 'global'}`}
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
              <Box sx={{ flex: 1 }}>
                <Typography variant="body2" sx={{ fontWeight: 500 }}>
                  {e.entity_name}
                </Typography>
                <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
                  {scope} · {e.week_start} · {e.mean_before.toFixed(2)} → {e.mean_after.toFixed(2)}
                </Typography>
              </Box>
              <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted }}>
                p={e.p_value < 0.001 ? '<0.001' : e.p_value.toFixed(3)}
              </Typography>
            </Box>
          );
        })}
      </CardContent>
    </Card>
  );
};

export default DriftFeedPanel;
