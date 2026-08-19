import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate, Link as RouterLink } from 'react-router-dom';
import {
  Box,
  Typography,
  Chip,
  CircularProgress,
  Paper,
  Grid,
  Card,
  CardHeader,
  CardContent,
  Autocomplete,
  TextField,
  ToggleButtonGroup,
  ToggleButton,
} from '@mui/material';
import { useData } from '../context/DataContext';
import { entityApi, statsApi } from '../services/api';
import { isStaticMode } from '../services/config/environment';
import SentimentChart from '../components/SentimentChart';
import EntityInfoPlate, { ActiveEntityInfo } from '../components/EntityInfoPlate';
import SentimentDistributionChart, { DistributionLayer } from '../components/SentimentDistributionChart';
import MultiSourceTrendChart from '../components/MultiSourceTrendChart';
import { EntitySentimentSummary, NewsSource, TrendPoint } from '../types';
import { tokens } from '../theme';

// All-time window: the corpus is a bounded snapshot, so a wall-clock lookback
// can be empty long before the data is. 0 = ALL_TIME sentinel (omitted by api.ts).
const DAYS = 0;
const TOP_ENTITIES = 20;
// How deep into the baseline sphere's ranking we look before falling back to
// per-entity fetches; matches the exporter's TRENDING_LIMIT so static mode
// sees the same set.
const SPHERE_DEPTH = 100;

// Role colors, page-wide: the paper under examination is always accent, the
// chosen baseline always gray — the site's subject-vs-anchor idiom.
const SUBJECT_COLOR = tokens.accent;
const BASELINE_COLOR = tokens.inkMuted;
const GLOBAL_EXTRA_COLOR = tokens.categorical[1];

type CompareMode = 'global' | 'country' | 'source';

