import React from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { Box, Typography, Card, CardContent, Chip, Stack } from '@mui/material';
import { useData } from '../context/DataContext';
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

const fmt = (n: number) => n.toLocaleString();

// Deterministic, template-based generator — no LLM call, no live "writing" animation.
// Every sentence is assembled from real counts already loaded by DataContext. Where
// this snapshot has no populated power/moral sentiment data (checked via
// entityApi.getEntityDistribution — currently empty for every entity), these
// templates stick to mention counts and coverage counts rather than claiming a
// portrayal ("cast as a villain", etc.) that the data doesn't back up.
function buildStories(entities: Entity[], sourceCount: number, countryCount: number): Story[] {
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

  const nextFive = entities.slice(5, 10);
  if (nextFive.length > 0) {
    stories.push({
      id: 'second-tier',
      headline: 'Just outside the spotlight',
      body: [
        `${nextFive.map((e) => e.name).join(', ')} round out the next tier of coverage, each mentioned between ${fmt(nextFive[nextFive.length - 1].mention_count ?? 0)} and ${fmt(nextFive[0].mention_count ?? 0)} times.`,
        `Together this second tier is a reminder that attention drops off fast: sources keep talking about ${lead.name} long after these names fade from the front page.`,
      ],
      entities: nextFive,
    });
  }

  stories.push({
    id: 'footprint',
    headline: 'The footprint behind this snapshot',
    body: [
      `This snapshot draws on ${sourceCount} sources across ${countryCount} countries, tracking ${entities.length} entities by mention count.`,
      `That breadth is what the comparisons elsewhere on this site are measured against — every entity page shows how a single source's coverage sits relative to this wider set.`,
    ],
    entities: [],
  });

  return stories;
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
              to={`/entities/${e.id}`}
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
  const { entities, sources, availableCountries, loading } = useData();

  const stories = buildStories(entities, sources.length, availableCountries.length);

  return (
    <Box>
      <Typography component="h2" sx={{ fontFamily: fontDisplay, fontWeight: 600, fontSize: '1.75rem', mb: 0.5 }}>
        Stories
      </Typography>
      <Typography variant="caption" sx={{ color: tokens.inkMuted, display: 'block', mb: 3 }}>
        Generated automatically from current tracking data: short briefs assembled directly from
        real mention counts. Every figure links to the entity it came from so you can check it
        yourself.
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
