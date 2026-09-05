import React, { useEffect, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Box, Button, Card, CardContent, CardHeader, CircularProgress, Link, Typography,
} from '@mui/material';
import { useData } from '../context/DataContext';
import { narrativeApi } from '../services/api';
import ReceiptsDrawer, { ReceiptsFilter } from '../components/ReceiptsDrawer';
import { tokens, monoNumber, archetypeColor } from '../theme';

// The symbols page: concept entities the press fights over — "The West",
// "Sovereignty", "Democracy" — ranked by cross-country contestation. These are
// frames, not actors; the watchlist is injected into the extraction prompt
// (analyzer/entity_resolution.py SYMBOL_WATCHLIST) so they get scored under
// stable names.

interface SymbolRow {
  name: string;
  entity_id: number | null;
  mention_count: number;
  countries: number;
  mean_power: number | null;
  mean_moral: number | null;
  divergence: number | null;
}

interface SymbolsResponse {
  tracked_since: string;
  days: number;
  symbols: SymbolRow[];
}

const scoreText = (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}`;

const SymbolsPage: React.FC = () => {
  const { getEntityById } = useData();
  const [data, setData] = useState<SymbolsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [receiptsFor, setReceiptsFor] = useState<ReceiptsFilter | null>(null);

  useEffect(() => {
    narrativeApi
      .getSymbols()
      .then(setData)
      .catch((err) => setError((err as Error).message));
  }, []);

  const scored = data?.symbols.filter((s) => s.mention_count > 0) ?? [];
  const unscored = data?.symbols.filter((s) => s.mention_count === 0) ?? [];

  return (
    <Box>
      <Typography variant="body2" sx={{ color: tokens.inkMuted, maxWidth: '78ch', mb: 3 }}>
        Symbols are the entities nobody can point at: the West, sovereignty, democracy, the
        elites. The press does not report on them so much as fight over them — so they are
        tracked here as concept entities, ranked by how far apart countries' readings sit.
        The watchlist entered the reader on {data?.tracked_since ?? '2026-09-06'}; mention
        volume before that date is incidental.
      </Typography>

      {error && (
        <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 2 }}>
          {error}
        </Typography>
      )}
      {!data && !error && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress size={26} />
        </Box>
      )}

      {data && (
        <Card>
          <CardHeader
            title="The watchlist, by contestation"
            subheader="Divergence = the sharpest disagreement between any two countries' readings (Jensen–Shannon). Blank until two countries each clear 10 scored mentions."
          />
          <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
            {scored.map((s, i) => {
              const inSnapshot = s.entity_id != null && !!getEntityById(s.entity_id);
              return (
                <Box
                  key={s.name}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: 1.5,
                    px: 2,
                    py: 1.1,
                    borderTop: i === 0 ? 'none' : `1px solid ${tokens.border}`,
                  }}
                >
                  <Box sx={{ flex: 1, minWidth: 200, display: 'flex', alignItems: 'center', gap: 1 }}>
                    {s.mean_power != null && s.mean_moral != null && (
                      <Box
                        sx={{
                          width: 9,
                          height: 9,
                          borderRadius: '50%',
                          bgcolor: archetypeColor(s.mean_power, s.mean_moral),
                          flexShrink: 0,
                        }}
                      />
                    )}
                    {inSnapshot ? (
                      <Link
                        component={RouterLink}
                        to={`/portrayals/${s.entity_id}`}
                        underline="hover"
                        sx={{ color: tokens.ink, fontWeight: 600, fontSize: '0.875rem' }}
                      >
                        {s.name}
                      </Link>
                    ) : (
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {s.name}
                      </Typography>
                    )}
                  </Box>
                  <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted }}>
                    {s.mention_count.toLocaleString()}× · {s.countries}{' '}
                    {s.countries === 1 ? 'country' : 'countries'}
                  </Typography>
                  {s.mean_moral != null && (
                    <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted }}>
                      moral {scoreText(s.mean_moral)}
                    </Typography>
                  )}
                  <Typography
                    variant="caption"
                    sx={{
                      ...monoNumber,
                      fontWeight: 600,
                      color: s.divergence != null ? tokens.villain : tokens.inkMuted,
                      minWidth: 64,
                      textAlign: 'right',
                    }}
                  >
                    {s.divergence != null ? `JSD ${s.divergence.toFixed(2)}` : '—'}
                  </Typography>
                  {inSnapshot && (
                    <Button
                      size="small"
                      onClick={() =>
                        setReceiptsFor({ entityId: s.entity_id!, entityName: s.name })
                      }
                    >
                      Receipts
                    </Button>
                  )}
                </Box>
              );
            })}
            {scored.length === 0 && (
              <Typography variant="body2" sx={{ color: tokens.inkMuted, px: 2, py: 3 }}>
                No scored symbol mentions yet — collection began {data.tracked_since}.
              </Typography>
            )}
          </CardContent>
        </Card>
      )}

      {unscored.length > 0 && (
        <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted, mt: 2 }}>
          Tracked, no scored mentions yet: {unscored.map((s) => s.name).join(' · ')}
        </Typography>
      )}

      <ReceiptsDrawer filter={receiptsFor} onClose={() => setReceiptsFor(null)} />
    </Box>
  );
};

export default SymbolsPage;
