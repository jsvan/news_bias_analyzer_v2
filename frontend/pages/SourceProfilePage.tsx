import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link as RouterLink } from 'react-router-dom';
import { Box, Typography, Card, CardHeader, CardContent, Chip, CircularProgress } from '@mui/material';
import { useData } from '../context/DataContext';
import { statsApi } from '../services/api';
import { CountryEntityData } from '../types';
import { tokens, archetypeColor, monoNumber } from '../theme';

const SourceProfilePage: React.FC = () => {
  const { name } = useParams<{ name: string }>();
  const navigate = useNavigate();
  const { entities, getSourceByName } = useData();
  const source = name ? getSourceByName(decodeURIComponent(name)) : undefined;

  const [topEntities, setTopEntities] = useState<CountryEntityData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!source) return;
    setLoading(true);
    statsApi
      .getNewspaperTopEntities(source.name, { days: 30, limit: 10 })
      .then((res) => setTopEntities(res?.entities || []))
      .catch(() => setTopEntities([]))
      .finally(() => setLoading(false));
  }, [source]);

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
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3, flexWrap: 'wrap' }}>
        <Typography component="h2" sx={{ fontFamily: '"Newsreader", Georgia, serif', fontStyle: 'italic', fontSize: '2rem' }}>
          {source.name}
        </Typography>
        {source.country && <Chip label={source.country} size="small" variant="outlined" />}
        {source.language && <Chip label={source.language} size="small" variant="outlined" />}
      </Box>

      <Card sx={{ mb: 4 }}>
        <CardHeader title="Bias Profile" subheader="Partisan and national-favoritism analysis" />
        <CardContent>
          <Typography variant="body2" sx={{ color: tokens.inkMuted }}>
            Bias-profile analysis not yet available for this source.
          </Typography>
        </CardContent>
      </Card>

      <Card>
        <CardHeader title="Top Covered Entities" subheader="Most-mentioned entities in this source's coverage, last 30 days" />
        <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
              <CircularProgress size={24} />
            </Box>
          ) : topEntities.length === 0 ? (
            <Box sx={{ px: 2, py: 3 }}>
              <Typography variant="body2" sx={{ color: tokens.inkMuted }}>
                No coverage data available yet for this source.
              </Typography>
            </Box>
          ) : (
            topEntities.map((entity, i) => {
              const match = entities.find((e) => e.name === entity.entity_name);
              return (
                <Box
                  key={entity.entity_name}
                  onClick={() => match && navigate(`/entities/${match.id}`)}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1.5,
                    px: 2,
                    py: 1.25,
                    cursor: match ? 'pointer' : 'default',
                    borderTop: i === 0 ? 'none' : `1px solid ${tokens.border}`,
                    '&:hover': match ? { bgcolor: tokens.surfaceSunken } : undefined,
                  }}
                >
                  <Box
                    sx={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      flexShrink: 0,
                      bgcolor: archetypeColor(entity.avg_power_score, entity.avg_moral_score),
                    }}
                  />
                  <Typography variant="body2" sx={{ flex: 1, fontWeight: 500 }}>
                    {entity.entity_name}
                  </Typography>
                  <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted }}>
                    P {entity.avg_power_score.toFixed(1)} &middot; M {entity.avg_moral_score.toFixed(1)}
                  </Typography>
                  <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted, minWidth: 90, textAlign: 'right' }}>
                    {entity.mention_count.toLocaleString()} mentions
                  </Typography>
                </Box>
              );
            })
          )}
        </CardContent>
      </Card>

      <Box sx={{ mt: 4 }}>
        <RouterLink to="/sources" style={{ color: tokens.accent, fontSize: '0.875rem' }}>
          &larr; Back to all sources
        </RouterLink>
      </Box>
    </Box>
  );
};

export default SourceProfilePage;
