import React from 'react';
import { Box, Typography } from '@mui/material';
import { EntitySentimentSummary } from '../types';
import { tokens, archetypeColor, archetypeLabel } from '../theme';

// What the sentiment scatter currently holds under the cursor (or pinned by a
// click), pushed up through SentimentChart's onActiveChange so each page can
// site the plate in its own layout — next to the pickers, right-aligned with
// the plot — instead of a popup chasing the mouse.
export interface ActiveEntityInfo {
  entity: string;
  baseline?: EntitySentimentSummary;
  overlay?: EntitySentimentSummary;
  baselineLabel: string;
  // Present only when the chart is drawing an overlay comparison.
  overlayLabel?: string;
  jsd?: number;
  pinned: boolean;
}

const line = (label: string | null, p: EntitySentimentSummary) =>
  `${label ? `${label} · ` : ''}Power ${p.power_score.toFixed(2)} · Moral ${p.moral_score.toFixed(2)}`;

// Fixed-footprint reading plate: same box whether empty, hovered, or pinned,
// so the layout never jumps while the mouse sweeps the scatter.
const EntityInfoPlate: React.FC<{ info: ActiveEntityInfo | null; sx?: object }> = ({ info, sx }) => {
  const subject = info ? info.overlay ?? info.baseline : undefined;
  return (
    <Box
      sx={{
        width: 300,
        minHeight: 118,
        bgcolor: tokens.surface,
        border: `1px solid ${tokens.border}`,
        borderRadius: 1,
        px: 1.5,
        py: 1,
        ...sx,
      }}
    >
      {!info || !subject ? (
        <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
          Hover a dot to read it here — click to pin, click anywhere to release.
        </Typography>
      ) : (
        <>
          <Typography variant="body2" sx={{ fontWeight: 600, color: tokens.ink }}>
            {info.entity}
          </Typography>
          {info.baseline && (
            <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted, fontFamily: 'monospace' }}>
              {line(info.overlayLabel ? info.baselineLabel : null, info.baseline)}
            </Typography>
          )}
          {info.overlay && info.overlayLabel && (
            <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted, fontFamily: 'monospace' }}>
              {line(info.overlayLabel, info.overlay)}
            </Typography>
          )}
          {info.baseline && info.overlay && (() => {
            const dp = info.overlay.power_score - info.baseline.power_score;
            const dm = info.overlay.moral_score - info.baseline.moral_score;
            return (
              <Typography variant="caption" sx={{ display: 'block', fontFamily: 'monospace', fontWeight: 600, color: archetypeColor(dp, dm) }}>
                More {archetypeLabel(dp, dm)} · Power {dp >= 0 ? '+' : ''}{dp.toFixed(2)} · Moral {dm >= 0 ? '+' : ''}{dm.toFixed(2)}
              </Typography>
            );
          })()}
          {info.overlayLabel && !info.overlay && (
            <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted }}>
              {info.overlayLabel} has too few scored mentions of this entity to read (fewer than 3)
            </Typography>
          )}
          {info.overlayLabel && info.overlay && !info.baseline && (
            <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted }}>
              No {info.baselineLabel} reading to compare (too few scored mentions there)
            </Typography>
          )}
          {subject.mention_count != null && (
            <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted }}>
              {subject.mention_count.toLocaleString()} mentions
            </Typography>
          )}
          {info.jsd != null && (
            <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted }}>
              Cross-country disagreement: JSD {info.jsd.toFixed(2)}
            </Typography>
          )}
          {info.pinned && (
            <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted, fontStyle: 'italic' }}>
              Pinned — click anywhere to release
            </Typography>
          )}
        </>
      )}
    </Box>
  );
};

export default EntityInfoPlate;
