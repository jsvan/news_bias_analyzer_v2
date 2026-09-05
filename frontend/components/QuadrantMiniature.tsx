import React, { useEffect, useMemo, useState } from 'react';
import { Box, Skeleton, Typography } from '@mui/material';
import { statsApi } from '../services/api';
import { tokens, archetypeColor, fontSans } from '../theme';
import { EntitySentimentSummary } from '../types';

// A live miniature of the power/moral quadrant: the most-mentioned entities,
// placed by the world press's average reading. Illustration, not instrument —
// no zoom, no picker; the real chart lives on the Entities page. At hero scale
// (limit≈100, labelTop>0) it plays the role of the front page's photograph.
//
// Default view centers the crossing on the PRESS AVERAGE, not on zero: the
// press's mean reading is well off neutral (news skews negative), so a
// zero-centered cross casts most of the world as villains. "Relative" asks the
// honest question — who does the press treat better or worse than it treats
// everyone — while the Raw toggle keeps the absolute scale inspectable.

interface QuadrantMiniatureProps {
  limit?: number;
  // Label this many of the biggest dots (skipping ones whose label would
  // collide with an already-placed label). 0 = no labels.
  labelTop?: number;
  // Extra caption line under the figure — the wire-photo credit.
  credit?: React.ReactNode;
  maxWidth?: number;
}

const W = 380;
const H = 330;
const LEFT = 10;
const RIGHT = W - 10;
const TOP = 22;
const BOTTOM = H - 24;
const CX = (LEFT + RIGHT) / 2;
const CY = (TOP + BOTTOM) / 2;

const clamp = (v: number) => Math.max(-2, Math.min(2, v));
const sx = (power: number) => CX + (clamp(power) / 2) * (RIGHT - LEFT - 20) / 2;
const sy = (moral: number) => CY - (clamp(moral) / 2) * (BOTTOM - TOP - 20) / 2;

const axisWord = { fontFamily: fontSans, fontSize: 10, letterSpacing: '0.08em', fill: tokens.inkMuted };
const cornerWord = { fontFamily: fontSans, fontSize: 10.5, fontWeight: 600, letterSpacing: '0.08em' };
// tokens.nuisance (#B06A0E) is 3.9:1 on surface — fine for dots, below the 4.5:1
// AA floor for small text. Same amber, darkened to 5.2:1, for the corner label only.
const wretchText = '#96590A';

