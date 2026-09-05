import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate, Link as RouterLink } from 'react-router-dom';
import {
  Autocomplete, Box, Button, Card, CardContent, CardHeader, CircularProgress,
  Grid, Link, TextField, Typography,
} from '@mui/material';
import { useData } from '../context/DataContext';
import { similarityApi } from '../services/api';
import PairScatterChart from '../components/PairScatterChart';
import ReceiptsDrawer, { ReceiptsFilter } from '../components/ReceiptsDrawer';
import { NewsSource } from '../types';
import { tokens, monoNumber, fontDisplay } from '../theme';

// Two papers head to head, at a stable URL a journalist can send:
// /landscape/pair/:a/:b (paper names; numeric ids also accepted). The
// correlation and shared-entity scatter that used to live in a dialog, plus
// what only one of them covers, and receipts for the widest gaps.

interface PairEntity {
  entity_id: number;
  name: string;
  score_a: number;
  score_b: number;
  n_a: number;
  n_b: number;
}

interface OnlyEntity {
  entity_id: number;
  name: string;
  score: number;
  n: number;
}

interface PairResponse {
  window_start: string | null;
  window_end: string | null;
  source_a: { source_id: number; name: string; country: string | null };
  source_b: { source_id: number; name: string; country: string | null };
  r: number | null;
  common: number;
  entities: PairEntity[];
  only_a?: OnlyEntity[];
  only_b?: OnlyEntity[];
}

const GAP_ROWS = 8;

export const pairPath = (a: string, b: string) =>
  `/landscape/pair/${encodeURIComponent(a)}/${encodeURIComponent(b)}`;

const resolveSource = (param: string | undefined, sources: NewsSource[]) => {
  if (!param) return undefined;
  const raw = decodeURIComponent(param);
  if (/^\d+$/.test(raw)) return sources.find((s) => s.id === Number(raw));
  const lower = raw.toLowerCase();
  return sources.find((s) => s.name.toLowerCase() === lower);
};

