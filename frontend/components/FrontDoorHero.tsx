import React from 'react';
import { Box, Typography, Grid } from '@mui/material';
import { tokens, monoNumber } from '../theme';

interface FrontDoorHeroProps {
  entityCount: number;
  sourceCount: number;
  countryCount: number;
}

const ARCHETYPES = [
  { label: 'Hero', desc: 'high power, high moral standing', color: tokens.hero },
  { label: 'Victim', desc: 'low power, high moral standing', color: tokens.victim },
  { label: 'Villain', desc: 'high power, low moral standing', color: tokens.villain },
  { label: 'Wretch', desc: 'low power, low moral standing', color: tokens.nuisance },
];

const Stat: React.FC<{ value: number; label: string }> = ({ value, label }) => (
  <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 0.75 }}>
    <Typography sx={{ ...monoNumber, fontSize: '1.125rem', fontWeight: 600, color: tokens.ink }}>
      {value.toLocaleString()}
    </Typography>
    <Typography variant="caption" sx={{ color: tokens.inkMuted, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
      {label}
    </Typography>
  </Box>
);

const FrontDoorHero: React.FC<FrontDoorHeroProps> = ({ entityCount, sourceCount, countryCount }) => (
  <Box
    component="section"
    sx={{
      mb: 4,
      pb: 4,
      borderBottom: `1px solid ${tokens.border}`,
      animation: 'hero-rise 480ms cubic-bezier(0.22, 1, 0.36, 1)',
      '@keyframes hero-rise': {
        from: { opacity: 0, transform: 'translateY(8px)' },
        to: { opacity: 1, transform: 'translateY(0)' },
      },
      '@media (prefers-reduced-motion: reduce)': {
        animation: 'none',
      },
    }}
  >
    <Grid container spacing={5}>
      <Grid item xs={12} md={7}>
        <Typography
          component="h2"
          sx={{
            fontFamily: '"Newsreader", Georgia, serif',
            fontWeight: 500,
            fontStyle: 'italic',
            fontSize: 'clamp(1.75rem, 2.4vw + 1rem, 2.75rem)',
            lineHeight: 1.15,
            letterSpacing: '-0.01em',
            textWrap: 'balance',
            mb: 2,
          } as any}
        >
          Every News Source Constructs the Same World Differently.
        </Typography>
        <Typography sx={{ color: tokens.inkMuted, maxWidth: '62ch', textWrap: 'pretty', mb: 3 } as any}>
          Read how sources and countries portray the same people, states, and organizations,
          and how their opinions change.
        </Typography>

        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
          <Stat value={entityCount} label="entities tracked" />
          <Stat value={sourceCount} label="sources" />
          <Stat value={countryCount} label="countries" />
        </Box>
      </Grid>

      <Grid item xs={12} md={5}>
        <Typography variant="caption" sx={{ color: tokens.inkMuted, textTransform: 'uppercase', letterSpacing: '0.04em', display: 'block', mb: 1.5 }}>
          How to read the quadrant
        </Typography>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.25 }}>
          {ARCHETYPES.map((a) => (
            <Box key={a.label} sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
              <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: a.color, flexShrink: 0 }} />
              <Typography variant="body2">
                <Box component="span" sx={{ fontWeight: 600 }}>{a.label}</Box>
                <Box component="span" sx={{ color: tokens.inkMuted }}> — {a.desc}</Box>
              </Typography>
            </Box>
          ))}
        </Box>
        <Typography variant="caption" sx={{ display: 'block', mt: 2, color: tokens.inkMuted }}>
          Power: how much control or agency a portrayal grants an entity. Moral: how favorably
          it's framed. Every entity below is plotted by both, per source.
        </Typography>
      </Grid>
    </Grid>
  </Box>
);

export default FrontDoorHero;
