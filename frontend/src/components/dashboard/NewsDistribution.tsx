import { useEffect, useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import { getCompanies } from '../../api/companies';
import type { Company } from '../../types/company';
import { dashboardApi } from '../../api/dashboard';
import { useLiveRefresh } from '../../hooks/useLiveRefresh';

const COLORS = ['#7C3AED','#9F67FF','#6D28D9','#8B5CF6','#A78BFA','#7C3AED','#5B21B6','#4C1D95','#6D28D9','#7C3AED'];

export default function NewsDistribution() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [totalNews, setTotalNews] = useState(0);
  const load = () => Promise.all([
    getCompanies({ status: 'active' }).then(response => setCompanies(response.results)),
    dashboardApi.viewer().then(response => setTotalNews(response.total_news)),
  ]);
  useEffect(() => { load(); }, []);
  useLiveRefresh(load);
  const data = companies
    .map(company => ({ symbol: company.symbol, count: company.news_count }))
    .sort((a, b) => b.count - a.count);

  return (
    <div className="card flex flex-col gap-4">
      <h3 className="text-sm font-semibold text-text-primary">News by Company</h3>

      <div className="h-44">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
            <XAxis type="number" tick={{ fontSize: 10, fill: '#475569' }} tickLine={false} axisLine={false} />
            <YAxis type="category" dataKey="symbol" tick={{ fontSize: 11, fill: '#94A3B8', fontWeight: 600 }} tickLine={false} axisLine={false} width={44} />
            <Tooltip
              cursor={{ fill: 'rgba(124,58,237,0.06)' }}
              contentStyle={{ background: '#161B2E', border: '1px solid #1E2538', borderRadius: 10, fontSize: 12 }}
              labelStyle={{ color: '#94A3B8' }}
              itemStyle={{ color: '#E2E8F0' }}
            />
            <Bar dataKey="count" radius={[0, 4, 4, 0]}>
              {data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} opacity={0.85} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-2 gap-3">
        {[
          { label: 'Total Articles', value: totalNews.toLocaleString() },
          { label: 'Companies tracked', value: companies.filter(company => company.is_tracked).length.toLocaleString() },
        ].map(s => (
          <div key={s.label} className="bg-bg-elevated rounded-lg p-3">
            <p className="text-xs text-text-muted">{s.label}</p>
            <p className="text-lg font-bold font-mono text-text-primary mt-0.5">{s.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
