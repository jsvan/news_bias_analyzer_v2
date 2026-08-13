import React, { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Typography,
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
import { statsApi } from '../services/api';
import SourceComparisonCard, { EntityComparison } from '../components/SourceComparisonCard';
import { NewsSource, CountryEntityData } from '../types';
import { tokens, archetypeColor, monoNumber } from '../theme';

const STORAGE_KEY = 'newsbias:my-sources';
const MAX_SOURCES = 3;
// All-time window: the corpus is a bounded snapshot, so a wall-clock lookback
// (e.g. last 30 days) can be empty long before the data is. 0 = ALL_TIME sentinel.
const DAYS = 0;

const WORLD_BASELINE = 'World (all tracked sources)';

interface DivergenceRow {
  name: string;
  type: string;
  bubblePower: number;
  bubbleMoral: number;
  basePower: number;
  baseMoral: number;
}

// One dumbbell row: baseline dot (gray) and bubble dot (archetype-colored) on a
// shared -2..+2 track, with the neutral 0 line always drawn.
const DumbbellRow: React.FC<{ row: DivergenceRow; dimension: 'moral' | 'power' }> = ({ row, dimension }) => {
  const bubble = dimension === 'moral' ? row.bubbleMoral : row.bubblePower;
  const base = dimension === 'moral' ? row.baseMoral : row.basePower;
  const pct = (v: number) => `${((Math.max(-2, Math.min(2, v)) + 2) / 4) * 100}%`;
  const delta = bubble - base;
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, px: 2, py: 0.75, '&:hover': { bgcolor: tokens.surfaceSunken } }}>
      <Box sx={{ width: 170, minWidth: 120 }}>
        <Typography variant="body2" noWrap sx={{ fontWeight: 600 }}>
          {row.name}
        </Typography>
        <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
          {row.type}
        </Typography>
      </Box>
      <Box sx={{ flex: 1, minWidth: 160 }}>
        <svg width="100%" height={22}>
          <line x1="0%" y1={11} x2="100%" y2={11} stroke={tokens.border} strokeWidth={1} />
          <line x1="50%" y1={2} x2="50%" y2={20} stroke={tokens.ink} strokeWidth={1} opacity={0.45} />
          <line x1={pct(base)} y1={11} x2={pct(bubble)} y2={11} stroke={tokens.inkMuted} strokeWidth={1.5} strokeDasharray="3 2" />
          <circle cx={pct(base)} cy={11} r={4.5} fill={tokens.inkMuted} />
          <circle
            cx={pct(bubble)}
            cy={11}
            r={5.5}
            fill={archetypeColor(row.bubblePower, row.bubbleMoral)}
            stroke={tokens.surface}
            strokeWidth={1.5}
          />
        </svg>
      </Box>
      <Typography sx={{ ...monoNumber, minWidth: 56, textAlign: 'right', fontWeight: 600, color: tokens.ink }}>
        {delta >= 0 ? '+' : ''}
        {delta.toFixed(2)}
      </Typography>
    </Box>
  );
};

