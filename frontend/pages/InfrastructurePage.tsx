import React, { useState } from 'react';
import { Box, Typography, ToggleButton, ToggleButtonGroup, Link as MuiLink } from '@mui/material';
import { tokens, fontMono } from '../theme';

// Flow-diagram primitives following mermaid's shape conventions — rounded rect =
// process, cylinder = datastore, dashed = external service, pill = user-facing
// endpoint — hand-drawn with theme tokens instead of the mermaid library so the
// chart reads as part of the instrument, not an embedded screenshot.

type NodeKind = 'process' | 'store' | 'external' | 'terminal';

interface FlowNodeProps {
  kind?: NodeKind;
  title: string;
  detail?: React.ReactNode;
  path?: string;
}

const nodeBase = {
  px: 2.5,
  py: 1.5,
  textAlign: 'center' as const,
  maxWidth: 480,
  alignSelf: 'center',
  bgcolor: tokens.surface,
  border: `1px solid ${tokens.border}`,
  borderRadius: '10px',
};

const CYLINDER_CAP = 11; // px half-height of the datastore's elliptical cap

const nodeKindSx: Record<NodeKind, object> = {
  process: {},
  store: {
    position: 'relative',
    mt: `${CYLINDER_CAP}px`,
    pt: 2.25,
    pb: 2,
    borderTop: 'none',
    borderRadius: `0 0 50% 50% / 0 0 ${CYLINDER_CAP + 3}px ${CYLINDER_CAP + 3}px`,
    '&::before': {
      content: '""',
      position: 'absolute',
      left: '-1px',
      right: '-1px',
      top: `-${CYLINDER_CAP}px`,
      height: `${CYLINDER_CAP * 2}px`,
      bgcolor: tokens.surface,
      border: `1px solid ${tokens.border}`,
      borderRadius: '50%',
    },
  },
  external: {
    borderStyle: 'dashed',
    bgcolor: tokens.surfaceSunken,
  },
  terminal: {
    borderRadius: '999px',
    borderColor: tokens.ink,
    px: 3,
  },
};

const FlowNode: React.FC<FlowNodeProps> = ({ kind = 'process', title, detail, path }) => (
  <Box sx={{ ...nodeBase, ...nodeKindSx[kind] }}>
    <Typography variant="body2" sx={{ fontWeight: 600, color: tokens.ink, position: 'relative' }}>
      {title}
    </Typography>
    {detail && (
      <Typography variant="caption" sx={{ color: tokens.inkMuted, display: 'block', mt: 0.25, lineHeight: 1.6 }}>
        {detail}
      </Typography>
    )}
    {path && (
      <Typography
        variant="caption"
        sx={{ fontFamily: fontMono, fontSize: '0.6875rem', color: tokens.accent, display: 'block', mt: 0.5 }}
      >
        {path}
      </Typography>
    )}
  </Box>
);

// Vertical edge with an on-the-line label (mermaid-style: label sits on the edge
// with the page background behind it).
const Arrow: React.FC<{ label?: React.ReactNode; minHeight?: number }> = ({ label, minHeight = 48 }) => (
  <Box
    sx={{
      position: 'relative',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight,
      py: label ? 0.75 : 0,
    }}
  >
    <Box
      sx={{
        position: 'absolute',
        top: 0,
        bottom: 0,
        left: '50%',
        width: '1.5px',
        ml: '-0.75px',
        bgcolor: tokens.inkMuted,
      }}
    />
    <Box
      sx={{
        position: 'absolute',
        bottom: '-1px',
        left: '50%',
        transform: 'translateX(-50%)',
        width: 0,
        height: 0,
        borderLeft: '5px solid transparent',
        borderRight: '5px solid transparent',
        borderTop: `7px solid ${tokens.inkMuted}`,
      }}
    />
    {label && (
      <Typography
        variant="caption"
        sx={{
          position: 'relative',
          bgcolor: tokens.paper,
          px: 1,
          py: 0.25,
          fontFamily: fontMono,
          fontSize: '0.6875rem',
          color: tokens.inkMuted,
          textAlign: 'center',
          maxWidth: '88%',
          lineHeight: 1.6,
          borderRadius: '4px',
        }}
      >
        {label}
      </Typography>
    )}
  </Box>
);