const SourceProfilePage: React.FC = () => {
  const { name } = useParams<{ name: string }>();
  const navigate = useNavigate();
  const { sources, meta, availableCountries, getSourceByName } = useData();
  const source = name ? getSourceByName(decodeURIComponent(name)) : undefined;

  // The page-wide comparison: every panel below reads against this baseline.
  const [compareMode, setCompareMode] = useState<CompareMode>('global');
  const [compareCountry, setCompareCountry] = useState<string | null>(null);
  const [compareSource, setCompareSource] = useState<NewsSource | null>(null);
  // Page-wide dimension for the distribution and history panels (the grid is
  // inherently two-dimensional and unaffected).
  const [dimension, setDimension] = useState<'power' | 'moral'>('moral');

  const [topEntities, setTopEntities] = useState<EntitySentimentSummary[]>([]);
  const [baselinePoints, setBaselinePoints] = useState<EntitySentimentSummary[]>([]);
  const [selected, setSelected] = useState<EntitySentimentSummary | null>(null);
  // The scatter's hovered/pinned reading, shown in the static plate above the
  // plot instead of a popup chasing the cursor.
  const [activeInfo, setActiveInfo] = useState<ActiveEntityInfo | null>(null);
  const [distLayers, setDistLayers] = useState<DistributionLayer[]>([]);
  const [historySeries, setHistorySeries] = useState<Record<string, TrendPoint[]>>({});

  const [loadingTop, setLoadingTop] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const baselineReady =
    compareMode === 'global' ||
    (compareMode === 'country' ? !!compareCountry : !!compareSource);
  const baselineLabel =
    compareMode === 'global'
      ? 'Global'
      : compareMode === 'country'
        ? (compareCountry ?? 'a country')
        : (compareSource?.name ?? 'another newspaper');
  // Distinct series key for the history chart; guaranteed != source.name
  // because the picker excludes the page's own paper.
  const baselineSeriesKey =
    compareMode === 'global'
      ? 'Global average'
      : compareMode === 'country'
        ? `${compareCountry} (all sources)`
        : (compareSource?.name ?? '');

  // Static mode only snapshots papers with enough scored mentions
  // (meta.trending_sources) — offering the rest would give empty comparisons.
  const newspaperOptions = useMemo(() => {
    const snapshotted =
      isStaticMode() && meta?.trending_sources ? new Set(meta.trending_sources) : null;
    return sources
      .filter((s) => s.id !== source?.id && (!snapshotted || snapshotted.has(s.id)))
      .slice()
      .sort(
        (a, b) =>
          (a.country || '').localeCompare(b.country || '') || a.name.localeCompare(b.name)
      );
  }, [sources, meta, source?.id]);

  // Every tracked paper, for the subject picker — unlike newspaperOptions this
  // includes the page's own paper (it's the picker's value) and skips the
  // static-snapshot filter, matching the doorways on the sources index.
  const paperOptions = useMemo(
    () =>
      sources
        .slice()
        .sort(
          (a, b) =>
            (a.country || '').localeCompare(b.country || '') || a.name.localeCompare(b.name)
        ),
    [sources]
  );

  // Jumping to the paper currently serving as the baseline would compare it
  // against itself; fall back to the global baseline instead.
  useEffect(() => {
    if (source && compareSource && compareSource.id === source.id) {
      setCompareSource(null);
      setCompareMode('global');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source?.id]);

  const handleModeChange = (mode: CompareMode | null) => {
    if (!mode) return;
    setCompareMode(mode);
    if (mode === 'country' && !compareCountry && source) {
      // The divergence people actually wonder about first: the paper vs its own country.
      setCompareCountry(availableCountries.includes(source.country) ? source.country : null);
    }
  };

  // ---- The paper's top entities (the grid's subject set) -------------------
  useEffect(() => {
    if (!source) return;
    let cancelled = false;
    setLoadingTop(true);
    // The subject changed under the plate; a pinned reading from the previous
    // paper would be wrong here.
    setActiveInfo(null);
    statsApi
      .getTrendingEntities(TOP_ENTITIES, DAYS || undefined, undefined, source.id)
      .then((rows: EntitySentimentSummary[]) => {
        if (cancelled) return;
        setTopEntities(rows);
        setSelected((prev) =>
          prev && rows.some((r) => r.id === prev.id) ? prev : (rows[0] ?? null)
        );
      })
      .catch(() => {
        if (!cancelled) setTopEntities([]);
      })
      .finally(() => {
        if (!cancelled) setLoadingTop(false);
      });
    return () => {
      cancelled = true;
    };
  }, [source?.id]);

  // ---- The baseline's reading of those same entities -----------------------
  useEffect(() => {
    if (!source || topEntities.length === 0 || !baselineReady) {
      setBaselinePoints([]);
      return;
    }
    let cancelled = false;

    // For a top entity outside the sphere's top ranking, ask for just that
    // entity's baseline layer (cheap since the layers param skips the global
    // KDE). null = the sphere genuinely has too little on it — the grid then
    // shows the paper's point without an anchor, which is itself the finding.
    const fillOne = async (e: EntitySentimentSummary): Promise<EntitySentimentSummary | null> => {
      if (e.id == null) return null;
      try {
        if (compareMode === 'global') {
          const hist = await statsApi.getHistoricalSentiment(e.id, { days: DAYS });
          const s = hist?.summary;
          if (s && s.total_mentions > 0) {
            return { ...e, power_score: s.avg_power_score, moral_score: s.avg_moral_score, mention_count: s.total_mentions };
          }
        } else if (compareMode === 'country' && compareCountry) {
          const res = await entityApi.getEntityDistribution(e.id, compareCountry, undefined, undefined, 'national');
          const n = res?.distributions?.national;
          if (n) return { ...e, power_score: n.power.mean, moral_score: n.moral.mean, mention_count: n.power.count };
        } else if (compareMode === 'source' && compareSource) {
          const res = await entityApi.getEntityDistribution(e.id, undefined, compareSource.id, undefined, 'source');
          const s = res?.distributions?.source;
          if (s) return { ...e, power_score: s.power.mean, moral_score: s.moral.mean, mention_count: s.power.count };
        }
      } catch {
        // no baseline reading for this entity
      }
      return null;
    };

    (async () => {
      try {
        const sphere: EntitySentimentSummary[] =
          compareMode === 'global'
            ? await statsApi.getTrendingEntities(SPHERE_DEPTH, DAYS || undefined)
            : compareMode === 'country'
              ? await statsApi.getTrendingEntities(SPHERE_DEPTH, DAYS || undefined, compareCountry!)
              : await statsApi.getTrendingEntities(SPHERE_DEPTH, DAYS || undefined, undefined, compareSource!.id);

        const byId = new Map(sphere.filter((r) => r.id != null).map((r) => [r.id, r]));
        const byName = new Map(sphere.map((r) => [r.entity.toLowerCase(), r]));

        const matched: EntitySentimentSummary[] = [];
        const missing: EntitySentimentSummary[] = [];
        for (const e of topEntities) {
          const hit = (e.id != null ? byId.get(e.id) : undefined) ?? byName.get(e.entity.toLowerCase());
          if (hit) {
            matched.push({ ...e, power_score: hit.power_score, moral_score: hit.moral_score, mention_count: hit.mention_count });
          } else {
            missing.push(e);
          }
        }
        const filled = (await Promise.all(missing.map(fillOne))).filter(
          (r): r is EntitySentimentSummary => r != null
        );
        if (!cancelled) setBaselinePoints([...matched, ...filled]);
      } catch {
        if (!cancelled) setBaselinePoints([]);
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source?.id, topEntities, compareMode, compareCountry, compareSource?.id]);

  // ---- Distribution + history for the selected entity ----------------------
  useEffect(() => {
    if (!source || !selected || selected.id == null || !baselineReady) {
      setDistLayers([]);
      setHistorySeries({});
      setLoadingDetail(false);
      return;
    }
    let cancelled = false;
    setLoadingDetail(true);
    const entityId = selected.id;

    const loadDistribution = async (): Promise<DistributionLayer[]> => {
      // One call carries the paper's own curve plus global (and national when
      // the baseline is a country); a second cheap call fetches the other
      // paper's curve when the baseline is a newspaper.
      const res = await entityApi
        .getEntityDistribution(entityId, compareMode === 'country' ? compareCountry! : undefined, source.id, DAYS || undefined)
        .catch(() => null);
      const d = res?.distributions ?? {};
      const layers: DistributionLayer[] = [];

      if (compareMode === 'global' && d.global) {
        layers.push({ key: 'baseline', label: 'Global', color: BASELINE_COLOR, power: d.global.power, moral: d.global.moral });
      } else if (compareMode === 'country' && d.national) {
        layers.push({ key: 'baseline', label: compareCountry!, color: BASELINE_COLOR, power: d.national.power, moral: d.national.moral });
      } else if (compareMode === 'source' && compareSource) {
        const other = await entityApi
          .getEntityDistribution(entityId, undefined, compareSource.id, DAYS || undefined, 'source')
          .catch(() => null);
        const s = other?.distributions?.source;
        if (s) layers.push({ key: 'baseline', label: compareSource.name, color: BASELINE_COLOR, power: s.power, moral: s.moral });
      }

      if (d.source) {
        layers.push({ key: 'subject', label: source.name, color: SUBJECT_COLOR, power: d.source.power, moral: d.source.moral });
      }
      // Global stays available as an extra chip when it isn't the baseline.
      if (compareMode !== 'global' && d.global) {
        layers.push({ key: 'global', label: 'Global', color: GLOBAL_EXTRA_COLOR, power: d.global.power, moral: d.global.moral });
      }
      return layers;
    };

    const loadBaselineHistory = async (): Promise<TrendPoint[]> => {
      if (compareMode === 'global') {
        const hist = await statsApi.getHistoricalSentiment(entityId, { days: DAYS });
        return hist?.daily_data ?? [];
      }
      if (compareMode === 'country') {
        // Without a countries filter the endpoint aggregates per country —
        // exactly the national average line we want (both live and static).
        const res = await statsApi.getSourceHistoricalSentiment(entityId, { days: DAYS });
        return res?.sources?.[compareCountry!]?.daily_data ?? [];
      }
      return statsApi.getSourceEntityHistory(compareSource!, entityId, { days: DAYS });
    };

    (async () => {
      const [layers, subjectDaily, baselineDaily] = await Promise.all([
        loadDistribution().catch(() => [] as DistributionLayer[]),
        statsApi.getSourceEntityHistory(source, entityId, { days: DAYS }).catch(() => [] as TrendPoint[]),
        loadBaselineHistory().catch(() => [] as TrendPoint[]),
      ]);
      if (cancelled) return;
      setDistLayers(layers);
      const series: Record<string, TrendPoint[]> = {};
      if (baselineDaily.length) series[baselineSeriesKey] = baselineDaily;
      if (subjectDaily.length) series[source.name] = subjectDaily;
      setHistorySeries(series);
      setLoadingDetail(false);
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source?.id, selected?.id, compareMode, compareCountry, compareSource?.id]);

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

  // Remount key for the distribution chart: resets its layer-visibility chips
  // whenever the comparison context changes.
  const comparisonKey = `${selected?.id}-${compareMode}-${compareCountry}-${compareSource?.id}`;

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
        The entities this paper covers most, read against a baseline of your choice — the world,
        one country's press, or another newspaper. Distance is divergence, not a verdict. The
        baseline, dimension, and selected entity apply to every panel on this page.
      </Typography>

      {/* Page-wide controls: which paper (navigates), then baseline, dimension, entity. */}
      <Paper sx={{ p: 2, mb: 4, bgcolor: tokens.surfaceSunken, border: `1px solid ${tokens.border}` }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} sm={6} md={3}>
            <Autocomplete
              size="small"
              options={paperOptions}
              groupBy={(s) => s.country || 'Other'}
              getOptionLabel={(s) => s.name}
              isOptionEqualToValue={(a, b) => a.id === b.id}
              value={source}
              disableClearable
              onChange={(_, v) => v && navigate(`/coverage/newspapers/${encodeURIComponent(v.name)}`)}
              renderInput={(params) => <TextField {...params} label="Newspaper" />}
            />
          </Grid>
          <Grid item xs={12} md="auto">
            <ToggleButtonGroup
              size="small"
              exclusive
              value={compareMode}
              onChange={(_, v: CompareMode | null) => handleModeChange(v)}
              aria-label="comparison baseline"
            >
              <ToggleButton value="global">vs Global</ToggleButton>
              <ToggleButton value="country">vs Country</ToggleButton>
              <ToggleButton value="source">vs Newspaper</ToggleButton>
            </ToggleButtonGroup>
          </Grid>
          {compareMode === 'country' && (
            <Grid item xs={12} sm={6} md={3}>
              <Autocomplete
                size="small"
                options={availableCountries}
                value={compareCountry}
                onChange={(_, v) => setCompareCountry(v)}
                renderInput={(params) => <TextField {...params} label="Country baseline" />}
              />
            </Grid>
          )}
          {compareMode === 'source' && (
            <Grid item xs={12} sm={6} md={3}>
              <Autocomplete
                size="small"
                options={newspaperOptions}
                groupBy={(s) => s.country || 'Other'}
                getOptionLabel={(s) => s.name}
                isOptionEqualToValue={(a, b) => a.id === b.id}
                value={compareSource}
                onChange={(_, v) => setCompareSource(v)}
                renderInput={(params) => <TextField {...params} label="Newspaper baseline" />}
              />
            </Grid>
          )}
          <Grid item xs={12} sm={6} md="auto">
            <ToggleButtonGroup
              size="small"
              exclusive
              value={dimension}
              onChange={(_, v: 'power' | 'moral' | null) => v != null && setDimension(v)}
              aria-label="sentiment dimension"
            >
              <ToggleButton value="power">Power</ToggleButton>
              <ToggleButton value="moral">Moral</ToggleButton>
            </ToggleButtonGroup>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Autocomplete
              size="small"
              options={topEntities}
              getOptionLabel={(e) => e.entity}
              isOptionEqualToValue={(a, b) => a.id === b.id}
              value={selected}
              onChange={(_, v) => v && setSelected(v)}
              disableClearable={selected != null}
              renderInput={(params) => <TextField {...params} label="Focus entity" />}
            />
          </Grid>
        </Grid>
      </Paper>

      {loadingTop ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
          <CircularProgress size={24} />
        </Box>
      ) : topEntities.length === 0 ? (
        <Box
          sx={{
            p: 4,
            textAlign: 'center',
            bgcolor: tokens.surfaceSunken,
            borderRadius: 1,
            border: `1px dashed ${tokens.border}`,
          }}
        >
          <Typography variant="body2" sx={{ color: tokens.inkMuted }}>
            Not enough scored coverage from {source.name} yet to map its top entities — check back
            once more of its articles have been analyzed.
          </Typography>
        </Box>
      ) : (
        <Grid container spacing={4}>
          <Grid item xs={12}>
            <Card>
              <CardHeader
                title={`Top ${topEntities.length} entities — drift from ${baselineLabel}`}
                subheader={
                  baselineReady
                    ? `Colored: ${source.name}'s reading, hued by drift direction — green toward Hero, red toward Villain, purple Victim, orange Wretch. Gray: ${baselineLabel}. The dashed line between a pair is the drift; click a dot to focus that entity below.`
                    : `Pick a ${compareMode === 'country' ? 'country' : 'newspaper'} above to anchor the comparison.`
                }
              />
              <CardContent>
                {/* Static reading plate, right-aligned with the plot edge. */}
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
                  <EntityInfoPlate info={activeInfo} />
                </Box>
                <SentimentChart
                  data={baselineReady ? baselinePoints : []}
                  overlay={{ label: source.name, data: topEntities }}
                  includeUnmatchedOverlay
                  baselineLabel={baselineLabel}
                  height={520}
                  showLabels
                  selectedEntity={selected?.entity ?? null}
                  onEntityClick={(p) => {
                    const row = topEntities.find((t) => t.entity === p.entity);
                    if (row) setSelected(row);
                  }}
                  onActiveChange={setActiveInfo}
                />
                <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted, px: 2 }}>
                  A dark dot without a gray anchor means {baselineLabel} has too few scored
                  mentions of that entity to compare — no drift to color.
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          {selected && (
            <>
              <Grid item xs={12} md={5}>
                <Card>
                  <CardHeader
                    title="Sentiment spread"
                    subheader={`Every scored mention of ${selected.entity}, as a distribution — ${source.name} overlaid on ${baselineLabel}`}
                  />
                  <CardContent>
                    {loadingDetail ? (
                      <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                        <CircularProgress size={24} />
                      </Box>
                    ) : distLayers.length > 0 ? (
                      <SentimentDistributionChart
                        key={comparisonKey}
                        layers={distLayers}
                        entityName={selected.entity}
                        title="Distribution"
                        dimension={dimension}
                        initiallyHidden={['global']}
                        height={400}
                      />
                    ) : (
                      <Box sx={{ py: 6, textAlign: 'center' }}>
                        <Typography variant="body2" sx={{ color: tokens.inkMuted }}>
                          No distribution data for {selected.entity} in this comparison
                          {isStaticMode() ? ' (not part of the static snapshot)' : ''}.
                        </Typography>
                      </Box>
                    )}
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={7}>
                <Card>
                  <CardHeader
                    title="Reporting history"
                    subheader={`${source.name}'s daily average on ${selected.entity} against ${baselineLabel}`}
                  />
                  <CardContent>
                    {loadingDetail ? (
                      <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                        <CircularProgress size={24} />
                      </Box>
                    ) : (
                      <Box sx={{ height: 440 }}>
                        <MultiSourceTrendChart
                          entityName={selected.entity}
                          sourcesTrends={historySeries}
                          controlledDimension={dimension}
                          colors={{
                            [source.name]: SUBJECT_COLOR,
                            [baselineSeriesKey]: BASELINE_COLOR,
                          }}
                          height={440}
                        />
                      </Box>
                    )}
                  </CardContent>
                </Card>
              </Grid>
            </>
          )}
        </Grid>
      )}

      <Box sx={{ mt: 4 }}>
        <RouterLink to="/coverage/newspapers" style={{ color: tokens.accent, fontSize: '0.875rem' }}>
          &larr; Back to all sources
        </RouterLink>
      </Box>
    </Box>
  );
};

export default SourceProfilePage;
