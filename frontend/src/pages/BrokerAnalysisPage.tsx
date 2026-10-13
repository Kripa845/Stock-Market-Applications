import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Download, ExternalLink, Globe, Search, Trophy } from 'lucide-react';
import PageHeader from '../components/common/PageHeader';
import BrokerBadge, { BrokerLogo } from '../components/brokers/BrokerBadge';
import TopBrokers from '../components/brokers/TopBrokers';
import BrokerActivityCharts from '../components/brokers/BrokerActivityCharts';
import { analysisApi, type BrokerAnalysisResponse, type BrokerDetailResponse, type BrokerProfile } from '../api/analysis';

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
    <label className="text-xs text-text-muted">Company<select className="input mt-1 w-full" value={value.company_id} onChange={e => set('company_id', e.target.value)}><option value="">All accessible companies</option>{companies.map(c => <option key={c.id} value={c.id}>{c.symbol} — {c.name}</option>)}</select></label>
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
    <PageHeader title="Broker Explorer" subtitle="Broker buy, sell and net activity over any date range, company or broker, from collected floorsheet trades." actions={<><Link className="btn-ghost flex items-center gap-2 text-xs" to="/top-brokers"><Trophy size={14} /> Top Brokers (one day)</Link><Link className="btn-ghost flex items-center gap-2 text-xs" to="/reports"><Download size={14} /> Export</Link></>} />
    <section className="card space-y-4">
      <FilterFields value={draft} onChange={setDraft} companies={data?.companies ?? []} brokers={data?.broker_options ?? []} brokerDirectory={data?.broker_directory ?? []} />
      <div className="flex flex-wrap gap-2"><button className="btn-primary flex items-center gap-2 text-xs" onClick={apply}><Search size={13} /> Apply Filters</button><button className="btn-ghost text-xs" onClick={reset}>Reset Filters</button></div>
    </section>
    {error && <div className="card flex items-center justify-between text-sm text-down">{error}<button onClick={refresh} className="btn-ghost text-xs">Retry</button></div>}
    {loading && <div className="card text-sm text-text-muted">Loading broker analysis…</div>}
    {!loading && data && <>
      <div className="card flex flex-wrap items-center justify-between gap-3"><div><p className="text-[10px] uppercase tracking-widest text-text-muted">Analysis Period</p><p className="font-mono text-sm text-text-primary">{data.sampled_dates.length ? `${dateLabel(data.sampled_dates[data.sampled_dates.length - 1])} — ${dateLabel(data.sampled_dates[0])}` : 'No sampled dates'}</p></div><div><p className="text-[10px] uppercase tracking-widest text-text-muted">Sampled Trading Sessions</p><p className="font-mono text-sm text-text-primary">{data.summary.sampled_trading_days}</p></div><p className="w-full text-[11px] text-text-muted">{data.note}</p></div>
      {data.count === 0 ? <div className="card py-10 text-center"><p className="text-sm text-text-primary">No floorsheet data available for the selected period.</p><p className="mt-1 text-xs text-text-muted">Broker activity analysis is available only when floorsheet data has been collected.</p></div> : <>
        <SummaryCards data={data} />
        <TopBrokers data={data} />
        <div className="card"><div className="mb-3 flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-sm font-semibold text-text-primary">Broker Turnover Ranking</h2><span className="text-xs text-text-muted">{data.count} brokers · {number(data.summary.transaction_count)} real transactions</span></div><input aria-label="Search brokers by name or number" value={brokerSearch} onChange={event => setBrokerSearch(event.target.value)} placeholder="Search name or broker number" className="input w-full sm:max-w-xs" /></div><div className="overflow-x-auto"><table className="w-full min-w-[760px] text-xs"><thead className="border-b border-bg-border"><tr><th className="px-2 py-2 text-left text-text-muted"># Rank</th><th className="px-2 py-2 text-left text-text-muted">Broker</th><th className="px-2 py-2 text-right text-up">Buy Turnover</th><th className="px-2 py-2 text-right text-down">Sell Turnover</th><th className="px-2 py-2 text-right text-text-muted">Total Turnover</th><th className="px-2 py-2 text-right text-text-muted">Trades</th><th className="px-2 py-2 text-right text-text-muted">Action</th></tr></thead><tbody>{data.results.filter(row => `${row.broker_name || row.name} ${row.short_name} ${row.broker_code}`.toLowerCase().includes(brokerSearch.trim().toLowerCase())).map((row, index) => { const brokerName = row.broker_name || `Broker ${row.broker_code}`; return <tr key={row.broker} className="table-row"><td className="px-2 py-3 text-text-muted">{(data.page - 1) * data.page_size + index + 1}</td><td className="px-2 py-3"><Link className="flex min-w-0 items-center text-text-primary hover:text-accent-light" to={`/broker-analysis/${encodeURIComponent(row.broker)}`}><BrokerBadge brokerCode={row.broker_code} name={brokerName} shortName={row.short_name} logoUrl={row.logo_url} /></Link></td><td className="px-2 py-3 text-right font-mono text-up">{turnover(row.buy_value)}</td><td className="px-2 py-3 text-right font-mono text-down">{turnover(row.sell_value)}</td><td className="px-2 py-3 text-right font-mono">{turnover(row.total_value)}</td><td className="px-2 py-3 text-right font-mono">{number(row.trades)}</td><td className="px-2 py-3 text-right"><Link className="text-accent-light hover:underline" to={`/broker-analysis/${encodeURIComponent(row.broker)}`}>View ›</Link></td></tr>; })}</tbody></table></div><div className="mt-3 flex justify-end gap-2"><button className="btn-ghost text-xs" disabled={!data.previous} onClick={() => setPage(data.previous ?? 1)}>Previous</button><span className="self-center text-xs text-text-muted">Page {data.page}</span><button className="btn-ghost text-xs" disabled={!data.next} onClick={() => setPage(data.next ?? page)}>Next</button></div></div>
      </>}
    </>}
  </div>;
}

