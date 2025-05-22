import React, { useState } from 'react';
import { 
  ResponsiveContainer, 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend,
  ReferenceLine,
  Label
} from 'recharts';
import { 
  Box, 
  Typography, 
  ToggleButtonGroup, 
  ToggleButton, 
  Paper,
  Tooltip as MuiTooltip
} from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';

// Define interfaces
interface TrendPoint {
  date: string;
  power_score: number;
  moral_score: number;
  mention_count: number;
}

interface EntityTrendChartProps {
  entityName: string;
  data: TrendPoint[];
  height?: number;
  showPower?: boolean;
  showMoral?: boolean;
}

const EntityTrendChart: React.FC<EntityTrendChartProps> = ({
  entityName,
  data,
  height = 400,
  showPower = true,
  showMoral = true
}) => {
  const [dimension, setDimension] = useState<'both' | 'power' | 'moral'>('both');
  const [smoothing, setSmoothing] = useState<boolean>(true);

  // Check if we have enough data
  const hasEnoughData = data && data.length > 2;

  // Format date for display
  const formatDate = (date: string) => {
    const d = new Date(date);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  };

  // Custom tooltip for the chart
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <Paper elevation={3} sx={{ p: 2, bgcolor: 'background.paper' }}>
          <Typography variant="subtitle2">{formatDate(label)}</Typography>
          {payload.map((entry: any, index: number) => (
            <Box key={`item-${index}`} sx={{ color: entry.color, mt: 1 }}>
              <Typography variant="caption" sx={{ display: 'block' }}>
                {entry.name}: {entry.value.toFixed(2)}
              </Typography>
            </Box>
          ))}
          <Typography variant="caption" sx={{ display: 'block', mt: 1, color: 'text.secondary' }}>
            Mentions: {data.find(d => d.date === label)?.mention_count || 0}
          </Typography>
        </Paper>
      );
    }
    return null;
  };

  const handleDimensionChange = (
    event: React.MouseEvent<HTMLElement>,
    newDimension: 'both' | 'power' | 'moral' | null
  ) => {
    if (newDimension !== null) {
      setDimension(newDimension);
    }
  };

  const handleSmoothingChange = (
    event: React.MouseEvent<HTMLElement>,
    newSmoothing: boolean | null
  ) => {
    if (newSmoothing !== null) {
      setSmoothing(newSmoothing);
    }
  };

  return (
    <Box sx={{ width: '100%', height: height }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Typography variant="subtitle1" sx={{ mr: 1 }}>
            {entityName} Sentiment Trend
          </Typography>
          <MuiTooltip title="Shows how sentiment towards this entity has changed over time. Higher values indicate more positive portrayal.">
            <InfoIcon fontSize="small" color="action" />
          </MuiTooltip>
        </Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <ToggleButtonGroup
            size="small"
            value={dimension}
            exclusive
            onChange={handleDimensionChange}
            aria-label="dimension selector"
          >
            <ToggleButton value="both" aria-label="both dimensions">
              Both
            </ToggleButton>
            <ToggleButton value="power" aria-label="power dimension">
              Power
            </ToggleButton>
            <ToggleButton value="moral" aria-label="moral dimension">
              Moral
            </ToggleButton>
          </ToggleButtonGroup>
          <ToggleButtonGroup
            size="small"
            value={smoothing}
            exclusive
            onChange={handleSmoothingChange}
            aria-label="smoothing selector"
          >
            <ToggleButton value={true} aria-label="smoothed line">
              Smooth
            </ToggleButton>
            <ToggleButton value={false} aria-label="exact line">
              Exact
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>
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
            Not enough trend data available for {entityName}
          </Typography>
        </Box>
      )}

      {hasEnoughData && (
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={data}
            margin={{ top: 20, right: 30, bottom: 20, left: 20 }}
          >
            <CartesianGrid strokeDasharray="3 3" opacity={0.4} />
            <XAxis 
              dataKey="date" 
              tickFormatter={formatDate}
              padding={{ left: 20, right: 20 }}
            />
            <YAxis 
              domain={[-2, 2]} 
              tickCount={9} 
            >
              <Label 
                value="Sentiment Score" 
                angle={-90} 
                position="insideLeft" 
                style={{ textAnchor: 'middle' }} 
              />
            </YAxis>
            <Tooltip content={<CustomTooltip />} />
            <Legend />
            <ReferenceLine y={0} stroke="#666" strokeDasharray="3 3" />
            
            {(dimension === 'both' || dimension === 'power') && (
              <Line
                type={smoothing ? "monotone" : "linear"}
                name="Power"
                dataKey="power_score"
                stroke="#8884d8"
                activeDot={{ r: 8 }}
                strokeWidth={2}
                dot={{ strokeWidth: 2 }}
              />
            )}
            {(dimension === 'both' || dimension === 'moral') && (
              <Line
                type={smoothing ? "monotone" : "linear"}
                name="Moral"
                dataKey="moral_score"
                stroke="#82ca9d"
                activeDot={{ r: 8 }}
                strokeWidth={2}
                dot={{ strokeWidth: 2 }}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      )}
    </Box>
  );
};

export default EntityTrendChart;