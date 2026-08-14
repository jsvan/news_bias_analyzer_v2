import React, { useState } from 'react';
import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  LabelList,
  Label,
  ReferenceLine,
  Customized
} from 'recharts';
import { Box, Typography, Chip, FormControl, InputLabel, Select, MenuItem, SelectChangeEvent, Alert } from '@mui/material';
import { EntitySentimentSummary } from '../types';
import { tokens, archetypeColor } from '../theme';

interface SentimentDataPoint extends EntitySentimentSummary {
  size: number;
  layer: 'baseline' | 'overlay';
}

interface SentimentChartProps {
  data: EntitySentimentSummary[];
  entityTypes?: Record<string, string[]>; // Type to list of entities mapping
  height?: number;
  showLabels?: boolean;
  // One sphere's reading of the same entities (a country, or a single
  // newspaper), drawn against the baseline. When set, baseline points recede
  // to gray anchors and the overlay's points carry the archetype color — the
  // same baseline-vs-reading idiom as the My Bubble divergence glyphs.
  overlay?: { label: string; data: EntitySentimentSummary[] } | null;
  // What `data` represents in tooltips: 'Global' unless the baseline is itself
  // a country (the newspaper-vs-its-country comparison).
  baselineLabel?: string;
  // entity name -> cross-country Jensen-Shannon divergence. Entities whose
  // spheres disagree get a dashed ring: a mean near neutral can be genuine
  // consensus or a fought-over average, and without this channel the two are
  // indistinguishable.
  contested?: Record<string, number>;
}

