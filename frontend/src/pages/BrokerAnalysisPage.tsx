import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Download, Search } from 'lucide-react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import PageHeader from '../components/common/PageHeader';
import BrokerBadge from '../components/brokers/BrokerBadge';
import BrokerAvatar from '../components/brokers/BrokerAvatar';
import { analysisApi, type BrokerActivity, type BrokerAnalysisResponse, type BrokerDetailResponse } from '../api/analysis';

type Filters = { start_date: string; end_date: string; company_id: string; broker: string };
const emptyFilters: Filters = { start_date: '', end_date: '', company_id: '', broker: '' };
const number = (value: number | string | null | undefined) => Number(value ?? 0).toLocaleString();
const turnover = (value: number | string | null | undefined) => `Rs. ${(Number(value ?? 0) / 10_000_000).toFixed(2)} Cr`;
const dateLabel = (value: string) => new Date(`${value}T00:00:00`).toLocaleDateString();

function useBrokerOverview(filters: Filters, page: number) {
  const [data, setData] = useState<BrokerAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const refresh = useCallback(() => {
    setLoading(true);
    setError('');
    analysisApi.getBrokerAnalysis({
      ...(filters.start_date && { start_date: filters.start_date }),
      ...(filters.end_date && { end_date: filters.end_date }),
      ...(filters.company_id && { company_id: Number(filters.company_id) }),
      ...(filters.broker && { broker: filters.broker }),
      page,
    }).then(setData).catch(() => setError('Unable to load broker activity. Check your access and try again.')).finally(() => setLoading(false));
  }, [filters, page]);
  useEffect(refresh, [refresh]);
  return { data, loading, error, refresh };
}

