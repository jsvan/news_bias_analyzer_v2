import React from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Box, Typography, Card, CardHeader, CardContent } from '@mui/material';
import { useData } from '../context/DataContext';
import { tokens, monoNumber } from '../theme';

const SearchPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { entities, sources } = useData();
  const query = (searchParams.get('q') || '').trim();

  if (!query) {
    return (
      <Box sx={{ px: 2, py: 6, textAlign: 'center' }}>
        <Typography variant="body1" sx={{ color: tokens.inkMuted }}>
          Use the search box in the header above to look up an entity or news source.
        </Typography>
      </Box>
    );
  }

  const needle = query.toLowerCase();
  const matchedEntities = entities.filter((e) => e.name.toLowerCase().includes(needle));
  const matchedSources = sources.filter((s) => s.name.toLowerCase().includes(needle));
  const noResults = matchedEntities.length === 0 && matchedSources.length === 0;

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 3 }}>
        Search results for &ldquo;{query}&rdquo;
      </Typography>

      {noResults && (
        <Box sx={{ px: 2, py: 6, textAlign: 'center' }}>
          <Typography variant="body1" sx={{ color: tokens.inkMuted }}>
            No results for &ldquo;{query}&rdquo;.
          </Typography>
        </Box>
      )}

      {matchedEntities.length > 0 && (
        <Card sx={{ mb: 3 }}>
          <CardHeader title="Entities" subheader={`${matchedEntities.length} match${matchedEntities.length === 1 ? '' : 'es'}`} />
          <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
            {matchedEntities.map((entity, i) => (
              <Box
                key={entity.id}
                onClick={() => navigate(`/entities/${entity.id}`)}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1.5,
                  px: 2,
                  py: 1,
                  cursor: 'pointer',
                  borderTop: i === 0 ? 'none' : `1px solid ${tokens.border}`,
                  '&:hover': { bgcolor: tokens.surfaceSunken },
                }}
              >
                <Typography variant="body2" sx={{ flex: 1 }}>
                  {entity.name}
                </Typography>
                <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
                  {entity.type}
                </Typography>
                <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted, minWidth: 60, textAlign: 'right' }}>
                  {(entity.mention_count || 0).toLocaleString()}
                </Typography>
              </Box>
            ))}
          </CardContent>
        </Card>
      )}

      {matchedSources.length > 0 && (
        <Card>
          <CardHeader title="Sources" subheader={`${matchedSources.length} match${matchedSources.length === 1 ? '' : 'es'}`} />
          <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
            {matchedSources.map((source, i) => (
              <Box
                key={source.id}
                onClick={() => navigate(`/sources/${encodeURIComponent(source.name)}`)}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1.5,
                  px: 2,
                  py: 1,
                  cursor: 'pointer',
                  borderTop: i === 0 ? 'none' : `1px solid ${tokens.border}`,
                  '&:hover': { bgcolor: tokens.surfaceSunken },
                }}
              >
                <Typography variant="body2" sx={{ flex: 1 }}>
                  {source.name}
                </Typography>
                <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
                  {source.country}
                </Typography>
                <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted, minWidth: 60, textAlign: 'right' }}>
                  {(source.article_count || 0).toLocaleString()}
                </Typography>
              </Box>
            ))}
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default SearchPage;
