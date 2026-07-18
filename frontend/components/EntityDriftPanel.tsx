import React, { useEffect, useState } from 'react';
import { Card, CardHeader, CardContent, Box, Typography, IconButton, Tooltip, Chip } from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';
import { tokens, monoNumber } from '../theme';
import { driftApi } from '../services/api';

interface DriftPoint {
  source_id: number | null;
  source_name: string | null;
  week_start: string;
  statistic: number;
  p_value: number;
  mean_before: number;
  mean_after: number;
}

interface EntityDriftResponse {
  entity_id: number;
  entity_name: string;
  dimension: string;
  global_shift: DriftPoint | null;
  source_shifts: DriftPoint[];
}

const DriftRow: React.FC<{ label: string; point: DriftPoint; first: boolean }> = ({ label, point, first }) => {
  const color = point.mean_after >= point.mean_before ? tokens.hero : tokens.villain;
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1.5,
        px: 2,
        py: 1.25,
        borderTop: first ? 'none' : `1px solid ${tokens.border}`,
      }}
    >
      <Box sx={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0, bgcolor: color }} />
      <Box sx={{ flex: 1 }}>
        <Typography variant="body2" sx={{ fontWeight: 500 }}>{label}</Typography>
        <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
          shifted around {point.week_start}: {point.mean_before.toFixed(2)} → {point.mean_after.toFixed(2)}
        </Typography>
      </Box>
      <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted, textAlign: 'right' }}>
        p={point.p_value < 0.001 ? '<0.001' : point.p_value.toFixed(3)}
      </Typography>
    </Box>
  );
};

// "Statistical surprise" - server/routers/drift_endpoints.py, backed by
// analyzer/narrative_metrics.py::pettitt_test. Distinguishes a GLOBAL shift (everyone
// moved together - an expected real-world event) from a SOURCE-specific residual shift
// (this one source moved on its own, unexplained by the global trend - the actually
// interesting editorial-stance signal). Computed live per entity, not from a cache.
const EntityDriftPanel: React.FC<{ entityId: number }> = ({ entityId }) => {
  const [dimension, setDimension] = useState<'power' | 'moral'>('moral');
  const [data, setData] = useState<EntityDriftResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    setError(null);
    driftApi.getEntityDrift(entityId, { dimension })
      .then(setData)
      .catch((err) => setError((err as Error).message));
  }, [entityId, dimension]);

  const hasAnyShift = !!data && (!!data.global_shift || data.source_shifts.length > 0);

  return (
    <Card>
      <CardHeader
        title="Statistical surprise"
        subheader="Significant shifts (Pettitt's changepoint test), not eyeballed"
        action={
          <Tooltip title="A GLOBAL shift means the whole corpus's average moved - an expected event. A source-specific shift means that one outlet moved on its own, after subtracting out the global trend - that's the editorial-stance surprise.">
            <IconButton>
              <InfoIcon />
            </IconButton>
          </Tooltip>
        }
      />
      <CardContent sx={{ pt: 0 }}>
        <Box sx={{ display: 'flex', gap: 1, mb: 1.5 }}>
          {(['moral', 'power'] as const).map((d) => (
            <Chip
              key={d}
              label={d === 'moral' ? 'Moral' : 'Power'}
              size="small"
              onClick={() => setDimension(d)}
              variant={dimension === d ? 'filled' : 'outlined'}
              sx={{
                bgcolor: dimension === d ? tokens.accent : 'transparent',
                color: dimension === d ? '#fff' : tokens.inkMuted,
                borderColor: tokens.accent,
              }}
            />
          ))}
        </Box>
      </CardContent>
      <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
        {error && (
          <Box sx={{ px: 2, py: 3 }}>
            <Typography variant="body2" sx={{ color: tokens.inkMuted }}>{error}</Typography>
          </Box>
        )}
        {!error && data === null && (
          <Box sx={{ px: 2, py: 3 }}>
            <Typography variant="body2" sx={{ color: tokens.inkMuted }}>Loading…</Typography>
          </Box>
        )}
        {!error && data && !hasAnyShift && (
          <Box sx={{ px: 2, py: 3 }}>
            <Typography variant="body2" sx={{ color: tokens.inkMuted }}>
              No statistically significant shift detected for this entity yet - either
              coverage has stayed stable, or there isn't enough weekly history to test.
            </Typography>
          </Box>
        )}
        {data?.global_shift && (
          <DriftRow label="Global (everyone moved together)" point={data.global_shift} first />
        )}
        {data?.source_shifts.map((s, i) => (
          <DriftRow
            key={s.source_id}
            label={`${s.source_name} (moved on its own)`}
            point={s}
            first={i === 0 && !data.global_shift}
          />
        ))}
      </CardContent>
    </Card>
  );
};

export default EntityDriftPanel;
