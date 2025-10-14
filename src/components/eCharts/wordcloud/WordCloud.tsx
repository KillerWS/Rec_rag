import React, { useEffect, useMemo, useRef, useState } from 'react';
import * as echarts from 'echarts';
import 'echarts-wordcloud';
import { Card, Checkbox, Radio, Select, Slider, Space, Typography } from 'antd';
import { fetchTestChartOption, fetchWordCloudV2 } from '../../../api/api';
import areas from '../../../data/berlin_areas.json';

const { Text } = Typography;
const { Option } = Select;

export interface WordCloudItem {
  text: string;
  freq?: number; // frequency or count
  tfidf?: number;
  pmi?: number;
  sentiment?: { pos?: number; neu?: number; neg?: number; conf?: number };
  examples?: Array<{ listing_id?: number | string; rating?: number; date?: string; snippet?: string }>;
}

interface WordCloudChartData {
  title: string;
  data: any;
  echarts_option?: any;
  type?: string;
  options?: any;
}

interface WordCloudProps {
  chartData: WordCloudChartData;
  height?: number;
  width?: string;
  modalVisible?: boolean;
  showControls?: boolean;
}

const clamp = (v: number, min: number, max: number) => Math.min(max, Math.max(min, v));

const pickFirstDistrict = (cd?: any): string => {
  const arr = (cd?.data?.districts || cd?.data?.neighbourhood_groups || []) as string[];
  if (Array.isArray(arr) && arr.length) return arr[0];
  return '';
};

