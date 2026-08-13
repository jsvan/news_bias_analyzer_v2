import React from 'react';
import { Box, Typography, Card, CardHeader, CardContent, Chip } from '@mui/material';
import { NewsSource } from '../types';
import { tokens, archetypeColor, monoNumber } from '../theme';

// One source held against the global baseline, entity by entity. Shared by
// My Bubble (the sources you read) and the source profile page (any source) —
// the same question either way: how far is this outlet's reading from the
// all-sources average, without calling either side correct.

export interface EntityComparison {
  name: string;
  type: string;
  sourcePower: number;
  sourceMoral: number;
  globalPower: number;
  globalMoral: number;
}

const GLYPH_SIZE = 56;

// Maps a -1..1 power/moral pair onto the glyph's pixel frame (y flipped: moral up = positive).
const toXY = (power: number, moral: number) => {
  const p = Math.max(-1, Math.min(1, power));
  const m = Math.max(-1, Math.min(1, moral));
  const pad = 8;
  const usable = (GLYPH_SIZE - pad * 2) / 2;
  return { x: GLYPH_SIZE / 2 + p * usable, y: GLYPH_SIZE / 2 - m * usable };
};

// Small power/moral scatter reused from the site's own quadrant metaphor: the filled
// dot (your source, archetype-colored) and the gray dot (global average) plus the
// connecting line make the divergence legible without implying either is "correct".
export const DivergenceGlyph: React.FC<{ sourcePower: number; sourceMoral: number; globalPower: number; globalMoral: number }> = ({
  sourcePower,
  sourceMoral,
  globalPower,
  globalMoral,
}) => {
  const s = toXY(sourcePower, sourceMoral);
  const g = toXY(globalPower, globalMoral);
  const mid = GLYPH_SIZE / 2;
  return (
    <svg width={GLYPH_SIZE} height={GLYPH_SIZE} viewBox={`0 0 ${GLYPH_SIZE} ${GLYPH_SIZE}`} style={{ flexShrink: 0 }}>
      <line x1={mid} y1={0} x2={mid} y2={GLYPH_SIZE} stroke={tokens.border} strokeWidth={1} />
      <line x1={0} y1={mid} x2={GLYPH_SIZE} y2={mid} stroke={tokens.border} strokeWidth={1} />
      <line x1={g.x} y1={g.y} x2={s.x} y2={s.y} stroke={tokens.inkMuted} strokeWidth={1.25} strokeDasharray="2 2" />
      <circle cx={g.x} cy={g.y} r={3.5} fill={tokens.inkMuted} />
      <circle cx={s.x} cy={s.y} r={4} fill={archetypeColor(sourcePower, sourceMoral)} stroke={tokens.surface} strokeWidth={1} />
    </svg>
  );
};

const SourceComparisonCard: React.FC<{ source: NewsSource; rows: EntityComparison[] }> = ({ source, rows }) => (
  <Card>
    <CardHeader
      title={source.name}
      subheader={source.country && source.country !== 'Unknown' ? source.country : undefined}
    />
    <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
      {rows.length === 0 ? (
        <Box
          sx={{
            m: 2,
            p: 3,
            textAlign: 'center',
            bgcolor: tokens.surfaceSunken,
            borderRadius: 1,
            border: `1px dashed ${tokens.border}`,
          }}
        >
          <Typography variant="body2" sx={{ color: tokens.inkMuted }}>
            No divergence signal yet for {source.name} &mdash; check back once more coverage has been analyzed.
          </Typography>
        </Box>
      ) : (
        rows.map((row, idx) => {
          const delta = Math.hypot(row.sourcePower - row.globalPower, row.sourceMoral - row.globalMoral);
          return (
            <Box
              key={row.name}
              sx={{
                display: 'flex',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: 2,
                px: 2,
                py: 1.5,
                borderTop: idx === 0 ? 'none' : `1px solid ${tokens.border}`,
                '&:hover': { bgcolor: tokens.surfaceSunken },
              }}
            >
              <DivergenceGlyph
                sourcePower={row.sourcePower}
                sourceMoral={row.sourceMoral}
                globalPower={row.globalPower}
                globalMoral={row.globalMoral}
              />
              <Box sx={{ flex: 1, minWidth: 140 }}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {row.name}
                </Typography>
                <Chip
                  label={row.type}
                  size="small"
                  variant="outlined"
                  sx={{ mt: 0.5, borderColor: tokens.border, color: tokens.inkMuted }}
                />
              </Box>
              <Box sx={{ textAlign: 'right', minWidth: 128 }}>
                <Typography variant="caption" sx={{ color: tokens.inkMuted, display: 'block' }}>
                  This source
                </Typography>
                <Typography sx={{ ...monoNumber, color: tokens.ink }}>
                  P {row.sourcePower.toFixed(2)} &middot; M {row.sourceMoral.toFixed(2)}
                </Typography>
              </Box>
              <Box sx={{ textAlign: 'right', minWidth: 128 }}>
                <Typography variant="caption" sx={{ color: tokens.inkMuted, display: 'block' }}>
                  Global average
                </Typography>
                <Typography sx={{ ...monoNumber, color: tokens.ink }}>
                  P {row.globalPower.toFixed(2)} &middot; M {row.globalMoral.toFixed(2)}
                </Typography>
              </Box>
              <Box sx={{ textAlign: 'right', minWidth: 64 }}>
                <Typography variant="caption" sx={{ color: tokens.inkMuted, display: 'block' }}>
                  Divergence
                </Typography>
                <Typography sx={{ ...monoNumber, fontWeight: 600, color: tokens.ink }}>{delta.toFixed(2)}</Typography>
              </Box>
            </Box>
          );
        })
      )}
    </CardContent>
  </Card>
);

export default SourceComparisonCard;
