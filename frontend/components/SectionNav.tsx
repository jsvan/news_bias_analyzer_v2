import React from 'react';
import { NavLink } from 'react-router-dom';
import { tokens } from '../theme';

// One link per front-page doorway (Coverage / Portrayals / The Landscape) plus
// the standing reads; each section's own views live in its SectionShell subnav.
const SECTIONS: { to: string; label: string; end?: boolean }[] = [
  // end: exact match only — "/" is a prefix of every route, so without it the
  // Front Page link would read as active everywhere.
  { to: '/', label: 'Front Page', end: true },
  { to: '/coverage', label: 'Coverage' },
  { to: '/portrayals', label: 'Portrayals' },
  { to: '/landscape', label: 'The Landscape' },
  { to: '/stories', label: 'Stories' },
];

// About the instrument rather than a content section — set apart on the right.
const META = { to: '/methodology', label: 'How this works' };

const linkStyle = (isActive: boolean): React.CSSProperties => ({
  textDecoration: 'none',
  color: isActive ? tokens.ink : tokens.inkMuted,
  fontFamily: '"IBM Plex Sans", -apple-system, sans-serif',
  fontSize: '0.875rem',
  fontWeight: isActive ? 600 : 500,
  whiteSpace: 'nowrap',
  padding: '12px 0',
  borderBottom: `2px solid ${isActive ? tokens.ink : 'transparent'}`,
  transition: 'color 180ms cubic-bezier(0.22, 1, 0.36, 1), border-color 180ms cubic-bezier(0.22, 1, 0.36, 1)',
});

const SectionNav: React.FC = () => (
  <nav
    style={{
      display: 'flex',
      gap: 24,
      overflowX: 'auto',
      borderBottom: `1px solid ${tokens.border}`,
      marginBottom: 32,
    }}
  >
    {SECTIONS.map((section) => (
      <NavLink key={section.to} to={section.to} end={section.end} style={({ isActive }) => linkStyle(isActive)}>
        {section.label}
      </NavLink>
    ))}
    <NavLink to={META.to} style={({ isActive }) => ({ ...linkStyle(isActive), marginLeft: 'auto' })}>
      {META.label}
    </NavLink>
  </nav>
);

export default SectionNav;