// Round-trip edge between two side-by-side nodes: a labeled arrow each way.
// Horizontal on wide screens, collapses to a stacked pair of vertical arrows on
// phones (where the two nodes stack).
const Exchange: React.FC<{ up: string; down: string }> = ({ up, down }) => (
  <>
    {/* md+: horizontal round trip */}
    <Box
      sx={{
        display: { xs: 'none', md: 'flex' },
        flexDirection: 'column',
        gap: 1.75,
        px: 1.5,
        minWidth: 170,
        alignSelf: 'center',
      }}
    >
      {[
        { label: up, dir: 'right' as const },
        { label: down, dir: 'left' as const },
      ].map(({ label, dir }) => (
        <Box key={dir}>
          <Typography
            variant="caption"
            sx={{
              fontFamily: fontMono,
              fontSize: '0.6875rem',
              color: tokens.inkMuted,
              display: 'block',
              textAlign: 'center',
              mb: 0.5,
              lineHeight: 1.5,
            }}
          >
            {label}
          </Typography>
          <Box sx={{ position: 'relative', height: '1.5px', bgcolor: tokens.inkMuted }}>
            <Box
              sx={{
                position: 'absolute',
                top: '-4.25px',
                [dir === 'right' ? 'right' : 'left']: '-1px',
                width: 0,
                height: 0,
                borderTop: '5px solid transparent',
                borderBottom: '5px solid transparent',
                [dir === 'right' ? 'borderLeft' : 'borderRight']: `7px solid ${tokens.inkMuted}`,
              }}
            />
          </Box>
        </Box>
      ))}
    </Box>
    {/* xs: the pair of nodes stacks, so the round trip becomes ↓ then ↑ */}
    <Box sx={{ display: { xs: 'flex', md: 'none' }, justifyContent: 'center', gap: 5, minHeight: 56 }}>
      {[
        { label: up, head: 'bottom' as const },
        { label: down, head: 'top' as const },
      ].map(({ label, head }) => (
        <Box key={head} sx={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
          <Box sx={{ position: 'absolute', top: 0, bottom: 0, left: '50%', width: '1.5px', ml: '-0.75px', bgcolor: tokens.inkMuted }} />
          <Box
            sx={{
              position: 'absolute',
              [head === 'bottom' ? 'bottom' : 'top']: '-1px',
              left: '50%',
              transform: 'translateX(-50%)',
              width: 0,
              height: 0,
              borderLeft: '5px solid transparent',
              borderRight: '5px solid transparent',
              [head === 'bottom' ? 'borderTop' : 'borderBottom']: `7px solid ${tokens.inkMuted}`,
            }}
          />
          <Typography
            variant="caption"
            sx={{
              position: 'relative',
              bgcolor: tokens.paper,
              px: 0.75,
              fontFamily: fontMono,
              fontSize: '0.625rem',
              color: tokens.inkMuted,
              maxWidth: 130,
              textAlign: 'center',
              lineHeight: 1.5,
            }}
          >
            {label}
          </Typography>
        </Box>
      ))}
    </Box>
  </>
);

// One edge splitting into two branch columns (branch centers at 25% / 75%,
// matching a gap-less 1fr/1fr grid below). Hidden on phones, where each branch
// column renders its own labeled Arrow instead.
const Fork: React.FC = () => (
  <Box sx={{ display: { xs: 'none', sm: 'block' }, position: 'relative', height: 56 }}>
    <svg width="100%" height="56" viewBox="0 0 100 56" preserveAspectRatio="none" aria-hidden="true">
      <path
        d="M50,0 V8 C50,28 25,26 25,42 V56"
        fill="none"
        stroke={tokens.inkMuted}
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />
      <path
        d="M50,0 V8 C50,28 75,26 75,42 V56"
        fill="none"
        stroke={tokens.inkMuted}
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
    {['25%', '75%'].map((left) => (
      <Box
        key={left}
        sx={{
          position: 'absolute',
          bottom: '-1px',
          left,
          transform: 'translateX(-50%)',
          width: 0,
          height: 0,
          borderLeft: '5px solid transparent',
          borderRight: '5px solid transparent',
          borderTop: `7px solid ${tokens.inkMuted}`,
        }}
      />
    ))}
  </Box>
);

// Self-loop annotation attached below a datastore: jobs that read the store and
// write back to it on a schedule.
const WriteBackLoop: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <Box
    sx={{
      alignSelf: 'center',
      mt: 1.25,
      px: 2,
      py: 1.25,
      maxWidth: 520,
      border: `1px dashed ${tokens.border}`,
      borderRadius: '8px',
      display: 'flex',
      gap: 1.5,
      alignItems: 'baseline',
    }}
  >
    <Typography aria-hidden="true" sx={{ fontFamily: fontMono, fontSize: '1rem', color: tokens.inkMuted, lineHeight: 1 }}>
      ↺
    </Typography>
    <Box>
      <Typography variant="caption" sx={{ fontWeight: 600, color: tokens.ink, display: 'block' }}>
        {title}
      </Typography>
      <Typography variant="caption" sx={{ color: tokens.inkMuted, lineHeight: 1.7 }}>
        {children}
      </Typography>
    </Box>
  </Box>
);

