import React, { useEffect, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { Box, Typography, Card, CardContent, Chip, Stack } from '@mui/material';
import { useData } from '../context/DataContext';
import { driftApi, narrativeApi } from '../services/api';
import { Entity } from '../types';
import { tokens, monoNumber, fontDisplay } from '../theme';

// A "story" is a headline + a couple of sentences of prose, plus the entities
// it's built from so a reader can click through and check the underlying numbers.
interface Story {
  id: string;
  headline: string;
  body: string[];
  entities: Entity[];
}

interface DriftEvent {
  entity_name: string;
  source_name: string | null;
  week_start: string;
  p_value: number;
  mean_before: number;
  mean_after: number;
}

interface ContestedEntry {
  entity_name: string;
  divergence: number;
}

const fmt = (n: number) => n.toLocaleString();
const fmtScore = (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}`;
const fmtP = (p: number) => (p < 0.001 ? 'p<0.001' : `p=${p.toFixed(3)}`);

// Deterministic, template-based generator — no LLM call, no live "writing"
// animation. Coverage stories are assembled from mention counts already loaded
// by DataContext; shift and contested stories restate what the drift and
// contested pipelines computed (Pettitt changepoints, cross-country JSD), so
// every claim is a number the reader can go check, not editorial prose.
function buildCoverageStories(entities: Entity[], sourceCount: number): Story[] {
  const stories: Story[] = [];
  if (entities.length === 0) return stories;

  const top5 = entities.slice(0, 5);
  const [lead, ...rest] = top5;
  const leadCount = lead.mention_count ?? 0;
  const runnerUps = rest
    .map((e) => `${e.name} (${fmt(e.mention_count ?? 0)})`)
    .join(', ');

  stories.push({
    id: 'most-covered',
    headline: `${lead.name} leads this period's coverage`,
    body: [
      `${lead.name} was the most-mentioned entity in this snapshot, appearing ${fmt(leadCount)} times across ${sourceCount} tracked sources.`,
      rest.length > 0
        ? `Close behind: ${runnerUps}.`
        : `No other entity came close in this snapshot.`,
    ],
    entities: top5,
  });

  const totalMentions = entities.reduce((sum, e) => sum + (e.mention_count ?? 0), 0);
  const top5Mentions = top5.reduce((sum, e) => sum + (e.mention_count ?? 0), 0);
  const sharePct = totalMentions > 0 ? Math.round((top5Mentions / totalMentions) * 100) : 0;

  stories.push({
    id: 'concentration',
    headline: 'Coverage concentrates on a handful of names',
    body: [
      `Of the ${entities.length} entities tracked this period, the top 5 — ${top5.map((e) => e.name).join(', ')} — account for ${sharePct}% of all recorded mentions.`,
      `The remaining ${entities.length - top5.length} entities split the other ${100 - sharePct}%.`,
    ],
    entities: top5,
  });

  return stories;
}

function buildShiftStories(events: DriftEvent[], entities: Entity[]): Story[] {
  const byName = new Map(entities.map((e) => [e.name, e]));
  return events.slice(0, 3).map((ev, i) => {
    const match = byName.get(ev.entity_name);
    const mover = ev.source_name ?? 'the whole corpus';
    const direction = ev.mean_after >= ev.mean_before ? 'up' : 'down';
    return {
      id: `shift-${i}`,
      headline: ev.source_name
        ? `${ev.source_name} changed its tone on ${ev.entity_name}`
        : `Coverage of ${ev.entity_name} shifted everywhere at once`,
      body: [
        `Around the week of ${ev.week_start}, ${mover}'s average moral score for ${ev.entity_name} moved ${direction} from ${fmtScore(ev.mean_before)} to ${fmtScore(ev.mean_after)} (${fmtP(ev.p_value)}, Pettitt changepoint test).`,
        ev.source_name
          ? `That move is measured after subtracting the global trend — this outlet moved on its own, which is the editorial-stance signal rather than a reaction everyone shared.`
          : `The corpus moving together usually marks a real-world event; the entity page shows which sources moved furthest.`,
      ],
      entities: match ? [match] : [],
    };
  });
}

