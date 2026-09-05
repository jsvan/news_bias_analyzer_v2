import React, { useEffect, useMemo, useState } from 'react';
import { useSearchParams, useNavigate, Link as RouterLink } from 'react-router-dom';
import {
  Autocomplete, Box, Button, Card, CardContent, CardHeader, CircularProgress,
  Grid, Link, TextField, Typography,
} from '@mui/material';
import { useData } from '../context/DataContext';
import { statsApi } from '../services/api';
import PairScatterChart from '../components/PairScatterChart';
import ReceiptsDrawer, { ReceiptsFilter } from '../components/ReceiptsDrawer';
import { Entity, EntitySentimentSummary } from '../types';
import { tokens, monoNumber, fontDisplay, archetypeColor, archetypeLabel } from '../theme';

// The mirror: two countries' presses on the same entities, side by side, at a
// shareable URL (/coverage/mirror?a=USA&b=Russia). The headline feature is
// reciprocity — what A's press says about country B and what B's press says
// about country A, on one row — with each nation's self-image beside it.

const SPHERE_DEPTH = 100;

// Sphere name (a source's `country`) → the entity that country appears as in
// coverage. Only the names that differ need an override; everything else
// resolves by its own name (alias-aware, via entities.json).
const COUNTRY_ENTITY_NAME: Record<string, string> = {
  USA: 'United States',
  UK: 'United Kingdom',
  UAE: 'United Arab Emirates',
};