const Legend: React.FC = () => {
  const swatch = {
    width: 26,
    height: 15,
    border: `1px solid ${tokens.inkMuted}`,
    flexShrink: 0,
    bgcolor: tokens.surface,
  };
  return (
    <Box
      sx={{
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'center',
        columnGap: 3,
        rowGap: 1,
        pt: 3,
        mt: 1,
        borderTop: `1px solid ${tokens.border}`,
      }}
    >
      {(
        [
          [{ ...swatch, borderRadius: '5px' }, 'process'],
          [{ ...swatch, borderRadius: '3px 3px 50% 50% / 3px 3px 7px 7px' }, 'datastore'],
          [{ ...swatch, borderRadius: '5px', borderStyle: 'dashed', bgcolor: tokens.surfaceSunken }, 'external service'],
          [{ ...swatch, borderRadius: '999px' }, 'what you use'],
        ] as [object, string][]
      ).map(([sx, label]) => (
        <Box key={label} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={sx} />
          <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
            {label}
          </Typography>
        </Box>
      ))}
    </Box>
  );
};

// ---------------------------------------------------------------------------
// The two architectures
// ---------------------------------------------------------------------------

const CurrentDiagram: React.FC = () => (
  <Box sx={{ display: 'flex', flexDirection: 'column' }}>
    <FlowNode
      kind="external"
      title="Global news feeds"
      detail="176 RSS feeds from outlets in 42 countries"
      path="scrapers/news_sources.py"
    />
    <Arrow label="scheduled fetch · every 30 min" />
    <FlowNode
      kind="process"
      title="Parallel scraper"
      detail="pulls each feed, extracts article text, skips what's already stored"
      path="scrapers/parallel_scraper.py"
    />
    <Arrow label="raw articles" />
    <FlowNode kind="store" title="PostgreSQL · articles" detail="full text, source, country, publish date" />
    <Arrow label="unanalyzed articles · batches of 100 · ≤ 5 batches in flight" />
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', md: 'minmax(0, 1fr) auto minmax(0, 1fr)' },
        alignItems: 'center',
        rowGap: 0,
        justifyItems: 'center',
      }}
    >
      <FlowNode
        kind="process"
        title="Batch analyzer"
        detail="builds one JSONL request per article, uploads, polls, ingests results"
        path="analyzer/batch_analyzer.py"
      />
      <Exchange up="JSONL batch up" down="entity–sentiment tuples back" />
      <FlowNode
        kind="external"
        title="OpenAI Batch API"
        detail="gpt-5-nano reads each article and scores every entity it mentions"
      />
    </Box>
    <Arrow label="entity mentions · power & moral, each in [-2, +2]" />
    <FlowNode kind="store" title="PostgreSQL · entities & mentions" detail="the single source every chart on this site reads from" />
    <WriteBackLoop title="Scheduled write-backs">
      Sundays: entity merge 01:00 · pruning 01:15 · source similarity 02:00 · embeddings 02:30 · drift
      detection 02:45. Daily: materialized-view refresh 00:30.
    </WriteBackLoop>
    <Box sx={{ height: 12 }} />
    <Fork />
    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, alignItems: 'start' }}>
      <Box sx={{ display: 'flex', flexDirection: 'column', px: { xs: 0, sm: 1 } }}>
        <Box sx={{ display: { xs: 'block', sm: 'none' } }}>
          <Arrow label="live path" />
        </Box>
        <FlowNode
          kind="process"
          title="FastAPI server"
          detail="dashboard · narrative · drift · embeddings · similarity · synchrony · statistical routers"
          path="server/extension_api.py"
        />
        <Arrow label="REST · JSON" minHeight={40} />
        <Box sx={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 1.5 }}>
          <FlowNode kind="terminal" title="Web dashboard" detail="live mode" />
          <FlowNode kind="terminal" title="Chrome extension" />
        </Box>
      </Box>
      <Box sx={{ display: 'flex', flexDirection: 'column', px: { xs: 0, sm: 1 }, mt: { xs: 3, sm: 0 } }}>
        <Box sx={{ display: { xs: 'block', sm: 'none' } }}>
          <Arrow label="static path" />
        </Box>
        <FlowNode
          kind="process"
          title="Snapshot export"
          detail="calls the live API handlers directly and dumps their JSON, so snapshots always match the API shapes"
          path="server/export_snapshots.py"
        />
        <Arrow label="git commit · Pages build" minHeight={40} />
        <FlowNode kind="terminal" title="Dashboard on GitHub Pages" detail="static mode — no server" />
      </Box>
    </Box>
    <Legend />
  </Box>
);