const SentimentChart: React.FC<SentimentChartProps> = ({
  data,
  entityTypes,
  height = 400,
  showLabels = true,
  overlay = null,
  baselineLabel = 'Global',
  contested = {}
}) => {
  const [selectedTypes, setSelectedTypes] = useState<string[]>(
    entityTypes ? Object.keys(entityTypes) : []
  );

  // Filter data based on selected entity types
  const filteredData: SentimentDataPoint[] = data
    .filter(item => {
      if (!entityTypes || selectedTypes.length === 0) return true;

      // Check if the entity belongs to any of the selected types
      for (const type of selectedTypes) {
        if (entityTypes[type]?.includes(item.entity)) {
          return true;
        }
      }
      return false;
    })
    .map(item => ({
      ...item,
      // Radius from log mention count: 40k-mention entities read bigger without drowning 100-mention ones
      size: 5 + Math.log10(Math.max(item.mention_count || 1, 1)) * 2.2,
      layer: 'baseline' as const,
    }));

  const hasOverlay = !!overlay && overlay.data.length > 0;

  // Overlay points are only drawn for entities present in the baseline set —
  // this keeps the chart a comparison. A baseline entity with NO overlay point
  // is itself a finding (that sphere is silent on it), noted in the tooltip.
  const globalByName = new Map(filteredData.map((d) => [d.entity, d]));
  const overlayData: SentimentDataPoint[] = hasOverlay
    ? overlay!.data
        .filter((d) => globalByName.has(d.entity))
        .map((d) => ({
          ...d,
          size: 5 + Math.log10(Math.max(d.mention_count || 1, 1)) * 2.2,
          layer: 'overlay' as const,
        }))
    : [];
  const overlayByName = new Map(overlayData.map((d) => [d.entity, d]));

  const maxJsd = Math.max(0.001, ...Object.values(contested));

  // Check if we have enough data for a meaningful scatter plot
  const hasEnoughData = filteredData.length >= 5; // Minimum number of entities needed for comparison

  // Only the most-mentioned points get static labels; the rest are tooltip-only.
  // 40 overlapping name labels is noise, not information.
  const labeledEntities = new Set(
    [...filteredData]
      .sort((a, b) => (b.mention_count || 0) - (a.mention_count || 0))
      .slice(0, 10)
      .map((d) => d.entity)
  );

  const handleTypeChange = (event: SelectChangeEvent<string[]>) => {
    const value = event.target.value;
    setSelectedTypes(typeof value === 'string' ? value.split(',') : value);
  };

  // Define quadrant labels
  const quadrantLabels = [
    { x: 1, y: 1, text: 'HERO', color: tokens.hero },
    { x: -1, y: 1, text: 'VICTIM', color: tokens.victim },
    { x: 1, y: -1, text: 'VILLAIN', color: tokens.villain },
    { x: -1, y: -1, text: 'WRETCH', color: tokens.nuisance }
  ];

  // Dashed connectors between each entity's global anchor and its country
  // reading. Drawn through Customized because recharts has no native way to
  // link points across two Scatter series; the axis scales come from chart
  // internals.
  const renderPairLinks = (props: any) => {
    const xScale = (Object.values(props.xAxisMap ?? {})[0] as any)?.scale;
    const yScale = (Object.values(props.yAxisMap ?? {})[0] as any)?.scale;
    if (!xScale || !yScale || overlayData.length === 0) return <g />;
    return (
      <g>
        {overlayData.map((c) => {
          const g = globalByName.get(c.entity);
          if (!g) return null;
          return (
            <line
              key={c.entity}
              x1={xScale(g.power_score)}
              y1={yScale(g.moral_score)}
              x2={xScale(c.power_score)}
              y2={yScale(c.moral_score)}
              stroke={tokens.inkMuted}
              strokeWidth={1.25}
              strokeDasharray="2 2"
              opacity={0.7}
            />
          );
        })}
      </g>
    );
  };

  return (
    <Box sx={{ width: '100%', height: height, padding: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        {entityTypes && (
          <FormControl sx={{ minWidth: 200 }}>
            <InputLabel id="entity-type-select-label">Entity Types</InputLabel>
            <Select
              labelId="entity-type-select-label"
              id="entity-type-select"
              multiple
              value={selectedTypes}
              onChange={handleTypeChange}
              renderValue={(selected) => (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {selected.map((value) => (
                    <Chip key={value} label={value} />
                  ))}
                </Box>
              )}
            >
              {entityTypes && Object.keys(entityTypes).map(type => (
                <MenuItem key={type} value={type}>
                  {type}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}
      </Box>

      {!hasEnoughData && (
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
          height: '80%',
          bgcolor: 'rgba(0,0,0,0.03)',
          borderRadius: 1,
          p: 3
        }}>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>
            Not enough entities available for meaningful sentiment comparison
          </Typography>
          <Typography variant="body2" color="text.secondary">
            At least 5 entities are needed to display a useful sentiment scatter plot
          </Typography>
          <Alert severity="info" sx={{ mt: 3, width: '80%' }}>
            Try selecting different entity types or wait for more data to be collected
          </Alert>
        </Box>
      )}

      {hasEnoughData && (
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart
            margin={{ top: 20, right: 30, bottom: 30, left: 30 }}
          >
          <CartesianGrid strokeDasharray="3 3" stroke={tokens.border} />
          {/* The quadrants only mean something relative to neutral - draw the cross. */}
          <ReferenceLine x={0} stroke={tokens.inkMuted} />
          <ReferenceLine y={0} stroke={tokens.inkMuted} />
          <XAxis
            type="number"
            dataKey="power_score"
            domain={[-2, 2]}
            tickCount={9}
            name="Power"
            tick={{ fill: tokens.inkMuted, fontSize: 11, fontFamily: 'monospace' }}
          >
            <Label value="Power Dimension" position="bottom" offset={10} style={{ fill: tokens.inkMuted, fontSize: 12 }} />
          </XAxis>
          <YAxis
            type="number"
            dataKey="moral_score"
            domain={[-2, 2]}
            tickCount={9}
            name="Morality"
            tick={{ fill: tokens.inkMuted, fontSize: 11, fontFamily: 'monospace' }}
          >
            <Label value="Moral Dimension" position="left" angle={-90} offset={10} style={{ fill: tokens.inkMuted, fontSize: 12 }} />
          </YAxis>
          <Tooltip
            cursor={{ strokeDasharray: '3 3' }}
            content={({ active, payload }) => {
              // Scatter tooltips get no category label, so the old labelFormatter
              // never had a name to show - read it off the point payload instead.
              const p = payload?.[0]?.payload as SentimentDataPoint | undefined;
              if (!active || !p || !p.entity) return null;
              const jsd = contested[p.entity];
              const counterpart =
                p.layer === 'baseline' ? overlayByName.get(p.entity) : globalByName.get(p.entity);
              return (
                <Box sx={{ bgcolor: tokens.surface, border: `1px solid ${tokens.border}`, borderRadius: 1, px: 1.5, py: 1 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600, color: tokens.ink }}>
                    {p.entity}
                  </Typography>
                  <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted, fontFamily: 'monospace' }}>
                    {hasOverlay ? (p.layer === 'baseline' ? `${baselineLabel} · ` : `${overlay!.label} · `) : ''}
                    Power {p.power_score.toFixed(2)} · Moral {p.moral_score.toFixed(2)}
                  </Typography>
                  {counterpart && (
                    <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted, fontFamily: 'monospace' }}>
                      {p.layer === 'baseline' ? `${overlay!.label} · ` : `${baselineLabel} · `}
                      Power {counterpart.power_score.toFixed(2)} · Moral {counterpart.moral_score.toFixed(2)}
                    </Typography>
                  )}
                  {hasOverlay && p.layer === 'baseline' && !counterpart && (
                    <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted }}>
                      Not among {overlay!.label}'s most-covered entities
                    </Typography>
                  )}
                  {p.mention_count != null && (
                    <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted }}>
                      {p.mention_count.toLocaleString()} mentions
                    </Typography>
                  )}
                  {jsd != null && (
                    <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted }}>
                      Cross-country disagreement: JSD {jsd.toFixed(2)}
                    </Typography>
                  )}
                </Box>
              );
            }}
          />

          {/* Render background quadrant labels */}
          {quadrantLabels.map((label, index) => (
            <Scatter
              key={`quadrant-${index}`}
              name=""
              data={[{ power_score: label.x, moral_score: label.y, size: 1, entity: '' }]}
              shape={(props: any) => (
                <text x={props.cx} y={props.cy} dy={5} textAnchor="middle" fill={label.color} style={{ fontWeight: 700, fontFamily: 'monospace', letterSpacing: '0.04em', opacity: 0.28 }}>
                  {label.text}
                </text>
              )}
              isAnimationActive={false}
              legendType="none"
            />
          ))}

          {hasOverlay && <Customized component={renderPairLinks} />}

          {/* Baseline layer: archetype-colored when it is the subject, receding
              to gray anchors when an overlay makes it the reference. */}
          <Scatter
            name="Entities"
            data={filteredData}
            fill={tokens.accent}
            isAnimationActive={!hasOverlay}
            shape={(props: any) => {
              const { cx, cy, payload } = props;
              const entityName = payload?.entity as string;
              const jsd = contested[entityName];
              const r = payload?.size ?? 9;
              return (
                <g>
                  {jsd != null && (
                    <circle
                      cx={cx}
                      cy={cy}
                      r={r + 3.5}
                      fill="none"
                      stroke={tokens.ink}
                      strokeWidth={1.25}
                      strokeDasharray="3 2"
                      opacity={0.25 + 0.6 * (jsd / maxJsd)}
                    />
                  )}
                  <circle
                    cx={cx}
                    cy={cy}
                    r={r}
                    fill={hasOverlay ? tokens.inkMuted : archetypeColor(payload.power_score, payload.moral_score)}
                    fillOpacity={hasOverlay ? 0.55 : 0.85}
                    stroke={tokens.surface}
                    strokeWidth={1.5}
                  />
                </g>
              );
            }}
          >
            {showLabels && (
              <LabelList
                dataKey="entity"
                position="top"
                offset={10}
                style={{ fontSize: '10px', fill: tokens.ink }}
                formatter={(name: string) => (labeledEntities.has(name) ? name : '')}
              />
            )}
          </Scatter>

          {/* Overlay layer: the selected sphere's reading, archetype-colored. */}
          {hasOverlay && (
            <Scatter
              name={overlay!.label}
              data={overlayData}
              isAnimationActive={false}
              shape={(props: any) => {
                const { cx, cy, payload } = props;
                return (
                  <circle
                    cx={cx}
                    cy={cy}
                    r={payload?.size ?? 9}
                    fill={archetypeColor(payload.power_score, payload.moral_score)}
                    fillOpacity={0.9}
                    stroke={tokens.surface}
                    strokeWidth={1.5}
                  />
                );
              }}
            />
          )}
        </ScatterChart>
      </ResponsiveContainer>
      )}
    </Box>
  );
};

export default SentimentChart;
