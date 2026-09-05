import React, { useEffect, useMemo, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Box, Button, Card, CardContent, CardHeader, Chip, Link, Typography,
} from '@mui/material';
import { useData } from '../context/DataContext';
import { driftApi } from '../services/api';
import ReceiptsDrawer, { ReceiptsFilter } from '../components/ReceiptsDrawer';
import { DriftFeedEntry, NewsSource } from '../types';
import { tokens, monoNumber, fontDisplay } from '../theme';

// The seismograph: one strip per country's press, time on x, a tick wherever a
// paper's changepoint fired. A vertical line of ticks across strips is a
// coordinated shift; a scattered pattern is organic drift. Below it, the drift
// feed as a table with receipts. Data: the precomputed entity_drift_events
// feed (analyzer/drift_detection.py's weekly Pettitt job).

// The recovered corpus's first scored week — the seismograph's left edge.
const CORPUS_START = '2026-07-13';
const FEED_LIMIT = 100;

const dayMs = 24 * 3600 * 1000;

const upColor = tokens.hero;
const downColor = tokens.villain;

interface StripRow {
  label: string;
  paperCount: number | null; // null for the Global strip
}

const Seismograph: React.FC<{ events: DriftFeedEntry[]; sources: NewsSource[] }> = ({
  events,
  sources,
}) => {
  const { rows, ticks, months, W, H, padL } = useMemo(() => {
    // Strips: Global first, then countries by tracked-paper count.
    const papersByCountry = new Map<string, NewsSource[]>();
    sources.forEach((s) => {
      const c = s.country || 'Other';
      if (!papersByCountry.has(c)) papersByCountry.set(c, []);
      papersByCountry.get(c)!.push(s);
    });
    const countries = [...papersByCountry.keys()].sort(
      (a, b) =>
        papersByCountry.get(b)!.length - papersByCountry.get(a)!.length || a.localeCompare(b)
    );
    const rows: StripRow[] = [
      { label: 'Global', paperCount: null },
      ...countries.map((c) => ({ label: c, paperCount: papersByCountry.get(c)!.length })),
    ];
    const rowIndex = new Map(rows.map((r, i) => [r.label, i]));
    const countryOf = new Map(sources.map((s) => [s.id, s.country || 'Other']));
    const paperIndex = new Map(
      sources.map((s) => [
        s.id,
        papersByCountry.get(s.country || 'Other')!.findIndex((p) => p.id === s.id),
      ])
    );

    // Time domain: corpus start → now (weeks fire at their Monday).
    const start = Date.parse(`${CORPUS_START}T00:00:00Z`);
    const end = Math.max(
      Date.now(),
      ...events.map((e) => Date.parse(`${e.week_start}T00:00:00Z`) + 7 * dayMs)
    );
    const padL = 96;
    const padR = 14;
    const padT = 22;
    const rowH = 17;
    const W = 1000;
    const plotW = W - padL - padR;
    const H = padT + rows.length * rowH + 6;
    const x = (iso: string) =>
      padL + ((Date.parse(`${iso}T00:00:00Z`) - start) / (end - start)) * plotW;

    const ticks = events
      .map((e) => {
        const row =
          e.source_id == null
            ? 0
            : rowIndex.get(countryOf.get(e.source_id) ?? 'Other');
        if (row == null) return null;
        // Same-week same-country events fan out horizontally by paper slot so
        // multiplicity stays visible instead of overprinting.
        const slot = e.source_id == null ? 0 : (paperIndex.get(e.source_id) ?? 0) % 5;
        return {
          key: `${e.entity_id}-${e.source_id ?? 'g'}-${e.week_start}-${e.dimension}`,
          x: x(e.week_start) + (slot - 2) * 2.2,
          y: padT + row * rowH,
          rowH,
          up: e.mean_after >= e.mean_before,
          title:
            `${e.entity_name} — ${e.source_name ?? 'whole corpus'}, week of ${e.week_start}: ` +
            `${e.mean_before.toFixed(2)} → ${e.mean_after.toFixed(2)} ` +
            `(p=${e.p_value < 0.001 ? '<0.001' : e.p_value.toFixed(3)})`,
        };
      })
      .filter(Boolean) as {
      key: string; x: number; y: number; rowH: number; up: boolean; title: string;
    }[];

    // Month gridlines across the domain.
    const months: { x: number; label: string }[] = [];
    const cursor = new Date(start);
    cursor.setUTCDate(1);
    cursor.setUTCMonth(cursor.getUTCMonth() + 1);
    while (cursor.getTime() < end) {
      months.push({
        x: padL + ((cursor.getTime() - start) / (end - start)) * plotW,
        label: cursor.toLocaleDateString(undefined, { month: 'short', timeZone: 'UTC' }),
      });
      cursor.setUTCMonth(cursor.getUTCMonth() + 1);
    }

    return { rows, ticks, months, W, H, padL };
  }, [events, sources]);

  return (
    <Box sx={{ overflowX: 'auto' }}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ minWidth: 640, display: 'block' }}>
        {rows.map((r, i) => (
          <g key={r.label}>
            {i % 2 === 1 && (
              <rect
                x={0}
                y={22 + i * 17}
                width={W}
                height={17}
                fill={tokens.surfaceSunken}
              />
            )}
            <text
              x={padL - 8}
              y={22 + i * 17 + 12}
              textAnchor="end"
              fontSize={10}
              fill={r.paperCount == null ? tokens.ink : tokens.inkMuted}
              fontFamily='"IBM Plex Sans", sans-serif'
              fontWeight={r.paperCount == null ? 600 : 400}
            >
              {r.label}
            </text>
          </g>
        ))}
        {months.map((m) => (
          <g key={m.label + m.x}>
            <line x1={m.x} y1={22} x2={m.x} y2={H - 6} stroke={tokens.border} strokeWidth={1} />
            <text
              x={m.x + 3}
              y={14}
              fontSize={10}
              fill={tokens.inkMuted}
              fontFamily='"IBM Plex Mono", monospace'
            >
              {m.label}
            </text>
          </g>
        ))}
        {ticks.map((t) => (
          <line
            key={t.key}
            x1={t.x}
            y1={t.y + 2.5}
            x2={t.x}
            y2={t.y + t.rowH - 2.5}
            stroke={t.up ? upColor : downColor}
            strokeWidth={2.4}
            opacity={0.9}
          >
            <title>{t.title}</title>
          </line>
        ))}
      </svg>
    </Box>
  );
};

