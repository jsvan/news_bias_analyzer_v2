import React, { useMemo } from 'react';
import { useNavigate, Link as RouterLink } from 'react-router-dom';
import {
  Box,
  Typography,
  Grid,
  Autocomplete,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Button,
  Chip,
  Link,
} from '@mui/material';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import { useData } from '../context/DataContext';
import { tokens, monoNumber, archetypeColor, archetypeLabel, fontDisplay } from '../theme';
import QuadrantMiniature from '../components/QuadrantMiniature';
import { Entity, NewsSource } from '../types';

const Mono: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Box component="span" sx={{ ...monoNumber, color: tokens.ink }}>
    {children}
  </Box>
);

// One doorway: the question set as a headline on the left, the control that
// answers it on the right. Each row's control differs, deliberately — these are
// three different actions, not three copies of a card.
const QuestionRow: React.FC<{ question: string; children: React.ReactNode; control: React.ReactNode }> = ({
  question,
  children,
  control,
}) => (
  // Padding lives on a plain Box: Grid spacing's negative container margins
  // would otherwise swallow it (they're why row text once sat directly on the
  // divider). Column-flex centering spreads any extra height an equal-row
  // parent grid assigns, and pb > pt keeps clear air above each divider.
  <Box
    component="section"
    sx={{ pt: 4, pb: 5, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}
  >
    <Grid container spacing={{ xs: 2, md: 4 }} alignItems="center">
      <Grid item xs={12} md={5}>
      <Typography
        component="h2"
        sx={{
          fontFamily: fontDisplay,
          fontWeight: 500,
          fontSize: '1.75rem',
          lineHeight: 1.2,
          letterSpacing: '-0.01em',
          textWrap: 'balance',
          mb: 1,
        } as any}
      >
        {question}
      </Typography>
      <Typography variant="body2" sx={{ color: tokens.inkMuted, maxWidth: '52ch' }}>
        {children}
      </Typography>
    </Grid>
      <Grid item xs={12} md={7}>
        {control}
      </Grid>
    </Grid>
  </Box>
);

// An example sentence shown the way the instrument reads every mention: the
// entity, its two scores, and the casting they add up to.
const ScoredQuote: React.FC<{ quote: string; entity: string; power: number; moral: number }> = ({
  quote,
  entity,
  power,
  moral,
}) => (
  <Box sx={{ my: 3.5, maxWidth: '56ch' }}>
    <Typography
      sx={{
        fontFamily: fontDisplay,
        fontStyle: 'italic',
        fontSize: '1.375rem',
        lineHeight: 1.35,
        textWrap: 'balance',
        mb: 1.25,
      } as any}
    >
      “{quote}”
    </Typography>
    <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', columnGap: 1.25, rowGap: 0.5 }}>
      <Box
        sx={{
          width: 9,
          height: 9,
          borderRadius: '50%',
          bgcolor: archetypeColor(power, moral),
          flexShrink: 0,
        }}
      />
      <Typography variant="caption" sx={{ color: tokens.inkMuted, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {entity}
      </Typography>
      <Typography variant="caption" sx={{ ...monoNumber, color: tokens.ink }}>
        power {power > 0 ? '+' : ''}
        {power.toFixed(1)} · moral {moral > 0 ? '+' : ''}
        {moral.toFixed(1)}
      </Typography>
      <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
        → {archetypeLabel(power, moral)}
      </Typography>
    </Box>
  </Box>
);

const ARCHETYPE_LEGEND = [
  { name: 'Hero', verb: 'celebrate', color: tokens.hero },
  { name: 'Victim', verb: 'help', color: tokens.victim },
  { name: 'Villain', verb: 'guard against', color: tokens.villain },
  { name: 'Wretch', verb: 'dismiss', color: tokens.nuisance },
];

const WelcomePage: React.FC = () => {
  const navigate = useNavigate();
  const { entities, sources, availableCountries, meta } = useData();

  // Autocomplete groups need their options pre-sorted by group.
  const newspaperOptions = useMemo(
    () =>
      [...sources].sort(
        (a, b) => (a.country || '').localeCompare(b.country || '') || a.name.localeCompare(b.name)
      ),
    [sources]
  );

  // entities arrive sorted by mention count — the head of the list is the news.
  const exampleEntities = entities.slice(0, 6);

  const latestArticle = meta?.most_recent_article_date
    ? new Date(meta.most_recent_article_date).toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    : null;

  return (
    <Box>
      {/* ————— Front door: headline left, the live quadrant as the page's photograph right ————— */}
      <Box
        component="section"
        sx={{
          pb: 5,
          animation: 'hero-rise 480ms cubic-bezier(0.22, 1, 0.36, 1)',
          '@keyframes hero-rise': {
            from: { opacity: 0, transform: 'translateY(8px)' },
            to: { opacity: 1, transform: 'translateY(0)' },
          },
          '@media (prefers-reduced-motion: reduce)': { animation: 'none' },
        }}
      >
        <Grid container spacing={{ xs: 4, md: 6 }}>
          <Grid item xs={12} md={7}>
            <Typography
              component="h2"
              sx={{
                fontFamily: fontDisplay,
                fontWeight: 500,
                fontStyle: 'italic',
                fontSize: 'clamp(1.75rem, 2.4vw + 1rem, 2.75rem)',
                lineHeight: 1.15,
                letterSpacing: '-0.01em',
                textWrap: 'balance',
                mb: 2.5,
              } as any}
            >
              Every news source constructs the same world differently.
            </Typography>
            <Typography
              variant="subtitle1"
              sx={{
                color: tokens.ink,
                maxWidth: '62ch',
                textWrap: 'pretty',
                mb: 1.5,
                '&::first-letter': {
                  fontFamily: fontDisplay,
                  float: 'left',
                  fontSize: '3.2em',
                  lineHeight: 0.85,
                  fontWeight: 600,
                  pr: '0.5rem',
                  pt: '0.2rem',
                },
              } as any}
            >
              We read the world's newspapers by machine, measure how each one portrays the people,
              countries, and organizations in the news, and set every outlet against the global
              average. A news bubble is hard to see from inside it; comparing your sources against
              the world's press is a way to find its walls.
            </Typography>
            <Typography sx={{ color: tokens.inkMuted, maxWidth: '68ch', textWrap: 'pretty' } as any}>
              Ideology, measured this way, is a warping of sentiment: a political slant shows up as
              one set of entities consistently cast as villains and another as heroes, and those
              castings drift over time. This site measures the differences and tracks the drift.
            </Typography>
          </Grid>
          <Grid item xs={12} md={5}>
            <QuadrantMiniature
              limit={100}
              labelTop={6}
              maxWidth={520}
              credit={
                <>
                  <Mono>{sources.length}</Mono> newspapers · <Mono>{availableCountries.length}</Mono>{' '}
                  countries
                  {latestArticle && (
                    <>
                      {' '}
                      · latest articles <Mono>{latestArticle}</Mono>
                    </>
                  )}
                </>
              }
            />
          </Grid>
        </Grid>
      </Box>

      {/* ————— The three doorways ————— */}
      <Box
        component="section"
        sx={{
          borderTop: `1px solid ${tokens.border}`,
          // Equal-height rows from md up: every doorway takes the tallest
          // row's height, one even rhythm. Stacked mobile keeps natural sizes.
          display: { md: 'grid' },
          gridAutoRows: { md: '1fr' },
          '& > section + section': { borderTop: `1px solid ${tokens.border}` },
        }}
      >
        <QuestionRow
          question="What is the press talking about?"
          control={
            <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 2 }}>
              <FormControl size="small" sx={{ minWidth: 220 }}>
                <InputLabel id="welcome-country-label">A country's press</InputLabel>
                <Select
                  labelId="welcome-country-label"
                  label="A country's press"
                  value=""
                  onChange={(e) => {
                    const country = e.target.value as string;
                    if (country) navigate(`/countries?country=${encodeURIComponent(country)}`);
                  }}
                >
                  {availableCountries.map((c) => (
                    <MenuItem key={c} value={c}>
                      {c}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <Typography variant="body2" sx={{ color: tokens.inkMuted }}>
                or
              </Typography>
              <Autocomplete
                size="small"
                options={newspaperOptions}
                groupBy={(s: NewsSource) => s.country || 'Other'}
                getOptionLabel={(s: NewsSource) => s.name}
                onChange={(_, source) => {
                  if (source) navigate(`/sources/${encodeURIComponent(source.name)}`);
                }}
                sx={{ width: { xs: '100%', sm: 260 } }}
                renderInput={(params) => <TextField {...params} label="A single newspaper" />}
              />
            </Box>
          }
        >
          Every country's press has its own front page. Pick a country to see which entities its
          newspapers dwell on and how they cast them — or go straight to one paper's profile.
        </QuestionRow>

        <QuestionRow
          question="How is one thing portrayed?"
          control={
            <Box>
              <Autocomplete
                size="small"
                options={entities}
                getOptionLabel={(e: Entity) => e.name}
                // Same-named entities of different types (two "Washington") need the
                // type tag to be told apart in the dropdown.
                renderOption={(props, option) => (
                  <Box component="li" {...props} sx={{ display: 'flex', justifyContent: 'space-between', gap: 1 }}>
                    <span>{option.name}</span>
                    <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
                      {option.type}
                    </Typography>
                  </Box>
                )}
                onChange={(_, entity) => {
                  if (entity) navigate(`/entities/${entity.id}`);
                }}
                sx={{ width: { xs: '100%', sm: 340 } }}
                renderInput={(params) => <TextField {...params} label="A person, country, or organization" />}
              />
              {exampleEntities.length > 0 && (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1.5 }}>
                  {exampleEntities.map((e) => (
                    <Chip
                      key={e.id}
                      label={e.name}
                      size="small"
                      variant="outlined"
                      onClick={() => navigate(`/entities/${e.id}`)}
                    />
                  ))}
                </Box>
              )}
            </Box>
          }
        >
          Follow one person, country, or organization across the world's press — who casts it as
          hero or villain, how far apart the readings sit, and how they move.
        </QuestionRow>

        <QuestionRow
          question="Where does each newspaper stand?"
          control={
            <Button variant="contained" endIcon={<ArrowForwardIcon />} onClick={() => navigate('/source-space')}>
              Open the source map
            </Button>
          }
        >
          Newspapers that cast the same entities the same way sit close together on the map.
          Distance is disagreement — and the entities doing the dividing are named.
        </QuestionRow>
      </Box>

      {/* ————— The measurement idea: explanation, not controls, so it sits on
          the recessed neutral layer instead of the paper the doorways act on ————— */}
      <Box
        component="section"
        sx={{
          bgcolor: tokens.surfaceSunken,
          borderRadius: '10px',
          px: { xs: 2.5, sm: 4 },
          py: 4,
          mt: 2.5,
          mb: 5,
        }}
      >
        <Typography
          component="h2"
          sx={{
            fontFamily: fontDisplay,
            fontWeight: 500,
            fontSize: '1.75rem',
            lineHeight: 1.2,
            letterSpacing: '-0.01em',
            mb: 2,
          } as any}
        >
          Sentiment means two things
        </Typography>

        <Typography sx={{ maxWidth: '66ch', textWrap: 'pretty' } as any}>
          Most sentiment analysis compresses a portrayal into one number. News actually passes two
          independent judgments on everyone it covers: how powerful they are, and how good they are.
        </Typography>

        <ScoredQuote quote="Hitler annexed Austria." entity="Hitler" power={1.8} moral={-1.7} />

        <Typography sx={{ maxWidth: '66ch', textWrap: 'pretty' } as any}>
          As a moral judgment this is negative — a state breaking international law. As a power
          judgment it is positive: force, wielded effectively.
        </Typography>

        <ScoredQuote
          quote="American victims of Hurricane Katrina are seeking aid."
          entity="The victims"
          power={-1.5}
          moral={1.2}
        />

        <Typography sx={{ maxWidth: '66ch', textWrap: 'pretty', mb: 2 } as any}>
          Here the judgments reverse: people with no power at all, morally deserving of help.
          Because the two axes move independently, we score every portrayal on both, separately.
        </Typography>

        <Typography sx={{ maxWidth: '66ch', textWrap: 'pretty', mb: 2 } as any}>
          Read together, the axes make four castings. The weak and immoral are wretches —
          unpleasant, but nothing to fear. The strong and immoral are villains, worth guarding
          against. The weak and moral are victims, who need help, and the strong and moral are
          heroes, who get celebrated. Every chart on this site colors entities by which casting a
          source gives them.
        </Typography>

        <Box sx={{ display: 'flex', flexWrap: 'wrap', columnGap: 3, rowGap: 1, alignItems: 'center' }}>
          {ARCHETYPE_LEGEND.map((a) => (
            <Box key={a.name} sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
              <Box sx={{ width: 9, height: 9, borderRadius: '50%', bgcolor: a.color, flexShrink: 0 }} />
              <Typography variant="caption" sx={{ color: tokens.ink }}>
                <Box component="span" sx={{ fontWeight: 600 }}>
                  {a.name}
                </Box>
                <Box component="span" sx={{ color: tokens.inkMuted }}>
                  {' '}
                  — {a.verb}
                </Box>
              </Typography>
            </Box>
          ))}
        </Box>
        <Typography variant="caption" sx={{ display: 'block', mt: 1.5, color: tokens.inkMuted }}>
          Example readings, in the format every mention on this site is scored.
        </Typography>
      </Box>

      <Box component="footer" sx={{ borderTop: `1px solid ${tokens.border}`, pt: 3, pb: 2 }}>
        <Typography variant="body2" sx={{ color: tokens.inkMuted, maxWidth: '68ch' }}>
          The measurement itself — how articles are scored, how entity names merge, and what the
          baselines weigh — is documented in{' '}
          <Link component={RouterLink} to="/methodology">
            How this works
          </Link>
          .
        </Typography>
      </Box>
    </Box>
  );
};

export default WelcomePage;
