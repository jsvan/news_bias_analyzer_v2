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
import { tokens, monoNumber } from '../theme';

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

  // Check if we have enough data
  const hasEnoughData = data && data.length > 2;

  // Format date for display. All-time series can cross a year boundary — without
  // the year, sparse ticks like "Mar 13 · Aug 29 · Apr 1" read as shuffled.
  const spansYears = data.length > 1 && new Date(data[0].date).getFullYear() !== new Date(data[data.length - 1].date).getFullYear();
  const formatDate = (date: string) => {
    const d = new Date(date);
    return spansYears
      ? d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: '2-digit' })
      : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  };

  // Custom tooltip for the chart
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <Paper
          elevation={0}
          sx={{ p: 2, bgcolor: tokens.surface, border: `1px solid ${tokens.border}`, borderRadius: '8px' }}
        >
          <Typography variant="subtitle2" sx={{ color: tokens.ink }}>{formatDate(label)}</Typography>
          {payload.map((entry: any, index: number) => (
            <Box key={`item-${index}`} sx={{ color: entry.color, mt: 1 }}>
              <Typography variant="caption" sx={{ display: 'block', ...monoNumber }}>
                {entry.name}: {entry.value.toFixed(2)}
              </Typography>
            </Box>
          ))}
          <Typography variant="caption" sx={{ display: 'block', mt: 1, color: tokens.inkMuted, ...monoNumber }}>
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
      </Box>

      {!hasEnoughData && (
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '80%',
          bgcolor: tokens.surfaceSunken,
          borderRadius: 1,
          border: `1px dashed ${tokens.border}`,
          p: 3
        }}>
          <Typography variant="body1" sx={{ color: tokens.inkMuted }}>
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
            <CartesianGrid strokeDasharray="3 3" stroke={tokens.border} />
            <XAxis
              dataKey="date"
              minTickGap={32}
              tickFormatter={formatDate}
              padding={{ left: 20, right: 20 }}
              tick={{ fill: tokens.inkMuted, fontSize: 11, fontFamily: 'monospace' }}
            />
            <YAxis
              domain={[-2, 2]}
              tickCount={9}
              tick={{ fill: tokens.inkMuted, fontSize: 11, fontFamily: 'monospace' }}
            >
              <Label
                value="Sentiment Score"
                angle={-90}
                position="insideLeft"
                style={{ textAnchor: 'middle', fill: tokens.inkMuted, fontSize: 12 }}
              />
            </YAxis>
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ fontSize: 12, color: tokens.inkMuted }} />
            <ReferenceLine y={0} stroke={tokens.inkMuted} strokeDasharray="3 3" />

            {(dimension === 'both' || dimension === 'power') && (
              <Line
                type="monotone"
                name="Power"
                dataKey="power_score"
                stroke={tokens.accent}
                activeDot={{ r: 8 }}
                strokeWidth={2}
                dot={{ strokeWidth: 2 }}
              />
            )}
            {(dimension === 'both' || dimension === 'moral') && (
              <Line
                type="monotone"
                name="Moral"
                dataKey="moral_score"
                stroke={tokens.categorical[1]}
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