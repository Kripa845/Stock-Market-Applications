import { useState, useMemo, useEffect } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { getCompanies } from '../../api/companies';
import { stocksApi } from '../../api/stocks';
import type { DailyPrice } from '../../types';
import { useLiveRefresh } from '../../hooks/useLiveRefresh';
import clsx from 'clsx';

const TABS = ['1W','1M','3M'] as const;
type Tab = typeof TABS[number];

const DAYS: Record<Tab, number> = { '1W': 7, '1M': 30, '3M': 90 };

interface TooltipProps { active?: boolean; payload?: any[]; label?: string; }

function CustomTooltip({ active, payload, label }: TooltipProps) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.value as number;
  const v = payload[1]?.value as number;
  return (
    <div className="bg-bg-elevated border border-bg-border rounded-xl p-3 text-xs shadow-xl">
      <p className="text-text-muted mb-1">{label}</p>
      <p className="text-text-primary font-mono font-semibold">Rs. {d?.toFixed(2)}</p>
      {v && <p className="text-text-secondary mt-0.5">Vol: {(v / 1000).toFixed(0)}K</p>}
    </div>
  );
}

export default function MarketOverviewChart() {
  const [tab, setTab] = useState<Tab>('1M');
  const [symbol, setSymbol] = useState('Market');
  const [prices, setPrices] = useState<DailyPrice[]>([]);

  const load = () => getCompanies({ status: 'active' }).then(async response => {
    const company = response.results[0];
    if (!company) return;
    setSymbol(company.symbol);
    const priceData = await stocksApi.getPrices(company.id, '90d');
    setPrices(priceData.prices);
  });

  useEffect(() => { load(); }, []);
  useLiveRefresh(load, 10000);

  const data = useMemo(() => {
    const sliced = prices.slice(-DAYS[tab]);
    return sliced.map(p => ({
      date: p.date.slice(5),   // MM-DD
      price: +p.close,
      volume: p.volume,
    }));
  }, [tab]);

  const first = data[0]?.price ?? 0;
  const last  = data[data.length - 1]?.price ?? 0;
  const positive = last >= first;

  return (
    <div className="card flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">Market Overview</h3>
          <p className="text-xs text-text-secondary mt-0.5">{symbol} — daily price & volume</p>
        </div>
        <div className="flex items-center gap-1 bg-bg-elevated rounded-lg p-0.5">
          {TABS.map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={clsx(
                'px-3 py-1 rounded-md text-xs font-medium transition-all',
                tab === t
                  ? 'bg-accent text-white'
                  : 'text-text-secondary hover:text-text-primary'
              )}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Price chart */}
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor={positive ? '#22C55E' : '#EF4444'} stopOpacity={0.2} />
                <stop offset="95%" stopColor={positive ? '#22C55E' : '#EF4444'} stopOpacity={0}   />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1E2538" vertical={false} />
            <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#475569' }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
            <YAxis domain={['auto','auto']} tick={{ fontSize: 10, fill: '#475569' }} tickLine={false} axisLine={false} tickFormatter={v => `${v}`} width={45} />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine y={first} stroke="#1E2538" strokeDasharray="4 4" />
            <Area
              type="monotone" dataKey="price" stroke={positive ? '#22C55E' : '#EF4444'}
              strokeWidth={1.5} fill="url(#priceGrad)" dot={false} activeDot={{ r: 3 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Volume bar chart */}
      <div className="h-16">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 0, right: 4, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="volGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#7C3AED" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#7C3AED" stopOpacity={0}   />
              </linearGradient>
            </defs>
            <XAxis dataKey="date" hide />
            <YAxis hide />
            <Tooltip content={<CustomTooltip />} />
            <Area type="monotone" dataKey="volume" stroke="#7C3AED" strokeWidth={1}
              fill="url(#volGrad)" dot={false} activeDot={{ r: 2 }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
