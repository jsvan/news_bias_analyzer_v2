import React, { useEffect, useMemo, useState } from 'react';
import { Box, Card, CardHeader, CardContent, CircularProgress, Typography } from '@mui/material';
import { narrativeApi } from '../services/api';
import { isStaticMode } from '../services/config/environment';
import SentimentChart from './SentimentChart';
import EntityInfoPlate, { ActiveEntityInfo } from './EntityInfoPlate';
import ReceiptsDrawer, { ReceiptsFilter } from './ReceiptsDrawer';
import TimeRangeSelect, { ALL_TIME } from './TimeRangeSelect';
import { EntitySentimentSummary, EntitySourceScatter, EntitySourceScatterPoint } from '../types';
import { tokens } from '../theme';

// The single-entity transpose of the global entity scatter: same chart, but
// each dot is one SOURCE's reading of this entity. Default view is averages
// only — each paper's all-time mean placement, no comparison. Picking a window
// from the dropdown turns on the drift comparison, which is temporal, not
// spatial: baseline = the same source's previous window of the selected
// length, so the dashed connector shows which way each newsroom moved.

const WINDOW_OPTIONS = [7, 14, 30, 60, 90];
// Static snapshots bake exactly two responses: the all-time averages (the
// default view) and one 4-week drift window — so the static picker clamps to
// those two choices, the same honesty pattern as the static-mode country
// pickers.
const STATIC_WINDOW = 30;

// Short window names for the info plate and copy: "Last month · Power …",
// "No Previous month reading to compare" — LABELS in TimeRangeSelect are
// picker-shaped ("Last 30 days"), not phrase-shaped.
const WINDOW_NOUN: Record<number, string> = {
  7: 'week',
  14: '2 weeks',
  30: 'month',
  60: '2 months',
  90: '3 months',
};

// mv_source_entity_week aggregates by ISO week — the API takes whole weeks.
// ALL_TIME (0) passes through as weeks=0, the endpoint's all-time sentinel.
const daysToWeeks = (days: number) =>
  days === ALL_TIME ? 0 : Math.max(1, Math.round(days / 7));

// SentimentChart joins baseline/overlay pairs on the `entity` name string, so
// a source's two windows pair up by carrying its name in that field.
const toSummary = (p: EntitySourceScatterPoint): EntitySentimentSummary => ({
  id: p.source_id,
  entity: p.source_name,
  type: p.country ?? undefined,
  power_score: p.power_score,
  moral_score: p.moral_score,
  mention_count: p.mention_count,
});

const EntitySourceScatterPanel: React.FC<{ entityId: number; entityName: string }> = ({
  entityId,
  entityName,
}) => {
  const staticMode = isStaticMode();
  const [days, setDays] = useState(ALL_TIME);
  const [scatter, setScatter] = useState<EntitySourceScatter | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeInfo, setActiveInfo] = useState<ActiveEntityInfo | null>(null);
  const [receiptsFor, setReceiptsFor] = useState<ReceiptsFilter | null>(null);

  const drift = days !== ALL_TIME;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setScatter(null);
    narrativeApi
      .getEntitySourceScatter(entityId, { weeks: daysToWeeks(days) })
      .then((res) => {
        if (!cancelled) setScatter(res);
      })
      .catch(() => {
        if (!cancelled) setScatter(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [entityId, days]);

  const noun = WINDOW_NOUN[days] ?? `${days} days`;
  const previous = useMemo(
    () => (scatter?.previous.sources ?? []).map(toSummary),
    [scatter]
  );
  const current = useMemo(
    () => (scatter?.current.sources ?? []).map(toSummary),
    [scatter]
  );
  // Averages mode plots the (all-time) current window as the baseline itself —
  // SentimentChart with no overlay draws plain archetype-colored dots.
  const chartData = drift ? previous : current;
  const overlay = useMemo(
    () => (drift ? { label: `Last ${noun}`, data: current } : null),
    [drift, noun, current]
  );

  // Mirrors SentimentChart's own >=5-dot floor (baseline + unmatched overlay)
  // so the thin case gets source-worded copy instead of the chart's
  // entity-worded empty state.
  const drawableDots = useMemo(() => {
    if (!drift) return current.length;
    const prevNames = new Set(previous.map((p) => p.entity));
    return previous.length + current.filter((c) => !prevNames.has(c.entity)).length;
  }, [drift, previous, current]);

  return (
    <Card>
      <CardHeader
        title={`Where Each Source Places ${entityName}`}
        subheader={
          !drift
            ? scatter?.current.start
              ? `Each dot is one newspaper's average reading across all scored coverage (${scatter.current.start} to ${scatter.current.end}).`
              : `Each dot is one newspaper's average reading across all scored coverage.`
            : scatter?.current.start
              ? `Each dot is one newspaper's average reading over ${scatter.current.start} to ${scatter.current.end}; its gray anchor is the same paper over ${scatter.previous.start} to ${scatter.previous.end}.`
              : `Each dot is one newspaper's average reading over the last ${noun}; its gray anchor is the same paper one ${noun}-window earlier.`
        }
      />
      <CardContent>
        {/* Controls stay mounted through refetches so the picker never
            vanishes mid-interaction; plate right-aligned with the plot edge. */}
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2, flexWrap: 'wrap', mb: 1 }}>
          <Box sx={{ minWidth: 190 }}>
            <TimeRangeSelect
              value={days}
              onChange={setDays}
              options={staticMode ? [STATIC_WINDOW] : WINDOW_OPTIONS}
              allowAllTime
              allTimeLabel="Average (all time)"
              label="Compare window"
            />
          </Box>
          <EntityInfoPlate info={activeInfo} sx={{ ml: 'auto' }} />
        </Box>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
            <CircularProgress size={24} />
          </Box>
        ) : drawableDots < 5 ? (
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
              Too few sources with enough scored mentions of {entityName}
              {drift ? ` in the last ${noun}` : ''} to draw a meaningful spread (at
              least 5 needed, each with 3+ scored mentions).
              {drift ? ' Try a wider window.' : ''}
            </Typography>
          </Box>
        ) : (
          <>
            <SentimentChart
              data={chartData}
              overlay={overlay}
              includeUnmatchedOverlay
              baselineLabel={drift ? `Previous ${noun}` : 'All time'}
              height={520}
              showLabels
              onActiveChange={setActiveInfo}
              onEntityClick={(p) => {
                // Dots here are sources (toSummary), so id is the source_id.
                if (p.id != null) {
                  setReceiptsFor({
                    entityId, entityName, sourceId: p.id, sourceName: p.entity,
                  });
                }
              }}
            />
            <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted, px: 2 }}>
              Hover a dot to read that newspaper's scoring in the plate above; click it to
              open the receipts — the actual headlines behind that average.{' '}
              {drift ? (
                <>
                  Dot color = drift direction since the previous {noun}-window (green toward
                  Hero, red toward Villain, purple Victim, orange Wretch). A dark dot without
                  a gray anchor is a paper with too few scored mentions back then to compare;
                  a lone gray dot is a paper that has since gone quiet on {entityName}.
                </>
              ) : (
                <>
                  Dot color = the quadrant that paper places {entityName} in (green Hero,
                  red Villain, purple Victim, orange Wretch). Pick a compare window above to
                  see which way each paper has drifted recently.
                </>
              )}
            </Typography>
          </>
        )}
      </CardContent>
      <ReceiptsDrawer filter={receiptsFor} onClose={() => setReceiptsFor(null)} />
    </Card>
  );
};

export default EntitySourceScatterPanel;
