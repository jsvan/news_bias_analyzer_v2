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
} from '@mui/material';
import { useData } from '../context/DataContext';
import { statsApi } from '../services/api';
import { NewsSource, CountryEntityData } from '../types';
import { tokens, archetypeColor, monoNumber } from '../theme';

const STORAGE_KEY = 'newsbias:my-sources';
const MAX_SOURCES = 3;
// All-time window: the corpus is a bounded snapshot, so a wall-clock lookback
// (e.g. last 30 days) can be empty long before the data is. 0 = ALL_TIME sentinel.
const DAYS = 0;
const GLYPH_SIZE = 56;

interface EntityComparison {
  name: string;
  type: string;
  sourcePower: number;
  sourceMoral: number;
  globalPower: number;
  globalMoral: number;
}

// Maps a -1..1 power/moral pair onto the glyph's pixel frame (y flipped: moral up = positive).
const toXY = (power: number, moral: number) => {
  const p = Math.max(-1, Math.min(1, power));
  const m = Math.max(-1, Math.min(1, moral));
  const pad = 8;
  const usable = (GLYPH_SIZE - pad * 2) / 2;
  return { x: GLYPH_SIZE / 2 + p * usable, y: GLYPH_SIZE / 2 - m * usable };
};

// Small power/moral scatter reused from the site's own quadrant metaphor: the filled
// dot (your source, archetype-colored) and the gray dot (global average) plus the
// connecting line make the divergence legible without implying either is "correct".
const DivergenceGlyph: React.FC<{ sourcePower: number; sourceMoral: number; globalPower: number; globalMoral: number }> = ({
  sourcePower,
  sourceMoral,
  globalPower,
  globalMoral,
}) => {
  const s = toXY(sourcePower, sourceMoral);
  const g = toXY(globalPower, globalMoral);
  const mid = GLYPH_SIZE / 2;
  return (
    <svg width={GLYPH_SIZE} height={GLYPH_SIZE} viewBox={`0 0 ${GLYPH_SIZE} ${GLYPH_SIZE}`} style={{ flexShrink: 0 }}>
      <line x1={mid} y1={0} x2={mid} y2={GLYPH_SIZE} stroke={tokens.border} strokeWidth={1} />
      <line x1={0} y1={mid} x2={GLYPH_SIZE} y2={mid} stroke={tokens.border} strokeWidth={1} />
      <line x1={g.x} y1={g.y} x2={s.x} y2={s.y} stroke={tokens.inkMuted} strokeWidth={1.25} strokeDasharray="2 2" />
      <circle cx={g.x} cy={g.y} r={3.5} fill={tokens.inkMuted} />
      <circle cx={s.x} cy={s.y} r={4} fill={archetypeColor(sourcePower, sourceMoral)} stroke={tokens.surface} strokeWidth={1} />
    </svg>
  );
};

const SourceComparisonCard: React.FC<{ source: NewsSource; rows: EntityComparison[] }> = ({ source, rows }) => (
  <Card>
    <CardHeader
      title={source.name}
      subheader={source.country && source.country !== 'Unknown' ? source.country : undefined}
    />
    <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
      {rows.length === 0 ? (
        <Box
          sx={{
            m: 2,
            p: 3,
            textAlign: 'center',
            bgcolor: tokens.surfaceSunken,
            borderRadius: 1,
            border: `1px dashed ${tokens.border}`,
          }}
        >
          <Typography variant="body2" sx={{ color: tokens.inkMuted }}>
            No divergence signal yet for {source.name} &mdash; check back once more coverage has been analyzed.
          </Typography>
        </Box>
      ) : (
        rows.map((row, idx) => {
          const delta = Math.hypot(row.sourcePower - row.globalPower, row.sourceMoral - row.globalMoral);
          return (
            <Box
              key={row.name}
              sx={{
                display: 'flex',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: 2,
                px: 2,
                py: 1.5,
                borderTop: idx === 0 ? 'none' : `1px solid ${tokens.border}`,
                '&:hover': { bgcolor: tokens.surfaceSunken },
              }}
            >
              <DivergenceGlyph
                sourcePower={row.sourcePower}
                sourceMoral={row.sourceMoral}
                globalPower={row.globalPower}
                globalMoral={row.globalMoral}
              />
              <Box sx={{ flex: 1, minWidth: 140 }}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {row.name}
                </Typography>
                <Chip
                  label={row.type}
                  size="small"
                  variant="outlined"
                  sx={{ mt: 0.5, borderColor: tokens.border, color: tokens.inkMuted }}
                />
              </Box>
              <Box sx={{ textAlign: 'right', minWidth: 128 }}>
                <Typography variant="caption" sx={{ color: tokens.inkMuted, display: 'block' }}>
                  Your source
                </Typography>
                <Typography sx={{ ...monoNumber, color: tokens.ink }}>
                  P {row.sourcePower.toFixed(2)} &middot; M {row.sourceMoral.toFixed(2)}
                </Typography>
              </Box>
              <Box sx={{ textAlign: 'right', minWidth: 128 }}>
                <Typography variant="caption" sx={{ color: tokens.inkMuted, display: 'block' }}>
                  Global average
                </Typography>
                <Typography sx={{ ...monoNumber, color: tokens.ink }}>
                  P {row.globalPower.toFixed(2)} &middot; M {row.globalMoral.toFixed(2)}
                </Typography>
              </Box>
              <Box sx={{ textAlign: 'right', minWidth: 64 }}>
                <Typography variant="caption" sx={{ color: tokens.inkMuted, display: 'block' }}>
                  Divergence
                </Typography>
                <Typography sx={{ ...monoNumber, fontWeight: 600, color: tokens.ink }}>{delta.toFixed(2)}</Typography>
              </Box>
            </Box>
          );
        })
      )}
    </CardContent>
  </Card>
);

const MyBubblePage: React.FC = () => {
  const { sources, entities } = useData();

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
          {selectedSources.map((source) => (
            <SourceComparisonCard key={source.id} source={source} rows={comparisons[source.name] || []} />
          ))}
        </Box>
      )}
    </Box>
  );
};

export default MyBubblePage;
