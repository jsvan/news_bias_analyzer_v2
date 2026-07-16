import { createTheme } from '@mui/material/styles';

// Design tokens — source of truth in /DESIGN.md (OKLCH values documented there;
// hex here because MUI's alpha()/decomposeColor() don't parse oklch()).
export const tokens = {
  paper: '#F6F7F9',
  surface: '#FDFDFE',
  surfaceSunken: '#EEF0F3',
  ink: '#171A20',
  inkMuted: '#5B6270',
  border: '#DEE1E6',
  accent: '#0E6E78',
  accentHover: '#0A5960',
  hero: '#1E7A4C',
  victim: '#7C3F8C',
  villain: '#AC2A3C',
  threat: '#B06A0E',
  categorical: [
    '#0E6E78', // teal
    '#B06A0E', // amber
    '#7C3F8C', // plum
    '#1E7A4C', // forest
    '#3C5A78', // slate-blue
    '#B0522F', // terracotta
    '#6E7A1E', // olive
    '#9C4066', // rose
    '#463C8C', // indigo
    '#5B6270', // graphite
  ],
};

// Assigns a stable categorical color by first-appearance order — replaces any
// fixed name/country -> color map (that pattern reads as a partisan mapping).
export function categoricalColor(key: string, seenOrder: string[]): string {
  const index = seenOrder.indexOf(key);
  const palette = tokens.categorical;
  return palette[(index < 0 ? seenOrder.length : index) % palette.length];
}

export const archetypeColor = (powerScore: number, moralScore: number): string => {
  if (moralScore >= 0) return powerScore >= 0 ? tokens.hero : tokens.victim;
  return powerScore >= 0 ? tokens.villain : tokens.threat;
};

export type ArchetypeLabel = 'Hero' | 'Victim' | 'Villain' | 'Threat';

export const archetypeLabel = (powerScore: number, moralScore: number): ArchetypeLabel => {
  if (moralScore >= 0) return powerScore >= 0 ? 'Hero' : 'Victim';
  return powerScore >= 0 ? 'Villain' : 'Threat';
};

const fontDisplay = '"Newsreader", Georgia, serif';
const fontSans = '"IBM Plex Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
const fontMono = '"IBM Plex Mono", "SFMono-Regular", Menlo, monospace';

export const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: tokens.accent, dark: tokens.accentHover, contrastText: '#FFFFFF' },
    secondary: { main: tokens.villain, contrastText: '#FFFFFF' },
    success: { main: tokens.hero },
    warning: { main: tokens.threat },
    error: { main: tokens.villain },
    info: { main: tokens.accent },
    background: { default: tokens.paper, paper: tokens.surface },
    text: { primary: tokens.ink, secondary: tokens.inkMuted },
    divider: tokens.border,
  },
  shape: { borderRadius: 10 },
  typography: {
    fontFamily: fontSans,
    h1: { fontFamily: fontDisplay, fontWeight: 600, letterSpacing: '-0.015em' },
    h2: { fontFamily: fontDisplay, fontWeight: 600, letterSpacing: '-0.015em' },
    h3: { fontFamily: fontDisplay, fontWeight: 600, letterSpacing: '-0.01em' },
    h4: { fontFamily: fontDisplay, fontWeight: 600, fontSize: '1.75rem', letterSpacing: '-0.01em' },
    h5: { fontFamily: fontDisplay, fontWeight: 600, fontSize: '1.375rem' },
    h6: { fontWeight: 600, fontSize: '1.125rem' },
    subtitle1: { fontSize: '1.125rem' },
    subtitle2: { fontSize: '0.875rem', fontWeight: 600 },
    body1: { fontSize: '1rem' },
    body2: { fontSize: '0.875rem' },
    caption: { fontSize: '0.75rem' },
    button: { textTransform: 'none', fontWeight: 600 },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: { backgroundColor: tokens.paper },
        '*::-webkit-scrollbar': { width: 8, height: 8 },
        '*::-webkit-scrollbar-track': { background: tokens.surfaceSunken },
        '*::-webkit-scrollbar-thumb': { backgroundColor: tokens.border, borderRadius: 4 },
        '*::-webkit-scrollbar-thumb:hover': { backgroundColor: tokens.inkMuted },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          boxShadow: 'none',
          border: `1px solid ${tokens.border}`,
          borderRadius: 10,
          backgroundColor: tokens.surface,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: { backgroundImage: 'none' },
        outlined: { borderColor: tokens.border },
      },
      defaultProps: { elevation: 0 },
    },
    MuiButton: {
      styleOverrides: {
        root: { borderRadius: 6, boxShadow: 'none' },
        contained: { boxShadow: 'none', '&:hover': { boxShadow: 'none' } },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { fontWeight: 500 },
      },
    },
    MuiTabs: {
      styleOverrides: {
        root: { minHeight: 44 },
        indicator: { height: 2, backgroundColor: tokens.ink },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          fontFamily: fontSans,
          textTransform: 'none',
          fontWeight: 500,
          minHeight: 44,
          color: tokens.inkMuted,
          '&.Mui-selected': { color: tokens.ink, fontWeight: 600 },
        },
      },
    },
  },
});

export const monoNumber = { fontFamily: fontMono, fontVariantNumeric: 'tabular-nums' } as const;
export { fontDisplay, fontSans, fontMono };
