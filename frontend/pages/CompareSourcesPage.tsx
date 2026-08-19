import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardHeader,
  CardContent,
  Paper,
  Autocomplete,
  TextField,
  Chip,
  CircularProgress,
  ToggleButtonGroup,
  ToggleButton,
} from '@mui/material';
import { useData } from '../context/DataContext';
import { statsApi, similarityApi } from '../services/api';
import { NewsSource, CountryEntityData } from '../types';
import { tokens, monoNumber } from '../theme';

const MAX_SELECTED = 4;
// All-time window: the corpus is a bounded snapshot; a wall-clock lookback can
// be empty long before the data is. Limit 20 is the endpoint's cap — the wider
// the lists, the more the selected sources' coverage can actually intersect.
const DAYS = 0;
const LIMIT = 20;

const clamp = (v: number) => Math.max(-2, Math.min(2, v));
const pct = (v: number) => `${((clamp(v) + 2) / 4) * 100}%`;

interface SharedRow {
  entity: string;
  type: string;
  // per selected-source score, aligned with the selection order; null = this
  // source's top list doesn't include the entity
  scores: (number | null)[];
  spread: number;
}

interface PairScore {
  a: string;
  b: string;
  score: number;
  common: number;
}

const CompareSourcesPage: React.FC = () => {
  const { sources, getSourceByName } = useData();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [selectedNames, setSelectedNames] = useState<string[]>(() => {
    const raw = searchParams.get('names');
    if (!raw) return [];
    return raw
      .split(',')
      .map((v) => v.trim())
      .filter(Boolean)
      .slice(0, MAX_SELECTED);
  });
  const [entitiesByName, setEntitiesByName] = useState<Record<string, CountryEntityData[]>>({});
  const [loading, setLoading] = useState(false);
  const [dimension, setDimension] = useState<'moral' | 'power'>('moral');
  const [pairScores, setPairScores] = useState<PairScore[] | null>(null);

  const selectedSources = useMemo(
    () => selectedNames.map((name) => getSourceByName(name)).filter((s): s is NewsSource => !!s),
    [selectedNames, getSourceByName]
  );

  // Keep the URL in sync so a comparison is shareable/bookmarkable.
  useEffect(() => {
    const params = new URLSearchParams(searchParams);
    if (selectedNames.length) params.set('names', selectedNames.join(','));
    else params.delete('names');
    setSearchParams(params, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedNames]);

  useEffect(() => {
    if (selectedNames.length === 0) {
      setEntitiesByName({});
      return;
    }
    let cancelled = false;
    setLoading(true);
    Promise.all(
      selectedNames.map((name) =>
        statsApi
          .getNewspaperTopEntities(name, { days: DAYS, limit: LIMIT })
          .then((res) => [name, res?.entities || []] as const)
          .catch(() => [name, []] as const)
      )
    )
      .then((results) => {
        if (cancelled) return;
        const next: Record<string, CountryEntityData[]> = {};
        results.forEach(([name, data]) => {
          next[name] = data;
        });
        setEntitiesByName(next);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedNames.join(',')]);

  // How similarly the selected pairs scored their shared coverage — the weekly
  // Pearson matrix the source map is built on, filtered to this picker.
  useEffect(() => {
    if (selectedNames.length < 2) {
      setPairScores(null);
      return;
    }
    let cancelled = false;
    similarityApi
      .getMatrix()
      .then((matrix: any) => {
        if (cancelled) return;
        const idToName = new Map<number, string>();
        (matrix?.sources ?? []).forEach((s: any) => idToName.set(s.source_id, s.name));
        const wanted = new Set(selectedNames);
        const pairs: PairScore[] = [];
        (matrix?.pairs ?? []).forEach((p: any) => {
          const a = idToName.get(p.source_id_1);
          const b = idToName.get(p.source_id_2);
          if (a && b && wanted.has(a) && wanted.has(b)) {
            pairs.push({ a, b, score: p.score, common: p.common_entities });
          }
        });
        setPairScores(pairs);
      })
      .catch(() => {
        if (!cancelled) setPairScores(null);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedNames.join(',')]);

  const { sharedRows, exclusives } = useMemo(() => {
    const lists = selectedNames.map((name) => entitiesByName[name] || []);
    const byEntity = new Map<string, { type: string; scores: (number | null)[]; mentions: number[] }>();
    lists.forEach((list, sourceIdx) => {
      list.forEach((e) => {
        const cur =
          byEntity.get(e.entity_name) ??
          { type: e.entity_type, scores: selectedNames.map(() => null as number | null), mentions: selectedNames.map(() => 0) };
        cur.scores[sourceIdx] = dimension === 'moral' ? e.avg_moral_score : e.avg_power_score;
        cur.mentions[sourceIdx] = e.mention_count;
        byEntity.set(e.entity_name, cur);
      });
    });

    const shared: SharedRow[] = [];
    const excl: Record<string, { entity: string; mentions: number }[]> = {};
    selectedNames.forEach((n) => (excl[n] = []));

    byEntity.forEach((v, entity) => {
      const present = v.scores.filter((s): s is number => s != null);
      if (present.length >= 2) {
        shared.push({
          entity,
          type: v.type,
          scores: v.scores,
          spread: Math.max(...present) - Math.min(...present),
        });
      } else {
        const idx = v.scores.findIndex((s) => s != null);
        if (idx >= 0) excl[selectedNames[idx]].push({ entity, mentions: v.mentions[idx] });
      }
    });

    shared.sort((a, b) => b.spread - a.spread);
    Object.values(excl).forEach((list) => list.sort((a, b) => b.mentions - a.mentions));
    return { sharedRows: shared, exclusives: excl };
  }, [entitiesByName, selectedNames, dimension]);

  const sourceColor = (idx: number) => tokens.categorical[idx % tokens.categorical.length];

  return (
    <Box>
      <Typography component="h2" sx={{ fontFamily: '"Newsreader", Georgia, serif', fontStyle: 'italic', fontSize: '2rem', mb: 1 }}>
        Compare reading diets
      </Typography>
      <Typography variant="body2" sx={{ color: tokens.inkMuted, mb: 3 }}>
        Where the selected sources read the same entities differently, and what each covers that
        the others don't — the joining is done for you, not left to the eye.
      </Typography>

      <Paper sx={{ p: 2, mb: 4, bgcolor: tokens.surfaceSunken, border: `1px solid ${tokens.border}` }}>
        <Autocomplete
          multiple
          id="compare-sources-select"
          options={sources}
          value={selectedSources}
          getOptionLabel={(s) => s.name}
          isOptionEqualToValue={(a, b) => a.name === b.name}
          getOptionDisabled={(option) =>
            selectedSources.length >= MAX_SELECTED && !selectedSources.some((s) => s.name === option.name)
          }
          onChange={(_, value) => setSelectedNames(value.slice(0, MAX_SELECTED).map((s) => s.name))}
          renderInput={(params) => (
            <TextField
              {...params}
              label="Select up to 4 sources"
              size="small"
              fullWidth
              helperText={`${selectedSources.length}/${MAX_SELECTED} selected`}
            />
          )}
          limitTags={4}
          disableCloseOnSelect
        />
      </Paper>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress size={28} />
        </Box>
      ) : selectedSources.length === 0 ? (
        <Box sx={{ textAlign: 'center', py: 8 }}>
          <Typography variant="body1" sx={{ color: tokens.inkMuted }}>
            Select sources above to compare how they read the entities they share.
          </Typography>
        </Box>
      ) : (
        <>
          {pairScores && pairScores.length > 0 && (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 3, alignItems: 'center' }}>
              <Typography variant="caption" sx={{ color: tokens.inkMuted, mr: 0.5 }}>
                Sentiment correlation on shared coverage:
              </Typography>
              {pairScores.map((p) => (
                <Chip
                  key={`${p.a}|${p.b}`}
                  size="small"
                  variant="outlined"
                  label={
                    <span>
                      {p.a} × {p.b}{' '}
                      <Box component="span" sx={{ ...monoNumber, fontWeight: 600, color: p.score >= 0 ? tokens.accent : tokens.villain }}>
                        {p.score >= 0 ? '+' : ''}
                        {p.score.toFixed(2)}
                      </Box>
                      <Box component="span" sx={{ color: tokens.inkMuted }}> · {p.common} shared</Box>
                    </span>
                  }
                  sx={{ borderColor: tokens.border }}
                />
              ))}
            </Box>
          )}

          <Card>
            <CardHeader
              title="Same entities, different readings"
              subheader="Entities in at least two of the selected sources' top coverage, sorted by the widest gap"
              action={
                <ToggleButtonGroup
                  size="small"
                  value={dimension}
                  exclusive
                  onChange={(_, v) => v && setDimension(v)}
                  sx={{ mt: 1, mr: 1 }}
                >
                  <ToggleButton value="moral">Moral</ToggleButton>
                  <ToggleButton value="power">Power</ToggleButton>
                </ToggleButtonGroup>
              }
            />
            <CardContent sx={{ pt: 0 }}>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mb: 1.5 }}>
                {selectedSources.map((s, idx) => (
                  <Chip
                    key={s.name}
                    label={s.name}
                    size="small"
                    variant="outlined"
                    onClick={() => navigate(`/coverage/newspapers/${encodeURIComponent(s.name)}`)}
                    sx={{ borderColor: sourceColor(idx), color: sourceColor(idx), cursor: 'pointer' }}
                  />
                ))}
              </Box>
              {sharedRows.length === 0 ? (
                <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 2 }}>
                  These sources' top coverage doesn't overlap — nothing to hold side by side.
                  Their exclusives below are the finding: they are talking about different worlds.
                </Typography>
              ) : (
                <>
                  <Box
                    sx={{
                      display: 'flex',
                      px: 2,
                      color: tokens.inkMuted,
                      fontFamily: '"IBM Plex Mono", monospace',
                      fontSize: 10,
                    }}
                  >
                    <span style={{ width: 160, minWidth: 110 }} />
                    <Box sx={{ flex: 1, display: 'flex', justifyContent: 'space-between', minWidth: 160 }}>
                      <span>-2</span>
                      <span>0 = neutral</span>
                      <span>+2</span>
                    </Box>
                    <span style={{ minWidth: 52, textAlign: 'right' }}>gap</span>
                  </Box>
                  {sharedRows.map((row) => {
                    const present = row.scores
                      .map((score, idx) => ({ score, idx }))
                      .filter((x): x is { score: number; idx: number } => x.score != null);
                    return (
                      <Box
                        key={row.entity}
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 2,
                          px: 2,
                          py: 0.9,
                          borderTop: `1px solid ${tokens.border}`,
                          '&:hover': { bgcolor: tokens.surfaceSunken },
                        }}
                      >
                        <Box sx={{ width: 160, minWidth: 110 }}>
                          <Typography variant="body2" noWrap sx={{ fontWeight: 600 }}>
                            {row.entity}
                          </Typography>
                          <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
                            {row.type}
                          </Typography>
                        </Box>
                        <Box sx={{ flex: 1, minWidth: 160 }}>
                          <svg width="100%" height={24}>
                            <line x1="0%" y1={12} x2="100%" y2={12} stroke={tokens.border} strokeWidth={1} />
                            <line x1="50%" y1={3} x2="50%" y2={21} stroke={tokens.ink} strokeWidth={1} opacity={0.45} />
                            <line
                              x1={pct(Math.min(...present.map((p) => p.score)))}
                              y1={12}
                              x2={pct(Math.max(...present.map((p) => p.score)))}
                              y2={12}
                              stroke={tokens.inkMuted}
                              strokeWidth={1.5}
                            />
                            {present.map(({ score, idx }) => (
                              <circle
                                key={idx}
                                cx={pct(score)}
                                cy={12}
                                r={4.5}
                                fill={sourceColor(idx)}
                                stroke={tokens.surface}
                                strokeWidth={1}
                                opacity={0.9}
                              >
                                <title>{`${selectedNames[idx]}: ${score.toFixed(2)}`}</title>
                              </circle>
                            ))}
                          </svg>
                        </Box>
                        <Typography
                          variant="caption"
                          sx={{ ...monoNumber, minWidth: 52, textAlign: 'right', fontWeight: 600, color: tokens.ink }}
                        >
                          {row.spread.toFixed(2)}
                        </Typography>
                      </Box>
                    );
                  })}
                </>
              )}
            </CardContent>
          </Card>

          <Card sx={{ mt: 4 }}>
            <CardHeader
              title="Only in one diet"
              subheader="Top coverage unique to each selected source — what the others are silent on"
            />
            <CardContent sx={{ pt: 0 }}>
              <Grid container spacing={2}>
                {selectedSources.map((s, idx) => {
                  const list = (exclusives[s.name] || []).slice(0, 6);
                  return (
                    <Grid item xs={12} sm={6} md={3} key={s.name}>
                      <Typography variant="subtitle2" sx={{ color: sourceColor(idx), mb: 0.5 }} noWrap>
                        {s.name}
                      </Typography>
                      {list.length === 0 ? (
                        <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
                          Nothing exclusive — all of its top coverage is shared.
                        </Typography>
                      ) : (
                        list.map((e) => (
                          <Box key={e.entity} sx={{ display: 'flex', justifyContent: 'space-between', gap: 1, py: 0.4 }}>
                            <Typography variant="body2" noWrap>
                              {e.entity}
                            </Typography>
                            <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted, flexShrink: 0 }}>
                              {e.mentions.toLocaleString()}
                            </Typography>
                          </Box>
                        ))
                      )}
                    </Grid>
                  );
                })}
              </Grid>
            </CardContent>
          </Card>
        </>
      )}
    </Box>
  );
};

export default CompareSourcesPage;
