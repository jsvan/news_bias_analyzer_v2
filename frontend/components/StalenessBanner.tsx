import React from 'react';
import { Alert, Typography } from '@mui/material';
import { tokens } from '../theme';
import { useData } from '../context/DataContext';

const STALE_THRESHOLD_HOURS = 48;

function formatAsOf(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric', month: 'long', day: 'numeric',
  });
}

// Renders nothing in live-API mode (meta is null there - see services/api.ts::metaApi) or
// while meta hasn't loaded yet. In static-snapshot mode, tells the user honestly whether
// the data they're looking at is current or stale, instead of silently showing zeroed
// recent-window numbers with no explanation (the bug this component exists to fix).
const StalenessBanner: React.FC = () => {
  const { meta } = useData();
  if (!meta) return null;

  const referenceDate = meta.most_recent_article_date ?? meta.generated_at;
  const hoursOld = (Date.now() - new Date(referenceDate).getTime()) / (1000 * 60 * 60);
  const asOf = formatAsOf(referenceDate);

  if (hoursOld > STALE_THRESHOLD_HOURS) {
    return (
      <Alert severity="warning" sx={{ mb: 3 }}>
        Data current through {asOf} — no newer articles have been collected since then.
        Recent-window figures (7/30/90 days) may show as empty even though older data is real.
      </Alert>
    );
  }

  // Scraping and analysis stall independently: during the Aug 27–Sep 2 2026
  // OpenAI batch outage articles kept arriving (so the check above stayed
  // quiet) while every sentiment reading flatlined for six days.
  const analysisDate = meta.most_recent_analysis_date;
  if (analysisDate) {
    const analysisHoursOld = (Date.now() - new Date(analysisDate).getTime()) / (1000 * 60 * 60);
    if (analysisHoursOld > STALE_THRESHOLD_HOURS) {
      return (
        <Alert severity="warning" sx={{ mb: 3 }}>
          Articles are still being collected, but sentiment analysis has been stalled
          since {formatAsOf(analysisDate)} — sentiment figures after that date are incomplete.
        </Alert>
      );
    }
  }

  return (
    <Typography variant="caption" sx={{ color: tokens.inkMuted, display: 'block', mb: 2 }}>
      Data current as of {asOf}
    </Typography>
  );
};

export default StalenessBanner;