const OriginalDiagram: React.FC = () => (
  <Box sx={{ display: 'flex', flexDirection: 'column' }}>
    <FlowNode kind="external" title="News articles across the web" detail="any site, any language" />
    <Arrow label="read & annotate in the browser" />
    <FlowNode
      kind="process"
      title="CommonSents · Chrome extension"
      detail="highlight a sentence, tag its keywords Pos / Neg / Neu — hotkeys or right-click menu"
      path="github.com/jsvan/CommonSents"
    />
    <Arrow label="annotations" />
    <FlowNode kind="store" title="Browser localStorage" detail="everything stays on the annotator's machine" />
    <Arrow label="copy / paste the formatted dump" />
    <FlowNode
      kind="process"
      title="Automated collection inbox"
      detail="annotators emailed their dumps; each sample auto-translated to English"
    />
    <Arrow label="~2 weeks of hand-labeled sentences" />
    <FlowNode
      kind="store"
      title="Fine-grained news-sentiment dataset"
      detail="built because no public dataset labeled sentiment per keyword in real news text"
    />
    <Arrow label="fine-tune" />
    <FlowNode
      kind="process"
      title="BERT masking model"
      detail={
        <>
          named entities BERT picks out are covered with <code style={{ fontFamily: fontMono }}>[MASK]</code>; the
          model emits a sentiment marker for each mask
        </>
      }
    />
    <Arrow />
    <FlowNode kind="terminal" title="Per-entity sentiment markers" detail="the ancestor of today's power & moral scores" />
    <Legend />
  </Box>
);

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

type View = 'current' | 'original';

