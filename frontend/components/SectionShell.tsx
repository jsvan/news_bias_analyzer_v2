import React from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { Box, Typography } from '@mui/material';
import { tokens, fontDisplay } from '../theme';

interface SubTab {
  to: string;
  label: string;
  // Overrides NavLink's prefix matching where a tab owns more than its own
  // subtree (e.g. "All entities" also owns /portrayals/:id profile pages).
  isActive?: (pathname: string) => boolean;
}

interface SectionConfig {
  name: string;
  question: string;
  tabs: SubTab[];
}

// One section per front-page doorway; the doorway question doubles as the
// section's standing subhead so the nav teaches the three-question model.
const SECTIONS: Record<'coverage' | 'portrayals' | 'landscape', SectionConfig> = {
  coverage: {
    name: 'Coverage',
    question: 'What is the press talking about?',
    tabs: [
      { to: '/coverage/countries', label: 'By country' },
      { to: '/coverage/newspapers', label: 'By newspaper' },
    ],
  },
  portrayals: {
    name: 'Portrayals',
    question: 'How is one thing portrayed?',
    tabs: [
      {
        to: '/portrayals',
        label: 'All entities',
        isActive: (pathname) =>
          pathname.startsWith('/portrayals') && !pathname.startsWith('/portrayals/side-by-side'),
      },
      { to: '/portrayals/side-by-side', label: 'Side by side' },
    ],
  },
  landscape: {
    name: 'The Landscape',
    question: 'How do the newspapers compare?',
    tabs: [
      { to: '/landscape/map', label: 'Source map' },
      { to: '/landscape/diets', label: 'Compare diets' },
      { to: '/landscape/my-bubble', label: 'My Bubble' },
    ],
  },
};

const tabStyle = (isActive: boolean): React.CSSProperties => ({
  textDecoration: 'none',
  color: isActive ? tokens.ink : tokens.inkMuted,
  fontFamily: '"IBM Plex Sans", -apple-system, sans-serif',
  fontSize: '0.875rem',
  fontWeight: isActive ? 600 : 500,
  whiteSpace: 'nowrap',
  paddingBottom: 3,
  borderBottom: `2px solid ${isActive ? tokens.ink : 'transparent'}`,
  transition: 'color 180ms cubic-bezier(0.22, 1, 0.36, 1), border-color 180ms cubic-bezier(0.22, 1, 0.36, 1)',
});

const SectionShell: React.FC<{ section: keyof typeof SECTIONS }> = ({ section }) => {
  const { name, question, tabs } = SECTIONS[section];
  const { pathname } = useLocation();

  return (
    <>
      <Box
        component="header"
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          columnGap: 3,
          rowGap: 1.5,
          mb: 3,
        }}
      >
        <Typography
          component="h2"
          sx={{
            fontFamily: fontDisplay,
            fontStyle: 'italic',
            fontWeight: 500,
            fontSize: '1.375rem',
            lineHeight: 1.2,
            letterSpacing: '-0.01em',
          }}
        >
          {question}
        </Typography>
        <Box component="nav" aria-label={`${name} views`} sx={{ display: 'flex', gap: 3 }}>
          {tabs.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              style={({ isActive }) => tabStyle(tab.isActive ? tab.isActive(pathname) : isActive)}
            >
              {tab.label}
            </NavLink>
          ))}
        </Box>
      </Box>
      <Outlet />
    </>
  );
};

export default SectionShell;
