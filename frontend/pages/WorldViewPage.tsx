import React from 'react';
import { Link } from 'react-router-dom';
import { Box, Typography } from '@mui/material';
import { useData } from '../context/DataContext';
import { tokens, monoNumber } from '../theme';

// No mapping library is installed and none should be added (see DESIGN.md) — a CSS grid of
// tiles stands in for a geographic map. Sentiment scores in the current snapshot are all
// zero (analysis pipeline hasn't populated them), so tiles are sized/ordered by the one real
// signal available — source count — rather than a fabricated divergence color scale. Same
// honest-degradation pattern as FrontDoorHero.
const WorldViewPage: React.FC = () => {
  const { sources, availableCountries, loading } = useData();

  const countryCounts = availableCountries
    .map((country) => ({ country, count: sources.filter((s) => s.country === country).length }))
    .sort((a, b) => b.count - a.count);

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        World View
      </Typography>
      <Typography sx={{ color: tokens.inkMuted, maxWidth: '70ch', mb: 3 }}>
        Every country this instrument tracks, by how many sources feed it. Click a tile to see
        that country's entity coverage.
      </Typography>

      {loading ? (
        <Typography sx={{ color: tokens.inkMuted }}>Loading...</Typography>
      ) : (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: 2,
          }}
        >
          {countryCounts.map(({ country, count }) => (
            <Box
              key={country}
              component={Link}
              to={`/countries?country=${encodeURIComponent(country)}`}
              sx={{
                display: 'block',
                textDecoration: 'none',
                p: 2,
                borderRadius: 1.25,
                bgcolor: tokens.surface,
                border: `1px solid ${tokens.border}`,
                transition: 'background-color 120ms ease',
                '&:hover': { bgcolor: tokens.surfaceSunken },
              }}
            >
              <Typography variant="subtitle2" sx={{ color: tokens.ink }}>
                {country}
              </Typography>
              <Typography sx={{ ...monoNumber, fontSize: '1.5rem', fontWeight: 600, color: tokens.ink, mt: 0.5 }}>
                {count}
              </Typography>
              <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
                {count === 1 ? 'source' : 'sources'}
              </Typography>
            </Box>
          ))}
        </Box>
      )}

      <Typography variant="caption" sx={{ display: 'block', mt: 3, color: tokens.inkMuted }}>
        Ordered by source count — the one real per-country signal in this snapshot. Coloring by
        divergence from the global baseline needs per-country sentiment scores the pipeline
        doesn't produce yet.
      </Typography>
    </Box>
  );
};

export default WorldViewPage;
