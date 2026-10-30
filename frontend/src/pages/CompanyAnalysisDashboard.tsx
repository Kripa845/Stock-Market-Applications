
import { useCallback, useEffect, useMemo, useState } from 'react';
import KlinePriceChart from '../components/charts/KlinePriceChart';
import {
  RANGE_TITLES, filterRange, rangeAvailable, rangeStart, unavailableReason, type RangeId,
} from '../components/charts/chartRanges';
import {
  Activity, AlertTriangle,
  Loader2, Newspaper,
  RefreshCw, TrendingUp,
} from 'lucide-react';
import clsx from 'clsx';

import PageHeader from '../components/common/PageHeader';
import Badge from '../components/common/Badge';
import CompanyLogo from '../components/companies/CompanyLogo';
import VolumeAnomalyChart from '../components/analysis/VolumeAnomalyChart';
import { NewsSentimentScatter } from '../components/analysis/NewsSentimentScatter';
import { useSearchParams } from 'react-router-dom';
import { getCompanies } from '../api/companies';
import {
  analysisApi,
  type BehaviorSummary,
  type CategorizedCompanyNews,
  type PricePoint,
  type NewsSentimentForwardResponse,
  type VolumeAnomaly,
} from '../api/analysis';
import type { Company } from '../types/company';
import {
  getIndexHistory, getIndices, getSubIndices, type IndexHistory, type IndexRow,
} from '../api/marketIndices';

// ─── Sub-components ───────────────────────────────────────────────────────────

function StatPill({
  label, value, sub, color = 'text-text-primary',
}: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div className="flex flex-col gap-0.5 min-w-[90px]">
      <span className="text-[10px] uppercase tracking-widest text-text-muted">{label}</span>
      <span className={clsx('text-base font-bold font-mono', color)}>{value}</span>
      {sub && <span className="text-[11px] text-text-muted">{sub}</span>}
    </div>
  );
}