const MyBubblePage: React.FC = () => {
  const { sources, entities, availableCountries } = useData();

  const [selectedNames, setSelectedNames] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed.slice(0, MAX_SOURCES) : [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(selectedNames));
  }, [selectedNames]);

  const selectedSources = useMemo(
    () => selectedNames.map((name) => sources.find((s) => s.name === name)).filter((s): s is NewsSource => !!s),
    [selectedNames, sources]
  );

  const [comparisons, setComparisons] = useState<Record<string, EntityComparison[]>>({});
  const [loadingCompare, setLoadingCompare] = useState(false);

  useEffect(() => {
    if (selectedSources.length === 0) {
      setComparisons({});
      return;
    }
    let cancelled = false;
    setLoadingCompare(true);

    (async () => {
      const perSource = await Promise.all(
        selectedSources.map(async (source) => {
          try {
            const res = await statsApi.getNewspaperTopEntities(source.name, { days: DAYS, limit: 10 });
            const raw: CountryEntityData[] = res?.entities || [];
            return { source, entities: raw.filter((e) => e.mention_count > 0) };
          } catch {
            return { source, entities: [] as CountryEntityData[] };
          }
        })
      );

      const idByName = new Map<string, number>();
      entities.forEach((e) => idByName.set(e.name.toLowerCase(), e.id));

      const uniqueIds = new Set<number>();
      perSource.forEach(({ entities: es }) =>
        es.forEach((e) => {
          const id = idByName.get(e.entity_name.toLowerCase());
          if (id != null) uniqueIds.add(id);
        })
      );

      const globalById = new Map<number, { power: number; moral: number }>();
      await Promise.all(
        Array.from(uniqueIds).map(async (id) => {
          try {
            const hist: any = await statsApi.getHistoricalSentiment(id, { days: DAYS });
            const summary = hist?.summary;
            if (summary && summary.total_mentions > 0) {
              globalById.set(id, { power: summary.avg_power_score, moral: summary.avg_moral_score });
            }
          } catch {
            // no global comparison point available for this entity — skip it
          }
        })
      );

      if (cancelled) return;

      const nextComparisons: Record<string, EntityComparison[]> = {};
      perSource.forEach(({ source, entities: es }) => {
        const rows: EntityComparison[] = [];
        es.forEach((e) => {
          const id = idByName.get(e.entity_name.toLowerCase());
          const g = id != null ? globalById.get(id) : undefined;
          if (g) {
            rows.push({
              name: e.entity_name,
              type: e.entity_type,
              sourcePower: e.avg_power_score,
              sourceMoral: e.avg_moral_score,
              globalPower: g.power,
              globalMoral: g.moral,
            });
          }
        });
        nextComparisons[source.name] = rows;
      });
      setComparisons(nextComparisons);
      setLoadingCompare(false);
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedNames.join('|'), entities.length]);

  // ---- Divergence visualization: bubble vs a selectable baseline ----
  const [baseline, setBaseline] = useState<string>(WORLD_BASELINE);
  const [dimension, setDimension] = useState<'moral' | 'power'>('moral');
  const [countryMap, setCountryMap] = useState<Map<string, { power: number; moral: number }> | null>(null);

  useEffect(() => {
    if (baseline === WORLD_BASELINE) {
      setCountryMap(null);
      return;
    }
    let cancelled = false;
    statsApi
      // The endpoint caps limit at 20; the bubble itself is only top-10 per source.
      .getCountryTopEntities(baseline, { days: DAYS, limit: 20 })
      .then((res: any) => {
        if (cancelled) return;
        const m = new Map<string, { power: number; moral: number }>();
        (res?.entities || []).forEach((e: CountryEntityData) =>
          m.set(e.entity_name.toLowerCase(), { power: e.avg_power_score, moral: e.avg_moral_score })
        );
        setCountryMap(m);
      })
      .catch(() => {
        if (!cancelled) setCountryMap(new Map());
      });
    return () => {
      cancelled = true;
    };
  }, [baseline]);

  const { divergenceRows, skippedForBaseline } = useMemo(() => {
    // Bubble position per entity = average across the selected sources covering it.
    const acc = new Map<string, { type: string; p: number[]; m: number[]; gp: number; gm: number }>();
    Object.values(comparisons).forEach((rows) =>
      rows.forEach((r) => {
        const cur = acc.get(r.name) ?? { type: r.type, p: [], m: [], gp: r.globalPower, gm: r.globalMoral };
        cur.p.push(r.sourcePower);
        cur.m.push(r.sourceMoral);
        acc.set(r.name, cur);
      })
    );
    const rows: DivergenceRow[] = [];
    let skipped = 0;
    acc.forEach((v, name) => {
      let basePower = v.gp;
      let baseMoral = v.gm;
      if (countryMap) {
        const c = countryMap.get(name.toLowerCase());
        if (!c) {
          skipped += 1; // baseline country has no scored coverage of this entity
          return;
        }
        basePower = c.power;
        baseMoral = c.moral;
      }
      rows.push({
        name,
        type: v.type,
        bubblePower: v.p.reduce((a, b) => a + b, 0) / v.p.length,
        bubbleMoral: v.m.reduce((a, b) => a + b, 0) / v.m.length,
        basePower,
        baseMoral,
      });
    });
    const key = (r: DivergenceRow) =>
      dimension === 'moral' ? Math.abs(r.bubbleMoral - r.baseMoral) : Math.abs(r.bubblePower - r.basePower);
    rows.sort((a, b) => key(b) - key(a));
    return { divergenceRows: rows.slice(0, 12), skippedForBaseline: skipped };
  }, [comparisons, countryMap, dimension]);

  const picker = (
    <Autocomplete
      multiple
      id="my-bubble-source-select"
      options={sources}
      value={selectedSources}
      getOptionLabel={(s) => (s.country && s.country !== 'Unknown' ? `${s.name} — ${s.country}` : s.name)}
      isOptionEqualToValue={(a, b) => a.id === b.id}
      getOptionDisabled={(option) => selectedSources.length >= MAX_SOURCES && !selectedSources.some((s) => s.id === option.id)}
      onChange={(_, value) => setSelectedNames(value.slice(0, MAX_SOURCES).map((s) => s.name))}
      renderInput={(params) => (
        <TextField
          {...params}
          label="Sources you read"
          size="small"
          fullWidth
          helperText={`${selectedSources.length}/${MAX_SOURCES} selected`}
        />
      )}
      limitTags={MAX_SOURCES}
      disableCloseOnSelect
    />
  );

  if (selectedSources.length === 0) {
    return (
      <Box sx={{ maxWidth: 720, mx: 'auto', py: 4, textAlign: 'center' }}>
        <Typography
          component="h2"
          sx={{ fontFamily: '"Newsreader", Georgia, serif', fontStyle: 'italic', fontSize: '2rem', mb: 2 } as any}
        >
          Where does your news diet stand?
        </Typography>
        <Typography sx={{ color: tokens.inkMuted, mb: 4, textWrap: 'pretty' } as any}>
          Pick the 1&ndash;3 sources you actually read. We'll compare how they portray the entities they
          cover most against the global average across all tracked sources &mdash; not to score you, but
          to show you the distance between your daily read and the wider landscape. Your picks stay on
          this device.
        </Typography>
        <Paper sx={{ p: 3, textAlign: 'left', bgcolor: tokens.surfaceSunken, border: `1px solid ${tokens.border}` }}>
          {picker}
        </Paper>
      </Box>
    );
  }

  return (
    <Box>
      <Typography
        component="h2"
        sx={{ fontFamily: '"Newsreader", Georgia, serif', fontStyle: 'italic', fontSize: '2rem', mb: 1 } as any}
      >
        My Bubble
      </Typography>
      <Typography variant="body2" sx={{ color: tokens.inkMuted, mb: 3 }}>
        The filled dot is your source's reading, colored by quadrant. The gray dot is the all-time
        global average for that same entity. Line length is the distance between them &mdash; not a
        verdict on either.
      </Typography>

      <Paper sx={{ p: 2, mb: 4, bgcolor: tokens.surfaceSunken, border: `1px solid ${tokens.border}` }}>{picker}</Paper>

      {loadingCompare ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress size={28} />
        </Box>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <Card>
            <CardHeader
              title="Where your bubble diverges most"
              subheader="Entities ranked by the gap between your sources' average portrayal and the baseline. The colored dot is your bubble; the gray dot is the baseline."
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
              <Autocomplete
                size="small"
                options={[WORLD_BASELINE, ...availableCountries]}
                value={baseline}
                disableClearable
                onChange={(_, v) => setBaseline(v)}
                renderInput={(params) => <TextField {...params} label="Baseline" />}
                sx={{ maxWidth: 340, mb: 1 }}
              />
              {divergenceRows.length === 0 ? (
                <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 2 }}>
                  {countryMap
                    ? `No overlap between your sources' top entities and ${baseline}'s scored coverage.`
                    : 'No divergence signal yet — check back once more coverage has been analyzed.'}
                </Typography>
              ) : (
                <>
                  <Box
                    sx={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      px: 2,
                      color: tokens.inkMuted,
                      fontFamily: '"IBM Plex Mono", monospace',
                      fontSize: 10,
                    }}
                  >
                    <span style={{ width: 170, minWidth: 120 }} />
                    <Box sx={{ flex: 1, display: 'flex', justifyContent: 'space-between', minWidth: 160 }}>
                      <span>-2</span>
                      <span>0 = neutral</span>
                      <span>+2</span>
                    </Box>
                    <span style={{ minWidth: 56, textAlign: 'right' }}>Δ</span>
                  </Box>
                  {divergenceRows.map((row) => (
                    <DumbbellRow key={row.name} row={row} dimension={dimension} />
                  ))}
                  {skippedForBaseline > 0 && (
                    <Typography variant="caption" sx={{ display: 'block', mt: 1, color: tokens.inkMuted }}>
                      {skippedForBaseline} of your bubble's entities have no scored coverage from {baseline} and are
                      not shown.
                    </Typography>
                  )}
                </>
              )}
            </CardContent>
          </Card>

          {selectedSources.map((source) => (
            <SourceComparisonCard key={source.id} source={source} rows={comparisons[source.name] || []} />
          ))}
        </Box>
      )}
    </Box>
  );
};

export default MyBubblePage;
