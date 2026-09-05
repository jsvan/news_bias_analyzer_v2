import React, { useEffect, useMemo, useState } from 'react';
import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  ReferenceLine,
  Customized
} from 'recharts';
import { Box, Typography, Chip, FormControl, InputLabel, Select, MenuItem, SelectChangeEvent, Alert } from '@mui/material';
import { EntitySentimentSummary } from '../types';
import { tokens, archetypeColor } from '../theme';
import EntityInfoPlate, { ActiveEntityInfo } from './EntityInfoPlate';

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
  // What `data` represents in readings: 'Global' unless the baseline is itself
  // a country (the newspaper-vs-its-country comparison).
  baselineLabel?: string;
  // entity name -> cross-country Jensen-Shannon divergence, surfaced in the
  // info plate: a mean near neutral can be genuine consensus or a fought-over
  // average, and without this number the two are indistinguishable.
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
  // The hovered/pinned entity's full reading, for a page-sited EntityInfoPlate
  // (static box above the plot instead of a popup chasing the cursor). When
  // omitted, the chart renders its own plate right-aligned above the plot.
  onActiveChange?: (info: ActiveEntityInfo | null) => void;
}

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
  onEntityClick,
  onActiveChange
}) => {
  const [selectedTypes, setSelectedTypes] = useState<string[]>(
    entityTypes ? Object.keys(entityTypes) : []
  );
  // Hover raises a point (and its drift partner) above the crowd and fills the
  // info plate; a click pins that state until a click anywhere dismisses it.
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
  // constantly, and fresh array identities would replay scatter animations and
  // re-run the label placement every mouse move.
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
  // is itself a finding (that sphere is silent on it), noted in the info plate.
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

  // Check if we have enough data for a meaningful scatter plot. Unmatched
  // overlay points count — with an inverted orientation the subject set can be
  // full while the baseline is still loading or sparse.
  const hasEnoughData = filteredData.length + unmatchedOverlay.length >= 5;

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

  // Thin readings recede: under five scored mentions a mean is an anecdote,
  // so the dot renders at half its layer's opacity (it stays clickable — the
  // receipts are how a reader checks an anecdote).
  const thinFactor = (p: SentimentDataPoint) =>
    p.mention_count != null && p.mention_count < 5 ? 0.5 : 1;

  const raiseHandlers = (entityName: string) => ({
    onMouseEnter: () => setHoverEntity(entityName),
    // Functional clear: with overlapping dots, enter-B can fire before
    // leave-A — the guard keeps a late leave from wiping the new hover.
    onMouseLeave: () => setHoverEntity((h) => (h === entityName ? null : h)),
  });

  // What the plate shows: the hovered dot while the mouse is on one, else the
  // pinned dot. Hovering while pinned previews the other entity and reverts on
  // mouse-out, so pinning never blocks exploration.
  const activeName = hoverEntity ?? pinnedEntity;
  const activeInfo = useMemo<ActiveEntityInfo | null>(() => {
    if (!activeName) return null;
    const base = globalByName.get(activeName);
    const over = overlayByName.get(activeName);
    if (!base && !over) return null;
    return {
      entity: activeName,
      baseline: base,
      overlay: over,
      baselineLabel,
      overlayLabel: hasOverlay ? overlay!.label : undefined,
      jsd: contested[activeName],
      pinned: pinnedEntity === activeName,
    };
  }, [activeName, globalByName, overlayByName, baselineLabel, hasOverlay, overlay, contested, pinnedEntity]);

  useEffect(() => {
    onActiveChange?.(activeInfo);
  }, [activeInfo, onActiveChange]);

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

  // Collision-free name labels, replacing recharts' LabelList: walk the points
  // by prominence (mention count) and keep a label only when its estimated
  // pixel box clears every box already kept. Dense regions self-thin to their
  // most-mentioned entity while sparse regions keep their names — and no two
  // labels ever sit on each other. Needs pixel coords, hence a Customized
  // layer instead of per-point labels.
  const renderPointLabels = (props: any) => {
    const xScale = (Object.values(props.xAxisMap ?? {})[0] as any)?.scale;
    const yScale = (Object.values(props.yAxisMap ?? {})[0] as any)?.scale;
    if (!xScale || !yScale || !showLabels) return <g />;
    const candidates = [...filteredData, ...unmatchedOverlay].sort(
      (a, b) => (b.mention_count || 0) - (a.mention_count || 0)
    );
    const kept: { x1: number; y1: number; x2: number; y2: number; x: number; y: number; name: string }[] = [];
    for (const d of candidates) {
      const cx = xScale(d.power_score);
      const cy = yScale(d.moral_score);
      // ~5.8px per character at font-size 10 — an estimate, padded below.
      const w = d.entity.length * 5.8;
      const x1 = cx - w / 2;
      const x2 = cx + w / 2;
      const y2 = cy - d.size - 4; // text baseline sits above the dot
      const y1 = y2 - 12;
      if (kept.some((k) => x1 < k.x2 + 6 && x2 > k.x1 - 6 && y1 < k.y2 + 3 && y2 > k.y1 - 3)) {
        continue;
      }
      kept.push({ x1, y1, x2, y2, x: cx, y: y2, name: d.entity });
    }
    return (
      <g style={{ pointerEvents: 'none' }}>
        {kept.map((k) => (
          <text key={k.name} x={k.x} y={k.y} textAnchor="middle" style={{ fontSize: 10, fill: tokens.ink }}>
            {k.name}
          </text>
        ))}
      </g>
    );
  };

  // Axis words on the central cross (the QuadrantMiniature idiom): the scales
  // only mean something relative to the crossing, so the words live there
  // instead of on detached edge captions.
  const renderAxisWords = (props: any) => {
    const xScale = (Object.values(props.xAxisMap ?? {})[0] as any)?.scale;
    const yScale = (Object.values(props.yAxisMap ?? {})[0] as any)?.scale;
    if (!xScale || !yScale) return <g />;
    const word = {
      fontSize: 10,
      letterSpacing: '0.08em',
      fill: tokens.inkMuted,
      paintOrder: 'stroke',
      stroke: tokens.surface,
      strokeWidth: 3,
      strokeLinejoin: 'round',
    } as React.CSSProperties;
    return (
      <g style={{ pointerEvents: 'none' }}>
        <text x={xScale(-2) + 4} y={yScale(0) - 5} textAnchor="start" style={word}>WEAK</text>
        <text x={xScale(2) - 4} y={yScale(0) - 5} textAnchor="end" style={word}>POWERFUL</text>
        <text x={xScale(0) + 5} y={yScale(2) + 10} textAnchor="start" style={word}>MORAL</text>
        <text x={xScale(0) + 5} y={yScale(-2) - 4} textAnchor="start" style={word}>IMMORAL</text>
      </g>
    );
  };

  // Hover/pin raise layer. SVG stacks by paint order, so the only way to lift
  // a pair above its neighbors is to redraw it in a layer painted after both
  // scatters. pointer-events stays off for the whole layer: the copies sit
  // exactly on the real dots and must never steal their mouse events.
  const renderActiveLayer = (props: any) => {
    const xScale = (Object.values(props.xAxisMap ?? {})[0] as any)?.scale;
    const yScale = (Object.values(props.yAxisMap ?? {})[0] as any)?.scale;
    if (!xScale || !yScale) return <g />;
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
            </g>
          );
        })}
      </g>
    );
  };

  return (
    <Box sx={{ width: '100%', height: height, padding: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 2 }}>
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
        {/* Pages that wire onActiveChange render the plate in their own layout;
            unwired uses still get one, right-aligned above the plot. */}
        {!onActiveChange && <EntityInfoPlate info={activeInfo} sx={{ ml: 'auto', mb: 1 }} />}
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
          {/* Numeric ticks stay on the edges for scale-reading; the axis WORDS
              live on the central cross (renderAxisWords) where they mean
              something. */}
          <XAxis
            type="number"
            dataKey="power_score"
            domain={[-2, 2]}
            tickCount={9}
            name="Power"
            tick={{ fill: tokens.inkMuted, fontSize: 11, fontFamily: 'monospace' }}
          />
          <YAxis
            type="number"
            dataKey="moral_score"
            domain={[-2, 2]}
            tickCount={9}
            name="Morality"
            tick={{ fill: tokens.inkMuted, fontSize: 11, fontFamily: 'monospace' }}
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

          <Customized component={renderAxisWords} />
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
                  <circle
                    cx={cx}
                    cy={cy}
                    r={r}
                    fill={hasOverlay ? tokens.inkMuted : archetypeColor(payload.power_score, payload.moral_score)}
                    fillOpacity={(hasOverlay ? 0.55 : 0.85) * thinFactor(payload)}
                    stroke={tokens.surface}
                    strokeWidth={1.5}
                  />
                </g>
              );
            }}
          />

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
                      fillOpacity={0.9 * thinFactor(payload)}
                      stroke={tokens.surface}
                      strokeWidth={1.5}
                    />
                  </g>
                );
              }}
            />
          )}

          <Customized component={renderPointLabels} />
          <Customized component={renderActiveLayer} />
        </ScatterChart>
      </ResponsiveContainer>
      )}
    </Box>
  );
};

export default SentimentChart;
