import React from 'react';
import { Outlet } from 'react-router-dom';
import { Box, Container, CircularProgress, Typography, Button } from '@mui/material';
import { useData } from '../context/DataContext';
import Masthead from './Masthead';
import FrontDoorHero from './FrontDoorHero';
import SectionNav from './SectionNav';
import StalenessBanner from './StalenessBanner';

const Layout: React.FC = () => {
  const { entities, sources, availableCountries, loading, refreshing, error, refresh } = useData();

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
        <FrontDoorHero
          entityCount={entities.length}
          sourceCount={sources.length}
          countryCount={availableCountries.length || 10}
        />
        <SectionNav />
        <Outlet />
      </Box>
    </Container>
  );
};

export default Layout;
