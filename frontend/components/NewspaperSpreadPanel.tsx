import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  CardHeader,
  CardContent,
  Box,
  Typography,
  Chip,
  Link,
  ToggleButtonGroup,
  ToggleButton,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useData } from '../context/DataContext';
import { CountryEntityData } from '../types';
import { tokens, categoricalColor, monoNumber } from '../theme';
import MultiSourceTrendChart from './MultiSourceTrendChart';

// Two complementary views over the same per-entity computation, split by
// UNANIMITY_GAP so an entity lands in exactly one of them:
//  - 'divergence' (default): "Where this country's press disagrees with
//    itself." Entities whose papers span at least the gap, widest first — the
//    country's internal front line.
//  - 'consensus': "Where this country's press is unanimous." Entities every
//    covering paper scores within the gap of each other, tightest first — the
//    shared verdicts nobody in the sphere argues about.
// Either way: one row per entity, each newspaper's mention-weighted average as
// a dot on a shared -2..+2 track. Clicking a row expands it in place into the
// full per-paper time series for that entity (MultiSourceTrendChart, scoped to
// this country's papers), so the static gap can be read against how it moved.

// An entity is "unanimous" when its outermost papers sit closer than this.
const UNANIMITY_GAP = 0.5;

interface Props {
  country: string;
  entities: CountryEntityData[];
  variant?: 'divergence' | 'consensus';
}

interface PaperScore {
  paper: string;
  score: number;
  mentions: number;
}

interface SpreadRow {
  entity: string;
  papers: PaperScore[];
  spread: number;
  // Original API row, kept so the expanded chart can use the raw trends.
  source: CountryEntityData;
}

const clamp = (v: number) => Math.max(-2, Math.min(2, v));
const pct = (v: number) => `${((clamp(v) + 2) / 4) * 100}%`;

