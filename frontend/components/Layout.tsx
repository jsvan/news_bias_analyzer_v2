import React from 'react';
import { Outlet, Link as RouterLink } from 'react-router-dom';
import { Box, Container, CircularProgress, Typography, Button } from '@mui/material';
import { useData } from '../context/DataContext';
import { tokens } from '../theme';
import Masthead from './Masthead';
import SectionNav from './SectionNav';
import StalenessBanner from './StalenessBanner';

const footerLinkSx = {
  color: tokens.inkMuted,
  textDecoration: 'none',
  '&:hover': { color: tokens.ink },
} as const;

const Layout: React.FC = () => {
  const { loading, refreshing, error, refresh } = useData();

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <Typography variant="h5" color="error" gutterBottom sx={{ whiteSpace: 'pre-line' }}>
          {error}
        </Typography>
        <Button variant="contained" sx={{ mt: 3 }} onClick={refresh}>
          Retry
        </Button>
      </Box>
    );
  }

  return (
    <Container maxWidth="xl">
      <Box sx={{ py: 4 }}>
        <Masthead onRefresh={refresh} refreshing={refreshing} />
        <StalenessBanner />
        <SectionNav />
        <Outlet />
        <Box
          component="footer"
          sx={{
            borderTop: `1px solid ${tokens.border}`,
            mt: 8,
            pt: 2.5,
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'baseline',
            justifyContent: 'space-between',
            columnGap: 3,
            rowGap: 1,
          }}
        >
          <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
            News Bias Analyzer — a mirror for the global information landscape
          </Typography>
          <Box sx={{ display: 'flex', gap: 3 }}>
            <Typography component={RouterLink} to="/methodology" variant="caption" sx={footerLinkSx}>
              How this works
            </Typography>
            <Typography component={RouterLink} to="/infrastructure" variant="caption" sx={footerLinkSx}>
              Infrastructure
            </Typography>
          </Box>
        </Box>
      </Box>
    </Container>
  );
};

export default Layout;
