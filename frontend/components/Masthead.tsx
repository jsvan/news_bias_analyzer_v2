import React, { useMemo, useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { Box, Typography, IconButton, Tooltip, CircularProgress, Autocomplete, TextField } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import DownloadIcon from '@mui/icons-material/Download';
import SearchIcon from '@mui/icons-material/Search';
import { tokens } from '../theme';
import { useData } from '../context/DataContext';
import { EntityType } from '../types';

interface MastheadProps {
  onRefresh: () => void;
  refreshing: boolean;
}

interface SearchOption {
  label: string;
  kind: 'Entity' | 'Source';
  entityType?: EntityType;
  to: string;
}

const SearchBox: React.FC = () => {
  const { entities, sources } = useData();
  const navigate = useNavigate();
  const [inputValue, setInputValue] = useState('');

  const options: SearchOption[] = useMemo(
    () => [
      ...entities.map((e) => ({
        label: e.name, kind: 'Entity' as const, entityType: e.type, to: `/entities/${e.id}`,
      })),
      ...sources.map((s) => ({ label: s.name, kind: 'Source' as const, to: `/sources/${encodeURIComponent(s.name)}` })),
    ],
    [entities, sources]
  );

  return (
    <Autocomplete
      freeSolo
      size="small"
      options={options}
      groupBy={(o) => o.kind}
      inputValue={inputValue}
      onInputChange={(_, value) => setInputValue(value)}
      getOptionLabel={(o) => (typeof o === 'string' ? o : o.label)}
      // Same-named entities of different types (e.g. two "Washington") are otherwise
      // indistinguishable in the dropdown - the type tag disambiguates without changing
      // what gets typed into the box when one is picked (getOptionLabel stays name-only).
      renderOption={(props, option) => (
        <Box component="li" {...props} sx={{ display: 'flex', justifyContent: 'space-between', gap: 1 }}>
          <span>{option.label}</span>
          {option.entityType && (
            <Typography variant="caption" sx={{ color: tokens.inkMuted }}>
              {option.entityType}
            </Typography>
          )}
        </Box>
      )}
      filterOptions={(opts, state) => {
        if (state.inputValue.length < 2) return [];
        const q = state.inputValue.toLowerCase();
        return opts.filter((o) => o.label.toLowerCase().includes(q)).slice(0, 12);
      }}
      onChange={(_, value) => {
        if (value && typeof value !== 'string') navigate(value.to);
      }}
      onKeyDown={(e) => {
        if (e.key === 'Enter' && inputValue.trim()) {
          navigate(`/search?q=${encodeURIComponent(inputValue.trim())}`);
        }
      }}
      sx={{ width: { xs: '100%', sm: 260 } }}
      renderInput={(params) => (
        <TextField
          {...params}
          placeholder="Search entities, sources..."
          InputProps={{
            ...params.InputProps,
            startAdornment: <SearchIcon fontSize="small" sx={{ color: tokens.inkMuted, mr: 0.5 }} />,
          }}
        />
      )}
    />
  );
};

const Masthead: React.FC<MastheadProps> = ({ onRefresh, refreshing }) => (
  <Box
    component="header"
    sx={{
      display: 'flex',
      flexWrap: 'wrap',
      gap: 2,
      justifyContent: 'space-between',
      alignItems: 'flex-end',
      borderBottom: `1px solid ${tokens.border}`,
      pb: 2,
      mb: 3,
    }}
  >
    <Box component={RouterLink} to="/" sx={{ textDecoration: 'none', color: 'inherit' }}>
      <Typography
        variant="h4"
        component="h1"
        sx={{ fontStyle: 'italic', lineHeight: 1.1 }}
      >
        News Bias Analyzer
      </Typography>
      <Typography variant="body2" sx={{ color: tokens.inkMuted, mt: 0.5 }}>
        A mirror for the global information landscape
      </Typography>
    </Box>

    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flex: { xs: '1 1 100%', sm: '0 1 auto' } }}>
      <SearchBox />
      <Tooltip title="Refresh data">
        <span>
          <IconButton onClick={onRefresh} disabled={refreshing} sx={{ color: tokens.inkMuted }}>
            {refreshing ? <CircularProgress size={20} /> : <RefreshIcon fontSize="small" />}
          </IconButton>
        </span>
      </Tooltip>
      <Tooltip title="Export data as CSV">
        <IconButton sx={{ color: tokens.inkMuted }}>
          <DownloadIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </Box>
  </Box>
);

export default Masthead;