function buildContestedStory(ranked: ContestedEntry[], entities: Entity[]): Story | null {
  if (ranked.length === 0) return null;
  const byName = new Map(entities.map((e) => [e.name, e]));
  const top = ranked.slice(0, 3);
  const listed = top
    .map((e) => `${e.entity_name} (JSD ${e.divergence.toFixed(2)})`)
    .join(', ');
  return {
    id: 'contested',
    headline: 'Where national spheres disagree most',
    body: [
      `Measured by Jensen-Shannon divergence between countries' sentiment distributions, the most contested entities in recent coverage are ${listed}.`,
      `A contested entity can still average near neutral — the disagreement, not the mean, is the story.`,
    ],
    entities: top.map((e) => byName.get(e.entity_name)).filter((e): e is Entity => !!e),
  };
}

const StoryCard: React.FC<{ story: Story }> = ({ story }) => (
  <Card>
    <CardContent>
      <Typography
        component="h3"
        sx={{ fontFamily: fontDisplay, fontWeight: 600, fontSize: '1.375rem', mb: 1.5 }}
      >
        {story.headline}
      </Typography>
      <Stack spacing={1} sx={{ mb: story.entities.length > 0 ? 2 : 0 }}>
        {story.body.map((sentence, i) => (
          <Typography key={i} variant="body1" sx={{ color: tokens.ink }}>
            {sentence}
          </Typography>
        ))}
      </Stack>
      {story.entities.length > 0 && (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          {story.entities.map((e) => (
            <Chip
              key={e.id}
              component={RouterLink}
              to={`/portrayals/${e.id}`}
              clickable
              size="small"
              variant="outlined"
              label={
                <>
                  {e.name}
                  <Box component="span" sx={{ ...monoNumber, color: tokens.inkMuted, ml: 0.75 }}>
                    {fmt(e.mention_count ?? 0)}
                  </Box>
                </>
              }
              sx={{ borderColor: tokens.border }}
            />
          ))}
        </Box>
      )}
    </CardContent>
  </Card>
);

const StoriesPage: React.FC = () => {
  const { entities, sources, loading } = useData();
  const [driftEvents, setDriftEvents] = useState<DriftEvent[]>([]);
  const [contested, setContested] = useState<ContestedEntry[]>([]);

  // Live-API computations; on a static snapshot these fail quietly and the
  // page falls back to coverage stories alone.
  useEffect(() => {
    driftApi
      .getDriftFeed({ dimension: 'moral', scope: 'all', limit: 5 })
      .then((data) => setDriftEvents(data?.events ?? []))
      .catch(() => setDriftEvents([]));
    narrativeApi
      .getContestedRanking({ days: 30, dimension: 'moral', limit: 5 })
      .then((data) => setContested(data?.entities ?? []))
      .catch(() => setContested([]));
  }, []);

  const contestedStory = buildContestedStory(contested, entities);
  const stories: Story[] = [
    ...buildShiftStories(driftEvents, entities),
    ...(contestedStory ? [contestedStory] : []),
    ...buildCoverageStories(entities, sources.length),
  ];

  return (
    <Box>
      <Typography component="h2" sx={{ fontFamily: fontDisplay, fontWeight: 600, fontSize: '1.75rem', mb: 0.5 }}>
        Stories
      </Typography>
      <Typography variant="caption" sx={{ color: tokens.inkMuted, display: 'block', mb: 3 }}>
        Generated automatically from the pipeline's own findings — statistically significant
        tone shifts, cross-country contestation, and coverage concentration. Every figure links
        to the entity it came from so you can check it yourself.
      </Typography>

      {loading && (
        <Typography variant="body2" sx={{ color: tokens.inkMuted }}>
          Loading tracking data…
        </Typography>
      )}

      {!loading && stories.length === 0 && (
        <Typography variant="body2" sx={{ color: tokens.inkMuted }}>
          No entities tracked yet — stories will appear once coverage data is available.
        </Typography>
      )}

      <Stack spacing={3}>
        {stories.map((story) => (
          <StoryCard key={story.id} story={story} />
        ))}
      </Stack>
    </Box>
  );
};

export default StoriesPage;
