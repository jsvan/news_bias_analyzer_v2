import React, { useEffect, useMemo, useState } from 'react';
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
import { Card, CardHeader, CardContent, Box, Typography, Chip } from '@mui/material';
import { tokens, categoricalColor, monoNumber } from '../theme';
import { narrativeApi } from '../services/api';

// The SVD source map (server/routers/narrative_endpoints.py::get_source_map,
// kernel analyzer/narrative_metrics.py::svd_source_map): sources as points in
// the plane the DATA defines - the two directions of greatest disagreement in
// how sources score the same entities. "Beyond left-right" made literal: the
// axes are empirical, unnamed, and re-derived from the corpus every load.

interface SourceMapPoint {
  source_id: number;
  source_name: string;
  country: string | null;
  x: number;
  y: number;
}

interface SourceMapResponse {
  weeks: number;
  explained_variance: number[];
  sources: SourceMapPoint[];
}

const SourceMapPanel: React.FC = () => {
  const [data, setData] = useState<SourceMapResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    narrativeApi
      .getSourceMap({ weeks: 12 })
      .then((d: SourceMapResponse) => setData(d))
      .catch((err) => setError((err as Error).message));
  }, []);

  const countryOrder = useMemo(() => {
    const order: string[] = [];
    (data?.sources ?? []).forEach((s) => {
      const c = s.country ?? 'Unknown';
      if (!order.includes(c)) order.push(c);
    });
    return order;
  }, [data]);

  const padded = useMemo(() => {
    const pts = data?.sources ?? [];
    if (!pts.length) return { xDomain: [-1, 1] as [number, number], yDomain: [-1, 1] as [number, number] };
    const xs = pts.map((p) => p.x);
    const ys = pts.map((p) => p.y);
    const pad = (lo: number, hi: number): [number, number] => {
      const m = Math.max((hi - lo) * 0.15, 0.1);
      return [lo - m, hi + m];
    };
    return {
      xDomain: pad(Math.min(...xs), Math.max(...xs)),
      yDomain: pad(Math.min(...ys), Math.max(...ys)),
    };
  }, [data]);

  return (
    <Card>
      <CardHeader
        title="The source map"
        subheader="Every source placed by the two directions of greatest disagreement the data itself contains (last 12 weeks)"
      />
      <CardContent sx={{ pt: 0 }}>
        {error && (
          <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 2 }}>
            {error}
          </Typography>
        )}
        {data && data.sources.length < 3 && !error && (
          <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 2 }}>
            Not enough overlapping coverage to place sources yet.
          </Typography>
        )}
        {data && data.sources.length >= 3 && (
          <>
            <ResponsiveContainer width="100%" height={420}>
              <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={tokens.border} />
                <XAxis
                  type="number"
                  dataKey="x"
                  domain={padded.xDomain}
                  tick={false}
                  label={{
                    value: 'Empirical axis 1',
                    position: 'insideBottom',
                    offset: 0,
                    fontSize: 11,
                    fill: tokens.inkMuted,
                  }}
                />
                <YAxis
                  type="number"
                  dataKey="y"
                  domain={padded.yDomain}
                  tick={false}
                  label={{
                    value: 'Empirical axis 2',
                    angle: -90,
                    position: 'insideLeft',
                    fontSize: 11,
                    fill: tokens.inkMuted,
                  }}
                />
                <ReferenceLine x={0} stroke={tokens.border} />
                <ReferenceLine y={0} stroke={tokens.border} />
                <Tooltip
                  cursor={false}
                  content={({ payload }) => {
                    const p = payload?.[0]?.payload as SourceMapPoint | undefined;
                    if (!p) return null;
                    return (
                      <Box
                        sx={{
                          bgcolor: tokens.surface,
                          border: `1px solid ${tokens.border}`,
                          borderRadius: 1,
                          px: 1.5,
                          py: 1,
                        }}
                      >
                        <Typography variant="body2" sx={{ color: tokens.ink }}>
                          {p.source_name}
                        </Typography>
                        <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
                          {p.country ?? 'Unknown'}
                        </Typography>
                      </Box>
                    );
                  }}
                />
                <Scatter
                  data={data.sources}
                  isAnimationActive={false}
                  shape={(props: any) => {
                    const { cx, cy, payload } = props;
                    const color = categoricalColor(payload.country ?? 'Unknown', countryOrder);
                    return (
                      <g>
                        <circle cx={cx} cy={cy} r={5} fill={color} opacity={0.85} />
                        <text
                          x={cx + 8}
                          y={cy + 3}
                          fontSize={10}
                          fill={tokens.inkMuted}
                          fontFamily='"IBM Plex Sans", sans-serif'
                        >
                          {payload.source_name}
                        </text>
                      </g>
                    );
                  }}
                />
              </ScatterChart>
            </ResponsiveContainer>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', mt: 0.5, flexWrap: 'wrap', gap: 1 }}>
              <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                {countryOrder.slice(0, 10).map((c) => (
                  <Chip
                    key={c}
                    label={c}
                    size="small"
                    variant="outlined"
                    sx={{
                      borderColor: categoricalColor(c, countryOrder),
                      color: tokens.inkMuted,
                      height: 20,
                      fontSize: 10,
                    }}
                  />
                ))}
              </Box>
              <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted }}>
                axes explain {data.explained_variance.map((v) => `${Math.round(v * 100)}%`).join(' + ')} of variance
              </Typography>
            </Box>
            <Typography variant="caption" sx={{ display: 'block', mt: 1, color: tokens.inkMuted }}>
              The axes have no assigned meaning — they are the strongest patterns of disagreement
              in the scores themselves. Sources that land close score the same entities alike.
            </Typography>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default SourceMapPanel;
