import React, { useEffect, useMemo, useState } from 'react';
import {
  Box, CircularProgress, Drawer, IconButton, Link, Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { narrativeApi, sourcesApi } from '../services/api';
import { EntityReceipt, EntityReceipts, NewsSource } from '../types';
import { tokens, archetypeColor, monoNumber } from '../theme';

// The evidence drawer: every chart on the site shows averages of scored
// mentions — this is where a reader clicks through to the mentions themselves.
// Opened from a scatter dot (one paper), a distribution card (one country, or
// unfiltered), or a paper's reporting-history card. Data is the per-entity
// receipts snapshot (receipts/{id}.json), fetched only when the drawer opens.

export interface ReceiptsFilter {
  entityId: number;
  entityName: string;
  // Narrow to one paper (a clicked dot / the profiled paper) …
  sourceId?: number;
  sourceName?: string;
  // … or to a specific set of papers (the pair page's two sides) …
  sourceIds?: number[];
  // … or to one country's press (the distribution card's national layer).
  country?: string;
  // Header label override when sourceIds is used (e.g. "BBC and RT").
  scopeLabel?: string;
}

interface ReceiptRow extends EntityReceipt {
  sourceId: number;
  sourceName: string;
  country: string | null;
}

// Enough to scroll a real sample without rendering a 500-row DOM for
// entities the whole world covers.
const MAX_ROWS = 120;

const score = (v: number | null | undefined) =>
  v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(2)}`;

// Fallback display for a receipt with no stored headline.
const hostnameOf = (url: string) => {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
};

const ReceiptsDrawer: React.FC<{ filter: ReceiptsFilter | null; onClose: () => void }> = ({
  filter,
  onClose,
}) => {
  const [receipts, setReceipts] = useState<EntityReceipts | null>(null);
  const [sources, setSources] = useState<NewsSource[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const entityId = filter?.entityId;
  useEffect(() => {
    if (entityId == null) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setReceipts(null);
    Promise.all([narrativeApi.getEntityReceipts(entityId), sourcesApi.getSources()])
      .then(([r, s]) => {
        if (cancelled) return;
        setReceipts(r);
        setSources(s ?? []);
      })
      .catch((err) => {
        if (cancelled) return;
        // The static snapshot only carries receipts for the top tracked
        // entities — turn the raw loader error into reader-facing copy.
        const msg = String(err?.message ?? '');
        setError(msg.startsWith('Snapshot not available')
          ? 'No receipts are snapshotted for this entity — only the top tracked entities carry them.'
          : msg || 'Receipts unavailable.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [entityId]);

  const rows = useMemo<ReceiptRow[]>(() => {
    if (!receipts || !filter) return [];
    const byId = new Map<number, NewsSource>(sources.map((s) => [s.id, s]));
    const all: ReceiptRow[] = [];
    const wanted = filter.sourceIds ? new Set(filter.sourceIds) : null;
    for (const [sid, list] of Object.entries(receipts.sources)) {
      const sourceId = Number(sid);
      if (filter.sourceId != null && sourceId !== filter.sourceId) continue;
      if (wanted && !wanted.has(sourceId)) continue;
      const src = byId.get(sourceId);
      if (filter.country && src?.country !== filter.country) continue;
      for (const r of list) {
        all.push({
          ...r,
          sourceId,
          sourceName: src?.name ?? filter.sourceName ?? `Source ${sid}`,
          country: src?.country ?? null,
        });
      }
    }
    // Newest first; undated rows sink to the bottom.
    all.sort((a, b) => (b.date ?? '').localeCompare(a.date ?? ''));
    return all;
  }, [receipts, sources, filter]);

  const scopeLabel = filter?.scopeLabel
    ? filter.scopeLabel
    : filter?.sourceName
      ? filter.sourceName
      : filter?.country
        ? `${filter.country}'s press`
        : 'all tracked papers';

  return (
    <Drawer
      anchor="right"
      open={!!filter}
      onClose={onClose}
      PaperProps={{ sx: { width: 'min(460px, 100vw)', bgcolor: tokens.paper } }}
    >
      {filter && (
        <>
          <Box
            sx={{
              position: 'sticky', top: 0, zIndex: 1,
              bgcolor: tokens.surface,
              borderBottom: `1px solid ${tokens.border}`,
              px: 2.5, py: 2,
              display: 'flex', alignItems: 'flex-start', gap: 1,
            }}
          >
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography variant="h6" sx={{ lineHeight: 1.3 }}>
                {filter.entityName} — receipts
              </Typography>
              <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
                The most recent scored mentions from {scopeLabel}
                {receipts ? ` (up to ${receipts.per_source} per paper)` : ''}.
              </Typography>
            </Box>
            <IconButton size="small" onClick={onClose} aria-label="Close receipts">
              <CloseIcon fontSize="small" />
            </IconButton>
          </Box>

          <Box sx={{ px: 2.5, py: 1.5 }}>
            {loading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                <CircularProgress size={24} />
              </Box>
            ) : error ? (
              <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 2 }}>
                {error}
              </Typography>
            ) : rows.length === 0 ? (
              <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 2 }}>
                No scored mentions of {filter.entityName} from {scopeLabel} in the
                receipts window.
              </Typography>
            ) : (
              <>
                {rows.slice(0, MAX_ROWS).map((r, i) => (
                  <Box
                    key={`${r.sourceId}-${r.url}-${i}`}
                    sx={{
                      py: 1.25,
                      borderBottom: `1px solid ${tokens.border}`,
                      '&:last-of-type': { borderBottom: 'none' },
                    }}
                  >
                    <Link
                      href={r.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      underline="hover"
                      sx={{ color: tokens.ink, fontWeight: 600, fontSize: '0.875rem', lineHeight: 1.35 }}
                    >
                      {r.title || hostnameOf(r.url)}
                      <OpenInNewIcon sx={{ fontSize: 12, ml: 0.5, verticalAlign: 'baseline', color: tokens.inkMuted }} />
                    </Link>
                    <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted, mt: 0.25 }}>
                      {r.sourceName}
                      {r.country ? ` (${r.country})` : ''}
                      {r.date ? ` · ${r.date}` : ''}
                      {' · '}
                      <Box
                        component="span"
                        sx={{
                          ...monoNumber,
                          fontWeight: 600,
                          color: archetypeColor(r.power_score ?? 0, r.moral_score ?? 0),
                        }}
                      >
                        Power {score(r.power_score)} · Moral {score(r.moral_score)}
                      </Box>
                    </Typography>
                    {r.sentence && (
                      <Typography
                        variant="caption"
                        sx={{
                          display: 'block', mt: 0.5, pl: 1.25,
                          borderLeft: `2px solid ${tokens.border}`,
                          color: tokens.inkMuted, fontStyle: 'italic',
                        }}
                      >
                        “{r.sentence}”
                      </Typography>
                    )}
                  </Box>
                ))}
                {rows.length > MAX_ROWS && (
                  <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted, py: 1.5 }}>
                    Showing the {MAX_ROWS} most recent of {rows.length} receipts.
                  </Typography>
                )}
                <Typography variant="caption" sx={{ display: 'block', color: tokens.inkMuted, py: 1.5 }}>
                  Scores are this mention's reading on the −2…+2 power and moral
                  scales. Quoted sentences exist only for coverage analyzed before
                  Aug 14, 2026, when quote extraction was retired from the pipeline.
                </Typography>
              </>
            )}
          </Box>
        </>
      )}
    </Drawer>
  );
};

export default ReceiptsDrawer;