function SectionTitle({ icon: Icon, children }: { icon: React.ElementType; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <Icon size={15} className="text-accent-light shrink-0" />
      <h3 className="text-sm font-semibold text-text-primary">{children}</h3>
    </div>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

// Index values arrive as decimal strings; a missing value is shown as "—", never 0.
function fmtPoints(value: string | null | undefined, signed = false) {
  if (value == null || value === '') return '—';
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  const text = n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return signed && n > 0 ? `+${text}` : text;
}

function computeVwap(prices: PricePoint[]) {
  const totalTurnover = prices.reduce((s, p) => s + parseFloat(p.turnover), 0);
  const totalVolume   = prices.reduce((s, p) => s + p.volume, 0);
  return totalVolume ? totalTurnover / totalVolume : 0;
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function CompanyAnalysisDashboard() {
  const [searchParams] = useSearchParams();
  const requestedSymbol = searchParams.get('symbol')?.toUpperCase();
  const [companies,   setCompanies]   = useState<Company[]>([]);
  const [selectedId,  setSelectedId]  = useState<number | null>(null);
  const [prices,      setPrices]      = useState<PricePoint[]>([]);
  const [behavior,    setBehavior]    = useState<BehaviorSummary | null>(null);
  const [categorizedNews, setCategorizedNews] = useState<CategorizedCompanyNews[] | null>(null);
  const [newsForward, setNewsForward] = useState<NewsSentimentForwardResponse | null>(null);
  const [loadingNewsForward, setLoadingNewsForward] = useState(false);
  const [newsForwardError, setNewsForwardError] = useState('');
  const [volumeAnomalies, setVolumeAnomalies] = useState<VolumeAnomaly[]>([]);
  const [volumeAnomalyRefresh, setVolumeAnomalyRefresh] = useState(0);
  const [loadingVolumeAnomalies, setLoadingVolumeAnomalies] = useState(false);
  const [volumeAnomalyError, setVolumeAnomalyError] = useState('');
  const [rangeChoice, setPriceRange]  = useState<RangeId>('1M');
  const [loading,     setLoading]     = useState(true);
  const [loadingData, setLoadingData] = useState(false);
  const [error,       setError]       = useState('');
  // NEPSE indices: when one is selected it replaces the company view.
  const [mainIndices, setMainIndices] = useState<IndexRow[]>([]);
  const [subIndices,  setSubIndices]  = useState<IndexRow[]>([]);
  const [selectedIndex, setSelectedIndex] = useState<string | null>(null);
  const [indexHistory,  setIndexHistory]  = useState<IndexHistory | null>(null);

  // Load the index list once (the 4 main indices and the 13 sub-indices).
  useEffect(() => {
    Promise.allSettled([getIndices(), getSubIndices()]).then(([mainRes, subRes]) => {
      if (mainRes.status === 'fulfilled') setMainIndices(mainRes.value.rows);
      if (subRes.status  === 'fulfilled') setSubIndices(subRes.value.rows);
    });
  }, []);

  // Load company list once
  useEffect(() => {
    getCompanies({ status: 'active' })
      .then(r => {
        setCompanies(r.results);
        const requested = r.results.find(c => c.symbol.toUpperCase() === requestedSymbol);
        setSelectedId((requested ?? r.results[0])?.id ?? null);
      })
      .catch(() => setError('Unable to load companies.'))
      .finally(() => setLoading(false));
  }, [requestedSymbol]);

  // Load extended historical prices once per company; the selected range is filtered from this history.
  const loadData = useCallback(() => {
    if (selectedIndex) {
      setLoadingData(true);
      setError('');
      setIndexHistory(null);
      getIndexHistory(selectedIndex)
        .then(setIndexHistory)
        .catch(() => setError('Unable to load index data. Check your permissions.'))
        .finally(() => setLoadingData(false));
      return;
    }
    if (!selectedId) return;
    setVolumeAnomalyRefresh(value => value + 1);
    setLoadingData(true);
    setError('');
    setPrices([]);
    setCategorizedNews(null);
    Promise.allSettled([
      analysisApi.getPrices(selectedId, 'all', { source: 'crawled' }),
      analysisApi.getBehavior(selectedId),
      analysisApi.getCategorizedCompanyNews(selectedId),
    ]).then(([prRes, bhRes, newsRes]) => {
      if (prRes.status   === 'fulfilled') setPrices(prRes.value.prices);
      if (bhRes.status   === 'fulfilled') setBehavior(bhRes.value);
      if (newsRes.status === 'fulfilled') setCategorizedNews(newsRes.value.results);
      // surface any hard errors
      const failed = [prRes, bhRes, newsRes].filter(r => r.status === 'rejected');
      if (failed.length === 3) setError('Unable to load company data. Check your permissions.');
    }).finally(() => setLoadingData(false));
  }, [selectedId, selectedIndex]);

  useEffect(() => { loadData(); }, [loadData]);

  // ── Derived values ──────────────────────────────────────────────────────────
  // No company while an index is shown, so the company-only requests below do not run.
  const company  = selectedIndex ? undefined : companies.find(c => c.id === selectedId);
  const week52 = indexHistory?.fifty_two_week;
  const latestIndex = indexHistory?.latest;
  const indexPriceLines = useMemo(() => [
    { label: `52W H ${fmtPoints(week52?.high)}`, value: week52?.high != null ? Number(week52.high) : null },
    { label: `52W L ${fmtPoints(week52?.low)}`,  value: week52?.low  != null ? Number(week52.low)  : null },
  ], [week52]);
  const indexChangeNote = `${fmtPoints(latestIndex?.change, true)} (${fmtPoints(latestIndex?.change_pct, true)}%)`
    .replace('(—%)', '(—)');
  const indexUp = latestIndex?.change_pct != null ? Number(latestIndex.change_pct) >= 0 : null;
  // Ranges count back from the latest crawled session, not from today, so a pause in crawling
  // never empties the view. A range the data cannot fill falls back to all available data.
  const priceDates = useMemo(() => [...new Set(prices.map(p => p.date))].sort(), [prices]);
  const priceRange: RangeId = rangeAvailable(priceDates, rangeChoice) ? rangeChoice : 'All';
  const rangeFrom = rangeStart(priceDates, priceRange);
  const chartPrices = useMemo(() => filterRange(prices, rangeFrom), [prices, rangeFrom]);
  const fetchMinuteBars = useCallback(
    (days: number) => selectedId ? analysisApi.getIntradayBars(selectedId, days) : Promise.resolve([]),
    [selectedId],
  );
  const vwap30   = useMemo(() => computeVwap(chartPrices), [chartPrices]);
  const anomalyDates = useMemo(
    () => volumeAnomalies.filter(v => v.is_anomaly).map(v => v.date),
    [volumeAnomalies],
  );

  useEffect(() => {
    if (!company) return;
    let cancelled = false;
    const startDate = rangeStart(priceDates, rangeAvailable(priceDates, '6M') ? '6M' : 'All');
    if (!startDate) return;
    setVolumeAnomalies([]);
    setLoadingVolumeAnomalies(true);
    setVolumeAnomalyError('');
    analysisApi.getVolumeAnomalies(company.symbol, { start_date: startDate, lookback: 20 })
      .then((result) => { if (!cancelled) setVolumeAnomalies(result); })
      .catch(() => { if (!cancelled) setVolumeAnomalyError('Unable to load volume anomaly history.'); })
      .finally(() => { if (!cancelled) setLoadingVolumeAnomalies(false); });
    return () => { cancelled = true; };
  }, [company, volumeAnomalyRefresh, priceDates]);

  useEffect(() => {
    if (!company) return;
    let cancelled = false;
    const startDate = rangeFrom;
    if (!startDate) return;
    setLoadingNewsForward(true);
    setNewsForwardError('');
    analysisApi.getNewsSentimentForward(company.symbol, { start_date: startDate })
      .then((result) => { if (!cancelled) setNewsForward(result); })
      .catch(() => { if (!cancelled) setNewsForwardError('Unable to load news sentiment correlation.'); })
      .finally(() => { if (!cancelled) setLoadingNewsForward(false); });
    return () => { cancelled = true; };
  }, [company, rangeFrom]);

  const latestClose = chartPrices.length ? parseFloat(chartPrices[chartPrices.length - 1].close) : 0;
  const firstClose  = chartPrices.length ? parseFloat(chartPrices[0].close) : 0;
  const positive    = latestClose >= firstClose;
  const spreadPct   = vwap30 ? ((latestClose - vwap30) / vwap30 * 100) : 0;

  // ── Render ──────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 size={28} className="animate-spin text-accent" />
      </div>
    );
  }

  return (
    <div className="trading-terminal-page space-y-6">

      {/* ── Page header ──────────────────────────────────────────────────── */}
      <PageHeader
        title="Technical Charts"
        subtitle="Price / volume trends, VWAP, broker activity, and categorized company news."
        actions={
          <button
            onClick={loadData}
            disabled={loadingData}
            className="btn-ghost flex items-center gap-2 text-xs"
          >
            <RefreshCw size={13} className={loadingData ? 'animate-spin' : ''} />
            Refresh
          </button>
        }
      />

      {error && (
        <div className="flex items-center gap-2 text-sm text-down">
          <AlertTriangle size={14} /> {error}
        </div>
      )}

      {/* ── Chart selector: indices first, then companies ──────────────────── */}
      <div className="space-y-2">
        {[
          { label: 'Indices', rows: mainIndices },
          { label: 'Sub-indices', rows: subIndices },
        ].filter(group => group.rows.length > 0).map(group => (
          <div key={group.label} className="flex flex-wrap items-center gap-2">
            <span className="w-24 shrink-0 text-[10px] uppercase tracking-widest text-text-muted">{group.label}</span>
            {group.rows.map(row => (
              <button
                key={row.code}
                onClick={() => setSelectedIndex(row.code)}
                className={clsx(
                  'px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
                  row.code === selectedIndex
                    ? 'bg-accent text-white shadow-md'
                    : 'bg-bg-elevated text-text-secondary hover:text-text-primary hover:bg-blue-500/10',
                )}
              >
                {row.name}
              </button>
            ))}
          </div>
        ))}
        <div className="flex flex-wrap items-center gap-2">
          {(mainIndices.length > 0 || subIndices.length > 0) && (
            <span className="w-24 shrink-0 text-[10px] uppercase tracking-widest text-text-muted">Companies</span>
          )}
          {companies.map(c => (
            <button
              key={c.id}
              onClick={() => { setSelectedIndex(null); setSelectedId(c.id); }}
              className={clsx(
                'px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all',
                !selectedIndex && c.id === selectedId
                  ? 'bg-accent text-white shadow-md'
                  : 'bg-bg-elevated text-text-secondary hover:text-text-primary hover:bg-blue-500/10',
              )}
            >
              {c.symbol}
            </button>
          ))}
        </div>
      </div>

      {/* ── Index header card + chart (replaces the company view) ────────── */}
      {selectedIndex && indexHistory && (
        <>
          <div className="card flex flex-wrap items-center gap-6 py-4">
            <div>
              <p className="font-semibold text-text-primary text-base">{indexHistory.name}</p>
              <p className="text-xs text-text-muted">
                NEPSE official daily data{latestIndex ? ` · as of ${latestIndex.date}` : ''}
              </p>
            </div>
            <div className="flex flex-wrap gap-5 ml-auto">
              <StatPill
                label="Latest close"
                value={fmtPoints(latestIndex?.close)}
                color={indexUp === null ? 'text-text-primary' : indexUp ? 'text-up' : 'text-down'}
              />
              <StatPill
                label="Change"
                value={indexChangeNote}
                color={indexUp === null ? 'text-text-secondary' : indexUp ? 'text-up' : 'text-down'}
                sub={latestIndex?.previous_date ? `vs ${latestIndex.previous_date}` : undefined}
              />
              <StatPill label="52W high" value={fmtPoints(week52?.high)} sub={week52?.high_date ?? undefined} />
              <StatPill label="52W low"  value={fmtPoints(week52?.low)}  sub={week52?.low_date ?? undefined} />
            </div>
          </div>

          {indexHistory.prices.length === 0 ? (
            <div className="card py-16 text-center">
              <p className="text-sm text-text-muted">No stored data for this index yet.</p>
            </div>
          ) : (
            <div className="card space-y-2">
              <SectionTitle icon={TrendingUp}>Price Action</SectionTitle>
              <div className="h-[720px]">
                <KlinePriceChart
                  prices={indexHistory.prices}
                  symbol={indexHistory.name}
                  indexCode={selectedIndex}
                  priceLines={indexPriceLines}
                  lastPriceNote={indexChangeNote}
                />
              </div>
            </div>
          )}
        </>
      )}

      {/* ── Company header card ───────────────────────────────────────────── */}
      {company && (
        <div className="card flex flex-wrap items-center gap-6 py-4">
          <div className="flex items-center gap-3">
            <CompanyLogo symbol={company.symbol} name={company.name} logoUrl={company.logo_url} size="md" />
            <div>
              <p className="font-semibold text-text-primary text-base">{company.symbol}</p>
              <p className="text-xs text-text-muted">{company.name}</p>
            </div>
          </div>

          <Badge variant="gray">{company.sector}</Badge>

          <div className="flex flex-wrap gap-5 ml-auto">
            <StatPill
              label="Latest close"
              value={`Rs. ${latestClose.toFixed(2)}`}
              color={positive ? 'text-up' : 'text-down'}
            />
            <StatPill
              label={`${priceRange} change`}
              value={`${positive ? '+' : ''}${firstClose ? ((latestClose - firstClose) / firstClose * 100).toFixed(2) : 0}%`}
              color={positive ? 'text-up' : 'text-down'}
            />
            <StatPill
              label={`VWAP ${priceRange}`}
              value={`Rs. ${vwap30.toFixed(2)}`}
              color="text-yellow-400"
            />
            <StatPill
              label="vs VWAP"
              value={`${spreadPct >= 0 ? '+' : ''}${spreadPct.toFixed(2)}%`}
              color={spreadPct >= 0 ? 'text-up' : 'text-down'}
              sub={spreadPct >= 0 ? 'Above VWAP' : 'Below VWAP'}
            />
          </div>
        </div>
      )}

      {loadingData && (
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <Loader2 size={12} className="animate-spin" /> Loading data…
        </div>
      )}

      {!selectedIndex && (<>
      {/* ── Range selector ───────────────────────────────────────────────── */}
      <div className="flex items-center gap-1 bg-bg-elevated rounded-lg p-0.5 w-fit">
        {(['5D', '1M', '3M', 'All'] as const).map(r => {
          const available = rangeAvailable(priceDates, r);
          return (
            <button
              key={r}
              disabled={!available}
              title={available ? RANGE_TITLES[r] : unavailableReason(priceDates, r)}
              onClick={() => setPriceRange(r)}
              className={clsx(
                'px-4 py-1.5 rounded text-xs font-medium transition-all disabled:cursor-not-allowed disabled:opacity-35',
                priceRange === r
                  ? 'bg-accent text-white'
                  : 'text-text-secondary enabled:hover:text-text-primary',
              )}
            >
              {r}
            </button>
          );
        })}
      </div>

      {prices.length === 0 && !loadingData ? (
        <div className="card py-16 text-center">
          <p className="text-sm text-text-muted">No price data available for this company.</p>
        </div>
      ) : (
        <>
          {/* TradingView-style price and volume chart */}
          <div className="card space-y-2">
            <SectionTitle icon={TrendingUp}>Price Action</SectionTitle>
            <div className="h-[720px]">
              <KlinePriceChart
                prices={prices}
                symbol={company?.symbol ?? ''}
                anomalyDates={anomalyDates}
                fetchMinuteBars={selectedId ? fetchMinuteBars : undefined}
                companyId={selectedId ?? undefined}
              />
            </div>
          </div>

          <VolumeAnomalyChart data={volumeAnomalies} loading={loadingVolumeAnomalies} error={volumeAnomalyError} />
          <NewsSentimentScatter data={newsForward} priceData={chartPrices} loading={loadingNewsForward} error={newsForwardError} />

          {/* ── Row 3: Behavior AI summary ───────────────────────────────── */}
          {behavior && (
            <div className="card">
              <SectionTitle icon={Activity}>Behavior Analysis Summary</SectionTitle>
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3 mb-4">
                <div className="bg-bg-elevated rounded-lg p-3">
                  <p className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Pressure</p>
                  <p className={clsx('text-sm font-semibold capitalize',
                    behavior.pressure === 'buying' ? 'text-up'
                    : behavior.pressure === 'selling' ? 'text-down'
                    : 'text-text-secondary')}>
                    {behavior.pressure === 'buying' ? '▲ ' : behavior.pressure === 'selling' ? '▼ ' : '— '}
                    {behavior.pressure}
                  </p>
                </div>
                <div className="bg-bg-elevated rounded-lg p-3">
                  <p className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Volume Anomaly</p>
                  <p className={clsx('text-sm font-semibold', behavior.volume_anomaly ? 'text-down' : 'text-up')}>
                    {behavior.volume_anomaly ? `⚡ Yes (${behavior.volume_ratio !== null ? Number(behavior.volume_ratio).toFixed(2) : '?'}×)` : '✓ Normal'}
                  </p>
                </div>
                <div className="bg-bg-elevated rounded-lg p-3">
                  <p className="text-[10px] text-text-muted uppercase tracking-wider mb-1">News Sentiment</p>
                  <p className={clsx('text-sm font-semibold',
                    behavior.news_sentiment_score > 0.1 ? 'text-up'
                    : behavior.news_sentiment_score < -0.1 ? 'text-down'
                    : 'text-text-secondary')}>
                    {behavior.news_sentiment_score.toFixed(3)} ({behavior.news_count_30d} articles)
                  </p>
                </div>
                <div className="bg-bg-elevated rounded-lg p-3">
                  <p className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Spread vs VWAP</p>
                  <p className={clsx('text-sm font-semibold',
                    behavior.price_to_vwap_spread_pct === null ? 'text-text-secondary'
                    : behavior.price_to_vwap_spread_pct >= 0 ? 'text-up' : 'text-down')}>
                    {behavior.price_to_vwap_spread_pct !== null
                      ? `${behavior.price_to_vwap_spread_pct >= 0 ? '+' : ''}${behavior.price_to_vwap_spread_pct.toFixed(2)}%`
                      : '—'}
                  </p>
                </div>
              </div>
              <p className="text-sm text-text-secondary leading-relaxed border-l-2 border-accent-dim pl-3">
                {behavior.summary_text}
              </p>
            </div>
          )}

          {/* Categorized articles tagged to the selected company */}
          <div className="card">
            <div className="mb-3 flex items-center justify-between gap-3">
              <SectionTitle icon={Newspaper}>{company?.symbol ?? 'Company'} News</SectionTitle>
              <span className="text-[10px] text-text-muted">{categorizedNews?.length ?? 0} categorized articles</span>
            </div>
            {categorizedNews === null ? (
              <p className="py-4 text-center text-xs text-text-muted">
                {loadingData ? 'Loading categorized company news…' : 'Unable to load categorized news.'}
              </p>
            ) : categorizedNews.length === 0 ? (
              <p className="py-4 text-center text-xs text-text-muted">
                No categorized news is linked to this company yet.
              </p>
            ) : (
              <div className="divide-y divide-bg-border">
                {categorizedNews.map(article => (
                  <article key={article.id} className="flex flex-wrap items-start justify-between gap-3 py-3 first:pt-0 last:pb-0">
                    <div className="min-w-0 flex-1">
                      <a href={article.url} target="_blank" rel="noreferrer" className="text-sm font-medium text-text-primary hover:text-accent-light">
                        {article.headline}
                      </a>
                      <p className="mt-1 text-[10px] text-text-muted">
                        {article.source}{article.published_at ? ` · ${new Date(article.published_at).toLocaleString()}` : ''}
                        {' · '}Company match {Math.round(article.confidence * 100)}%{article.is_manual ? ' · Manually categorized' : ''}
                      </p>
                    </div>
                    <span className={clsx(
                      'rounded px-2 py-1 text-[10px] uppercase',
                      article.sentiment_label === 'positive' ? 'bg-up/10 text-up'
                        : article.sentiment_label === 'negative' ? 'bg-down/10 text-down'
                        : 'bg-bg-elevated text-text-muted',
                    )}>
                      {article.sentiment_label || 'Sentiment unavailable'}
                    </span>
                  </article>
                ))}
              </div>
            )}
          </div>
        </>
      )}
      </>)}
    </div>
  );
}
