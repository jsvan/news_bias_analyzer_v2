import React, { useEffect, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Card,
  CardHeader,
  CardContent,
  Box,
  Typography,
  Chip,
  CircularProgress,
  Link as MuiLink,
} from '@mui/material';
import { tokens, monoNumber } from '../theme';
import { narrativeApi } from '../services/api';

// The shared international agenda (server/routers/narrative_endpoints.py::
// get_global_agenda): entities ranked by how many countries' sources covered
// them over the map's window. This is the map's foundation made visible - the
// few thousand entities the world talks about together, versus the long local
// tail (each country's own politicians, towns, schools) that the map's breadth
// floor deliberately excludes.

interface AgendaEntity {
  entity_id: number;
  name: string;
  type: string | null;
  countries: number;
  sources: number;
  mentions: number;
  mean_moral: number;
  mean_power: number;
}

interface AgendaResponse {
  window_start: string | null;
  window_end: string | null;
  total_entities: number;
  international_entities: number;
  entities: AgendaEntity[];
}

const SHOWN = 15;

const scoreColor = (score: number): string =>
  score >= 0 ? tokens.accent : tokens.villain;

const GlobalAgendaPanel: React.FC = () => {
  const [data, setData] = useState<AgendaResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    narrativeApi
      .getGlobalAgenda({ limit: SHOWN })
      .then((d: AgendaResponse) => setData(d))
      .catch((err) => setError((err as Error).message));
  }, []);

  const maxCountries = data?.entities[0]?.countries ?? 1;

  return (
    <Card>
      <CardHeader
        title="The shared agenda"
        subheader={`What the whole world covers at once — entities ranked by how many countries' sources mentioned them${
          data?.window_start ? ` (${data.window_start} to ${data.window_end})` : ''
        }`}
      />
      <CardContent sx={{ pt: 0 }}>
        {error && (
          <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 2 }}>
            {error}
          </Typography>
        )}
        {!data && !error && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress size={24} />
          </Box>
        )}
        {data && (
          <>
            {data.entities.map((e, idx) => (
              <Box
                key={e.entity_id}
                sx={{
                  display: 'flex',
                  alignItems: 'baseline',
                  gap: 1.5,
                  px: 0.5,
                  py: 0.75,
                  borderTop: idx === 0 ? 'none' : `1px solid ${tokens.border}`,
                }}
              >
                <Typography
                  variant="caption"
                  sx={{ ...monoNumber, color: tokens.inkMuted, width: 20, flexShrink: 0 }}
                >
                  {idx + 1}
                </Typography>
                <Box sx={{ minWidth: 0, flex: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                    <MuiLink
                      component={RouterLink}
                      to={`/portrayals/${e.entity_id}`}
                      sx={{
                        color: tokens.ink,
                        fontWeight: 500,
                        fontSize: '0.875rem',
                        textDecoration: 'none',
                        '&:hover': { color: tokens.accent },
                      }}
                      noWrap
                    >
                      {e.name}
                    </MuiLink>
                    {e.type && (
                      <Chip
                        label={e.type}
                        size="small"
                        variant="outlined"
                        sx={{ height: 18, fontSize: 10, color: tokens.inkMuted }}
                      />
                    )}
                  </Box>
                  {/* Breadth bar: countries covering this entity, relative to the leader. */}
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.25 }}>
                    <Box
                      sx={{
                        height: 4,
                        borderRadius: 2,
                        bgcolor: tokens.accent,
                        opacity: 0.35,
                        width: `${(e.countries / maxCountries) * 100}%`,
                        maxWidth: 160,
                        flexShrink: 0,
                      }}
                    />
                    <Typography variant="caption" sx={{ color: tokens.inkMuted }} noWrap>
                      {e.countries} countries · {e.sources} papers · {e.mentions.toLocaleString()} mentions
                    </Typography>
                  </Box>
                </Box>
                <Typography
                  variant="body2"
                  sx={{ ...monoNumber, color: scoreColor(e.mean_moral), flexShrink: 0 }}
                >
                  {e.mean_moral >= 0 ? '+' : ''}
                  {e.mean_moral.toFixed(2)}
                </Typography>
              </Box>
            ))}
            <Typography variant="caption" sx={{ display: 'block', mt: 1.5, color: tokens.inkMuted }}>
              Of {data.total_entities.toLocaleString()} entities mentioned this window, only{' '}
              {data.international_entities.toLocaleString()} were covered by sources from 3+
              countries — the rest are somebody's local conversation. The source map is built
              on this shared slice alone. Right column: mention-weighted mean moral score.
            </Typography>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default GlobalAgendaPanel;
