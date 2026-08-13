import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  CardHeader,
  CardContent,
  Box,
  Typography,
  Chip,
  ToggleButtonGroup,
  ToggleButton,
} from '@mui/material';
import { useData } from '../context/DataContext';
import { CountryEntityData } from '../types';
import { tokens, categoricalColor, monoNumber } from '../theme';

// "Where this country's press disagrees with itself." One row per entity: each
// newspaper's average score as a dot on a shared -2..+2 track, the span between
// the outermost papers drawn as a line. Rows sort by that span, so the top of
// the list is the country's internal front line — the divergence-within-a-
// country signal the project singles out — rather than a spaghetti of unrelated
// entities on one time axis.

interface Props {
  country: string;
  entities: CountryEntityData[];
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
}

const clamp = (v: number) => Math.max(-2, Math.min(2, v));
const pct = (v: number) => `${((clamp(v) + 2) / 4) * 100}%`;

const NewspaperSpreadPanel: React.FC<Props> = ({ country, entities }) => {
  const navigate = useNavigate();
  const { entities: allEntities } = useData();
  const [dimension, setDimension] = useState<'moral' | 'power'>('moral');

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
      // One paper is a reading, not a disagreement — the spread needs two.
      if (papers.length >= 2) {
        const scores = papers.map((p) => p.score);
        built.push({
          entity: entity.entity_name,
          papers,
          spread: Math.max(...scores) - Math.min(...scores),
        });
      }
    });
    built.sort((a, b) => b.spread - a.spread);
    return { rows: built, paperOrder: order };
  }, [entities, dimension]);

  return (
    <Card>
      <CardHeader
        title={`Where ${country}'s press disagrees with itself`}
        subheader="Each dot is one newspaper's average score for the entity; rows sort by the widest internal gap"
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
            No entity in this window is covered by two or more of {country}'s tracked papers —
            nothing to compare yet.
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
            {rows.map((row) => {
              const match = allEntities.find((e) => e.name === row.entity);
              return (
                <Box
                  key={row.entity}
                  onClick={() => match && navigate(`/entities/${match.id}`)}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 2,
                    px: 2,
                    py: 0.9,
                    borderTop: `1px solid ${tokens.border}`,
                    cursor: match ? 'pointer' : 'default',
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
                </Box>
              );
            })}
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mt: 1.5 }}>
              {paperOrder.map((paper) => (
                <Chip
                  key={paper}
                  label={paper}
                  size="small"
                  variant="outlined"
                  onClick={() => navigate(`/sources/${encodeURIComponent(paper)}`)}
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
              for the paper and its exact score; click a row for the entity, a chip for the paper.
            </Typography>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default NewspaperSpreadPanel;