const scoreText = (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}`;

const OnlyCoversCard: React.FC<{
  paper: string;
  other: string;
  rows: OnlyEntity[];
  linkFor: (id: number) => string | null;
}> = ({ paper, other, rows, linkFor }) => (
  <Card sx={{ height: '100%' }}>
    <CardHeader
      title={`Only ${paper} covers`}
      subheader={`Entities with 3+ scored mentions in ${paper} and none in ${other} this window`}
    />
    <CardContent sx={{ p: 0, '&:last-child': { pb: 1 } }}>
      {rows.length === 0 ? (
        <Typography variant="body2" sx={{ color: tokens.inkMuted, px: 2, py: 2 }}>
          Nothing above the floor — their coverage lists overlap.
        </Typography>
      ) : (
        rows.map((e, i) => {
          const to = linkFor(e.entity_id);
          return (
            <Box
              key={e.entity_id}
              sx={{
                display: 'flex',
                alignItems: 'baseline',
                gap: 1.5,
                px: 2,
                py: 0.9,
                borderTop: i === 0 ? 'none' : `1px solid ${tokens.border}`,
              }}
            >
              {to ? (
                <Link
                  component={RouterLink}
                  to={to}
                  underline="hover"
                  sx={{ flex: 1, color: tokens.ink, fontSize: '0.875rem', fontWeight: 500 }}
                >
                  {e.name}
                </Link>
              ) : (
                <Typography variant="body2" sx={{ flex: 1, fontWeight: 500 }}>
                  {e.name}
                </Typography>
              )}
              <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted }}>
                {e.n}× · {scoreText(e.score)}
              </Typography>
            </Box>
          );
        })
      )}
    </CardContent>
  </Card>
);

const PairPage: React.FC = () => {
  const { a: aParam, b: bParam } = useParams<{ a: string; b: string }>();
  const navigate = useNavigate();
  const { sources, getEntityById } = useData();

  const a = resolveSource(aParam, sources);
  const b = resolveSource(bParam, sources);

  const [data, setData] = useState<PairResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [receiptsFor, setReceiptsFor] = useState<ReceiptsFilter | null>(null);
  // Half-built pair on the no-params /landscape/pair form: navigate only once
  // both sides are chosen.
  const [pendingA, setPendingA] = useState<NewsSource | null>(null);
  const [pendingB, setPendingB] = useState<NewsSource | null>(null);

  useEffect(() => {
    if (!a || !b) return;
    let cancelled = false;
    setData(null);
    setError(null);
    similarityApi
      .getPair(a.id, b.id)
      .then((d: PairResponse) => {
        if (!cancelled) setData(d);
      })
      .catch((err) => {
        if (!cancelled) setError((err as Error).message);
      });
    return () => {
      cancelled = true;
    };
  }, [a?.id, b?.id]);

  const gaps = useMemo(
    () =>
      [...(data?.entities ?? [])]
        .sort(
          (x, y) => Math.abs(y.score_a - y.score_b) - Math.abs(x.score_a - x.score_b)
        )
        .slice(0, GAP_ROWS),
    [data]
  );

  // Entity links only where the profile page can actually answer (the
  // snapshotted top entities); everything else renders as plain text.
  const linkFor = (id: number) => (getEntityById(id) ? `/portrayals/${id}` : null);

  const pickerOptions = useMemo(
    () =>
      [...sources].sort(
        (x, y) => (x.country || '').localeCompare(y.country || '') || x.name.localeCompare(y.name)
      ),
    [sources]
  );

  const picker = (
    value: NewsSource | undefined,
    onPick: (s: NewsSource) => void,
    label: string
  ) => (
    <Autocomplete
      size="small"
      options={pickerOptions}
      value={value ?? null}
      groupBy={(s) => s.country || 'Other'}
      getOptionLabel={(s) => s.name}
      isOptionEqualToValue={(x, y) => x.id === y.id}
      onChange={(_, s) => s && onPick(s)}
      sx={{ width: { xs: '100%', sm: 250 } }}
      renderInput={(params) => <TextField {...params} label={label} />}
    />
  );

  if (sources.length && (!a || !b)) {
    return (
      <Box sx={{ py: 4 }}>
        <Typography variant="h6" sx={{ mb: 1 }}>
          Pick two papers to compare
        </Typography>
        <Typography variant="body2" sx={{ color: tokens.inkMuted, mb: 2 }}>
          {aParam && !a ? `"${decodeURIComponent(aParam)}" isn't a tracked paper. ` : ''}
          {bParam && !b ? `"${decodeURIComponent(bParam)}" isn't a tracked paper.` : ''}
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          {picker(a ?? pendingA ?? undefined, (s) => {
            const other = b ?? pendingB;
            if (other) navigate(pairPath(s.name, other.name));
            else setPendingA(s);
          }, 'Paper A')}
          {picker(b ?? pendingB ?? undefined, (s) => {
            const other = a ?? pendingA;
            if (other) navigate(pairPath(other.name, s.name));
            else setPendingB(s);
          }, 'Paper B')}
        </Box>
      </Box>
    );
  }
  if (!a || !b) return null; // sources still loading

  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          columnGap: 2,
          rowGap: 1.5,
          mb: 1,
        }}
      >
        <Typography
          component="h2"
          sx={{
            fontFamily: fontDisplay,
            fontStyle: 'italic',
            fontWeight: 500,
            fontSize: '1.5rem',
            letterSpacing: '-0.01em',
          }}
        >
          {a.name} <Box component="span" sx={{ color: tokens.inkMuted }}>×</Box> {b.name}
        </Typography>
        <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', ml: 'auto' }}>
          {picker(a, (s) => navigate(pairPath(s.name, b.name)), 'Paper A')}
          {picker(b, (s) => navigate(pairPath(a.name, s.name)), 'Paper B')}
        </Box>
      </Box>
      <Typography variant="body2" sx={{ color: tokens.inkMuted, maxWidth: '78ch', mb: 3 }}>
        {data ? (
          <>
            {data.r != null ? (
              <>
                Moral-score correlation{' '}
                <Box component="span" sx={{ ...monoNumber, color: tokens.ink, fontWeight: 600 }}>
                  {data.r >= 0 ? '+' : ''}
                  {data.r.toFixed(2)}
                </Box>{' '}
                over
              </>
            ) : (
              'Too little overlap for a correlation —'
            )}{' '}
            {data.common} entities both papers scored
            {data.window_start ? ` (${data.window_start} to ${data.window_end})` : ''}. This page
            has a stable address — send it.
          </>
        ) : (
          'Loading…'
        )}
      </Typography>

      {error && (
        <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 3 }}>
          {error}
        </Typography>
      )}
      {!data && !error && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress size={26} />
        </Box>
      )}

      {data && (
        <Grid container spacing={4}>
          <Grid item xs={12}>
            <Card>
              <CardHeader
                title="Where each entity lands"
                subheader={`${a.name}'s reading across, ${b.name}'s up — the dashed diagonal is perfect agreement`}
              />
              <CardContent>
                <PairScatterChart
                  aName={a.name}
                  bName={b.name}
                  entities={data.entities}
                  height={480}
                  onPointClick={(id) => {
                    const to = linkFor(id);
                    if (to) navigate(to);
                  }}
                />
                <Typography variant="caption" sx={{ display: 'block', mt: 1, color: tokens.inkMuted }}>
                  One point per entity both papers scored; point size tracks how often the
                  less-frequent side mentioned it. Labels mark the widest disagreements; click a
                  point to open that entity's profile.
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12}>
            <Card>
              <CardHeader
                title="Where they part ways"
                subheader="The widest gaps between the two readings, with the receipts behind each"
              />
              <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
                {gaps.length === 0 && (
                  <Typography variant="body2" sx={{ color: tokens.inkMuted, px: 2, py: 3 }}>
                    No shared entities in this window.
                  </Typography>
                )}
                {gaps.map((e, i) => {
                  const to = linkFor(e.entity_id);
                  return (
                    <Box
                      key={e.entity_id}
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
                      <Box sx={{ flex: 1, minWidth: 180 }}>
                        {to ? (
                          <Link
                            component={RouterLink}
                            to={to}
                            underline="hover"
                            sx={{ color: tokens.ink, fontWeight: 600, fontSize: '0.875rem' }}
                          >
                            {e.name}
                          </Link>
                        ) : (
                          <Typography variant="body2" sx={{ fontWeight: 600 }}>
                            {e.name}
                          </Typography>
                        )}
                      </Box>
                      <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted }}>
                        {a.name} {scoreText(e.score_a)} ({e.n_a}×)
                      </Typography>
                      <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted }}>
                        {b.name} {scoreText(e.score_b)} ({e.n_b}×)
                      </Typography>
                      <Typography
                        variant="caption"
                        sx={{ ...monoNumber, fontWeight: 600, color: tokens.villain }}
                      >
                        Δ {Math.abs(e.score_a - e.score_b).toFixed(2)}
                      </Typography>
                      <Button
                        size="small"
                        onClick={() =>
                          setReceiptsFor({
                            entityId: e.entity_id,
                            entityName: e.name,
                            sourceIds: [a.id, b.id],
                            scopeLabel: `${a.name} and ${b.name}`,
                          })
                        }
                      >
                        Receipts
                      </Button>
                    </Box>
                  );
                })}
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <OnlyCoversCard
              paper={a.name}
              other={b.name}
              rows={data.only_a ?? []}
              linkFor={linkFor}
            />
          </Grid>
          <Grid item xs={12} md={6}>
            <OnlyCoversCard
              paper={b.name}
              other={a.name}
              rows={data.only_b ?? []}
              linkFor={linkFor}
            />
          </Grid>
        </Grid>
      )}

      <ReceiptsDrawer filter={receiptsFor} onClose={() => setReceiptsFor(null)} />
    </Box>
  );
};

export default PairPage;