const scoreText = (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}`;

const findCountryEntity = (country: string, entities: Entity[]): Entity | undefined => {
  const target = (COUNTRY_ENTITY_NAME[country] ?? country).toLowerCase();
  return entities.find(
    (e) =>
      e.name.toLowerCase() === target ||
      (e.aliases ?? []).some((al: string) => al.toLowerCase() === target)
  );
};

// One reciprocity cell: how `sphere`'s press casts `about`.
const ReciprocityCell: React.FC<{
  sphere: string;
  about: string;
  row: EntitySentimentSummary | undefined;
  onReceipts: (() => void) | null;
  self?: boolean;
}> = ({ sphere, about, row, onReceipts, self }) => (
  <Box
    sx={{
      flex: 1,
      minWidth: 240,
      p: 2,
      border: `1px solid ${tokens.border}`,
      borderRadius: 1,
      bgcolor: self ? tokens.surfaceSunken : tokens.surface,
    }}
  >
    <Typography variant="caption" sx={{ color: tokens.inkMuted, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
      {sphere}'s press on {self ? 'itself' : about}
    </Typography>
    {row ? (
      <>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.75 }}>
          <Box
            sx={{
              width: 10,
              height: 10,
              borderRadius: '50%',
              bgcolor: archetypeColor(row.power_score, row.moral_score),
              flexShrink: 0,
            }}
          />
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            {archetypeLabel(row.power_score, row.moral_score)}
          </Typography>
          <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted }}>
            power {scoreText(row.power_score)} · moral {scoreText(row.moral_score)}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
          {row.mention_count != null && (
            <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
              {row.mention_count.toLocaleString()} scored mentions
            </Typography>
          )}
          {onReceipts && (
            <Button size="small" sx={{ py: 0, minWidth: 0 }} onClick={onReceipts}>
              Receipts
            </Button>
          )}
        </Box>
      </>
    ) : (
      <Typography variant="body2" sx={{ color: tokens.inkMuted, mt: 0.75 }}>
        Not among this press's top scored entities.
      </Typography>
    )}
  </Box>
);

const MirrorPage: React.FC = () => {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { entities, availableCountries, getEntityById } = useData();

  const a = params.get('a') ?? '';
  const b = params.get('b') ?? '';
  const bothChosen = !!a && !!b && a !== b;

  const [rowsA, setRowsA] = useState<EntitySentimentSummary[] | null>(null);
  const [rowsB, setRowsB] = useState<EntitySentimentSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [receiptsFor, setReceiptsFor] = useState<ReceiptsFilter | null>(null);

  useEffect(() => {
    if (!bothChosen) return;
    let cancelled = false;
    setRowsA(null);
    setRowsB(null);
    setError(null);
    Promise.all([
      statsApi.getTrendingEntities(SPHERE_DEPTH, undefined, a, undefined, SPHERE_DEPTH),
      statsApi.getTrendingEntities(SPHERE_DEPTH, undefined, b, undefined, SPHERE_DEPTH),
    ])
      .then(([ra, rb]) => {
        if (cancelled) return;
        setRowsA(ra ?? []);
        setRowsB(rb ?? []);
      })
      .catch((err) => {
        if (!cancelled) setError((err as Error).message);
      });
    return () => {
      cancelled = true;
    };
  }, [a, b, bothChosen]);

  const setCountry = (side: 'a' | 'b', value: string | null) => {
    const next = new URLSearchParams(params);
    if (value) next.set(side, value);
    else next.delete(side);
    navigate(`/coverage/mirror?${next.toString()}`);
  };

  const shared = useMemo(() => {
    if (!rowsA || !rowsB) return [];
    const byId = new Map(rowsB.filter((r) => r.id != null).map((r) => [r.id!, r]));
    return rowsA
      .filter((r) => r.id != null && byId.has(r.id))
      .map((r) => {
        const other = byId.get(r.id!)!;
        return {
          entity_id: r.id!,
          name: r.entity,
          score_a: r.moral_score,
          score_b: other.moral_score,
          n_a: r.mention_count ?? 0,
          n_b: other.mention_count ?? 0,
        };
      });
  }, [rowsA, rowsB]);

  const gaps = useMemo(
    () =>
      [...shared]
        .sort((x, y) => Math.abs(y.score_a - y.score_b) - Math.abs(x.score_a - x.score_b))
        .slice(0, 8),
    [shared]
  );

  const entityA = useMemo(() => findCountryEntity(a, entities), [a, entities]);
  const entityB = useMemo(() => findCountryEntity(b, entities), [b, entities]);
  const rowFor = (rows: EntitySentimentSummary[] | null, entity: Entity | undefined) =>
    entity && rows ? rows.find((r) => r.id === entity.id) : undefined;

  const linkFor = (id: number) => (getEntityById(id) ? `/portrayals/${id}` : null);

  const picker = (side: 'a' | 'b', label: string, value: string) => (
    <Autocomplete
      size="small"
      options={availableCountries}
      value={value || null}
      onChange={(_, v) => setCountry(side, v)}
      sx={{ width: { xs: '100%', sm: 220 } }}
      renderInput={(p) => <TextField {...p} label={label} />}
    />
  );

  const loading = bothChosen && !error && (rowsA === null || rowsB === null);

  return (
    <Box>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', columnGap: 2, rowGap: 1.5, mb: 1 }}>
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
          {bothChosen ? (
            <>
              {a} <Box component="span" sx={{ color: tokens.inkMuted }}>⇄</Box> {b}
            </>
          ) : (
            'The mirror'
          )}
        </Typography>
        <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', ml: 'auto' }}>
          {picker('a', "Country A's press", a)}
          {picker('b', "Country B's press", b)}
        </Box>
      </Box>
      <Typography variant="body2" sx={{ color: tokens.inkMuted, maxWidth: '78ch', mb: 3 }}>
        Two countries' presses held up to each other: how each one casts the other, how each
        casts itself, and where their readings of the same world part ways. This page has a
        stable address — send it.
      </Typography>

      {!bothChosen && (
        <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 2 }}>
          Pick two different countries above{availableCountries.length ? '' : ' (loading…)'}.
        </Typography>
      )}
      {error && (
        <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 2 }}>
          {error}
        </Typography>
      )}
      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress size={26} />
        </Box>
      )}

      {bothChosen && rowsA && rowsB && (
        <Grid container spacing={4}>
          <Grid item xs={12}>
            <Card>
              <CardHeader
                title="Reciprocity"
                subheader="What each press says about the other country — and about its own"
              />
              <CardContent>
                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
                  <ReciprocityCell
                    sphere={a}
                    about={b}
                    row={rowFor(rowsA, entityB)}
                    onReceipts={
                      entityB
                        ? () =>
                            setReceiptsFor({
                              entityId: entityB.id,
                              entityName: entityB.name,
                              country: a,
                              scopeLabel: `${a}'s press`,
                            })
                        : null
                    }
                  />
                  <ReciprocityCell
                    sphere={b}
                    about={a}
                    row={rowFor(rowsB, entityA)}
                    onReceipts={
                      entityA
                        ? () =>
                            setReceiptsFor({
                              entityId: entityA.id,
                              entityName: entityA.name,
                              country: b,
                              scopeLabel: `${b}'s press`,
                            })
                        : null
                    }
                  />
                </Box>
                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                  <ReciprocityCell sphere={a} about={a} row={rowFor(rowsA, entityA)} onReceipts={null} self />
                  <ReciprocityCell sphere={b} about={b} row={rowFor(rowsB, entityB)} onReceipts={null} self />
                </Box>
                <Typography variant="caption" sx={{ display: 'block', mt: 1.5, color: tokens.inkMuted }}>
                  Self-image cells (recessed) are each press writing about its own country — the
                  diagonal of the reciprocity matrix.
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12}>
            <Card>
              <CardHeader
                title="The same world, twice"
                subheader={`${a}'s press across, ${b}'s press up — every entity both presses scored, moral dimension`}
              />
              <CardContent>
                {shared.length < 5 ? (
                  <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 3 }}>
                    Too few entities scored by both presses to draw.
                  </Typography>
                ) : (
                  <>
                    <PairScatterChart
                      aName={`${a}'s press`}
                      bName={`${b}'s press`}
                      entities={shared}
                      height={480}
                      onPointClick={(id) => {
                        const to = linkFor(id);
                        if (to) navigate(to);
                      }}
                    />
                    <Typography variant="caption" sx={{ display: 'block', mt: 1, color: tokens.inkMuted }}>
                      One point per entity both presses scored; the dashed diagonal is perfect
                      agreement. Labels mark the widest disagreements; click a point for the
                      entity's profile.
                    </Typography>
                  </>
                )}
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12}>
            <Card>
              <CardHeader
                title="Where the mirrors bend"
                subheader="The widest gaps between the two presses' readings, with receipts from each side"
              />
              <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
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
                        {a} {scoreText(e.score_a)}
                      </Typography>
                      <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted }}>
                        {b} {scoreText(e.score_b)}
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
                            country: a,
                            scopeLabel: `${a}'s press`,
                          })
                        }
                      >
                        {a} receipts
                      </Button>
                      <Button
                        size="small"
                        onClick={() =>
                          setReceiptsFor({
                            entityId: e.entity_id,
                            entityName: e.name,
                            country: b,
                            scopeLabel: `${b}'s press`,
                          })
                        }
                      >
                        {b} receipts
                      </Button>
                    </Box>
                  );
                })}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      <ReceiptsDrawer filter={receiptsFor} onClose={() => setReceiptsFor(null)} />
    </Box>
  );
};

export default MirrorPage;
