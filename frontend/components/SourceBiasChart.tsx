import React, { useState } from 'react';
import {
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Legend,
  Tooltip
} from 'recharts';
import { 
  Box, 
  Typography, 
  ToggleButtonGroup, 
  ToggleButton, 
  Paper,
  Tooltip as MuiTooltip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip
} from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';

// Define interfaces
interface SourceBiasPoint {
  entity: string;
  type: string;
  [key: string]: number | string; // For dynamic source scores
}

interface SourceBiasChartProps {
  title?: string;
  entities: string[];
  sources: Array<{id: number, name: string}>;
  data: SourceBiasPoint[];
  height?: number;
  dimension?: 'power' | 'moral';
}

const SourceBiasChart: React.FC<SourceBiasChartProps> = ({
  title = 'Source Bias Comparison',
  entities,
  sources,
  data,
  height = 500,
  dimension = 'power'
}) => {
  const [selectedSources, setSelectedSources] = useState<number[]>(
    sources.slice(0, 3).map(s => s.id)
  );
  const [selectedDimension, setSelectedDimension] = useState<'power' | 'moral'>(dimension);
  const [entityFilter, setEntityFilter] = useState<'all' | 'person' | 'country' | 'organization'>('all');

  const handleSourceChange = (event: any) => {
    setSelectedSources(event.target.value as number[]);
  };

  const handleDimensionChange = (
    event: React.MouseEvent<HTMLElement>,
    newDimension: 'power' | 'moral' | null
  ) => {
    if (newDimension !== null) {
      setSelectedDimension(newDimension);
    }
  };

  const handleEntityFilterChange = (event: any) => {
    setEntityFilter(event.target.value as 'all' | 'person' | 'country' | 'organization');
  };

  // Filter data based on entity type
  const filteredData = data.filter(item => {
    if (entityFilter === 'all') return true;
    return item.type === entityFilter;
  });

  // Format data for radar chart
  const radarData = filteredData.map(item => {
    const formattedItem: any = {
      entity: item.entity,
      fullMark: 2 // Maximum sentiment score
    };
    
    // Add scores for selected sources
    selectedSources.forEach(sourceId => {
      const source = sources.find(s => s.id === sourceId);
      if (source) {
        const key = `${selectedDimension}_${source.id}`;
        formattedItem[source.name] = item[key] || 0;
      }
    });
    
    return formattedItem;
  });

  // Check if we have enough data
  const hasEnoughData = radarData.length >= 3;

  // Custom tooltip for the chart
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <Paper elevation={3} sx={{ p: 2, bgcolor: 'background.paper' }}>
          <Typography variant="subtitle2">{label}</Typography>
          {payload.map((entry: any, index: number) => (
            <Box key={`item-${index}`} sx={{ color: entry.color, mt: 1 }}>
              <Typography variant="caption" sx={{ display: 'block' }}>
                {entry.name}: {entry.value.toFixed(2)}
              </Typography>
            </Box>
          ))}
        </Paper>
      );
    }
    return null;
  };

  return (
    <Box sx={{ width: '100%', height }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Typography variant="h6" sx={{ mr: 1 }}>
            {title}
          </Typography>
          <MuiTooltip title="This chart shows how different news sources portray the same entities. The further from center, the more positive the sentiment.">
            <InfoIcon fontSize="small" color="action" />
          </MuiTooltip>
        </Box>
        
        <Box sx={{ display: 'flex', gap: 2 }}>
          <ToggleButtonGroup
            size="small"
            value={selectedDimension}
            exclusive
            onChange={handleDimensionChange}
            aria-label="dimension selector"
          >
            <ToggleButton value="power" aria-label="power dimension">
              Power
            </ToggleButton>
            <ToggleButton value="moral" aria-label="moral dimension">
              Moral
            </ToggleButton>
          </ToggleButtonGroup>

          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel id="entity-filter-label">Entity Type</InputLabel>
            <Select
              labelId="entity-filter-label"
              value={entityFilter}
              onChange={handleEntityFilterChange}
              label="Entity Type"
            >
              <MenuItem value="all">All Types</MenuItem>
              <MenuItem value="person">People</MenuItem>
              <MenuItem value="country">Countries</MenuItem>
              <MenuItem value="organization">Organizations</MenuItem>
            </Select>
          </FormControl>
        </Box>
      </Box>

      <Box sx={{ display: 'flex', mb: 2 }}>
        <FormControl fullWidth size="small">
          <InputLabel id="sources-select-label">Compare Sources</InputLabel>
          <Select
            labelId="sources-select-label"
            id="sources-select"
            multiple
            value={selectedSources}
            onChange={handleSourceChange}
            renderValue={(selected) => (
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                {(selected as number[]).map((sourceId) => {
                  const source = sources.find(s => s.id === sourceId);
                  return source ? (
                    <Chip key={sourceId} label={source.name} size="small" />
                  ) : null;
                })}
              </Box>
            )}
          >
            {sources.map((source) => (
              <MenuItem key={source.id} value={source.id}>
                {source.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      {!hasEnoughData && (
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '80%',
          bgcolor: 'background.paper',
          borderRadius: 1,
          border: '1px dashed',
          borderColor: 'divider',
          p: 3
        }}>
          <Typography variant="body1" color="text.secondary">
            Not enough data available for comparison. Select different entity types or sources.
          </Typography>
        </Box>
      )}

      {hasEnoughData && (
        <ResponsiveContainer width="100%" height="90%">
          <RadarChart outerRadius={150} data={radarData}>
            <PolarGrid />
            <PolarAngleAxis dataKey="entity" />
            <PolarRadiusAxis domain={[-2, 2]} tickCount={5} />
            <Tooltip content={<CustomTooltip />} />

            {/* Create a radar for each selected source */}
            {selectedSources.map((sourceId, index) => {
              const source = sources.find(s => s.id === sourceId);
              if (!source) return null;

              // Generate a different color for each source
              const colors = ['#8884d8', '#82ca9d', '#ffc658', '#ff7300', '#0088fe', '#00c49f'];
              const color = colors[index % colors.length];

              return (
                <Radar
                  key={sourceId}
                  name={source.name}
                  dataKey={source.name}
                  stroke={color}
                  fill={color}
                  fillOpacity={0.2}
                />
              );
            })}
            <Legend />
          </RadarChart>
        </ResponsiveContainer>
      )}
    </Box>
  );
};

export default SourceBiasChart;