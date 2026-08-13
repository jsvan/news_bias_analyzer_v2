import React, { useEffect, useState } from 'react';
import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from 'recharts';
import { Card, CardHeader, CardContent, Box, Typography, Chip, Autocomplete, TextField } from '@mui/material';
import { tokens, archetypeColor, monoNumber } from '../theme';
import { narrativeApi } from '../services/api';
import { useData } from '../context/DataContext';

// Archetype quadrant + trajectory (server/routers/narrative_endpoints.py::
// get_entity_archetype, kernels in analyzer/narrative_metrics.py::archetype/
// trajectory). The entity's position on the power x moral plane, aggregated
// globally across sources, with its weekly path - how a portrayal *moves*
// through hero/victim/villain/threat space, not just where it sits today.
// Up to two country paths can be overlaid against the global one - same
// endpoint with its `country` filter.

interface ArchetypePoint {
  window_index: number;
  power: number;
  moral: number;
}

interface ArchetypeResponse {
  entity_id: number;
  entity_name: string;
  current_archetype: string;
  power: number;
  moral: number;
  trajectory: ArchetypePoint[] | null;
}

const ARCHETYPE_DISPLAY: Record<string, { label: string; color: string }> = {
  hero: { label: 'Hero', color: tokens.hero },
  victim: { label: 'Victim', color: tokens.victim },
  villain: { label: 'Villain', color: tokens.villain },
  nuisance: { label: 'Threat', color: tokens.threat },
  neutral: { label: 'Neutral', color: tokens.inkMuted },
};

const QUADRANT_LABELS = [
  { x: 1.1, y: 1.6, text: 'HERO', color: tokens.hero },
  { x: -1.1, y: 1.6, text: 'VICTIM', color: tokens.victim },
  { x: 1.1, y: -1.7, text: 'VILLAIN', color: tokens.villain },
  { x: -1.1, y: -1.7, text: 'THREAT', color: tokens.threat },
];

const MAX_OVERLAYS = 2;
// Fixed slot colors for the overlay paths (slot 1, slot 2) - stable while
// countries are swapped in and out, distinct from the ink-muted global path.
const OVERLAY_COLORS = [tokens.categorical[0], tokens.categorical[1]];

