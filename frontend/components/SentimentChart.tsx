import React, { useEffect, useMemo, useState } from 'react';
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
import { tokens, archetypeColor, archetypeLabel } from '../theme';

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
  // to gray anchors and each overlay point is colored by the DIRECTION of its
  // drift from its anchor (more moral + more powerful than the baseline =
  // toward Hero, etc.) — the overlay answers "which way does this sphere
  // pull?", not "which quadrant did it land in".
  overlay?: { label: string; data: EntitySentimentSummary[] } | null;
  // What `data` represents in tooltips: 'Global' unless the baseline is itself
  // a country (the newspaper-vs-its-country comparison).
  baselineLabel?: string;
  // entity name -> cross-country Jensen-Shannon divergence. Entities whose
  // spheres disagree get a dashed ring: a mean near neutral can be genuine
  // consensus or a fought-over average, and without this channel the two are
  // indistinguishable.
  contested?: Record<string, number>;
  // By default the baseline defines the entity set and overlay points without a
  // baseline partner are dropped (the entity-page comparison). The source
  // profile page inverts that: the overlay (the paper's top entities) IS the
  // subject, so unmatched overlay points must still render — their missing
  // anchor is the finding (the baseline sphere is silent on them).
  includeUnmatchedOverlay?: boolean;
  // Page-level entity selection: the named entity gets a highlight ring, and
  // clicking any point reports it up. Both optional — the chart stays a plain
  // display when the page doesn't wire them. Independent of the chart's own
  // hover-raise and click-to-pin behavior, which need no wiring.
  selectedEntity?: string | null;
  onEntityClick?: (entity: EntitySentimentSummary) => void;
}

// Stable pseudo-random priority per entity name (FNV-1a). Label sampling must
// not re-roll on hover re-renders, so "random" here means hash-arbitrary: an
// unpredictable but repeatable pick, uncorrelated with mention counts.
const labelPriority = (name: string): number => {
  let h = 2166136261;
  for (let i = 0; i < name.length; i++) {
    h ^= name.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) / 4294967296;
};

