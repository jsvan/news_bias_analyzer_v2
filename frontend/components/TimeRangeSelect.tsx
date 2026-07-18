import React from 'react';
import { FormControl, InputLabel, Select, MenuItem } from '@mui/material';

// Sentinel for "no day filter" - falsy, so the existing `if (params.days) ...`
// guards in services/api.ts already omit it from the request without changes there.
export const ALL_TIME = 0;

const LABELS: Record<number, string> = {
  7: 'Last 7 days',
  14: 'Last 2 weeks',
  30: 'Last 30 days',
  60: 'Last 2 months',
  90: 'Last 3 months',
  180: 'Last 6 months',
  365: 'Last year',
};

export const describeTimeRange = (days: number): string =>
  days === ALL_TIME ? 'all time' : `the last ${days} days`;

interface TimeRangeSelectProps {
  value: number;
  onChange: (days: number) => void;
  options: number[]; // day counts, e.g. [7, 30, 90]
  label?: string;
}

const TimeRangeSelect: React.FC<TimeRangeSelectProps> = ({ value, onChange, options, label = 'Time Range' }) => (
  <FormControl fullWidth size="small">
    <InputLabel id="time-range-label">{label}</InputLabel>
    <Select
      labelId="time-range-label"
      value={value}
      label={label}
      onChange={(e) => onChange(e.target.value as number)}
    >
      <MenuItem value={ALL_TIME}>All Time</MenuItem>
      {options.map((days) => (
        <MenuItem key={days} value={days}>
          {LABELS[days] || `Last ${days} days`}
        </MenuItem>
      ))}
    </Select>
  </FormControl>
);

export default TimeRangeSelect;