const ArchetypeQuadrantPanel: React.FC<{ entityId: number }> = ({ entityId }) => {
  const { availableCountries } = useData();
  const [data, setData] = useState<ArchetypeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [overlayCountries, setOverlayCountries] = useState<string[]>([]);
  const [overlays, setOverlays] = useState<Record<string, ArchetypePoint[]>>({});

  useEffect(() => {
    setData(null);
    setError(null);
    setOverlays({});
    setOverlayCountries([]);
    narrativeApi
      .getArchetype(entityId, { weeks: 12 })
      .then((d: ArchetypeResponse) => setData(d))
      .catch((err) => setError((err as Error).message));
  }, [entityId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const next: Record<string, ArchetypePoint[]> = {};
      await Promise.all(
        overlayCountries.map(async (c) => {
          try {
            const d: ArchetypeResponse = await narrativeApi.getArchetype(entityId, { weeks: 12, country: c });
            if (d.trajectory?.length) next[c] = d.trajectory;
          } catch {
            // no scored coverage from this country in the window - draw nothing
          }
        })
      );
      if (!cancelled) setOverlays(next);
    })();
    return () => {
      cancelled = true;
    };
  }, [entityId, overlayCountries]);

  const path = data?.trajectory ?? [];
  const display = ARCHETYPE_DISPLAY[data?.current_archetype ?? 'neutral'];
  const emptyOverlays = overlayCountries.filter((c) => !overlays[c]);

  return (
    <Card>
      <CardHeader
        title={data ? `Archetype trajectory — ${data.entity_name}` : 'Archetype trajectory'}
        subheader="Power × moral plane, weekly path over the last 12 weeks. Gray path: all sources worldwide; colored paths: one country's sources."
        action={
          data && (
            <Chip
              label={display.label}
              size="small"
              sx={{ bgcolor: display.color, color: '#fff', mt: 1, mr: 1 }}
            />
          )
        }
      />
      <CardContent sx={{ pt: 0 }}>
        {error && (
          <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 2 }}>
            {error}
          </Typography>
        )}
        {data && !path.length && !error && (
          <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 2 }}>
            Fewer than 3 weeks of scored coverage in the window — not enough to draw a path.
          </Typography>
        )}
        {path.length >= 1 && (
          <>
            <Autocomplete
              multiple
              size="small"
              options={availableCountries}
              value={overlayCountries}
              onChange={(_, value) => setOverlayCountries(value.slice(0, MAX_OVERLAYS))}
              getOptionDisabled={(option) =>
                overlayCountries.length >= MAX_OVERLAYS && !overlayCountries.includes(option)
              }
              renderInput={(params) => (
                <TextField {...params} label={`Compare countries (up to ${MAX_OVERLAYS})`} />
              )}
              sx={{ mb: 1.5 }}
            />
            <ResponsiveContainer width="100%" height={320}>
              <ScatterChart margin={{ top: 10, right: 10, bottom: 10, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={tokens.border} />
                <XAxis
                  type="number"
                  dataKey="power"
                  domain={[-2, 2]}
                  ticks={[-2, -1, 0, 1, 2]}
                  tick={{ fontSize: 11, fill: tokens.inkMuted }}
                  label={{ value: 'Power', position: 'insideBottom', offset: -5, fontSize: 11, fill: tokens.inkMuted }}
                />
                <YAxis
                  type="number"
                  dataKey="moral"
                  domain={[-2, 2]}
                  ticks={[-2, -1, 0, 1, 2]}
                  tick={{ fontSize: 11, fill: tokens.inkMuted }}
                  label={{ value: 'Moral', angle: -90, position: 'insideLeft', fontSize: 11, fill: tokens.inkMuted }}
                />
                <ReferenceLine x={0} stroke={tokens.border} />
                <ReferenceLine y={0} stroke={tokens.border} />
                {QUADRANT_LABELS.map((q) => (
                  <text
                    key={q.text}
                    x={`${50 + (q.x / 4.4) * 100}%`}
                    y={`${50 - (q.y / 4.6) * 100}%`}
                    textAnchor="middle"
                    fill={q.color}
                    opacity={0.25}
                    fontSize={12}
                    fontFamily='"IBM Plex Mono", monospace'
                  >
                    {q.text}
                  </text>
                ))}
                <Tooltip
                  cursor={false}
                  formatter={(value: number) => value.toFixed(2)}
                  labelFormatter={() => ''}
                  contentStyle={{
                    backgroundColor: tokens.surface,
                    border: `1px solid ${tokens.border}`,
                    borderRadius: 6,
                    fontSize: 12,
                  }}
                />
                {/* The global path: older waypoints fade; the line shows the route. */}
                <Scatter
                  data={path}
                  line={{ stroke: tokens.inkMuted, strokeWidth: 1, strokeDasharray: '4 3' }}
                  isAnimationActive={false}
                  shape={(props: any) => {
                    const { cx, cy, payload } = props;
                    const idx = path.findIndex((p) => p.window_index === payload.window_index);
                    const isLast = idx === path.length - 1;
                    const opacity = isLast ? 1 : 0.25 + (0.5 * idx) / Math.max(path.length - 1, 1);
                    return (
                      <circle
                        cx={cx}
                        cy={cy}
                        r={isLast ? 7 : 4}
                        fill={isLast ? archetypeColor(payload.power, payload.moral) : tokens.inkMuted}
                        opacity={opacity}
                        stroke={isLast ? tokens.surface : 'none'}
                        strokeWidth={isLast ? 2 : 0}
                      />
                    );
                  }}
                />
                {/* Country overlays: same fade-to-current treatment, slot-colored. */}
                {overlayCountries.map((c, slot) =>
                  overlays[c] ? (
                    <Scatter
                      key={c}
                      data={overlays[c]}
                      line={{ stroke: OVERLAY_COLORS[slot], strokeWidth: 1.25 }}
                      isAnimationActive={false}
                      shape={(props: any) => {
                        const { cx, cy, payload } = props;
                        const pts = overlays[c];
                        const idx = pts.findIndex((p) => p.window_index === payload.window_index);
                        const isLast = idx === pts.length - 1;
                        const opacity = isLast ? 1 : 0.3 + (0.5 * idx) / Math.max(pts.length - 1, 1);
                        return (
                          <circle
                            cx={cx}
                            cy={cy}
                            r={isLast ? 6 : 3.5}
                            fill={OVERLAY_COLORS[slot]}
                            opacity={opacity}
                            stroke={isLast ? tokens.surface : 'none'}
                            strokeWidth={isLast ? 2 : 0}
                          />
                        );
                      }}
                    />
                  ) : null
                )}
              </ScatterChart>
            </ResponsiveContainer>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
                  Faded dots are earlier weeks; the large dot is the current position.
                </Typography>
                {overlayCountries.map((c, slot) =>
                  overlays[c] ? (
                    <Chip
                      key={c}
                      label={c}
                      size="small"
                      variant="outlined"
                      sx={{ height: 18, fontSize: 10, color: OVERLAY_COLORS[slot], borderColor: OVERLAY_COLORS[slot] }}
                    />
                  ) : null
                )}
                {emptyOverlays.length > 0 && (
                  <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
                    (no scored coverage: {emptyOverlays.join(', ')})
                  </Typography>
                )}
              </Box>
              <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted }}>
                now P {data!.power >= 0 ? '+' : ''}{data!.power.toFixed(2)} · M{' '}
                {data!.moral >= 0 ? '+' : ''}{data!.moral.toFixed(2)}
              </Typography>
            </Box>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default ArchetypeQuadrantPanel;
