import { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts';
import PageHeader from '../components/common/PageHeader';
import EmptyState from '../components/common/EmptyState';
import { getCompanies } from '../api/companies';
import { stocksApi } from '../api/stocks';
import { useLiveRefresh } from '../hooks/useLiveRefresh';
import type { Company, DailyPrice, FloorsheetTransaction } from '../types';

type BrokerTotals = { broker: string; quantity: number; amount: number; transactions: number };

function formatQuantity(value: number) {
  return value >= 1_000_000 ? `${(value / 1_000_000).toFixed(2)}M` : `${(value / 1_000).toFixed(0)}K`;
}

function BrokerTable({ rows, title, color }: { rows: BrokerTotals[]; title: string; color: string }) {
  return <div className="card"><h3 className={`text-sm font-semibold mb-3 ${color}`}>{title}</h3><table className="w-full text-xs"><thead><tr className="text-text-muted border-b border-bg-border"><th className="text-left py-1.5 font-medium">Broker</th><th className="text-right py-1.5 font-medium">Qty</th><th className="text-right py-1.5 font-medium">Amount</th><th className="text-right py-1.5 font-medium">Txns</th></tr></thead><tbody>{rows.map(row => <tr key={row.broker} className="table-row"><td className="py-2 text-text-secondary">{row.broker}</td><td className="py-2 text-right font-mono">{formatQuantity(row.quantity)}</td><td className="py-2 text-right font-mono">Rs. {row.amount.toLocaleString()}</td><td className="py-2 text-right text-text-muted">{row.transactions}</td></tr>)}</tbody></table>{rows.length === 0 && <p className="text-xs text-text-muted">No floorsheet data available.</p>}</div>;
}

export default function TradingPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [prices, setPrices] = useState<DailyPrice[]>([]);
  const [floorsheet, setFloorsheet] = useState<FloorsheetTransaction[]>([]);
  const [error, setError] = useState('');

  const loadCompanies = () => getCompanies({ status: 'active' }).then(response => { setCompanies(response.results); setSelectedId(current => current ?? response.results[0]?.id ?? null); }).catch(() => setError('Unable to load companies.'));
  const loadData = () => { if (!selectedId) return; Promise.all([stocksApi.getPrices(selectedId, '90d'), stocksApi.getFloorsheet(selectedId)]).then(([priceData, floorData]) => { setPrices(priceData.prices); setFloorsheet(floorData.transactions); setError(''); }).catch(() => setError('Unable to load trading data.')); };

  useEffect(() => { loadCompanies(); }, []);
  useEffect(() => { loadData(); }, [selectedId]);
  useLiveRefresh(loadData, 10000);

  const company = companies.find(item => item.id === selectedId);
  const chartData = prices.slice(-30).map(price => ({ date: price.date.slice(5), close: Number(price.close), volume: price.volume }));
  const averageVolume = prices.reduce((total, price) => total + price.volume, 0) / (prices.length || 1);
  const buyers = aggregateBrokers(floorsheet, 'buyer_broker');
  const sellers = aggregateBrokers(floorsheet, 'seller_broker');

  if (!companies.length && !error) return <p className="text-text-secondary">Loading trading data...</p>;
  return <div className="space-y-6"><PageHeader title="Trading Behavior" subtitle="Live prices, volume, and floorsheet broker activity." />{error && <div className="text-sm text-down flex items-center gap-2"><AlertTriangle size={14} />{error}</div>}{companies.length === 0 && <EmptyState title="No companies available" description="Crawl or configure companies before viewing trading data." />}{companies.length > 0 && <><div className="flex flex-wrap items-center gap-2">{companies.map(item => <button key={item.id} onClick={() => setSelectedId(item.id)} className={`px-3 py-1.5 rounded-lg text-xs font-mono ${item.id === selectedId ? 'bg-accent text-white' : 'bg-bg-elevated text-text-secondary'}`}>{item.symbol}</button>)}</div><div className="flex items-center gap-3"><span className="text-sm text-text-secondary">Analyzing:</span><strong className="font-mono text-accent-light">{company?.symbol}</strong><span className="text-sm text-text-secondary">{company?.name}</span></div>{chartData.length === 0 ? <EmptyState title="No price data" description="This company has no crawled prices yet." /> : <><div className="grid grid-cols-1 xl:grid-cols-2 gap-4"><div className="card"><h3 className="text-sm font-semibold mb-4">Close Price</h3><div className="h-56"><ResponsiveContainer><AreaChart data={chartData}><CartesianGrid strokeDasharray="3 3" stroke="#1E2538" vertical={false}/><XAxis dataKey="date" tick={{fontSize:10,fill:'#475569'}}/><YAxis domain={['auto','auto']} tick={{fontSize:10,fill:'#475569'}}/><Tooltip/><Area dataKey="close" stroke="#22C55E" fill="rgba(34,197,94,.12)" name="Close"/></AreaChart></ResponsiveContainer></div></div><div className="card"><h3 className="text-sm font-semibold mb-4">Volume</h3><div className="h-56"><ResponsiveContainer><BarChart data={chartData}><CartesianGrid strokeDasharray="3 3" stroke="#1E2538" vertical={false}/><XAxis dataKey="date" tick={{fontSize:10,fill:'#475569'}}/><YAxis tick={{fontSize:10,fill:'#475569'}}/><Tooltip/><Bar dataKey="volume" fill="#60A5FA" name="Volume">{chartData.map((item, index) => <Cell key={index} fill={item.volume > averageVolume * 2 ? '#EF4444' : '#60A5FA'} />)}</Bar></BarChart></ResponsiveContainer></div></div></div><p className="text-xs text-text-muted">Average volume: {formatQuantity(averageVolume)}. Red bars exceed twice the observed average.</p></>}{<div className="grid grid-cols-1 lg:grid-cols-2 gap-4"><BrokerTable rows={buyers} title="Top Buyers" color="text-up"/><BrokerTable rows={sellers} title="Top Sellers" color="text-down"/></div>}</>}</div>;
}

function aggregateBrokers(rows: FloorsheetTransaction[], field: 'buyer_broker' | 'seller_broker'): BrokerTotals[] {
  const totals = new Map<string, BrokerTotals>();
  rows.forEach(row => { const broker = row[field]; const current = totals.get(broker) ?? { broker, quantity: 0, amount: 0, transactions: 0 }; current.quantity += row.quantity; current.amount += Number(row.amount ?? Number(row.rate) * row.quantity); current.transactions += 1; totals.set(broker, current); });
  return [...totals.values()].sort((left, right) => right.quantity - left.quantity).slice(0, 10);
}
