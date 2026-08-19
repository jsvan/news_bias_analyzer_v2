import React, { useState } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Label,
  ReferenceLine
} from 'recharts';
import { Box, Typography, ToggleButtonGroup, ToggleButton, Chip } from '@mui/material';
import { Distribution, SentimentDistributions } from '../types';
import { tokens, monoNumber } from '../theme';

// Fixed 3-way palette for the classic global/national/source comparison — not a
// rotating first-appearance palette, since those three roles are stable slots.
const GLOBAL_COLOR = tokens.accent;
const NATIONAL_COLOR = tokens.categorical[1];
const SOURCE_COLOR = tokens.categorical[2];

// One overlay-able curve. The chart itself no longer knows about global /
// national / source roles — any page can stack any comparison (e.g. two
// newspapers) by passing its own layers. All backend PDFs share one fixed
// x-grid, so overlaid curves are directly comparable by construction.
export interface DistributionLayer {
  key: string;
  label: string;
  color: string;
  power?: Distribution;
  moral?: Distribution;
}

// Adapter for the live API's fixed global/national/source response shape —
// keeps existing callers (the entity profile page) one function call away from
// the generic layer API.
export function layersFromDistributions(d: SentimentDistributions | null | undefined): DistributionLayer[] {
  const layers: DistributionLayer[] = [];
  if (!d) return layers;
  if (d.global) layers.push({ key: 'global', label: 'Global', color: GLOBAL_COLOR, power: d.global.power, moral: d.global.moral });
  if (d.national) layers.push({ key: 'national', label: d.national.country, color: NATIONAL_COLOR, power: d.national.power, moral: d.national.moral });
  if (d.source) layers.push({ key: 'source', label: d.source.source_name, color: SOURCE_COLOR, power: d.source.power, moral: d.source.moral });
  return layers;
}

interface SentimentDistributionChartProps {
  title?: string;
  entityName: string;
  layers: DistributionLayer[];
  height?: number;
  // Controlled mode: the page owns the power/moral toggle (page-wide toggles)
  // and no internal toggle is rendered. Omit for the self-contained behavior.
  dimension?: 'power' | 'moral';
  // Layer keys hidden until their chip is clicked. Initial-only — remount with
  // a key when the comparison context changes.
  initiallyHidden?: string[];
}