const WordCloud: React.FC<WordCloudProps> = ({ chartData, height = 360, width = '100%', modalVisible, showControls = true }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);

  const defaultDistrict = useMemo(() => (chartData?.data?.default_district || 'Mitte') as string, [chartData]);
  const testMode = useMemo(() => Boolean(chartData?.options?.use_test_endpoint), [chartData]);
  const hardcodedNeighbourhood = 'Helmholtzplatz';

  // two-level selection
  const districtOptions = (areas as any)?.districts || [];
  const [selectedGroup, setSelectedGroup] = useState<string>(() => (districtOptions[0] || 'Pankow'));
  const neighbourhoodOptions: string[] = useMemo(() => {
    const map = (areas as any)?.neighbourhoods_by_group || {};
    return map[selectedGroup] || [];
  }, [selectedGroup]);
  const [selectedNeighbourhood, setSelectedNeighbourhood] = useState<string>(() => hardcodedNeighbourhood);

  // controls
  const [selectedDistrict, setSelectedDistrict] = useState<string>(() => pickFirstDistrict(chartData) || (chartData?.data?.default_district || 'Mitte'));
  const [topN, setTopN] = useState<number>(50);
  const [metric, setMetric] = useState<'frequency' | 'tfidf' | 'pmi'>('frequency');
  const [sentiments, setSentiments] = useState<{ pos: boolean; neu: boolean; neg: boolean }>({ pos: true, neu: true, neg: true });
  const [selectedWord, setSelectedWord] = useState<WordCloudItem | null>(null);

  // remote option from backend or test endpoint
  const [remoteOption, setRemoteOption] = useState<any | null>(chartData?.echarts_option || null);

  // remote data states (for side summary fallback)
  const [remoteWords, setRemoteWords] = useState<WordCloudItem[] | null>(null);
  // Commented out unused loading state to fix TypeScript build error
  // const [loading, setLoading] = useState<boolean>(false);

  // sync default neighbourhood on group change
  useEffect(() => {
    if (neighbourhoodOptions.length) {
      setSelectedNeighbourhood((prev) => neighbourhoodOptions.includes(prev) ? prev : neighbourhoodOptions[0]);
    }
  }, [neighbourhoodOptions]);

  // fetch via V2 when not in testMode
  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      if (testMode) return; // handled by test effect
      if (!selectedNeighbourhood) return;
      // setLoading(true); // Commented out to fix build error
      try {
        const data = await fetchWordCloudV2({ level: 'neighbourhood', name: selectedNeighbourhood, top_n: topN, metric: metric as any });
        if (cancelled) return;
        const arr = Array.isArray(data) ? data : [];
        setRemoteWords(
          arr
            .map((w: any) => ({
              text: w.text || w.word || '',
              freq: w.freq ?? w.count,
              tfidf: typeof w.tfidf === 'number' ? w.tfidf : undefined,
              pmi: typeof w.pmi === 'number' ? w.pmi : (typeof w.log_odds === 'number' ? w.log_odds : undefined),
              sentiment: w.sentiment,
              examples: Array.isArray(w.examples) ? w.examples : []
            }))
            .filter((w) => w.text)
        );
        setRemoteOption(null); // using local build
      } finally {
        // if (!cancelled) setLoading(false); // Commented out to fix build error
      }
    };
    run();
    return () => { cancelled = true; };
  }, [testMode, selectedNeighbourhood, topN, metric]);

  // normalize incoming data (fallback)
  const wordsFromProp: WordCloudItem[] = useMemo(() => {
    const rawWords = chartData?.data?.words;
    const rawData = chartData?.data;
    const arr: any[] = Array.isArray(rawWords) ? rawWords : (Array.isArray(rawData) ? rawData : []);
    return arr.map((w: any): WordCloudItem => ({
      text: w.text || w.word || String(w.name || w.term || ''),
      freq: typeof w.freq === 'number' ? w.freq : (typeof w.count === 'number' ? w.count : undefined),
      tfidf: typeof w.tfidf === 'number' ? w.tfidf : undefined,
      pmi: typeof w.pmi === 'number' ? w.pmi : (typeof w.log_odds === 'number' ? w.log_odds : undefined),
      sentiment: w.sentiment || undefined,
      examples: w.examples || []
    })).filter((w) => w.text);
  }, [chartData]);

  const districts: string[] = useMemo(() => {
    const arr = chartData?.data?.districts || chartData?.data?.neighbourhood_groups || [];
    if (Array.isArray(arr) && arr.length) {
      return ['All', ...arr];
    }
    return ['All'];
  }, [chartData]);

  // keep selection valid when options change
  useEffect(() => {
    const validSet = new Set(districts);
    if (!validSet.has(selectedDistrict) || selectedDistrict === 'All' || !selectedDistrict) {
      const firstReal = (districts || []).find((d) => d && d !== 'All');
      setSelectedDistrict(firstReal || defaultDistrict);
    }
  }, [districts, defaultDistrict]);

  // keep remoteOption in sync with server-pushed option
  useEffect(() => {
    if (chartData?.echarts_option) {
      setRemoteOption(chartData.echarts_option);
    }
  }, [chartData]);

  // fetch option for selected district via /test/chart-option when in testMode
  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      if (!testMode) {
        // setLoading(false); // Commented out to fix build error
        return;
      }
      // For testing, always send neighbourhood level with a valid small-area name
      const name = hardcodedNeighbourhood;
      // setLoading(true); // Commented out to fix build error
      try {
        const payload: any = {
          type: 'comments_wordcloud',
          preferences: {
            level: 'neighbourhood',
            group: undefined,
            name,
            top_n: topN,
            measure: metric === 'frequency' ? 'freq' : metric // tfidf | pmi -> pmi not supported? keep as is
          }
        };
        console.log('[WordCloud] test payload =>', payload);
        const res: any = await fetchTestChartOption(payload);
        if (cancelled) return;
        const opt = res?.echarts_option || res?.data?.echarts_option || null;
        setRemoteOption(opt);
        // derive words list from option if possible for side summary
        const series = opt?.series && Array.isArray(opt.series) ? opt.series.find((s: any) => s.type === 'wordCloud') : null;
        const dataArr = series?.data || [];
        if (Array.isArray(dataArr) && dataArr.length) {
          const mapped = dataArr
            .map((d: any) => ({
              text: d.name || d.text || '',
              freq: typeof d.value === 'number' ? d.value : undefined,
              tfidf: typeof d.tfidf === 'number' ? d.tfidf : undefined,
              pmi: typeof d.pmi === 'number' ? d.pmi : (typeof d.log_odds === 'number' ? d.log_odds : undefined),
              sentiment: d.sentiment || undefined,
              examples: Array.isArray(d.examples) ? d.examples : []
            }))
            .filter((w: any) => w.text);
          setRemoteWords(mapped);
        } else {
          setRemoteWords(null);
        }
      } finally {
        // if (!cancelled) setLoading(false); // Commented out to fix build error
      }
    };
    run();
    return () => { cancelled = true; };
  }, [topN, metric, testMode]);

  const sourceWords: WordCloudItem[] = useMemo(() => {
    return (remoteWords && remoteWords.length > 0) ? remoteWords : wordsFromProp;
  }, [remoteWords, wordsFromProp]);

  // derive metric values and color for fallback option
  const preparedData = useMemo(() => {
    const words = sourceWords;
    const metricGetter = (w: WordCloudItem) => {
      if (metric === 'tfidf') return w.tfidf ?? w.freq ?? 0;
      if (metric === 'pmi') return w.pmi ?? w.freq ?? 0;
      return w.freq ?? 0;
    };

    const filtered = words.filter((w) => {
      const s = w.sentiment || {};
      const pos = s.pos ?? 0, neu = s.neu ?? 0, neg = s.neg ?? 0; // default to 0s
      const maxLabel = pos >= neg && pos >= neu ? 'pos' : (neg >= pos && neg >= neu ? 'neg' : 'neu');
      if (!sentiments[maxLabel as 'pos' | 'neu' | 'neg']) return false;
      return true;
    });

    const sorted = filtered.sort((a, b) => metricGetter(b) - metricGetter(a)).slice(0, topN);
    const values = sorted.map(metricGetter);
    const vMin = Math.min(...values, 0);
    const vMax = Math.max(...values, 1);

    const colorFor = (w: WordCloudItem) => {
      const s = w.sentiment || {};
      const pos = s.pos ?? 0, neu = s.neu ?? 0, neg = s.neg ?? 0; // default to 0s
      const conf = clamp(s.conf ?? Math.max(pos, neu, neg), 0, 1);
      let h = 0, sat = 0.6, lightMin = 0.4, lightMax = 0.65;
      if (pos >= neg && pos >= neu) {
        h = 150;
      } else if (neg >= pos && neg >= neu) {
        h = 0;
      } else {
        // neutral
        sat = 0; // gray
      }
      const l = lightMin + (lightMax - lightMin) * conf;
      const sPerc = Math.round(sat * 100);
      const lPerc = Math.round(l * 100);
      return sat === 0 ? `hsl(0, 0%, ${lPerc}%)` : `hsl(${h}, ${sPerc}%, ${lPerc}%)`;
    };

    const mapped = sorted.map((w) => {
      const raw = metricGetter(w);
      const norm = vMax > vMin ? (raw - vMin) / (vMax - vMin) : 0;
      const score = Math.sqrt(clamp(norm, 0, 1));
      return {
        name: w.text,
        value: Math.max(1, Math.round(score * 100)),
        original: w,
        itemStyle: { color: colorFor(w) }
      } as any;
    });

    // Frequency-weighted sentiment split normalized to 100%
    const summaryWeighted = sorted.reduce((acc: any, w) => {
      const s = w.sentiment || {};
      const pos = s.pos ?? 0;
      const neu = s.neu ?? 0;
      const neg = s.neg ?? 0;
      const weight = typeof w.freq === 'number' ? w.freq : 1;
      acc.pos += weight * pos;
      acc.neu += weight * neu;
      acc.neg += weight * neg;
      return acc;
    }, { pos: 0, neu: 0, neg: 0 });
    const total = summaryWeighted.pos + summaryWeighted.neu + summaryWeighted.neg;
    const summaryPercent = total > 0
      ? {
          pos: (summaryWeighted.pos / total) * 100,
          neu: (summaryWeighted.neu / total) * 100,
          neg: (summaryWeighted.neg / total) * 100,
        }
      : { pos: 0, neu: 0, neg: 0 };

    return { data: mapped, summary: summaryPercent };
  }, [sourceWords, metric, sentiments, topN]);

  // build fallback echarts option
  const buildOption = (): echarts.EChartsOption => {
    return {
      title: {
        text: chartData?.title || 'Review Word Cloud',
        left: 'center'
      },
      tooltip: {
        trigger: 'item',
        formatter: (p: any) => {
          const w: WordCloudItem | undefined = p?.data?.original;
          if (!w) return p.name;
          const s = w.sentiment || {};
          const metricVal = metric === 'frequency' ? (w.freq ?? 0) : (metric === 'tfidf' ? (w.tfidf ?? 0) : (w.pmi ?? 0));
          const lines = [
            `<div style="font-weight:600;margin-bottom:4px;">${w.text}</div>`,
            `<div>Value: <b>${metricVal.toFixed ? metricVal.toFixed(2) : metricVal}</b> (${metric})</div>`,
            `<div>Sentiment — Pos: ${(s.pos ?? 0).toFixed(2)}, Neu: ${(s.neu ?? 0).toFixed(2)}, Neg: ${(s.neg ?? 0).toFixed(2)}</div>`
          ];
          return lines.join('');
        }
      },
      series: [
        {
          type: 'wordCloud',
          shape: 'circle',
          gridSize: 8,
          sizeRange: [12, 48],
          rotationRange: [-15, 15],
          rotationStep: 3,
          drawOutOfBound: false,
          textStyle: {
            fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial',
          },
          emphasis: {
            focus: 'self',
            textStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(0,0,0,0.25)',
              borderColor: '#d4af37',
              borderWidth: 2
            }
          },
          data: preparedData.data
        } as any
      ]
    };
  };

  // init and updates
  useEffect(() => {
    if (!chartRef.current) return;
    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current);
    }
    const option = remoteOption || buildOption();
    chartInstance.current.setOption(option as any, true);

    const onResize = () => chartInstance.current?.resize();
    window.addEventListener('resize', onResize);

    const handleClick = (params: any) => {
      const w = params?.data?.original as WordCloudItem | undefined;
      if (w) setSelectedWord(w);
    };
    chartInstance.current.on('click', handleClick);

    return () => {
      window.removeEventListener('resize', onResize);
      chartInstance.current?.off('click', handleClick);
    };
  }, [chartData, remoteOption, preparedData]);

  // handle modal visibility resize
  useEffect(() => {
    if (modalVisible && chartInstance.current) {
      setTimeout(() => chartInstance.current?.resize(), 200);
    }
  }, [modalVisible]);

  // right panel content derived (fallback summary)
  const topList = useMemo(() => {
    const items = preparedData.data.slice(0, Math.min(10, preparedData.data.length));
    return items.map((d: any) => ({
      word: d.name,
      value: d.original ? (metric === 'frequency' ? d.original.freq : metric === 'tfidf' ? d.original.tfidf : d.original.pmi) : d.value
    }));
  }, [preparedData, metric]);

  return (
    <div style={{ width }}>
      {showControls && (
        <div className="flex items-center justify-between mb-2" style={{ gap: 8 }}>
          <Space wrap>
            <Select
              value={selectedGroup}
              onChange={setSelectedGroup}
              style={{ minWidth: 220 }}
              size="small"
            >
              {districtOptions.map((d: string) => (
                <Option key={d} value={d}>{d}</Option>
              ))}
            </Select>

            <Select
              value={selectedNeighbourhood}
              onChange={setSelectedNeighbourhood}
              style={{ minWidth: 220 }}
              size="small"
              placeholder="Select neighbourhood"
            >
              {neighbourhoodOptions.map((n: string) => (
                <Option key={n} value={n}>{n}</Option>
              ))}
            </Select>

            <Space size={12}>
              <span className="text-xs">Top N</span>
              <Slider min={10} max={100} step={5} value={topN} onChange={(v: any) => setTopN(v)} style={{ width: 180 }} />
            </Space>

            <Radio.Group size="small" value={metric} onChange={(e) => setMetric(e.target.value)}>
              <Radio.Button value="frequency">Frequency</Radio.Button>
              <Radio.Button value="tfidf">TF-IDF</Radio.Button>
              <Radio.Button value="pmi">PMI</Radio.Button>
            </Radio.Group>

            <Checkbox.Group
              options={[{ label: '🟢 Pos', value: 'pos' }, { label: '⚪ Neu', value: 'neu' }, { label: '🔴 Neg', value: 'neg' }]}
              value={Object.entries(sentiments).filter(([, v]) => v).map(([k]) => k)}
              onChange={(vals) => {
                setSentiments({ pos: (vals as string[]).includes('pos'), neu: (vals as string[]).includes('neu'), neg: (vals as string[]).includes('neg') });
              }}
            />
          </Space>
        </div>
      )}

      <div className="flex" style={{ gap: 12 }}>
        <div style={{ width: showControls ? '70%' : '100%' }}>
          <div ref={chartRef} style={{ height: `${height}px`, width: '100%', minHeight: 220, position: 'relative' }} />
        </div>

        {showControls && (
          <div style={{ width: '30%' }}>
            <Card size="small" title="Comment insights" bordered>
              <div className="mb-2">
                <Text type="secondary">Sentiment split</Text>
                <div className="mt-1 text-xs" style={{ display: 'flex', gap: 8 }}>
                  <span style={{ color: '#16a34a' }}>Pos: {(preparedData.summary.pos ?? 0).toFixed(2)}%</span>
                  <span style={{ color: '#595959' }}>Neu: {(preparedData.summary.neu ?? 0).toFixed(2)}%</span>
                  <span style={{ color: '#dc2626' }}>Neg: {(preparedData.summary.neg ?? 0).toFixed(2)}%</span>
                </div>
              </div>

              <div className="mb-2">
                <Text type="secondary">Top terms</Text>
                <div className="mt-1 text-xs">
                  {topList.map((t) => (
                    <div key={t.word} className="flex justify-between"><span>{t.word}</span><span>{typeof t.value === 'number' ? t.value.toFixed ? t.value.toFixed(2) : t.value : t.value}</span></div>
                  ))}
                </div>
              </div>

              {selectedWord && (
                <div>
                  <Text strong>Evidence for "{selectedWord.text}"</Text>
                  <div className="mt-1 text-xs" style={{ maxHeight: 180, overflowY: 'auto' }}>
                    {(selectedWord.examples || []).slice(0, 5).map((ex, idx) => (
                      <div key={idx} className="mb-1"> 
                        <div># {ex.listing_id} • {ex.rating ?? '-'}★ • {ex.date ?? ''}</div>
                        <div style={{ color: '#595959' }}>{ex.snippet}</div>
                      </div>
                    ))}
                    {(!selectedWord.examples || selectedWord.examples.length === 0) && (
                      <div className="text-gray-500">No examples available.</div>
                    )}
                  </div>
                </div>
              )}
            </Card>
          </div>
        )}
      </div>
    </div>
  );
};

export default WordCloud; 