const externalUrl = (value: string) => (/^https?:\/\//i.test(value) ? value : `https://${value}`);

function BrokerProfileCard({ profile, summary }: { profile: BrokerProfile; summary: BrokerDetailResponse['summary'] }) {
  const net = Number(summary.net_value);
  const stance = net > 0 ? { label: 'Net Buyer', className: 'bg-up/10 text-up' } : net < 0 ? { label: 'Net Seller', className: 'bg-down/10 text-down' } : { label: 'Balanced', className: 'bg-bg-elevated text-text-muted' };
  const links = [
    profile.tms_link && { href: externalUrl(profile.tms_link), label: 'TMS Login', icon: ExternalLink },
    profile.website && { href: externalUrl(profile.website), label: 'Website', icon: Globe },
  ].filter(Boolean) as Array<{ href: string; label: string; icon: typeof Globe }>;
  return <section className="card flex flex-col gap-4 sm:flex-row sm:items-center">
    <BrokerLogo brokerCode={profile.broker_code} name={profile.name} shortName={profile.short_name} logoUrl={profile.logo_url} size={72} />
    <div className="min-w-0 flex-1 space-y-1">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="truncate text-lg font-bold text-text-primary">{profile.name}</h2>
        <span className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${stance.className}`}>{stance.label}</span>
      </div>
      <p className="text-xs text-text-muted">
        <span className="font-mono">Broker #{profile.broker_code}</span>
        {profile.short_name && profile.short_name !== profile.name && <> · {profile.short_name}</>}
        {!profile.in_directory && <> · not in the broker directory</>}
      </p>
      {links.length > 0 && <div className="flex flex-wrap gap-3 pt-1">{links.map(({ href, label, icon: Icon }) => <a key={label} href={href} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-xs text-accent-light hover:underline"><Icon size={12} /> {label}</a>)}</div>}
    </div>
    <div className="grid grid-cols-2 gap-4 text-right sm:min-w-[220px]">
      <div><p className="text-[10px] uppercase tracking-widest text-text-muted">Total Turnover</p><p className="font-mono text-sm font-bold">{turnover(summary.total_value)}</p></div>
      <div><p className="text-[10px] uppercase tracking-widest text-text-muted">Trades</p><p className="font-mono text-sm font-bold">{number(summary.trades)}</p></div>
    </div>
  </section>;
}

export function BrokerDetailPage() {
  const { brokerId = '' } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [filters, setFilters] = useState<Filters>({
    ...emptyFilters,
    company_id: searchParams.get('company_id') ?? '',
    start_date: searchParams.get('start_date') ?? '',
    end_date: searchParams.get('end_date') ?? '',
  });
  const [data, setData] = useState<BrokerDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
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
  const selectedCompany = data?.companies.find(item => String(item.company_id) === filters.company_id);
  const latestSession = data?.daily_activity[data.daily_activity.length - 1];
  const brokerName = data?.profile?.name ?? `Broker #${brokerId}`;
  const title = selectedCompany ? `${selectedCompany.symbol} · ${brokerName}` : brokerName;
  return <div className="space-y-5">
    <PageHeader title={title} subtitle={selectedCompany ? selectedCompany.name : 'Broker-side activity from captured floorsheet transactions.'} actions={<button className="btn-ghost flex items-center gap-2 text-xs" onClick={() => navigate(-1)}><ArrowLeft size={14} /> Back</button>} />
    <section className="card space-y-4"><FilterFields value={filters} onChange={setFilters} companies={data?.company_options ?? []} /><button className="btn-primary text-xs" onClick={load}>Apply Filters</button></section>
    {error && <div className="card text-sm text-down">{error}</div>}
    {loading && <div className="card text-sm text-text-muted">Loading broker detail…</div>}
    {!loading && data && <>
      {data.profile && <BrokerProfileCard profile={data.profile} summary={data.summary} />}
      {latestSession && <section className="card space-y-3"><div><h2 className="text-xs font-semibold uppercase tracking-wider text-accent-light">Latest Captured Session</h2><p className="text-[11px] text-text-muted">{dateLabel(latestSession.date)} · based on stored floorsheet rows</p></div><div className="grid grid-cols-2 gap-2 xl:grid-cols-4"><div className="bg-bg-elevated p-3"><p className="text-[10px] uppercase text-text-muted">Buy Turnover</p><p className="font-mono text-up">{turnover(latestSession.buy_value)}</p></div><div className="bg-bg-elevated p-3"><p className="text-[10px] uppercase text-text-muted">Sell Turnover</p><p className="font-mono text-down">{turnover(latestSession.sell_value)}</p></div><div className="bg-bg-elevated p-3"><p className="text-[10px] uppercase text-text-muted">Transactions</p><p className="font-mono">{number(latestSession.trades)}</p></div><div className="bg-bg-elevated p-3"><p className="text-[10px] uppercase text-text-muted">Observed Price Range</p><p className="font-mono">{latestSession.low_rate ?? '—'} – {latestSession.high_rate ?? '—'}</p></div></div></section>}
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">{[['Shares Bought', number(data.summary.buy_quantity)], ['Shares Sold', number(data.summary.sell_quantity)], ['Buy Turnover', turnover(data.summary.buy_value)], ['Sell Turnover', turnover(data.summary.sell_value)], ['Net Position', number(data.summary.net_quantity)], ['Net Amount', turnover(data.summary.net_value)], ['Avg Buy Price', data.summary.buy_quantity ? `Rs. ${(Number(data.summary.buy_value) / data.summary.buy_quantity).toFixed(2)}` : '—'], ['Avg Sell Price', data.summary.sell_quantity ? `Rs. ${(Number(data.summary.sell_value) / data.summary.sell_quantity).toFixed(2)}` : '—']].map(([label, value]) => <div className="card" key={label}><p className="text-[10px] uppercase tracking-widest text-text-muted">{label}</p><p className="mt-1 font-mono text-lg font-bold tabular-nums">{value}</p></div>)}</div>
      <BrokerActivityCharts daily={data.daily_activity} sessions={data.trading_sessions ?? []} />
      <div className="card"><div className="mb-3"><h2 className="text-sm font-semibold text-text-primary">Traded Stocks</h2><p className="text-[10px] text-text-muted">Companies are limited to accessible, active companies with captured trades.</p></div><div className="overflow-x-auto"><table className="w-full min-w-[760px] text-xs"><thead className="border-b border-bg-border text-text-muted"><tr>{['Company', 'Sector', 'Buy Turnover', 'Sell Turnover', 'Total Turnover', 'Trades', 'Action'].map(x => <th key={x} className="px-2 py-2 text-right first:text-left">{x}</th>)}</tr></thead><tbody>{data.companies.map(company => <tr className="table-row" key={company.company_id}><td className="px-2 py-2"><span className="font-semibold text-text-primary">{company.symbol}</span><p className="text-[10px] text-text-muted">{company.name}</p></td><td className="px-2 py-2 text-right text-text-muted">{company.sector}</td><td className="px-2 py-2 text-right font-mono text-up">{turnover(company.buy_value)}</td><td className="px-2 py-2 text-right font-mono text-down">{turnover(company.sell_value)}</td><td className="px-2 py-2 text-right font-mono">{turnover(Number(company.buy_value) + Number(company.sell_value))}</td><td className="px-2 py-2 text-right font-mono">{number(company.trades)}</td><td className="px-2 py-2 text-right"><Link className="text-accent-light hover:underline" to={`/broker-analysis/${encodeURIComponent(brokerId)}?company_id=${company.company_id}`}>View ›</Link></td></tr>)}</tbody></table></div>{data.sampled_dates.length > 0 && <p className="mt-3 text-[11px] text-text-muted">Active in {data.sampled_dates.length} captured sessions · {dateLabel(data.sampled_dates[0])} – {dateLabel(data.sampled_dates[data.sampled_dates.length - 1])}</p>}</div>
    </>}
  </div>;
}