const SentimentChart: React.FC<SentimentChartProps> = ({
  data,
  entityTypes,
  height = 400,
  showLabels = true,
  overlay = null,
  baselineLabel = 'Global',
  contested = {},
  includeUnmatchedOverlay = false,
  selectedEntity = null,
  onEntityClick
}) => {
  const [selectedTypes, setSelectedTypes] = useState<string[]>(
    entityTypes ? Object.keys(entityTypes) : []
  );
  // Hover raises a point (and its drift partner) above the crowd; a click pins
  // that raised state plus an info card until a click anywhere dismisses it.
  const [hoverEntity, setHoverEntity] = useState<string | null>(null);
  const [pinnedEntity, setPinnedEntity] = useState<string | null>(null);

  // "Click anywhere dismisses": dot clicks stopPropagation before this fires,
  // so they re-pin instead of dismissing.
  useEffect(() => {
    if (!pinnedEntity) return;
    const dismiss = () => setPinnedEntity(null);
    document.addEventListener('click', dismiss);
    return () => document.removeEventListener('click', dismiss);
  }, [pinnedEntity]);

  // Derived collections are memoized: hover state changes re-render the chart
  // constantly now, and fresh array identities would replay scatter animations
  // and re-run the label draw every mouse move.
  const filteredData: SentimentDataPoint[] = useMemo(
    () =>
      data
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
        })),
    [data, entityTypes, selectedTypes]
  );

  const hasOverlay = !!overlay && overlay.data.length > 0;

  // Overlay points are only drawn for entities present in the baseline set —
  // this keeps the chart a comparison. A baseline entity with NO overlay point
  // is itself a finding (that sphere is silent on it), noted in the tooltip.
  // includeUnmatchedOverlay inverts the orientation: the overlay is the subject
  // set, so its points render regardless of a baseline partner.
  const globalByName = useMemo(
    () => new Map(filteredData.map((d) => [d.entity, d])),
    [filteredData]
  );
  const overlayData: SentimentDataPoint[] = useMemo(
    () =>
      hasOverlay
        ? overlay!.data
            .filter((d) => includeUnmatchedOverlay || globalByName.has(d.entity))
            .map((d) => ({
              ...d,
              size: 5 + Math.log10(Math.max(d.mention_count || 1, 1)) * 2.2,
              layer: 'overlay' as const,
            }))
        : [],
    [hasOverlay, overlay, includeUnmatchedOverlay, globalByName]
  );
  const overlayByName = useMemo(
    () => new Map(overlayData.map((d) => [d.entity, d])),
    [overlayData]
  );
  const unmatchedOverlay = useMemo(
    () => overlayData.filter((d) => !globalByName.has(d.entity)),
    [overlayData, globalByName]
  );

  const maxJsd = Math.max(0.001, ...Object.values(contested));

  // Check if we have enough data for a meaningful scatter plot. Unmatched
  // overlay points count — with an inverted orientation the subject set can be
  // full while the baseline is still loading or sparse.
  const hasEnoughData = filteredData.length + unmatchedOverlay.length >= 5;

  // One label per 0.5×0.5 data-unit cell, pseudo-randomly chosen. Ranking by
  // mentions piled every label onto the dense center while outlying regions
  // went unnamed; per-cell sampling spreads the names across the plane.
  const labeledEntities = useMemo(() => {
    const bestPerCell = new Map<string, SentimentDataPoint>();
    for (const d of [...filteredData, ...unmatchedOverlay]) {
      const key = `${Math.floor(d.power_score / 0.5)}|${Math.floor(d.moral_score / 0.5)}`;
      const cur = bestPerCell.get(key);
      if (!cur || labelPriority(d.entity) > labelPriority(cur.entity)) {
        bestPerCell.set(key, d);
      }
    }
    return new Set([...bestPerCell.values()].map((d) => d.entity));
  }, [filteredData, unmatchedOverlay]);

  const handleTypeChange = (event: SelectChangeEvent<string[]>) => {
    const value = event.target.value;
    setSelectedTypes(typeof value === 'string' ? value.split(',') : value);
  };

  // Drift-direction fill for an overlay point: the deltas run through the same
  // sign logic as absolute positions, so up-right (more moral, more powerful
  // than the baseline) = hero green. A point with no anchor has no drift to
  // encode — neutral ink, so it can't borrow a direction it doesn't have.
  const overlayFill = (p: SentimentDataPoint): string => {
    const anchor = globalByName.get(p.entity);
    return anchor
      ? archetypeColor(p.power_score - anchor.power_score, p.moral_score - anchor.moral_score)
      : tokens.ink;
  };

  const handleDotClick = (e: React.MouseEvent, p: SentimentDataPoint) => {
    e.stopPropagation();
    setPinnedEntity((cur) => (cur === p.entity ? null : p.entity));
    onEntityClick?.(p);
  };

  const raiseHandlers = (entityName: string) => ({
    onMouseEnter: () => setHoverEntity(entityName),
    // Functional clear: with overlapping dots, enter-B can fire before
    // leave-A — the guard keeps a late leave from wiping the new hover.
    onMouseLeave: () => setHoverEntity((h) => (h === entityName ? null : h)),
  });

  // The full per-entity reading, shared verbatim between the hover tooltip and
  // the pinned card so pinning never changes what the reader sees.
  const entityCard = (p: SentimentDataPoint, pinned = false) => {
    const jsd = contested[p.entity];
    const counterpart =
      p.layer === 'baseline' ? overlayByName.get(p.entity) : globalByName.get(p.entity);
    return (
      <Box
        sx={{
          bgcolor: tokens.surface,
          border: `1px solid ${tokens.border}`,
          borderRadius: 1,
          px: 1.5,
          py: 1,
          ...(pinned ? { boxShadow: 3, display: 'inline-block', maxWidth: 260 } : {}),
        }}
      >
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
        {counterpart && (() => {
          // Drift is always overlay minus baseline, whichever layer is hovered —
          // this line names the direction the dot's color encodes.
          const o = p.layer === 'overlay' ? p : counterpart;
          const b = p.layer === 'overlay' ? counterpart : p;
          const dp = o.power_score - b.power_score;
          const dm = o.moral_score - b.moral_score;
          return (
            <Typography variant="caption" sx={{ display: 'block', fontFamily: 'monospace', fontWeight: 600, color: archetypeColor(dp, dm) }}>
              More {archetypeLabel(dp, dm)} · Power {dp >= 0 ? '+' : ''}{dp.toFixed(2)} · Moral {dm >= 0 ? '+' : ''}{dm.toFixed(2)}
            </Typography>
          );
        })()}
        {hasOverlay && p.layer === 'baseline' && !counterpart && (
          <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted }}>
            Not among {overlay!.label}'s most-covered entities
          </Typography>
        )}
        {hasOverlay && p.layer === 'overlay' && !counterpart && (
          <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted }}>
            No {baselineLabel} reading to compare (too few scored mentions there)
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

  // Hover/pin raise layer. SVG stacks by paint order, so the only way to lift
  // a pair above its neighbors is to redraw it in a layer painted after both
  // scatters. pointer-events stays off for the whole layer: the copies sit
  // exactly on the real dots and must never steal their mouse events — and a
  // click landing "on" the pinned card is still a click-anywhere dismissal.
  const renderActiveLayer = (props: any) => {
    const xScale = (Object.values(props.xAxisMap ?? {})[0] as any)?.scale;
    const yScale = (Object.values(props.yAxisMap ?? {})[0] as any)?.scale;
    if (!xScale || !yScale) return <g />;
    const plot = props.offset ?? { left: 40, top: 20, width: (props.width ?? 700) - 100, height: (props.height ?? 460) - 80 };
    const names = [pinnedEntity, hoverEntity].filter(
      (n, i, a): n is string => n != null && a.indexOf(n) === i
    );
    return (
      <g style={{ pointerEvents: 'none' }}>
        {names.map((name) => {
          const base = globalByName.get(name);
          const over = overlayByName.get(name);
          if (!base && !over) return null;
          const focal = over ?? base!;
          const fx = xScale(focal.power_score);
          const fy = yScale(focal.moral_score);
          return (
            <g key={name}>
              {base && over && (
                <line
                  x1={xScale(base.power_score)}
                  y1={yScale(base.moral_score)}
                  x2={fx}
                  y2={fy}
                  stroke={tokens.ink}
                  strokeWidth={1.5}
                  strokeDasharray="2 2"
                />
              )}
              {base && (
                <circle
                  cx={xScale(base.power_score)}
                  cy={yScale(base.moral_score)}
                  r={base.size}
                  fill={hasOverlay ? tokens.inkMuted : archetypeColor(base.power_score, base.moral_score)}
                  stroke={tokens.surface}
                  strokeWidth={1.5}
                />
              )}
              {over && (
                <circle cx={fx} cy={fy} r={over.size} fill={overlayFill(over)} stroke={tokens.surface} strokeWidth={1.5} />
              )}
              <text
                x={fx}
                y={fy - (focal.size + 7)}
                textAnchor="middle"
                style={{ fontSize: 11, fontWeight: 600, fill: tokens.ink, stroke: tokens.surface, strokeWidth: 3, paintOrder: 'stroke' }}
              >
                {name}
              </text>
              {pinnedEntity === name && (() => {
                // Anchor the pinned card beside the dot, flipping/clamping to
                // stay inside the plot area.
                const W = 260;
                const H = 170;
                const x = fx + 14 + W > plot.left + plot.width ? fx - 14 - W : fx + 14;
                const y = Math.max(plot.top, Math.min(fy - 24, plot.top + plot.height - H));
                return (
                  <foreignObject x={x} y={y} width={W} height={H} style={{ overflow: 'visible' }}>
                    {entityCard(focal, true)}
                  </foreignObject>
                );
              })()}
            </g>
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
              // The pinned card already shows this entity — a hover box on top
              // of it would just double the same reading.
              if (p.entity === pinnedEntity) return null;
              return entityCard(p);
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
                <g
                  onClick={entityName ? (e: React.MouseEvent) => handleDotClick(e, payload) : undefined}
                  {...(entityName ? raiseHandlers(entityName) : {})}
                  style={entityName ? { cursor: 'pointer' } : undefined}
                >
                  {selectedEntity != null && entityName === selectedEntity && (
                    <circle cx={cx} cy={cy} r={r + 5} fill="none" stroke={tokens.accent} strokeWidth={2} />
                  )}
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

          {/* Overlay layer: the selected sphere's reading, drift-colored. */}
          {hasOverlay && (
            <Scatter
              name={overlay!.label}
              data={overlayData}
              isAnimationActive={false}
              shape={(props: any) => {
                const { cx, cy, payload } = props;
                const entityName = payload?.entity as string;
                return (
                  <g
                    onClick={entityName ? (e: React.MouseEvent) => handleDotClick(e, payload) : undefined}
                    {...(entityName ? raiseHandlers(entityName) : {})}
                    style={entityName ? { cursor: 'pointer' } : undefined}
                  >
                    {selectedEntity != null && entityName === selectedEntity && (
                      <circle cx={cx} cy={cy} r={(payload?.size ?? 9) + 5} fill="none" stroke={tokens.accent} strokeWidth={2} />
                    )}
                    <circle
                      cx={cx}
                      cy={cy}
                      r={payload?.size ?? 9}
                      fill={overlayFill(payload)}
                      fillOpacity={0.9}
                      stroke={tokens.surface}
                      strokeWidth={1.5}
                    />
                  </g>
                );
              }}
            >
              {/* Unmatched overlay points have no baseline twin to carry their
                  label — label them here (matched ones stay labeled via the
                  baseline layer, so no doubles). */}
              {showLabels && includeUnmatchedOverlay && (
                <LabelList
                  dataKey="entity"
                  position="top"
                  offset={10}
                  style={{ fontSize: '10px', fill: tokens.ink }}
                  formatter={(name: string) =>
                    labeledEntities.has(name) && !globalByName.has(name) ? name : ''
                  }
                />
              )}
            </Scatter>
          )}

          <Customized component={renderActiveLayer} />
        </ScatterChart>
      </ResponsiveContainer>
      )}
    </Box>
  );
};

export default SentimentChart;