const NewspaperSpreadPanel: React.FC<Props> = ({ country, entities, variant = 'divergence' }) => {
  const navigate = useNavigate();
  const { entities: allEntities } = useData();
  const [dimension, setDimension] = useState<'moral' | 'power'>('moral');
  const [expandedEntity, setExpandedEntity] = useState<string | null>(null);
  const isConsensus = variant === 'consensus';

  const { rows, paperOrder } = useMemo(() => {
    const order: string[] = [];
    const built: SpreadRow[] = [];
    entities.forEach((entity) => {
      const papers: PaperScore[] = [];
      Object.entries(entity.newspapers).forEach(([paper, trends]) => {
        // Mention-weighted mean so a paper's one-off aside doesn't count like
        // its sustained coverage.
        let weighted = 0;
        let mentions = 0;
        trends.forEach((t) => {
          const score = dimension === 'moral' ? t.moral_score : t.power_score;
          if (typeof score === 'number' && !isNaN(score) && t.mention_count > 0) {
            weighted += score * t.mention_count;
            mentions += t.mention_count;
          }
        });
        if (mentions > 0) {
          papers.push({ paper, score: weighted / mentions, mentions });
          if (!order.includes(paper)) order.push(paper);
        }
      });
      // One paper is a reading, not an agreement or a disagreement — both
      // variants need at least two.
      if (papers.length >= 2) {
        const scores = papers.map((p) => p.score);
        built.push({
          entity: entity.entity_name,
          papers,
          spread: Math.max(...scores) - Math.min(...scores),
          source: entity,
        });
      }
    });
    const kept = built.filter((r) =>
      isConsensus ? r.spread < UNANIMITY_GAP : r.spread >= UNANIMITY_GAP
    );
    kept.sort((a, b) => (isConsensus ? a.spread - b.spread : b.spread - a.spread));
    return { rows: kept, paperOrder: order };
  }, [entities, dimension, isConsensus]);

  // Explicit colors keep the expanded chart's lines identical to the row dots
  // (the chart's own fallback groups by country parsed from the name, which
  // would re-derive a different assignment for bare paper names).
  const chartColors = useMemo(
    () => Object.fromEntries(paperOrder.map((p) => [p, categoricalColor(p, paperOrder)])),
    [paperOrder]
  );

  return (
    <Card>
      <CardHeader
        title={
          isConsensus
            ? `Where ${country}'s press is unanimous`
            : `Where ${country}'s press disagrees with itself`
        }
        subheader={
          isConsensus
            ? `Each dot is one newspaper's average score for the entity; every gap is under ${UNANIMITY_GAP}, tightest first`
            : "Each dot is one newspaper's average score for the entity; rows sort by the widest internal gap"
        }
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
        {rows.length === 0 ? (
          <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 2 }}>
            {isConsensus
              ? `No entity in this window has two or more of ${country}'s tracked papers scoring within ${UNANIMITY_GAP} of each other — its top entities are all contested.`
              : `No entity in this window splits two or more of ${country}'s tracked papers by at least ${UNANIMITY_GAP} — where coverage overlaps, the papers broadly agree.`}
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
              <span style={{ width: 28 }} />
            </Box>
            {rows.map((row) => {
              const match = allEntities.find((e) => e.name === row.entity);
              const isExpanded = expandedEntity === row.entity;
              return (
                <React.Fragment key={row.entity}>
                  <Box
                    onClick={() =>
                      setExpandedEntity((prev) => (prev === row.entity ? null : row.entity))
                    }
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 2,
                      px: 2,
                      py: 0.9,
                      borderTop: `1px solid ${tokens.border}`,
                      cursor: 'pointer',
                      bgcolor: isExpanded ? tokens.surfaceSunken : 'transparent',
                      '&:hover': { bgcolor: tokens.surfaceSunken },
                    }}
                  >
                    <Box sx={{ width: 160, minWidth: 110 }}>
                      <Typography variant="body2" noWrap sx={{ fontWeight: 600 }}>
                        {row.entity}
                      </Typography>
                      <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
                        {row.papers.length} papers
                      </Typography>
                    </Box>
                    <Box sx={{ flex: 1, minWidth: 160 }}>
                      <svg width="100%" height={24}>
                        <line x1="0%" y1={12} x2="100%" y2={12} stroke={tokens.border} strokeWidth={1} />
                        <line x1="50%" y1={3} x2="50%" y2={21} stroke={tokens.ink} strokeWidth={1} opacity={0.45} />
                        <line
                          x1={pct(Math.min(...row.papers.map((p) => p.score)))}
                          y1={12}
                          x2={pct(Math.max(...row.papers.map((p) => p.score)))}
                          y2={12}
                          stroke={tokens.inkMuted}
                          strokeWidth={1.5}
                        />
                        {row.papers.map((p) => (
                          <circle key={p.paper} cx={pct(p.score)} cy={12} r={4.5}
                            fill={categoricalColor(p.paper, paperOrder)}
                            stroke={tokens.surface}
                            strokeWidth={1}
                            opacity={0.9}
                          >
                            <title>{`${p.paper}: ${p.score.toFixed(2)} (${p.mentions} mentions)`}</title>
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
                    <ExpandMoreIcon
                      fontSize="small"
                      sx={{
                        width: 28,
                        color: tokens.inkMuted,
                        transform: isExpanded ? 'rotate(180deg)' : 'none',
                        transition: 'transform 120ms',
                      }}
                    />
                  </Box>
                  {isExpanded && (
                    <Box
                      sx={{
                        borderTop: `1px dashed ${tokens.border}`,
                        bgcolor: tokens.surfaceSunken,
                        px: 2,
                        pt: 2,
                        pb: 1,
                      }}
                    >
                      <Box sx={{ height: 400 }}>
                        <MultiSourceTrendChart
                          entityName={row.entity}
                          sourcesTrends={row.source.newspapers}
                          height={400}
                          controlledDimension={dimension}
                          colors={chartColors}
                        />
                      </Box>
                      {match && (
                        <Link
                          component="button"
                          variant="caption"
                          onClick={() => navigate(`/portrayals/${match.id}`)}
                          sx={{ color: tokens.inkMuted, mt: 0.5 }}
                        >
                          Open {row.entity}'s full profile →
                        </Link>
                      )}
                    </Box>
                  )}
                </React.Fragment>
              );
            })}
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mt: 1.5 }}>
              {paperOrder.map((paper) => (
                <Chip
                  key={paper}
                  label={paper}
                  size="small"
                  variant="outlined"
                  onClick={() => navigate(`/coverage/newspapers/${encodeURIComponent(paper)}`)}
                  sx={{
                    borderColor: categoricalColor(paper, paperOrder),
                    color: tokens.inkMuted,
                    height: 20,
                    fontSize: 10,
                    cursor: 'pointer',
                  }}
                />
              ))}
            </Box>
            <Typography variant="caption" sx={{ display: 'block', mt: 1, color: tokens.inkMuted }}>
              Scores are mention-weighted averages per paper over the selected window. Hover a dot
              for the paper and its exact score; click a row to expand each paper's line over time,
              a chip for the paper.
            </Typography>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default NewspaperSpreadPanel;
