import React from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { Box, Typography, Card, CardHeader, CardContent, Chip, Link as MuiLink } from '@mui/material';
import { tokens, monoNumber, fontMono } from '../theme';

// "How this works" - a documentation page, not a marketing page. Every claim here is
// checked against the current code (analyzer/narrative_metrics.py, the server/routers/*
// endpoints, and frontend/services/api.ts) at time of writing, not aspirational -
// see each section's Status line. Examples are real responses captured from a running
// instance, not fabricated numbers, so a skeptical reader can spot-check them.

type Status = 'live' | 'computed' | 'designed' | 'standalone';

const STATUS_LABEL: Record<Status, string> = {
  live: 'Live',
  computed: 'Computed — not yet visualized',
  designed: 'Designed & self-tested — not exposed',
  standalone: 'Standalone script — not the live pipeline',
};

const StatusChip: React.FC<{ status: Status }> = ({ status }) => (
  <Chip
    label={STATUS_LABEL[status]}
    size="small"
    variant={status === 'live' ? 'filled' : 'outlined'}
    sx={{
      bgcolor: status === 'live' ? tokens.accent : 'transparent',
      color: status === 'live' ? '#fff' : tokens.inkMuted,
      borderColor: status === 'live' ? tokens.accent : tokens.border,
      fontWeight: 600,
      flexShrink: 0,
    }}
  />
);

const Kernel: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Typography
    component="code"
    sx={{ ...monoNumber, fontSize: '0.8125rem', color: tokens.accent, bgcolor: tokens.surfaceSunken, px: 0.75, py: 0.25, borderRadius: '4px' }}
  >
    {children}
  </Typography>
);

const Bullets: React.FC<{ items: React.ReactNode[] }> = ({ items }) => (
  <Box component="ul" sx={{ m: 0, pl: 2.5, display: 'flex', flexDirection: 'column', gap: 0.5 }}>
    {items.map((item, i) => (
      <Typography key={i} component="li" variant="body2">
        {item}
      </Typography>
    ))}
  </Box>
);

const Formula: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Box
    sx={{
      fontFamily: fontMono,
      fontSize: '0.8125rem',
      color: tokens.ink,
      bgcolor: tokens.surfaceSunken,
      border: `1px solid ${tokens.border}`,
      borderRadius: '6px',
      px: 2,
      py: 1.25,
      overflowX: 'auto',
      whiteSpace: 'pre-wrap',
      lineHeight: 1.7,
    }}
  >
    {children}
  </Box>
);

const Example: React.FC<{ caption: string; children: React.ReactNode }> = ({ caption, children }) => (
  <Box>
    <Typography variant="caption" sx={{ color: tokens.inkMuted, display: 'block', mb: 0.5 }}>
      {caption}
    </Typography>
    <Box
      sx={{
        fontFamily: fontMono,
        fontSize: '0.75rem',
        color: tokens.ink,
        bgcolor: tokens.surfaceSunken,
        border: `1px solid ${tokens.border}`,
        borderRadius: '6px',
        px: 2,
        py: 1.25,
        overflowX: 'auto',
        whiteSpace: 'pre',
        lineHeight: 1.7,
      }}
    >
      {children}
    </Box>
  </Box>
);

// Compact "what backs this, where it's wired" line, replacing a full sentence per section.
const Meta: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Typography variant="caption" sx={{ color: tokens.inkMuted, display: 'block', lineHeight: 1.8 }}>
    {children}
  </Typography>
);

const DashboardLink: React.FC<{ to: string; children: React.ReactNode }> = ({ to, children }) => (
  <MuiLink component={RouterLink} to={to} sx={{ color: tokens.accent, fontWeight: 600, fontSize: '0.875rem' }}>
    {children} →
  </MuiLink>
);

interface SectionProps {
  id: string;
  title: string;
  status: Status;
  children: React.ReactNode;
}

const Section: React.FC<SectionProps> = ({ id, title, status, children }) => (
  <Card id={id} sx={{ scrollMarginTop: 24 }}>
    <CardHeader
      title={title}
      action={<Box sx={{ pt: 0.5 }}><StatusChip status={status} /></Box>}
    />
    <CardContent sx={{ pt: 0, display: 'flex', flexDirection: 'column', gap: 1.25 }}>{children}</CardContent>
  </Card>
);