const QuadrantMiniature: React.FC<QuadrantMiniatureProps> = ({
  limit = 60,
  labelTop = 0,
  credit,
  maxWidth = 400,
}) => {
  const [data, setData] = useState<EntitySentimentSummary[] | null>(null);
  const [mode, setMode] = useState<'relative' | 'raw'>('relative');

  useEffect(() => {
    let cancelled = false;
    statsApi
      .getTrendingEntities(limit)
      .then((d: EntitySentimentSummary[]) => {
        if (!cancelled) setData(d);
      })
      .catch(() => {
        // The empty frame still teaches the quadrant; dots are a bonus.
        if (!cancelled) setData([]);
      });
    return () => {
      cancelled = true;
    };
  }, [limit]);

  // Mention-weighted press average — where the crossing sits in relative mode.
  const avg = useMemo(() => {
    if (!data?.length) return { power: 0, moral: 0 };
    let n = 0;
    let p = 0;
    let m = 0;
    for (const e of data) {
      const w = e.mention_count ?? 1;
      n += w;
      p += e.power_score * w;
      m += e.moral_score * w;
    }
    return { power: p / n, moral: m / n };
  }, [data]);

  if (data === null) {
    return <Skeleton variant="rounded" sx={{ width: '100%', maxWidth }} height={300} />;
  }

  const relative = mode === 'relative';
  const cross = relative ? { x: sx(avg.power), y: sy(avg.moral) } : { x: CX, y: CY };
  // Quadrant membership (and so dot color) is judged against the crossing:
  // relative mode asks "better or worse than the press's average reading".
  const dotColor = (e: EntitySentimentSummary) =>
    relative
      ? archetypeColor(e.power_score - avg.power, e.moral_score - avg.moral)
      : archetypeColor(e.power_score, e.moral_score);

  // Greedy label placement, biggest entities first: skip any label that would
  // sit on top of one already placed. Deterministic and collision-free enough
  // for the handful of names a figure caption can carry.
  const labels: { x: number; y: number; name: string }[] = [];
  if (labelTop > 0) {
    for (const e of data) {
      if (labels.length >= labelTop) break;
      const x = sx(e.power_score);
      const y = sy(e.moral_score);
      if (labels.some((l) => Math.abs(l.y - y) < 13 && Math.abs(l.x - x) < 90)) continue;
      labels.push({ x, y, name: e.entity });
    }
  }

  return (
    <Box sx={{ maxWidth }}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: '100%', height: 'auto', display: 'block' }}
        role="img"
        aria-label={`The ${data.length} most-mentioned entities plotted by power and moral sentiment. Heroes sit top right, victims top left, villains bottom right, wretches bottom left.`}
      >
        <rect x={0.5} y={0.5} width={W - 1} height={H - 1} rx={10} fill={tokens.surface} stroke={tokens.border} />

        {/* The quadrants only mean something relative to a reference — the
            cross IS the chart, and where it sits is the raw/relative choice. */}
        <line x1={LEFT} x2={RIGHT} y1={cross.y} y2={cross.y} stroke={tokens.inkMuted} strokeOpacity={0.45} />
        <line x1={cross.x} x2={cross.x} y1={TOP} y2={BOTTOM} stroke={tokens.inkMuted} strokeOpacity={0.45} />
        {relative && (
          <text
            x={cross.x + 5}
            y={cross.y - 5}
            style={{
              fontFamily: fontSans,
              fontSize: 8.5,
              letterSpacing: '0.06em',
              fill: tokens.inkMuted,
              paintOrder: 'stroke',
              stroke: tokens.surface,
              strokeWidth: 3,
              strokeLinejoin: 'round',
            } as React.CSSProperties}
          >
            PRESS AVERAGE
          </text>
        )}

        {/* Sorted by mentions descending, so big dots draw first and small ones stay on top. */}
        {data.map((e) => (
          <circle
            key={e.id ?? e.entity}
            cx={sx(e.power_score)}
            cy={sy(e.moral_score)}
            r={Math.min(7, 2.2 + Math.sqrt(e.mention_count ?? 1) * 0.055)}
            fill={dotColor(e)}
            fillOpacity={0.55}
            stroke={dotColor(e)}
            strokeOpacity={0.9}
            strokeWidth={0.75}
          >
            <title>{`${e.entity} — power ${e.power_score.toFixed(1)}, moral ${e.moral_score.toFixed(1)}`}</title>
          </circle>
        ))}

        {/* Halo stroke keeps names legible over the dot field. */}
        {labels.map((l) => (
          <text
            key={l.name}
            x={l.x > W - 96 ? l.x - 9 : l.x + 9}
            y={l.y + 3.5}
            textAnchor={l.x > W - 96 ? 'end' : 'start'}
            style={{
              fontFamily: fontSans,
              fontSize: 10,
              fontWeight: 500,
              fill: tokens.ink,
              paintOrder: 'stroke',
              stroke: tokens.surface,
              strokeWidth: 3,
              strokeLinejoin: 'round',
            } as React.CSSProperties}
          >
            {l.name}
          </text>
        ))}

        <text x={CX} y={15} textAnchor="middle" style={axisWord}>MORAL</text>
        <text x={CX} y={H - 9} textAnchor="middle" style={axisWord}>IMMORAL</text>
        <text x={16} y={cross.y - 6} textAnchor="start" style={axisWord}>WEAK</text>
        <text x={W - 16} y={cross.y - 6} textAnchor="end" style={axisWord}>POWERFUL</text>

        <text x={16} y={42} textAnchor="start" style={{ ...cornerWord, fill: tokens.victim }}>VICTIM</text>
        <text x={W - 16} y={42} textAnchor="end" style={{ ...cornerWord, fill: tokens.hero }}>HERO</text>
        <text x={16} y={BOTTOM - 12} textAnchor="start" style={{ ...cornerWord, fill: wretchText }}>WRETCH</text>
        <text x={W - 16} y={BOTTOM - 12} textAnchor="end" style={{ ...cornerWord, fill: tokens.villain }}>VILLAIN</text>
      </svg>
      <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, mt: 1, flexWrap: 'wrap' }}>
        <Typography variant="caption" sx={{ color: tokens.inkMuted, maxWidth: '46ch' }}>
          {data.length > 0
            ? relative
              ? `The ${data.length} most-mentioned entities, colored by their casting relative to the press's average reading. Bigger dots get more coverage.`
              : `The ${data.length} most-mentioned entities on the absolute scale — the press average sits at power ${avg.power.toFixed(2)}, moral ${avg.moral.toFixed(2)}, not at zero.`
            : 'How the two axes lay out the four castings.'}
        </Typography>
        {data.length > 0 && (
          <Box component="span" sx={{ ml: 'auto', whiteSpace: 'nowrap' }}>
            {(['relative', 'raw'] as const).map((m) => (
              <Box
                key={m}
                component="button"
                onClick={() => setMode(m)}
                sx={{
                  border: 'none',
                  background: 'none',
                  cursor: 'pointer',
                  p: 0,
                  ml: 1.25,
                  fontFamily: fontSans,
                  fontSize: '0.72rem',
                  color: mode === m ? tokens.ink : tokens.inkMuted,
                  fontWeight: mode === m ? 600 : 400,
                  borderBottom: `1px solid ${mode === m ? tokens.ink : 'transparent'}`,
                }}
              >
                {m === 'relative' ? 'Relative' : 'Raw'}
              </Box>
            ))}
          </Box>
        )}
      </Box>
      {credit && (
        <Typography variant="caption" sx={{ display: 'block', mt: 0.5, color: tokens.inkMuted }}>
          {credit}
        </Typography>
      )}
    </Box>
  );
};

export default QuadrantMiniature;
