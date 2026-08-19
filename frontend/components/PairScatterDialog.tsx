import React, { useEffect, useRef, useState } from 'react';
import * as echarts from 'echarts/core';
import { ScatterChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, MarkLineComponent } from 'echarts/components';
import { LabelLayout } from 'echarts/features';
import { CanvasRenderer } from 'echarts/renderers';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  Box,
  Typography,
  CircularProgress,
  IconButton,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { tokens, monoNumber, fontSans } from '../theme';
import { similarityApi } from '../services/api';

// The "why" behind a similarity number: every entity both sources scored in
// the window, source A's reading on x against source B's on y. Points on the
// diagonal are read identically; the labeled off-diagonal outliers are where
// the two part ways - "they agree on everything except Israel and NATO".
// Live: /similarity/pair; static: intersected client-side from
// stats/source_vectors.json (staticData.getSimilarityPair).

echarts.use([ScatterChart, GridComponent, TooltipComponent, MarkLineComponent,
              LabelLayout, CanvasRenderer]);

export interface PairRef {
  source_id: number;
  name: string;
}

interface PairEntity {
  entity_id: number;
  name: string;
  score_a: number;
  score_b: number;
  n_a: number;
  n_b: number;
}

interface PairResponse {
  window_start: string | null;
  window_end: string | null;
  r: number | null;
  common: number;
  entities: PairEntity[];
}

// Label only the sharpest disagreements; the rest stay hover-only.
const LABELED_OUTLIERS = 12;

const PairScatterDialog: React.FC<{
  a: PairRef | null;
  b: PairRef | null;
  onClose: () => void;
}> = ({ a, b, onClose }) => {
  const open = !!(a && b);
  const [data, setData] = useState<PairResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!a || !b) return;
    setData(null);
    setError(null);
    similarityApi
      .getPair(a.source_id, b.source_id)
      .then((d: PairResponse) => setData(d))
      .catch((err) => setError((err as Error).message));
  }, [a?.source_id, b?.source_id]);

  useEffect(() => {
    if (!open || !data || !chartRef.current) return;
    if (!chartInstance.current) chartInstance.current = echarts.init(chartRef.current);
    const chart = chartInstance.current;

    const scores = data.entities.flatMap((e) => [e.score_a, e.score_b]);
    const lo = Math.min(-0.5, ...scores) - 0.15;
    const hi = Math.max(0.5, ...scores) + 0.15;
    const byGap = [...data.entities].sort(
      (x, y) => Math.abs(y.score_a - y.score_b) - Math.abs(x.score_a - x.score_b));
    const labeled = new Set(byGap.slice(0, LABELED_OUTLIERS).map((e) => e.entity_id));

    const axis = (name: string) => ({
      type: 'value' as const,
      min: lo,
      max: hi,
      name,
      nameLocation: 'middle' as const,
      nameGap: 22,
      nameTextStyle: { fontSize: 11, color: tokens.inkMuted, fontFamily: fontSans },
      axisLabel: { fontSize: 9, color: tokens.inkMuted },
      splitLine: { lineStyle: { color: tokens.border, type: 'dashed' as const } },
    });

    chart.setOption({
      animation: false,
      grid: { top: 14, right: 24, bottom: 40, left: 44 },
      xAxis: axis(`${a!.name} score`),
      yAxis: axis(`${b!.name} score`),
      tooltip: {
        trigger: 'item',
        backgroundColor: tokens.surface,
        borderColor: tokens.border,
        textStyle: { color: tokens.ink, fontSize: 12, fontFamily: fontSans },
        extraCssText: 'border-radius: 6px; box-shadow: none;',
        formatter: (p: any) =>
          `${p.data.name}<br/><span style="color:${tokens.inkMuted};font-size:11px">` +
          `${a!.name}: ${p.value[0].toFixed(2)} (${p.data.n_a}×) · ` +
          `${b!.name}: ${p.value[1].toFixed(2)} (${p.data.n_b}×)</span>`,
      },
      series: [{
        type: 'scatter',
        data: data.entities.map((e) => ({
          name: e.name,
          value: [e.score_a, e.score_b],
          n_a: e.n_a,
          n_b: e.n_b,
          symbolSize: 4 + 2.5 * Math.sqrt(Math.min(e.n_a, e.n_b)),
          label: {
            show: labeled.has(e.entity_id),
            position: 'right',
            distance: 5,
            fontSize: 9,
            color: tokens.inkMuted,
            fontFamily: fontSans,
            formatter: e.name,
          },
        })),
        itemStyle: { color: tokens.accent, opacity: 0.6,
                     borderColor: tokens.surface, borderWidth: 0.5 },
        labelLayout: { hideOverlap: true },
        emphasis: { label: { show: true, color: tokens.ink, fontWeight: 600 },
                    itemStyle: { opacity: 1 } },
        markLine: {
          silent: true,
          symbol: 'none',
          animation: false,
          lineStyle: { color: tokens.border, width: 1 },
          label: { show: false },
          data: [
            { xAxis: 0 },
            { yAxis: 0 },
            // The agreement diagonal: identical readings land on this line.
            [{ coord: [lo, lo], lineStyle: { type: 'dashed', color: tokens.inkMuted } },
             { coord: [hi, hi] }],
          ],
        },
      }],
    });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(chartRef.current);
    return () => observer.disconnect();
  }, [open, data]);

  // The chart div unmounts with the dialog; drop the instance with it.
  useEffect(() => {
    if (!open) {
      chartInstance.current?.dispose();
      chartInstance.current = null;
    }
  }, [open]);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle sx={{ pb: 0.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
          <Box>
            {a?.name} <Typography component="span" sx={{ color: tokens.inkMuted }}>×</Typography> {b?.name}
            {data && (
              <Typography variant="body2" component="div" sx={{ color: tokens.inkMuted, mt: 0.25 }}>
                {data.r != null ? (
                  <>correlation <Box component="span" sx={{ ...monoNumber, color: tokens.ink }}>
                    {data.r >= 0 ? '+' : ''}{data.r.toFixed(2)}
                  </Box> over </>
                ) : 'too little overlap for a correlation — '}
                {data.common} shared entities
                {data.window_start ? ` (${data.window_start} to ${data.window_end})` : ''}
              </Typography>
            )}
          </Box>
          <IconButton size="small" onClick={onClose} sx={{ color: tokens.inkMuted }}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>
      </DialogTitle>
      <DialogContent>
        {error && (
          <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 3 }}>{error}</Typography>
        )}
        {!data && !error && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress size={26} />
          </Box>
        )}
        {data && (
          <>
            <Box ref={chartRef} sx={{ width: '100%', height: 440 }} />
            <Typography variant="caption" sx={{ display: 'block', mt: 1, color: tokens.inkMuted }}>
              One point per entity both papers scored; the dashed diagonal is perfect
              agreement, and point size tracks how often the less-frequent side mentioned
              it. Labels mark the widest disagreements.
            </Typography>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default PairScatterDialog;
