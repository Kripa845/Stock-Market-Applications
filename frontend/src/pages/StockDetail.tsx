import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, TrendingUp, TrendingDown, Star } from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { formatDistanceToNow } from 'date-fns';
import { getCompanies } from '../api/companies';
import { stocksApi } from '../api/stocks';
import { newsApi } from '../api/news';
import Badge from '../components/common/Badge';
import EmptyState from '../components/common/EmptyState';
import type { Company, DailyPrice, FloorsheetTransaction, NewsArticle, SentimentLabel, BrokerRow } from '../types';

const TABS = ['Overview','Price','News','Trading','Floorsheet'] as const;
type Tab = typeof TABS[number];
const brokerRows: BrokerRow[] = [];

const TT = { background:'#161B2E', border:'1px solid #1E2538', borderRadius:10, fontSize:12 };

function SentimentBadge({ label }: { label: SentimentLabel }) {
  if (!label) return null;
  const m = { positive:'green', negative:'red', neutral:'gray' } as const;
  return <Badge variant={m[label]}>{label}</Badge>;
}

export default function StockDetail() {
  const { symbol } = useParams<{ symbol: string }>();
  const navigate   = useNavigate();
  const [tab, setTab] = useState<Tab>('Overview');
  const [priceRange, setPriceRange] = useState<7|30|90>(30);
  const [company, setCompany] = useState<Company | null>(null);
  const [prices, setPrices] = useState<DailyPrice[]>([]);
  const [floorsheet, setFloorsheet] = useState<FloorsheetTransaction[]>([]);
  const [relatedNews, setRelatedNews] = useState<NewsArticle[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const companyData = await getCompanies({ search: symbol, status: 'active' });
        const companies = companyData.results[0];
        if (!companies) throw new Error('Company not found');
        setCompany(companies);
        const [priceData, floorData, newsData] = await Promise.all([
          stocksApi.getPrices(companies.id, `${priceRange}d`),
          stocksApi.getFloorsheet(companies.id),
          newsApi.getNews({ company_id: companies.id }),
        ]);
        setPrices(priceData.prices);
        setFloorsheet(floorData.transactions);
        setRelatedNews(newsData.results);
      } catch {
        setCompany(null);
      } finally { setLoading(false); }
    };
    if (symbol) load();
  }, [symbol, priceRange]);

  if (loading) return <p className="text-text-secondary">Loading company...</p>;
  if (!company) {
    return (
      <EmptyState
        title={`Company "${symbol?.toUpperCase()}" not found`}
        description="Check the symbol or go back to the stocks list."
      />
    );
  }

  const sliced    = prices.slice(-priceRange);
  const first     = +sliced[0]?.close || 0;
  const last      = +sliced[sliced.length-1]?.close || 0;
  const prev      = +prices[prices.length-2]?.close || last;
  const change    = +(last - prev).toFixed(2);
  const changePct = +((change / prev) * 100).toFixed(2);
  const positive  = changePct >= 0;

  const chartData = sliced.map(p => ({
    date:   p.date.slice(5),
    price:  +p.close,
    volume: p.volume,
    vwap: undefined,
  }));

  return (
    <div className="space-y-5">
      {/* Back */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors"
      >
        <ArrowLeft size={14} /> Back
      </button>

      {/* Header card */}
      <div className="card flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-accent flex items-center justify-center font-bold font-mono text-white text-sm">
            {company.symbol.slice(0,3)}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-text-primary">{company.symbol}</h1>
              <Badge variant="gray">{company.sector}</Badge>
            </div>
            <p className="text-sm text-text-secondary">{company.name}</p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-3xl font-bold font-mono text-text-primary">Rs. {last.toFixed(2)}</p>
          <p className={`flex items-center justify-end gap-1 text-sm font-medium mt-1 ${positive ? 'text-up' : 'text-down'}`}>
            {positive ? <TrendingUp size={14}/> : <TrendingDown size={14}/>}
            {positive ? '+' : ''}{change} ({positive ? '+' : ''}{changePct}%)
          </p>
        </div>
        <button className="p-2 rounded-lg hover:bg-bg-elevated transition-colors text-text-muted hover:text-yellow-400">
          <Star size={16}/>
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-bg-elevated rounded-xl p-1 w-fit">
        {TABS.map(t => (
          <button
            key={t} onClick={() => setTab(t)}
            className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${
              tab === t ? 'bg-accent text-white' : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {(tab === 'Overview' || tab === 'Price') && (
        <div className="space-y-4">
          {/* Range selector */}
          <div className="flex items-center gap-1 bg-bg-elevated rounded-lg p-0.5 w-fit">
            {([7,30,90] as const).map(d => (
              <button key={d} onClick={() => setPriceRange(d)}
                className={`px-3 py-1 rounded text-xs font-medium transition-all ${priceRange===d ? 'bg-accent text-white' : 'text-text-secondary hover:text-text-primary'}`}>
                {d === 7 ? '1W' : d === 30 ? '1M' : '3M'}
              </button>
            ))}
          </div>

          {/* Price chart */}
          <div className="card h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{top:4,right:4,left:0,bottom:0}}>
                <defs>
                  <linearGradient id="sdGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={positive ? '#22C55E' : '#EF4444'} stopOpacity={0.2}/>
                    <stop offset="95%" stopColor={positive ? '#22C55E' : '#EF4444'} stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E2538" vertical={false}/>
                <XAxis dataKey="date" tick={{fontSize:10,fill:'#475569'}} tickLine={false} axisLine={false} interval="preserveStartEnd"/>
                <YAxis domain={['auto','auto']} tick={{fontSize:10,fill:'#475569'}} tickLine={false} axisLine={false} width={48}/>
                <Tooltip contentStyle={TT}/>
                <ReferenceLine y={first} stroke="#1E2538" strokeDasharray="4 4"/>
                <Area type="monotone" dataKey="price" stroke={positive ? '#22C55E' : '#EF4444'}
                  strokeWidth={1.5} fill="url(#sdGrad)" dot={false}/>
                <Area type="monotone" dataKey="vwap" stroke="#7C3AED" strokeWidth={1}
                  fill="none" dot={false} strokeDasharray="4 2"/>
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Volume chart */}
          <div className="card h-28">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{top:0,right:4,left:0,bottom:0}}>
                <XAxis dataKey="date" tick={{fontSize:10,fill:'#475569'}} tickLine={false} axisLine={false} interval="preserveStartEnd"/>
                <YAxis tick={{fontSize:10,fill:'#475569'}} tickLine={false} axisLine={false}
                  tickFormatter={v=>`${(v/1000).toFixed(0)}K`} width={40}/>
                <Tooltip contentStyle={TT} formatter={(v)=>[`${(Number(v ?? 0)/1000).toFixed(0)}K`,'']}/>
                <Bar dataKey="volume" fill="#7C3AED" opacity={0.6} radius={[2,2,0,0]}/>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {tab === 'Overview' && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: '52W High', value: `Rs. ${Math.max(...prices.map(p=>+p.close)).toFixed(2)}` },
                { label: '52W Low',  value: `Rs. ${Math.min(...prices.map(p=>+p.close)).toFixed(2)}` },
                { label: 'Avg Volume', value: `${((prices.reduce((s,p)=>s+p.volume,0)/prices.length)/1000).toFixed(0)}K` },
                { label: 'Sector',   value: company.sector },
              ].map(s => (
                <div key={s.label} className="card-elevated text-center">
                  <p className="text-xs text-text-muted">{s.label}</p>
                  <p className="text-sm font-semibold text-text-primary mt-0.5 truncate">{s.value}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'News' && (
        <div className="space-y-3">
          {relatedNews.length === 0
            ? <EmptyState title="No news found" description="No articles categorized for this company yet." />
            : relatedNews.map(n => (
              <div key={n.id} className="card hover:border-accent/30 transition-all cursor-pointer group">
                <p className="text-sm font-medium text-text-primary group-hover:text-accent-light transition-colors line-clamp-2">{n.headline}</p>
                <div className="flex flex-wrap items-center gap-2 mt-2">
                  <SentimentBadge label={n.sentiment_label}/>
                  <span className="text-xs text-text-muted ml-auto">
                    {formatDistanceToNow(new Date(n.published_at), {addSuffix:true})} · {n.source}
                  </span>
                </div>
              </div>
            ))
          }
        </div>
      )}

      {tab === 'Trading' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="card">
            <h3 className="text-sm font-semibold text-up mb-3">Top Buyers</h3>
            <table className="w-full text-xs"><thead><tr className="text-text-muted border-b border-bg-border">
              <th className="text-left py-1.5 font-medium">Broker</th>
              <th className="text-right py-1.5 font-medium">Qty</th>
              <th className="text-right py-1.5 font-medium">Txns</th>
            </tr></thead><tbody>
              {brokerRows.map((r,i)=>(
                <tr key={i} className="table-row">
                  <td className="py-2 text-text-secondary truncate max-w-[160px]">{r.buyer_broker}</td>
                  <td className="py-2 text-right font-mono text-up font-medium">{(r.total_quantity/1000).toFixed(1)}K</td>
                  <td className="py-2 text-right text-text-muted">{r.transaction_count}</td>
                </tr>
              ))}
            </tbody></table>
          </div>
          <div className="card">
            <h3 className="text-sm font-semibold text-down mb-3">Top Sellers</h3>
            <table className="w-full text-xs"><thead><tr className="text-text-muted border-b border-bg-border">
              <th className="text-left py-1.5 font-medium">Broker</th>
              <th className="text-right py-1.5 font-medium">Qty</th>
              <th className="text-right py-1.5 font-medium">Txns</th>
            </tr></thead><tbody>
              {brokerRows.map((r,i)=>(
                <tr key={i} className="table-row">
                  <td className="py-2 text-text-secondary truncate max-w-[160px]">{r.seller_broker}</td>
                  <td className="py-2 text-right font-mono text-down font-medium">{(r.total_quantity/1000).toFixed(1)}K</td>
                  <td className="py-2 text-right text-text-muted">{r.transaction_count}</td>
                </tr>
              ))}
            </tbody></table>
          </div>
        </div>
      )}

      {tab === 'Floorsheet' && (
        <div className="card overflow-x-auto">
          <h3 className="text-sm font-semibold text-text-primary mb-3">Recent Floorsheet Transactions</h3>
          <table className="w-full text-xs min-w-[520px]">
            <thead><tr className="text-text-muted border-b border-bg-border">
              <th className="text-left py-1.5 font-medium">#</th>
              <th className="text-left py-1.5 font-medium">Buyer Broker</th>
              <th className="text-left py-1.5 font-medium">Seller Broker</th>
              <th className="text-right py-1.5 font-medium">Qty</th>
              <th className="text-right py-1.5 font-medium">Rate</th>
              <th className="text-right py-1.5 font-medium">Amount</th>
            </tr></thead>
            <tbody>
              {floorsheet.map(f => (
                <tr key={f.id} className="table-row">
                  <td className="py-2 text-text-muted">{f.id}</td>
                  <td className="py-2 text-text-secondary">{f.buyer_broker}</td>
                  <td className="py-2 text-text-secondary">{f.seller_broker}</td>
                  <td className="py-2 text-right font-mono">{f.quantity.toLocaleString()}</td>
                  <td className="py-2 text-right font-mono">{Number(f.rate).toFixed(2)}</td>
                  <td className="py-2 text-right font-mono text-text-primary">
                    Rs. {Number(f.amount).toLocaleString(undefined, {maximumFractionDigits:0})}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
