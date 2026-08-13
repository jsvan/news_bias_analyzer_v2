import React, { useEffect, useState } from 'react';
import { useParams, Link as RouterLink } from 'react-router-dom';
import { Box, Typography, Chip, CircularProgress } from '@mui/material';
import { useData } from '../context/DataContext';
import { statsApi } from '../services/api';
import SourceComparisonCard, { EntityComparison } from '../components/SourceComparisonCard';
import { CountryEntityData } from '../types';
import { tokens } from '../theme';

// All-time window: the corpus is a bounded snapshot, so a wall-clock lookback
// can be empty long before the data is. 0 = ALL_TIME sentinel (omitted by api.ts).
const DAYS = 0;

const SourceProfilePage: React.FC = () => {
  const { name } = useParams<{ name: string }>();
  const { entities, getSourceByName } = useData();
  const source = name ? getSourceByName(decodeURIComponent(name)) : undefined;

  const [rows, setRows] = useState<EntityComparison[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!source || entities.length === 0) return;
    let cancelled = false;
    setLoading(true);

    (async () => {
      try {
        const res = await statsApi.getNewspaperTopEntities(source.name, { days: DAYS, limit: 10 });
        const top: CountryEntityData[] = (res?.entities || []).filter(
          (e: CountryEntityData) => e.mention_count > 0
        );

        const idByName = new Map<string, number>();
        entities.forEach((e) => idByName.set(e.name.toLowerCase(), e.id));

        const built: EntityComparison[] = [];
        await Promise.all(
          top.map(async (e) => {
            const id = idByName.get(e.entity_name.toLowerCase());
            if (id == null) return;
            try {
              const hist: any = await statsApi.getHistoricalSentiment(id, { days: DAYS });
              const summary = hist?.summary;
              if (summary && summary.total_mentions > 0) {
                built.push({
                  name: e.entity_name,
                  type: e.entity_type,
                  sourcePower: e.avg_power_score,
                  sourceMoral: e.avg_moral_score,
                  globalPower: summary.avg_power_score,
                  globalMoral: summary.avg_moral_score,
                });
              }
            } catch {
              // no global comparison point for this entity — skip it
            }
          })
        );

        if (!cancelled) {
          // Preserve the source's own coverage order (most-mentioned first).
          const order = new Map(top.map((e, i) => [e.entity_name, i]));
          built.sort((a, b) => (order.get(a.name) ?? 0) - (order.get(b.name) ?? 0));
          setRows(built);
        }
      } catch {
        if (!cancelled) setRows([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [source, entities]);

  if (!source) {
    return (
      <Box sx={{ textAlign: 'center', py: 8 }}>
        <Typography variant="h5" sx={{ color: tokens.inkMuted }}>
          Source not found
        </Typography>
        <Typography variant="body2" sx={{ color: tokens.inkMuted, mt: 1 }}>
          It may not be among the tracked news sources. Try browsing the full list instead.
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1, flexWrap: 'wrap' }}>
        <Typography component="h2" sx={{ fontFamily: '"Newsreader", Georgia, serif', fontStyle: 'italic', fontSize: '2rem' }}>
          {source.name}
        </Typography>
        {source.country && <Chip label={source.country} size="small" variant="outlined" />}
        {source.language && <Chip label={source.language} size="small" variant="outlined" />}
      </Box>
      <Typography variant="body2" sx={{ color: tokens.inkMuted, mb: 3, maxWidth: 720 }}>
        The entities this source covers most, held against the global average across all tracked
        sources. The colored dot is this source's reading; the gray dot is the baseline. Distance
        is divergence, not a verdict.
      </Typography>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
          <CircularProgress size={24} />
        </Box>
      ) : (
        <SourceComparisonCard source={source} rows={rows} />
      )}

      <Box sx={{ mt: 4 }}>
        <RouterLink to="/sources" style={{ color: tokens.accent, fontSize: '0.875rem' }}>
          &larr; Back to all sources
        </RouterLink>
      </Box>
    </Box>
  );
};

export default SourceProfilePage;
