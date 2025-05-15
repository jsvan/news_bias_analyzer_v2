import React, { useState } from 'react';
import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  LabelList,
  Label
} from 'recharts';
import { Box, Typography, Chip, FormControl, InputLabel, Select, MenuItem, SelectChangeEvent, Alert } from '@mui/material';
import { EntitySentimentSummary } from '../types';

interface SentimentDataPoint extends EntitySentimentSummary {
  size: number;
}

interface SentimentChartProps {
  title?: string;
  data: EntitySentimentSummary[];
  entityTypes?: Record<string, string[]>; // Type to list of entities mapping
  height?: number;
  showLabels?: boolean;
}

const SentimentChart: React.FC<SentimentChartProps> = ({ 
  title = 'Sentiment Analysis',
  data,
  entityTypes,
  height = 400,
  showLabels = true
}) => {
  const [selectedTypes, setSelectedTypes] = useState<string[]>(
    entityTypes ? Object.keys(entityTypes) : []
  );

  // Filter data based on selected entity types
  const filteredData: SentimentDataPoint[] = data
    .filter(item => {
      if (!entityTypes || selectedTypes.length === 0) return true;

      // Check if the entity belongs to any of the selected types
      for (const type of selectedTypes) {
        if (entityTypes[type]?.includes(item.entity)) {
          return true;
        }
      }
      return false;
    })
    .map(item => ({
      ...item,
      size: 20 + (item.global_percentile || 0) / 5 // Size based on percentile
    }));

  // Check if we have enough data for a meaningful scatter plot
  const hasEnoughData = filteredData.length >= 5; // Minimum number of entities needed for comparison

  const handleTypeChange = (event: SelectChangeEvent<string[]>) => {
    const value = event.target.value;
    setSelectedTypes(typeof value === 'string' ? value.split(',') : value);
  };

  // Generate a color based on entity name (for consistent coloring)
  const getEntityColor = (entity: string) => {
    // Simple hash function to generate a color
    let hash = 0;
    for (let i = 0; i < entity.length; i++) {
      hash = entity.charCodeAt(i) + ((hash << 5) - hash);
    }
    
    // Convert to RGB
    const r = (hash & 0xFF0000) >> 16;
    const g = (hash & 0x00FF00) >> 8;
    const b = hash & 0x0000FF;
    
    return `rgb(${r}, ${g}, ${b})`;
  };

  // Define quadrant labels
  const quadrantLabels = [
    { x: 2.5, y: 2.5, text: 'HERO', color: '#4caf50' },
    { x: -2.5, y: 2.5, text: 'VICTIM', color: '#9c27b0' },
    { x: 2.5, y: -2.5, text: 'VILLAIN', color: '#f44336' },
    { x: -2.5, y: -2.5, text: 'THREAT', color: '#ff9800' }
  ];

  return (
    <Box sx={{ width: '100%', height: height, padding: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box>
          <Typography variant="h6" gutterBottom>
            {title}
          </Typography>
          {!hasEnoughData && (
            <Typography variant="caption" color="error" sx={{ display: 'block', mt: 0.5 }}>
              Insufficient data for meaningful sentiment comparison
            </Typography>
          )}
        </Box>
        
        {entityTypes && (
          <FormControl sx={{ minWidth: 200 }}>
            <InputLabel id="entity-type-select-label">Entity Types</InputLabel>
            <Select
              labelId="entity-type-select-label"
              id="entity-type-select"
              multiple
              value={selectedTypes}
              onChange={handleTypeChange}
              renderValue={(selected) => (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {selected.map((value) => (
                    <Chip key={value} label={value} />
                  ))}
                </Box>
              )}
            >
              {entityTypes && Object.keys(entityTypes).map(type => (
                <MenuItem key={type} value={type}>
                  {type}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}
      </Box>
      
      {!hasEnoughData && (
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
          height: '80%',
          bgcolor: 'rgba(0,0,0,0.03)',
          borderRadius: 1,
          p: 3
        }}>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>
            Not enough entities available for meaningful sentiment comparison
          </Typography>
          <Typography variant="body2" color="text.secondary">
            At least 5 entities are needed to display a useful sentiment scatter plot
          </Typography>
          <Alert severity="info" sx={{ mt: 3, width: '80%' }}>
            Try selecting different entity types or wait for more data to be collected
          </Alert>
        </Box>
      )}

      {hasEnoughData && (
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart
            margin={{ top: 20, right: 30, bottom: 30, left: 30 }}
          >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            type="number"
            dataKey="power_score"
            domain={[-2, 2]}
            tickCount={9}
            name="Power"
          >
            <Label value="Power Dimension" position="bottom" offset={10} />
          </XAxis>
          <YAxis
            type="number"
            dataKey="moral_score"
            domain={[-2, 2]}
            tickCount={9}
            name="Morality"
          >
            <Label value="Moral Dimension" position="left" angle={-90} offset={10} />
          </YAxis>
          <ZAxis type="number" dataKey="size" range={[20, 100]} />
          <Tooltip
            formatter={(value: number, name: string) => {
              return [value.toFixed(2), name === 'size' ? 'Global Percentile' : name];
            }}
            labelFormatter={(label) => {
              const item = data.find(d => d.entity === label);
              return `${item?.entity}`;
            }}
            cursor={{ strokeDasharray: '3 3' }}
          />
          
          {/* Render background quadrant labels */}
          {quadrantLabels.map((label, index) => (
            <Scatter
              key={`quadrant-${index}`}
              name=""
              data={[{ power_score: label.x, moral_score: label.y, size: 1, entity: '' }]}
              shape={() => (
                <text x={0} y={0} dy={5} textAnchor="middle" fill={label.color} style={{ fontWeight: 'bold', opacity: 0.2 }}>
                  {label.text}
                </text>
              )}
              isAnimationActive={false}
              legendType="none"
            />
          ))}
          
          {/* Main scatter plot for entities */}
          <Scatter
            name="Entities"
            data={filteredData}
            fill="#8884d8"
            isAnimationActive={true}
            shape={(props: any) => {
              const { cx, cy, entity } = props;
              return (
                <circle 
                  cx={cx} 
                  cy={cy} 
                  r={10} 
                  fill={getEntityColor(entity)} 
                  fillOpacity={0.8}
                  stroke="#fff"
                  strokeWidth={1}
                />
              );
            }}
          >
            {showLabels && (
              <LabelList
                dataKey="entity"
                position="top"
                offset={10}
                style={{ fontSize: '10px', fill: '#333' }}
              />
            )}
          </Scatter>
          <Legend />
        </ScatterChart>
      </ResponsiveContainer>
      )}
    </Box>
  );
};

export default SentimentChart;