const ShiftsPage: React.FC = () => {
  const { sources } = useData();
  const [dimension, setDimension] = useState<'power' | 'moral'>('moral');
  const [events, setEvents] = useState<DriftFeedEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [receiptsFor, setReceiptsFor] = useState<ReceiptsFilter | null>(null);

  useEffect(() => {
    let cancelled = false;
    setEvents(null);
    setError(null);
    driftApi
      .getDriftFeed({ dimension, scope: 'all', limit: FEED_LIMIT })
      .then((data) => {
        if (!cancelled) setEvents(data.events ?? []);
      })
      .catch((err) => {
        if (!cancelled) setError((err as Error).message);
      });
    return () => {
      cancelled = true;
    };
  }, [dimension]);

  const corpusWeeks = Math.floor(
    (Date.now() - Date.parse(`${CORPUS_START}T00:00:00Z`)) / (7 * dayMs)
  );

  return (
    <Box>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', columnGap: 3, rowGap: 1, mb: 1 }}>
        <Typography
          component="h2"
          sx={{
            fontFamily: fontDisplay,
            fontStyle: 'italic',
            fontWeight: 500,
            fontSize: '1.375rem',
            letterSpacing: '-0.01em',
          }}
        >
          What changed this week?
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          {(['moral', 'power'] as const).map((d) => (
            <Chip
              key={d}
              label={d === 'moral' ? 'Moral' : 'Power'}
              size="small"
              onClick={() => setDimension(d)}
              variant={dimension === d ? 'filled' : 'outlined'}
              sx={{
                bgcolor: dimension === d ? tokens.accent : 'transparent',
                color: dimension === d ? '#fff' : tokens.inkMuted,
                borderColor: tokens.accent,
              }}
            />
          ))}
        </Box>
      </Box>
      <Typography variant="body2" sx={{ color: tokens.inkMuted, maxWidth: '78ch', mb: 3 }}>
        Every entity's weekly sentiment series is tested for statistically significant breaks
        (Pettitt's changepoint test). A shift is either the whole corpus moving together — an
        event in the world — or one paper moving alone beyond what the global trend explains,
        which is an editorial decision showing itself.
      </Typography>

      <Card sx={{ mb: 4 }}>
        <CardHeader
          title="Seismograph"
          subheader="One strip per country's press. Each tick is a changepoint: green rose, red fell. A vertical line of ticks across strips is a coordinated shift; a scattered pattern is organic drift."
        />
        <CardContent>
          {events === null && !error ? (
            <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 4, textAlign: 'center' }}>
              Loading…
            </Typography>
          ) : error ? (
            <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 2 }}>
              {error}
            </Typography>
          ) : (
            <>
              <Seismograph events={events!} sources={sources} />
              <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted, mt: 1.5 }}>
                {events!.length} changepoint{events!.length === 1 ? '' : 's'} on the{' '}
                {dimension} dimension so far.
                {events!.length < 20 && (
                  <>
                    {' '}
                    Detection needs eight scored weeks per series and the corpus began July 13,
                    2026 ({corpusWeeks} weeks ago) — the strips fill in as history accrues.
                  </>
                )}
              </Typography>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader
          title="The drift feed"
          subheader="Every flagged shift, most significant first, with the receipts behind it"
        />
        <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
          {events?.length === 0 && (
            <Box sx={{ px: 2, py: 3 }}>
              <Typography variant="body2" sx={{ color: tokens.inkMuted }}>
                No significant shifts on the {dimension} dimension yet.
              </Typography>
            </Box>
          )}
          {events?.map((e, i) => {
            const up = e.mean_after >= e.mean_before;
            return (
              <Box
                key={`${e.entity_id}-${e.source_id ?? 'g'}-${e.week_start}`}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: 1.5,
                  px: 2,
                  py: 1.25,
                  borderTop: i === 0 ? 'none' : `1px solid ${tokens.border}`,
                }}
              >
                <Box sx={{ flex: 1, minWidth: 220 }}>
                  <Link
                    component={RouterLink}
                    to={`/portrayals/${e.entity_id}`}
                    underline="hover"
                    sx={{ color: tokens.ink, fontWeight: 600, fontSize: '0.875rem' }}
                  >
                    {e.entity_name}
                  </Link>
                  <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted }}>
                    {e.source_name ?? 'Whole corpus'} · week of {e.week_start}
                  </Typography>
                </Box>
                <Typography
                  variant="caption"
                  sx={{ ...monoNumber, fontWeight: 600, color: up ? upColor : downColor }}
                >
                  {e.mean_before.toFixed(2)} → {e.mean_after.toFixed(2)}
                </Typography>
                <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted }}>
                  p={e.p_value < 0.001 ? '<0.001' : e.p_value.toFixed(3)}
                </Typography>
                <Button
                  size="small"
                  onClick={() =>
                    setReceiptsFor({
                      entityId: e.entity_id,
                      entityName: e.entity_name,
                      ...(e.source_id != null && e.source_name
                        ? { sourceId: e.source_id, sourceName: e.source_name }
                        : {}),
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

      <ReceiptsDrawer filter={receiptsFor} onClose={() => setReceiptsFor(null)} />
    </Box>
  );
};

export default ShiftsPage;
