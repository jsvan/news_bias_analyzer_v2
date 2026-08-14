import React from 'react';
import { NavLink } from 'react-router-dom';
import { tokens } from '../theme';

const SECTIONS = [
  { to: '/entities', label: 'Entities' },
  { to: '/sources', label: 'Sources' },
  { to: '/source-space', label: 'Source Space' },
  { to: '/countries', label: 'Countries' },
  { to: '/compare/entities', label: 'Compare', activeMatch: '/compare' },
  { to: '/stories', label: 'Stories' },
  { to: '/my-bubble', label: 'My Bubble' },
  { to: '/methodology', label: 'How this works' },
  { to: '/infrastructure', label: 'Infrastructure' },
];

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
      <NavLink
        key={section.to}
        to={section.to}
        style={({ isActive }) =>
          linkStyle(section.activeMatch ? location.hash.includes(section.activeMatch) : isActive)
        }
      >
        {section.label}
      </NavLink>
    ))}
  </nav>
);

export default SectionNav;