function FilterFields({
  value, onChange, companies, brokers, brokerDirectory = [],
}: {
  value: Filters;
  onChange: (value: Filters) => void;
  companies: Array<{ id: number; symbol: string; name: string }>;
  brokers?: string[];
  brokerDirectory?: BrokerAnalysisResponse['broker_directory'];
}) {
  const set = (key: keyof Filters, next: string) => onChange({ ...value, [key]: next });
  const brokerNames = new Map<string, string>(brokerDirectory.map(item => [item.broker_code, item.name]));
  return <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
    <label className="text-xs text-text-muted">Start Date<input className="input mt-1 w-full" type="date" value={value.start_date} onChange={e => set('start_date', e.target.value)} /></label>
    <label className="text-xs text-text-muted">End Date<input className="input mt-1 w-full" type="date" value={value.end_date} onChange={e => set('end_date', e.target.value)} /></label>
    <label className="text-xs text-text-muted">Company<select className="input mt-1 w-full" value={value.company_id} onChange={e => set('company_id', e.target.value)}><option value="">All accessible companies</option>{companies.map(c => <option key={c.id} value={c.id}>{c.symbol} â€” {c.name}</option>)}</select></label>
    <label className="text-xs text-text-muted">Broker<select className="input mt-1 w-full" value={value.broker} onChange={e => set('broker', e.target.value)}><option value="">All brokers</option>{(brokers ?? []).map(b => <option key={b} value={b}>{brokerNames.get(b) ?? `Broker ${b}`} · #{b}</option>)}</select></label>
  </div>;
}

function SummaryCards({ data }: { data: BrokerAnalysisResponse }) {
  const cards = [
    ['Total Turnover', turnover(data.summary.total_turnover)],
    ['Buy Turnover', turnover(data.summary.total_buy_value)],
    ['Sell Turnover', turnover(data.summary.total_sell_value)],
    ['Transactions', number(data.summary.transaction_count)],
    ['Sampled Sessions', number(data.summary.sampled_trading_days)],
  ] as const;
  return <div className="grid grid-cols-2 gap-3 xl:grid-cols-5">{cards.map(([label, value], i) => <div className="card" key={label}><p className="text-[10px] uppercase tracking-widest text-text-muted">{label}</p><p className={`mt-1 font-mono text-xl font-bold tabular-nums ${i === 0 ? 'text-up' : i === 1 ? 'text-down' : 'text-text-primary'}`}>{value}</p></div>)}</div>;
}

function Ranking({ title, rows, field, color }: { title: string; rows: BrokerActivity[]; field: 'buy_quantity' | 'sell_quantity' | 'net_quantity'; color: string }) {
  return <div className="card"><h2 className="mb-3 text-sm font-semibold text-text-primary">{title}</h2>{rows.length ? <ol className="space-y-2">{rows.map((row, index) => <li key={row.broker}><Link to={`/broker-analysis/${encodeURIComponent(row.broker)}`} className="flex items-center justify-between gap-3 text-xs hover:text-accent-light"><span className="flex min-w-0 items-center gap-2"><span className="text-text-secondary">{index + 1}.</span><BrokerBadge brokerCode={row.broker_code} name={row.name} shortName={row.short_name} logoUrl={row.logo_url} /></span><span className={`font-mono font-semibold tabular-nums ${color}`}>{number(row[field])}</span></Link></li>)}</ol> : <p className="text-xs text-text-muted">No broker activity in this selection.</p>}</div>;
}

export default function BrokerAnalysisPage() {
  const [searchParams] = useSearchParams();
  const initialFilters = { ...emptyFilters, company_id: searchParams.get('company_id') ?? '' };
  const [filters, setFilters] = useState(initialFilters);
  const [draft, setDraft] = useState(initialFilters);
  const [page, setPage] = useState(1);
  const [brokerSearch, setBrokerSearch] = useState('');
  const { data, loading, error, refresh } = useBrokerOverview(filters, page);
  const apply = () => { setPage(1); setFilters(draft); };
  const reset = () => { setDraft(emptyFilters); setPage(1); setFilters(emptyFilters); };
  return <div className="space-y-5">
    <PageHeader title="Floorsheet / Broker Analysis" subtitle="Broker-side buy, sell, and net activity from collected floorsheet transactions." actions={<Link className="btn-ghost flex items-center gap-2 text-xs" to="/reports"><Download size={14} /> Export</Link>} />
    <section className="card space-y-4">
      <FilterFields value={draft} onChange={setDraft} companies={data?.companies ?? []} brokers={data?.broker_options ?? []} brokerDirectory={data?.broker_directory ?? []} />
      <div className="flex flex-wrap gap-2"><button className="btn-primary flex items-center gap-2 text-xs" onClick={apply}><Search size={13} /> Apply Filters</button><button className="btn-ghost text-xs" onClick={reset}>Reset Filters</button></div>
    </section>
    {error && <div className="card flex items-center justify-between text-sm text-down">{error}<button onClick={refresh} className="btn-ghost text-xs">Retry</button></div>}
    {loading && <div className="card text-sm text-text-muted">Loading broker analysisâ€¦</div>}
    {!loading && data && <>
      <div className="card flex flex-wrap items-center justify-between gap-3"><div><p className="text-[10px] uppercase tracking-widest text-text-muted">Analysis Period</p><p className="font-mono text-sm text-text-primary">{data.sampled_dates.length ? `${dateLabel(data.sampled_dates[data.sampled_dates.length - 1])} â€” ${dateLabel(data.sampled_dates[0])}` : 'No sampled dates'}</p></div><div><p className="text-[10px] uppercase tracking-widest text-text-muted">Sampled Trading Sessions</p><p className="font-mono text-sm text-text-primary">{data.summary.sampled_trading_days}</p></div><p className="w-full text-[11px] text-text-muted">{data.note}</p></div>
      {data.count === 0 ? <div className="card py-10 text-center"><p className="text-sm text-text-primary">No floorsheet data available for the selected period.</p><p className="mt-1 text-xs text-text-muted">Broker activity analysis is available only when floorsheet data has been collected.</p></div> : <>
        <SummaryCards data={data} />
        <div className="grid gap-4 xl:grid-cols-2"><Ranking title="Most Active Buyer Brokers" rows={data.most_active_buyers} field="buy_quantity" color="text-up" /><Ranking title="Most Active Seller Brokers" rows={data.most_active_sellers} field="sell_quantity" color="text-down" /></div>
        <div className="grid gap-4 xl:grid-cols-2"><Ranking title="Top Net Buyers" rows={data.top_net_buyers} field="net_quantity" color="text-up" /><Ranking title="Top Net Sellers" rows={data.top_net_sellers} field="net_quantity" color="text-down" /></div>
        <div className="card"><div className="mb-3 flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-sm font-semibold text-text-primary">Broker Turnover Ranking</h2><span className="text-xs text-text-muted">{data.count} brokers · {number(data.summary.transaction_count)} real transactions</span></div><input aria-label="Search brokers by name or number" value={brokerSearch} onChange={event => setBrokerSearch(event.target.value)} placeholder="Search name or broker number" className="input w-full sm:max-w-xs" /></div><div className="overflow-x-auto"><table className="w-full min-w-[760px] text-xs"><thead className="border-b border-bg-border"><tr><th className="px-2 py-2 text-left text-text-muted"># Rank</th><th className="px-2 py-2 text-left text-text-muted">Broker</th><th className="px-2 py-2 text-right text-up">Buy Turnover</th><th className="px-2 py-2 text-right text-down">Sell Turnover</th><th className="px-2 py-2 text-right text-text-muted">Total Turnover</th><th className="px-2 py-2 text-right text-text-muted">Trades</th><th className="px-2 py-2 text-right text-text-muted">Action</th></tr></thead><tbody>{data.results.filter(row => `${row.broker_name || row.name} ${row.short_name} ${row.broker_code}`.toLowerCase().includes(brokerSearch.trim().toLowerCase())).map((row, index) => { const brokerName = row.broker_name || `Broker ${row.broker_code}`; return <tr key={row.broker} className="table-row"><td className="px-2 py-3 text-text-muted">{(data.page - 1) * data.page_size + index + 1}</td><td className="px-2 py-3"><Link className="flex min-w-0 items-center gap-3 text-text-primary hover:text-accent-light" to={`/broker-analysis/${encodeURIComponent(row.broker)}`}><BrokerAvatar brokerNo={row.broker_code} name={brokerName} /><span className="min-w-0"><span className="block max-w-[260px] truncate font-semibold" title={brokerName}>{brokerName}</span><span className="mt-0.5 block text-[10px] font-normal text-text-muted">Broker No. {row.broker_code}</span></span></Link></td><td className="px-2 py-3 text-right font-mono text-up">{turnover(row.buy_value)}</td><td className="px-2 py-3 text-right font-mono text-down">{turnover(row.sell_value)}</td><td className="px-2 py-3 text-right font-mono">{turnover(row.total_value)}</td><td className="px-2 py-3 text-right font-mono">{number(row.trades)}</td><td className="px-2 py-3 text-right"><Link className="text-accent-light hover:underline" to={`/broker-analysis/${encodeURIComponent(row.broker)}`}>View ›</Link></td></tr>; })}</tbody></table></div><div className="mt-3 flex justify-end gap-2"><button className="btn-ghost text-xs" disabled={!data.previous} onClick={() => setPage(data.previous ?? 1)}>Previous</button><span className="self-center text-xs text-text-muted">Page {data.page}</span><button className="btn-ghost text-xs" disabled={!data.next} onClick={() => setPage(data.next ?? page)}>Next</button></div></div>
      </>}
    </>}
  </div>;
}

export function BrokerDetailPage() {
  const { brokerId = '' } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [filters, setFilters] = useState<Filters>({ ...emptyFilters, company_id: searchParams.get('company_id') ?? '' });
  const [data, setData] = useState<BrokerDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [trendRange, setTrendRange] = useState('ALL');
  useEffect(() => {
    const companyId = searchParams.get('company_id') ?? '';
    setFilters(current => current.company_id === companyId ? current : { ...current, company_id: companyId });
  }, [searchParams]);
  const load = useCallback(() => {
    setLoading(true); setError('');
    analysisApi.getBrokerDetail(brokerId, {
      ...(filters.start_date && { start_date: filters.start_date }),
      ...(filters.end_date && { end_date: filters.end_date }),
      ...(filters.company_id && { company_id: Number(filters.company_id) }),
    }).then(setData).catch(() => setError('No broker activity found for this selection, or the data could not be loaded.')).finally(() => setLoading(false));
  }, [brokerId, filters]);
  useEffect(load, [load]);
  const chartData = useMemo(() => {
    const rows = data?.daily_activity ?? [];
    const rangeDays: Record<string, number> = { '1M': 31, '3M': 92, '6M': 183, '1Y': 366 };
    const days = rangeDays[trendRange];
    const lastDate = rows.length ? new Date(`${rows[rows.length - 1].date}T00:00:00`) : null;
    return rows.filter(row => !days || !lastDate || new Date(`${row.date}T00:00:00`).getTime() >= lastDate.getTime() - days * 86400000)
      .map(row => ({ ...row, date: row.date.slice(5) }));
  }, [data, trendRange]);
  const selectedCompany = data?.companies.find(item => String(item.company_id) === filters.company_id);
  const latestSession = data?.daily_activity[data.daily_activity.length - 1];
  const title = selectedCompany ? `${selectedCompany.symbol} · Broker #${brokerId}` : `Broker #${brokerId}`;
  return <div className="space-y-5">
    <PageHeader title={title} subtitle={selectedCompany ? selectedCompany.name : 'Broker-side activity from captured floorsheet transactions.'} actions={<button className="btn-ghost flex items-center gap-2 text-xs" onClick={() => navigate(-1)}><ArrowLeft size={14} /> Back to analysis</button>} />
    <section className="card space-y-4"><FilterFields value={filters} onChange={setFilters} companies={data?.company_options ?? []} /><button className="btn-primary text-xs" onClick={load}>Apply Filters</button></section>
    {error && <div className="card text-sm text-down">{error}</div>}
    {loading && <div className="card text-sm text-text-muted">Loading broker detailâ€¦</div>}
    {!loading && data && <>
      {latestSession && <section className="card space-y-3"><div><h2 className="text-xs font-semibold uppercase tracking-wider text-accent-light">Latest Captured Session</h2><p className="text-[11px] text-text-muted">{dateLabel(latestSession.date)} · based on stored floorsheet rows</p></div><div className="grid grid-cols-2 gap-2 xl:grid-cols-4"><div className="bg-bg-elevated p-3"><p className="text-[10px] uppercase text-text-muted">Buy Turnover</p><p className="font-mono text-up">{turnover(latestSession.buy_value)}</p></div><div className="bg-bg-elevated p-3"><p className="text-[10px] uppercase text-text-muted">Sell Turnover</p><p className="font-mono text-down">{turnover(latestSession.sell_value)}</p></div><div className="bg-bg-elevated p-3"><p className="text-[10px] uppercase text-text-muted">Transactions</p><p className="font-mono">{number(latestSession.trades)}</p></div><div className="bg-bg-elevated p-3"><p className="text-[10px] uppercase text-text-muted">Observed Price Range</p><p className="font-mono">{latestSession.low_rate ?? 'â€”'} â€“ {latestSession.high_rate ?? 'â€”'}</p></div></div></section>}
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">{[['Shares Bought', number(data.summary.buy_quantity)], ['Shares Sold', number(data.summary.sell_quantity)], ['Buy Turnover', turnover(data.summary.buy_value)], ['Sell Turnover', turnover(data.summary.sell_value)], ['Net Position', number(data.summary.net_quantity)], ['Net Amount', turnover(data.summary.net_value)], ['Avg Buy Price', data.summary.buy_quantity ? `Rs. ${(Number(data.summary.buy_value) / data.summary.buy_quantity).toFixed(2)}` : 'â€”'], ['Avg Sell Price', data.summary.sell_quantity ? `Rs. ${(Number(data.summary.sell_value) / data.summary.sell_quantity).toFixed(2)}` : 'â€”']].map(([label, value]) => <div className="card" key={label}><p className="text-[10px] uppercase tracking-widest text-text-muted">{label}</p><p className="mt-1 font-mono text-lg font-bold tabular-nums">{value}</p></div>)}</div>
      <div className="card"><div className="mb-3 flex flex-wrap items-center justify-between gap-2"><div><h2 className="text-sm font-semibold text-text-primary">Buy / Sell Quantity Trend</h2><p className="text-[10px] text-text-muted">Only dates present in captured floorsheet data</p></div><div className="flex gap-1">{['1M', '3M', '6M', '1Y', 'ALL'].map(range => <button key={range} className={`rounded px-2 py-1 text-[10px] ${trendRange === range ? 'bg-accent text-white' : 'text-text-muted hover:bg-bg-elevated'}`} onClick={() => setTrendRange(range)}>{range}</button>)}</div></div>{chartData.length ? <ResponsiveContainer width="100%" height={260}><LineChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}><CartesianGrid stroke="var(--trading-grid)" strokeDasharray="3 3" /><XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--trading-muted)' }} /><YAxis orientation="right" tick={{ fontSize: 10, fill: 'var(--trading-muted)' }} /><Tooltip /><Line dataKey="buy_quantity" name="Buy quantity" stroke="var(--trading-up)" dot={false} /><Line dataKey="sell_quantity" name="Sell quantity" stroke="var(--trading-down)" dot={false} /></LineChart></ResponsiveContainer> : <p className="text-xs text-text-muted">No captured sessions in this period.</p>}</div>
      <div className="card"><div className="mb-3"><h2 className="text-sm font-semibold text-text-primary">Traded Stocks</h2><p className="text-[10px] text-text-muted">Companies are limited to accessible, active companies with captured trades.</p></div><div className="overflow-x-auto"><table className="w-full min-w-[760px] text-xs"><thead className="border-b border-bg-border text-text-muted"><tr>{['Company', 'Sector', 'Buy Turnover', 'Sell Turnover', 'Total Turnover', 'Trades', 'Action'].map(x => <th key={x} className="px-2 py-2 text-right first:text-left">{x}</th>)}</tr></thead><tbody>{data.companies.map(company => <tr className="table-row" key={company.company_id}><td className="px-2 py-2"><span className="font-semibold text-text-primary">{company.symbol}</span><p className="text-[10px] text-text-muted">{company.name}</p></td><td className="px-2 py-2 text-right text-text-muted">{company.sector}</td><td className="px-2 py-2 text-right font-mono text-up">{turnover(company.buy_value)}</td><td className="px-2 py-2 text-right font-mono text-down">{turnover(company.sell_value)}</td><td className="px-2 py-2 text-right font-mono">{turnover(Number(company.buy_value) + Number(company.sell_value))}</td><td className="px-2 py-2 text-right font-mono">{number(company.trades)}</td><td className="px-2 py-2 text-right"><Link className="text-accent-light hover:underline" to={`/broker-analysis/${encodeURIComponent(brokerId)}?company_id=${company.company_id}`}>View ›</Link></td></tr>)}</tbody></table></div>{data.sampled_dates.length > 0 && <p className="mt-3 text-[11px] text-text-muted">Captured sessions ({data.sampled_dates.length}): {data.sampled_dates.map(dateLabel).join(', ')}</p>}</div>
    </>}
  </div>;
}