const TOC_ITEMS: { id: string; label: string }[] = [
  { id: 'contested', label: 'Contested ranking' },
  { id: 'embeddings', label: 'Entity relatedness' },
  { id: 'drift', label: 'Drift & changepoint detection' },
  { id: 'archetype', label: 'Archetype & trajectory' },
  { id: 'source-map', label: 'Source map (SVD)' },
  { id: 'salience', label: 'Salience asymmetry' },
  { id: 'lagged-correlation', label: 'Lead-lag correlation' },
  { id: 'synchrony', label: 'Synchrony score' },
  { id: 'event-study', label: 'Event study: the founding axiom' },
];

const scrollTo = (id: string) => (e: React.MouseEvent) => {
  e.preventDefault();
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
};

const MethodologyPage: React.FC = () => {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, maxWidth: 880, mx: 'auto' }}>
      <Box>
        <Typography variant="h4" sx={{ mb: 1 }}>
          How this works
        </Typography>
        <Typography variant="body1" sx={{ color: tokens.inkMuted, maxWidth: 720, mb: 1.5 }}>
          Premise: if every observer had perfect information and no bias, sentiment would
          move in lockstep worldwide. It doesn't. The gap between spheres is the signal —
          not proof one sphere is "biased." Status below reflects what's actually wired
          today, not the roadmap.
        </Typography>
        <Bullets
          items={[
            <>Two axes per mention: power, moral — each in <code>[-2, +2]</code>.</>,
            <>"Sphere" = country of the source.</>,
            <>Kernels: <Kernel>analyzer/narrative_metrics.py</Kernel> — dependency-free, self-tested (<Kernel>python -m analyzer.narrative_metrics</Kernel>).</>,
          ]}
        />
      </Box>

      <Card sx={{ bgcolor: tokens.surfaceSunken }}>
        <CardContent>
          <Typography variant="caption" sx={{ color: tokens.inkMuted, fontWeight: 600, letterSpacing: '0.02em', textTransform: 'uppercase' }}>
            Contents
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5, mt: 1 }}>
            {TOC_ITEMS.map((item) => (
              <MuiLink
                key={item.id}
                href={`#${item.id}`}
                onClick={scrollTo(item.id)}
                sx={{ color: tokens.accent, fontSize: '0.875rem', fontWeight: 500, textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}
              >
                {item.label}
              </MuiLink>
            ))}
          </Box>
        </CardContent>
      </Card>

      {/* ---------------------------------------------------------------- */}
      <Section id="contested" title="Contested ranking" status="live">
        <Bullets
          items={[
            'Ranks entities by how sharply spheres disagree — the "front line" view, no editorial call.',
            <>Per entity: 8-bin normalized histogram of scores per sphere (<Kernel>sentiment_histogram</Kernel>), ranked by the <em>worst</em> pairwise divergence, not the mean — one sharp disagreement is the story even if the rest agree.</>,
            'Floor: 10 scored mentions per sphere, so thin coverage can\'t fake a divergence.',
          ]}
        />
        <Formula>{`JSD(P, Q) = ½·D_KL(P‖M) + ½·D_KL(Q‖M),   M = ½(P + Q)
(base-2 log ⇒ bounded in [0, 1]; symmetric, unlike raw KL divergence)`}</Formula>
        <Example caption="GET /narrative/contested?days=30&dimension=moral&limit=5 — live, 2026-07-18">
{`{"entity_name": "Chinese Communist Party", "divergence": 0.8425}
{"entity_name": "Ukrainian government",     "divergence": 0.7756}
{"entity_name": "Hiroshima",                "divergence": 0.6800}
{"entity_name": "Pakistan",                 "divergence": 0.6755}
{"entity_name": "Volodymyr Zelensky",       "divergence": 0.6297}`}
        </Example>
        <Meta>
          <Kernel>contested_ranking</Kernel> + <Kernel>js_divergence</Kernel> + <Kernel>sentiment_histogram</Kernel> ·{' '}
          <Kernel>narrative_endpoints.py::get_contested_ranking</Kernel> → <Kernel>GET /narrative/contested</Kernel>
        </Meta>
        <DashboardLink to="/entities">"The front line" on the Entities page</DashboardLink>
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section id="embeddings" title="Entity relatedness" status="live">
        <Bullets
          items={[
            'What the corpus says two entities have to do with each other — not a hand-curated hierarchy like "Trump → Republicans."',
            <>Co-occurrence vector: PPMI-weighted co-mention matrix → TruncatedSVD (24 dims). Topical signal.</>,
            <>Sentiment vector: entity × (source, week) mean-moral matrix → <Kernel>svd_source_map</Kernel>. Rhetorical signal — talked about the same way, by the same sources, in the same weeks.</>,
            'Kept separate on purpose (never blended); neighbors ranked by cosine similarity.',
          ]}
        />
        <Formula>{`PPMI(i,j) = max(0, log2( count(i,j)·N / (count(i)·count(j)) ))`}</Formula>
        <Example caption="GET /narrative/related/48917 (Joe Biden), limit=5 — live, 2026-07-18">
{`vector=cooccurrence (topical):
  Harrison Fields               0.9963
  Donald Trump                  0.9950
  Department of Justice         0.9946
  Maxine Waters                 0.9938
  Attorney General Pam Bondi    0.9925

vector=sentiment (rhetorical):
  Germany                       0.8143
  Sweden                        0.7971
  United Kingdom                0.7858
  NATO                          0.7664
  Ukraine                       0.7543`}
        </Example>
        <Bullets
          items={[
            'The split does real work: co-occurrence surfaces domestic-politics overlap; sentiment surfaces which countries score Biden the same way (NATO-aligned states).',
          ]}
        />
        <Meta>
          <Kernel>analyzer/entity_embeddings.py</Kernel> (reuses <Kernel>svd_source_map</Kernel>) ·{' '}
          <Kernel>embeddings_endpoints.py</Kernel> → <Kernel>GET /narrative/related/&#123;entity_id&#125;</Kernel> · rebuilt weekly, ≥15 mentions
        </Meta>
        <DashboardLink to="/entities/48917">"Related entities" on an entity profile</DashboardLink>
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section id="drift" title="Drift & changepoint detection" status="live">
        <Bullets
          items={[
            'Separates "everyone moved together" (expected, real-world event) from "this one source moved on its own" — the actual editorial-stance signal.',
            'Pettitt\'s test: single-changepoint test, no normality assumption — fits short, noisy weekly series.',
            <>Run twice per entity: once on the corpus-wide weekly mean (<strong>GLOBAL</strong> shift), once per source on its residual from the global mean (<strong>SOURCE</strong> shift).</>,
            'NaN weeks dropped, not zeroed; needs ≥8 valid weeks; only p<0.05 surfaced.',
          ]}
        />
        <Formula>{`K_t = Σ_{i≤t} Σ_{j>t} sign(x_i − x_j),     K = max_t |K_t|
p ≈ min(1, 2·exp(−6K² / (n³ + n²)))        (asymptotic approximation)
residual_series = source_series − global_series   (per week, before testing)`}</Formula>
        <Example caption="GET /narrative/drift-feed?dimension=moral&limit=2 — live, 2026-07-18">
{`Joe Biden          GLOBAL                        week 2025-05-26
  K=154.0  p=0.000315   mean 0.556 → -0.092

Germany            source: Frankfurter Allgemeine  week 2025-04-07
  K=144.0  p=0.002191   mean 0.000 → 0.066`}
        </Example>
        <Meta>
          <Kernel>pettitt_test</Kernel> + <Kernel>residual_series</Kernel> · live per-entity: <Kernel>GET /narrative/drift/&#123;entity_id&#125;</Kernel> ·
          precomputed feed (<Kernel>drift_detection.py</Kernel>): <Kernel>GET /narrative/drift-feed</Kernel>
        </Meta>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <DashboardLink to="/entities">"Significant shifts" feed</DashboardLink>
          <DashboardLink to="/entities/48917">"Statistical surprise" panel</DashboardLink>
        </Box>
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section id="archetype" title="Archetype & trajectory" status="computed">
        <Bullets
          items={[
            'Where an entity sits on the power × moral plane, and how it\'s moved — this project\'s replacement for a left-right label.',
            'archetype(): quadrant by sign(power, moral); "neutral" only when both axes are weak (< 0.25).',
            'trajectory(): weekly (power, moral) waypoints; needs ≥3 real points to draw a path.',
          ]}
        />
        <Formula>{`archetype(power, moral):
  if |power| < 0.25 and |moral| < 0.25 → "neutral"
  else → quadrant by sign(power), sign(moral)
         (True,True)="hero"  (True,False)="villain"
         (False,True)="victim"  (False,False)="nuisance"`}
        </Formula>
        <Example caption="GET /narrative/archetype/48917?weeks=12 (Joe Biden) — live, 2026-07-18">
{`current_archetype: "villain"
power: 0.774   moral: -0.016
(|power| clears the band, so sign alone decides: power ≥ 0, moral < 0 → villain,
 despite moral being barely negative — the band only fires when both axes are weak)

trajectory (12 weekly waypoints), e.g.:
  week 0:  power 0.769  moral -0.062
  week 4:  power 0.830  moral -0.024
  week 11: power 0.774  moral -0.016`}
        </Example>
        <Meta>
          <Kernel>archetype</Kernel> + <Kernel>trajectory</Kernel> · <Kernel>narrative_endpoints.py::get_entity_archetype</Kernel> →{' '}
          <Kernel>GET /narrative/archetype/&#123;entity_id&#125;</Kernel> · tested, no frontend caller (checked against <Kernel>services/api.ts</Kernel>)
        </Meta>
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section id="source-map" title="Source map (SVD)" status="computed">
        <Bullets
          items={[
            'Empirical axes instead of an asserted left-right spectrum — sources close together score similarly across the same entities.',
            <>Matrix: source × entity mean sentiment, shrunk toward the grand mean by mention count (<Kernel>shrunk_means</Kernel>) — a single-mention cell no longer swings a source\'s position.</>,
            'NaN cells filled with 0 after column-centering (no signal); plain SVD; top-2 components = coordinates.',
          ]}
        />
        <Formula>{`shrunk = (Σx + k·mean_global) / (n + k),  k = 10 pseudo-mentions
SVD(matrix) → top-2 singular vectors × singular values = source coordinates`}
        </Formula>
        <Example caption="GET /narrative/source-map?weeks=12&dimension=moral — live, 2026-07-18">
{`explained_variance: [0.0956, 0.0583]   (dims 1+2 explain ~15% of total variance)

Fox News (USA)              x= 0.49  y=-1.94
The New York Times (USA)    x=-2.53  y=-2.44
The Guardian (UK)           x=-7.65  y= 4.61
RT (Russia)                 x= 1.53  y= 1.69
TASS (Russia)                x= 2.16  y= 2.34`}
        </Example>
        <Bullets
          items={[
            'Read honestly: RT/TASS cluster, NYT/Fox land far apart — but 2 dims explain only ~15% of variance here, so treat placements as suggestive, not precise.',
          ]}
        />
        <Meta>
          <Kernel>svd_source_map</Kernel> + <Kernel>shrunk_means</Kernel> · <Kernel>narrative_endpoints.py::get_source_map</Kernel> →{' '}
          <Kernel>GET /narrative/source-map</Kernel> · tested, not rendered — a scatter-plot view is separate work
        </Meta>
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section id="salience" title="Salience asymmetry" status="computed">
        <Bullets
          items={[
            'Coverage volume, not tone: which entities a sphere covers a lot vs. barely at all — a selection-bias signal, distinct from sentiment.',
            '+1-smoothed log2 ratio of mention rate between two spheres. 0 = equal attention; +3 ≈ 8× louder in sphere A.',
          ]}
        />
        <Formula>{`salience_asymmetry(a, b, total_a, total_b) = log2( (a+1)/(total_a+1)  ÷  (b+1)/(total_b+1) )`}</Formula>
        <Example caption="GET /narrative/salience?country_a=USA&country_b=Russia&days=60 — live, 2026-07-18">
{`"Kiev"                     -7.52   (0 US mentions,  93 Russia mentions)
"Bank of Russia"           -7.49   (0 US mentions,  91 Russia mentions)

country_a=USA&country_b=UK:
"Vladimir V. Putin"        +8.21   (191 US mentions,  0 UK mentions)
"Labour"                   -7.47   (0 US mentions,  272 UK mentions)`}
        </Example>
        <Meta>
          <Kernel>salience_asymmetry</Kernel> · <Kernel>narrative_endpoints.py::get_salience_asymmetry</Kernel> → <Kernel>GET /narrative/salience</Kernel> ·
          tested, no dashboard caller
        </Meta>
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section id="lagged-correlation" title="Lead-lag correlation" status="designed">
        <Bullets
          items={[
            'Does one sphere\'s sentiment move first, and does another follow — not answerable by the dashboard today.',
            'Correlates diff(a) with diff(b) at each lag in [-4, +4]; significance via 1000-permutation shuffle — the defensible alternative to Granger causality on short, noisy series.',
          ]}
        />
        <Formula>{`corr(diff(a), diff(b) shifted by lag)  for lag in [-4, +4]
best_lag = argmax |corr|`}
        </Formula>
        <Example caption="analyzer/narrative_metrics.py::self_test — synthetic series, not corpus data">
{`series B = series A shifted by 2 weeks
→ lagged_correlation recovers best_lag=+2, corr>0.90, p<0.05`}
        </Example>
        <Meta>
          <Kernel>lagged_correlation</Kernel> · self-tested only — no endpoint, no frontend caller
        </Meta>
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section id="synchrony" title="Synchrony score" status="designed">
        <Bullets
          items={[
            'For one entity, do sources in a cluster move together (coordinated) or independently (organic)?',
            'Coordination fingerprint distinct from sentiment agreement — measures whether sources\' changes correlate, not just whether their levels match.',
          ]}
        />
        <Formula>{`synchrony_score = | mean_{i<j} corr(Δsource_i, Δsource_j) |,  bounded [0, 1]
only sources with full (no-gap) coverage across the window are compared`}
        </Formula>
        <Example caption="analyzer/narrative_metrics.py::self_test calibration — synthetic data, not corpus data">
{`5 sources sharing one underlying directive signal → synchrony_score > 0.80
5 fully independent sources                        → synchrony_score < 0.30`}
        </Example>
        <Meta>
          <Kernel>synchrony_score</Kernel> · self-tested, used for real inside <Kernel>event_study.py</Kernel> (below) — but that script is
          standalone, so this kernel has no endpoint and no dashboard caller
        </Meta>
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section id="event-study" title="Event study: does the founding axiom hold?" status="standalone">
        <Bullets
          items={[
            <>Standalone, read-only script (<Kernel>analyzer/event_study.py</Kernel>, never imported by the live pipeline) — tests the founding axiom against the real corpus, run via <Kernel>python -m analyzer.event_study</Kernel>.</>,
            'Corpus\'s only dense multi-source window: 2025-05-12 to 2025-08-25 (16 weeks) — the live pipeline\'s own run. The Jan 6, 2021 case that motivated the script isn\'t in the data at all.',
            'Event case: Israel-Iran war (strikes 2025-06-13). Null case: Canada, same window, no known singular event.',
          ]}
        />
        <Example caption="python -m analyzer.event_study — real output, 2026-07-18">
{`Changepoint (Pettitt's test, global weekly series):
  Iran:    shift at 2025-06-02, p=0.303 (not significant), swing 0.38
  Israel:  shift at 2025-07-21, p=0.048 (significant, but 6 wks after the event)
  Canada:  shift at 2025-06-16, p=0.108 (not significant), swing 0.13   [null]

Cross-country synchronization (the actual founding-axiom test):
  Iran:    19/23 spheres moved with the global shift (83%)  synchrony=0.34
  Israel:  22/29 spheres moved with the global shift (76%)  synchrony=0.32
  Canada:  12/22 spheres moved with the global shift (55%, ≈coin-flip)  synchrony=0.09   [null]`}
        </Example>
        <Bullets
          items={[
            'Synchronization: consistent with the axiom — Iran 83% sign-agreement / 0.34 synchrony vs. Canada\'s 55% (coin-flip) / 0.09, same window.',
            'Changepoint timing: not a clean confirmation — Iran not significant, Israel\'s shift landed 6 weeks late, and the null case cleared some of the same thresholds too.',
            'One event, ~4-month span: plausible and worth continued testing, not settled.',
          ]}
        />
      </Section>
    </Box>
  );
};

export default MethodologyPage;