const SentimentDistributionChart: React.FC<SentimentDistributionChartProps> = ({
  title = 'Sentiment Distribution',
  entityName,
  layers,
  height = 400,
  dimension: controlledDimension,
  initiallyHidden = []
}) => {
  const [internalDimension, setInternalDimension] = useState<'power' | 'moral'>('power');
  const dimension = controlledDimension ?? internalDimension;

  // Layer visibility is real state: the chips are working toggles.
  const [hidden, setHidden] = useState<Set<string>>(new Set(initiallyHidden));
  const toggleLayer = (key: string) =>
    setHidden((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  const layersWithData = layers.filter((l) => (l[dimension]?.pdf?.x?.length ?? 0) > 0);
  const visibleLayers = layersWithData.filter((l) => !hidden.has(l.key));

  // Merge all visible curves onto a shared x-axis. The backend emits every
  // layer on one fixed grid, so this is index alignment in practice; a map by
  // x-value keeps mixed-grid inputs rendering instead of mispairing.
  const pointsByX = new Map<number, Record<string, number>>();
  visibleLayers.forEach((l) => {
    const pdf = l[dimension]!.pdf!;
    pdf.x.forEach((x, i) => {
      const point = pointsByX.get(x) ?? { x };
      point[l.key] = pdf.y[i];
      pointsByX.set(x, point);
    });
  });
  const distributionData = [...pointsByX.values()].sort((a, b) => a.x - b.x);

  // Enough data = some layer has a real curve for this dimension (visibility
  // doesn't count against it — hiding every chip shouldn't flip the empty state).
  const hasEnoughData = layersWithData.some((l) => (l[dimension]!.pdf!.x.length ?? 0) >= 20);

  const layerName = (l: DistributionLayer): string => {
    const count = l[dimension]?.count;
    return count != null ? `${l.label} (n=${count})` : l.label;
  };

  return (
    <Box sx={{ width: '100%', height: height, padding: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, flexWrap: 'wrap', gap: 1 }}>
        <Box>
          <Typography variant="h6" sx={{ color: tokens.ink }}>
            {title}: {entityName}
          </Typography>
          <Typography variant="subtitle2" sx={{ color: tokens.inkMuted }}>
            {dimension === 'power' ? 'Power Dimension' : 'Moral Dimension'} Distribution
          </Typography>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {/* Toggle which curves to show */}
          <Box>
            {layers.map((l) => (
              <Chip
                key={l.key}
                label={l.label}
                sx={{
                  mx: 0.5,
                  bgcolor: !hidden.has(l.key) ? l.color : 'transparent',
                  color: !hidden.has(l.key) ? '#FFFFFF' : tokens.inkMuted,
                  border: `1px solid ${!hidden.has(l.key) ? l.color : tokens.border}`,
                }}
                onClick={() => toggleLayer(l.key)}
              />
            ))}
          </Box>

          {/* Dimension toggle — only in uncontrolled mode; pages with a
              page-wide dimension control pass `dimension` instead. */}
          {controlledDimension == null && (
            <ToggleButtonGroup
              value={dimension}
              exclusive
              onChange={(_, v: 'power' | 'moral' | null) => v != null && setInternalDimension(v)}
              aria-label="sentiment dimension"
              size="small"
            >
              <ToggleButton value="power" aria-label="power dimension">
                Power
              </ToggleButton>
              <ToggleButton value="moral" aria-label="moral dimension">
                Moral
              </ToggleButton>
            </ToggleButtonGroup>
          )}
        </Box>
      </Box>

      {!hasEnoughData && (
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
          height: '80%',
          bgcolor: tokens.surfaceSunken,
          borderRadius: 1,
          border: `1px solid ${tokens.border}`,
          p: 3
        }}>
          <Typography variant="body1" sx={{ mb: 2, color: tokens.inkMuted }}>
            Not enough data available for meaningful statistical visualization
          </Typography>
          <Typography variant="body2" sx={{ color: tokens.inkMuted }}>
            Additional entity mentions are required for reliable distribution analysis
          </Typography>
        </Box>
      )}

      {hasEnoughData && (
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={distributionData}
            margin={{ top: 20, right: 30, bottom: 30, left: 30 }}
          >
          <CartesianGrid strokeDasharray="3 3" stroke={tokens.border} />
          <XAxis
            dataKey="x"
            type="number"
            domain={['dataMin', 'dataMax']}
            tickCount={9}
            tickFormatter={(v: number) => v.toFixed(1)}
            tick={{ fill: tokens.inkMuted, fontSize: 11, fontFamily: 'monospace' }}
          >
            <Label
              value={dimension === 'power' ? 'Power Score' : 'Moral Score'}
              position="bottom"
              offset={10}
              style={{ fill: tokens.inkMuted, fontSize: 12 }}
            />
          </XAxis>
          <YAxis tick={{ fill: tokens.inkMuted, fontSize: 11, fontFamily: 'monospace' }}>
            <Label value="Probability Density" position="left" angle={-90} offset={10} style={{ fill: tokens.inkMuted, fontSize: 12 }} />
          </YAxis>
          <Tooltip
            formatter={(value: number) => [value.toFixed(4), 'Probability Density']}
            labelFormatter={(label) => `Score: ${Number(label).toFixed(2)}`}
            contentStyle={{ border: `1px solid ${tokens.border}`, borderRadius: 8, backgroundColor: tokens.surface }}
            labelStyle={{ color: tokens.ink }}
            itemStyle={{ color: tokens.ink, ...monoNumber }}
          />
          <Legend wrapperStyle={{ fontSize: 12, color: tokens.inkMuted }} />

          {/* Neutral is the anchor of the whole scale - always visible. */}
          <ReferenceLine
            x={0}
            stroke={tokens.ink}
            strokeWidth={1.25}
            label={{ value: 'neutral', position: 'insideTopLeft', fill: tokens.inkMuted, fontSize: 11 }}
          />

          {/* Mean marker per visible curve */}
          {visibleLayers.map((l) =>
            l[dimension]?.mean !== undefined ? (
              <ReferenceLine
                key={`mean-${l.key}`}
                x={l[dimension]!.mean}
                stroke={l.color}
                strokeDasharray="3 3"
                label={{ value: `${l.label} mean`, position: 'top', fill: tokens.inkMuted, fontSize: 11 }}
              />
            ) : null
          )}

          {/* The curves themselves, overlaid translucently */}
          {visibleLayers.map((l) => (
            <Area
              key={l.key}
              type="monotone"
              dataKey={l.key}
              name={layerName(l)}
              fill={l.color}
              stroke={l.color}
              fillOpacity={0.3}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
      )}
    </Box>
  );
};

export default SentimentDistributionChart;
