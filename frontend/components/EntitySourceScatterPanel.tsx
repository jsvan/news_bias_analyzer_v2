import React, { useEffect, useMemo, useState } from 'react';
import { Box, Card, CardHeader, CardContent, CircularProgress, Typography } from '@mui/material';
import { narrativeApi } from '../services/api';
import { isStaticMode } from '../services/config/environment';
import SentimentChart from './SentimentChart';
import EntityInfoPlate, { ActiveEntityInfo } from './EntityInfoPlate';
import TimeRangeSelect from './TimeRangeSelect';
import { EntitySentimentSummary, EntitySourceScatter, EntitySourceScatterPoint } from '../types';
import { tokens } from '../theme';

// The single-entity transpose of the global entity scatter: same chart, but
// each dot is one SOURCE's reading of this entity. The drift comparison is
// temporal, not spatial — baseline = the same source's previous window of the
// selected length, so the dashed connector shows which way each newsroom moved.

const WINDOW_OPTIONS = [7, 14, 30, 60, 90];
const DEFAULT_WINDOW = 30;

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
const daysToWeeks = (days: number) => Math.max(1, Math.round(days / 7));

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
  // Static snapshots bake exactly one window (the 4-week default) — clamp the
  // picker there, the same honesty pattern as the static-mode country pickers.
  const staticMode = isStaticMode();
  const [days, setDays] = useState(DEFAULT_WINDOW);
  const [scatter, setScatter] = useState<EntitySourceScatter | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeInfo, setActiveInfo] = useState<ActiveEntityInfo | null>(null);

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
  const overlay = useMemo(
    () => ({ label: `Last ${noun}`, data: current }),
    [noun, current]
  );

  // Mirrors SentimentChart's own >=5-dot floor (baseline + unmatched overlay)
  // so the thin case gets source-worded copy instead of the chart's
  // entity-worded empty state.
  const drawableDots = useMemo(() => {
    const prevNames = new Set(previous.map((p) => p.entity));
    return previous.length + current.filter((c) => !prevNames.has(c.entity)).length;
  }, [previous, current]);

  return (
    <Card>
      <CardHeader
        title={`Where Each Source Places ${entityName}`}
        subheader={
          scatter?.current.start
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
              options={staticMode ? [DEFAULT_WINDOW] : WINDOW_OPTIONS}
              allowAllTime={false}
              disabled={staticMode}
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
              Too few sources with enough scored mentions of {entityName} in the last{' '}
              {noun} to draw a meaningful spread (at least 5 needed, each with 3+ scored
              mentions). Try a wider window.
            </Typography>
          </Box>
        ) : (
          <>
            <SentimentChart
              data={previous}
              overlay={overlay}
              includeUnmatchedOverlay
              baselineLabel={`Previous ${noun}`}
              height={520}
              showLabels
              onActiveChange={setActiveInfo}
            />
            <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted, px: 2 }}>
              Hover a dot to read that newspaper's scoring in the plate above; click to pin,
              click anywhere to release. Dot color = drift direction since the previous{' '}
              {noun}-window (green toward Hero, red toward Villain, purple Victim, orange
              Wretch). A dark dot without a gray anchor is a paper with too few scored
              mentions back then to compare; a lone gray dot is a paper that has since gone
              quiet on {entityName}.
            </Typography>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default EntitySourceScatterPanel;