const InfrastructurePage: React.FC = () => {
  const [view, setView] = useState<View>('current');

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, maxWidth: 880, mx: 'auto' }}>
      <Box>
        <Typography variant="h4" sx={{ mb: 1 }}>
          Infrastructure
        </Typography>
        <Typography variant="body1" sx={{ color: tokens.inkMuted, maxWidth: 720 }}>
          The machinery behind the dashboard: what collects the articles, what scores them, and how the
          results reach you. The pipeline running today is the default view; toggle to see the original
          BERT-based design it grew out of.
        </Typography>
      </Box>

      <ToggleButtonGroup
        exclusive
        value={view}
        onChange={(_, v: View | null) => v && setView(v)}
        aria-label="architecture version"
        sx={{
          alignSelf: 'flex-start',
          bgcolor: tokens.surface,
          '& .MuiToggleButton-root': {
            textTransform: 'none',
            fontWeight: 600,
            fontSize: '0.875rem',
            px: 2.25,
            py: 0.75,
            color: tokens.inkMuted,
            borderColor: tokens.border,
            '&.Mui-selected': {
              bgcolor: tokens.accent,
              color: '#fff',
              '&:hover': { bgcolor: tokens.accentHover },
            },
          },
        }}
      >
        <ToggleButton value="current">Current pipeline</ToggleButton>
        <ToggleButton value="original">Original (BERT)</ToggleButton>
      </ToggleButtonGroup>

      <Box
        key={view}
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: 3,
          '@keyframes viewFade': {
            from: { opacity: 0, transform: 'translateY(6px)' },
            to: { opacity: 1, transform: 'none' },
          },
          animation: 'viewFade 220ms cubic-bezier(0.22, 1, 0.36, 1)',
          '@media (prefers-reduced-motion: reduce)': { animation: 'none' },
        }}
      >
        {view === 'current' ? (
          <>
            <Typography variant="body2" sx={{ color: tokens.inkMuted, maxWidth: 720 }}>
              176 feeds in 42 countries are scraped every half hour. OpenAI's Batch API scores every entity
              mention on two axes — power and moral, each in [-2, +2] — and everything downstream reads
              from one PostgreSQL database.
            </Typography>
            <CurrentDiagram />
          </>
        ) : (
          <>
            <Typography variant="body2" sx={{ color: tokens.inkMuted, maxWidth: 720 }}>
              Before the OpenAI pipeline, sentiment came from an in-house BERT model. The training data
              had to be collected by hand first, because no public dataset labeled fine-grained sentiment
              on real news text.
            </Typography>
            <OriginalDiagram />
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, maxWidth: 720 }}>
              <Typography variant="h6">Hand annotation: CommonSents</Typography>
              <Typography variant="body2">
                <MuiLink href="https://github.com/jsvan/CommonSents" target="_blank" rel="noopener" sx={{ color: tokens.accent, fontWeight: 600 }}>
                  CommonSents
                </MuiLink>{' '}
                was a Chrome extension for turning ordinary news reading into annotation. It worked on any
                website: highlight a sentence, then mark the keywords inside it as positive, negative, or
                neutral with hotkeys or a right-click menu. Annotations lived in the browser's
                localStorage, and contributors copy-pasted the formatted contents into an email to an
                automated collection account. Foreign-language articles were fair game — each sample was
                auto-translated to English on arrival. Within about two weeks the extension had collected
                enough labeled sentences to train on.
              </Typography>
              <Box
                component="blockquote"
                sx={{
                  m: 0,
                  mt: 0.5,
                  pl: 2,
                  borderLeft: `1px solid ${tokens.border}`,
                }}
              >
                <Typography variant="body2" sx={{ fontStyle: 'italic', color: tokens.inkMuted }}>
                  "This is actually super fun to do with legal articles because these are supposed to be
                  neutral and so they mostly are, but when you read them piece by piece like you have to do
                  in order to code them, it really highlights how legal writing can very powerfully shape
                  your understanding of an issue through subtle sentiment markers."
                </Typography>
                <Typography variant="caption" sx={{ color: tokens.inkMuted, display: 'block', mt: 0.5 }}>
                  — Anya Vanecek, CommonSents annotator
                </Typography>
              </Box>
              <Typography variant="h6" sx={{ mt: 1 }}>
                The masking model
              </Typography>
              <Typography variant="body2">
                The dataset fine-tuned a BERT model on a masking task. Named entities the model picked out
                were covered with a <code style={{ fontFamily: fontMono, fontSize: '0.8125rem' }}>[MASK]</code>{' '}
                token, and the model learned to output a sentiment marker for each mask — tying sentiment
                to the entity itself rather than to the sentence around it. That entity-level framing is
                the part that survived: the extraction engine changed from BERT to OpenAI batch scoring,
                but the unit of analysis is still the entity mention, now scored on power and moral axes
                instead of a single polarity.
              </Typography>
            </Box>
          </>
        )}
      </Box>
    </Box>
  );
};

export default InfrastructurePage;
