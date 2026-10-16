import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Building2,
  CheckCircle2,
  Eye,
  Layers,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  X,
} from 'lucide-react';

import apiClient from '../../api/client';
import { useAuth } from '../../contexts/AuthContext';
import CompanyLogo from '../../components/companies/CompanyLogo';
import Sparkline from '../../components/common/Sparkline';
import type { Company } from '../../types/company';

interface CompanyForm {
  symbol: string;
  name: string;
  sector: string;
  is_active: boolean;
  is_tracked: boolean;
}

const emptyForm: CompanyForm = {
  symbol: '',
  name: '',
  sector: '',
  is_active: true,
  is_tracked: true,
};

type StatusFilter = 'all' | 'active' | 'inactive';
type TrackedFilter = 'all' | 'tracked' | 'not_tracked';
type SortKey = 'symbol' | 'sector' | 'price' | 'change' | 'volume';
type SortDir = 'asc' | 'desc';

const priceFormat = new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const compactFormat = new Intl.NumberFormat('en-IN', { notation: 'compact', maximumFractionDigits: 1 });

function apiErrorMessage(err: any, fallback: string): string {
  const data = err?.response?.data;
  if (typeof data?.detail === 'string') return data.detail;
  if (typeof data === 'object' && data !== null) {
    const first = Object.values(data)[0];
    return String(Array.isArray(first) ? first[0] : first);
  }
  return fallback;
}

// Value a column sorts by; null means "no data" and always sorts last.
function sortValue(company: Company, key: SortKey): string | number | null {
  switch (key) {
    case 'symbol': return company.symbol;
    case 'sector': return company.sector || null;
    case 'price': return company.latest_price;
    case 'change': return company.price_change_percent;
    case 'volume': return company.volume_24h;
  }
}

// =====================================================
// SMALL BUILDING BLOCKS
// =====================================================

function StatCard({ icon, label, value, hint }: { icon: React.ReactNode; label: string; value: number | string; hint?: string }) {
  return (
    <div className="card flex items-center gap-3">
      <div className="rounded-md bg-accent/10 p-2 text-accent-light">{icon}</div>
      <div className="min-w-0">
        <div className="text-xs text-text-secondary">{label}</div>
        <div className="font-mono text-lg font-semibold text-text-primary">{value}</div>
        {hint && <div className="truncate text-[11px] text-text-muted">{hint}</div>}
      </div>
    </div>
  );
}

function Segmented<T extends string>({ value, options, onChange, label }: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-md border border-bg-border bg-bg-elevated p-0.5">
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(option.value)}
            className={`whitespace-nowrap rounded px-3 py-1.5 text-xs font-medium transition-colors ${
              selected ? 'bg-accent/20 text-accent-light' : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

function Switch({ checked, onChange, disabled, label }: {
  checked: boolean;
  onChange?: () => void;
  disabled?: boolean;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={(event) => {
        event.stopPropagation();
        onChange?.();
      }}
      className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
        checked ? 'bg-accent' : 'bg-bg-border'
      }`}
    >
      <span
        className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${
          checked ? 'translate-x-[18px]' : 'translate-x-0.5'
        }`}
      />
    </button>
  );
}

function SortHeader({ label, sortKey, sort, onSort, align = 'left', className = '' }: {
  label: string;
  sortKey: SortKey;
  sort: { key: SortKey; dir: SortDir };
  onSort: (key: SortKey) => void;
  align?: 'left' | 'right';
  className?: string;
}) {
  const active = sort.key === sortKey;
  const Icon = !active ? ArrowUpDown : sort.dir === 'asc' ? ArrowUp : ArrowDown;
  return (
    <th
      className={`px-4 py-3 text-xs font-semibold uppercase tracking-wide text-text-muted ${align === 'right' ? 'text-right' : ''} ${className}`}
      aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
    >
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className={`inline-flex items-center gap-1 uppercase transition-colors hover:text-text-primary ${active ? 'text-text-primary' : ''}`}
      >
        {label}
        <Icon size={12} className={active ? '' : 'opacity-40'} />
      </button>
    </th>
  );
}

function ChangePill({ value }: { value: number | null }) {
  if (value === null) return <span className="text-xs text-text-muted">—</span>;
  const tone = value > 0 ? 'bg-up/10 text-up' : value < 0 ? 'bg-down/10 text-down' : 'bg-bg-elevated text-text-secondary';
  return (
    <span className={`inline-flex min-w-[68px] justify-end rounded px-2 py-0.5 font-mono text-xs font-medium ${tone}`}>
      {value > 0 ? '+' : ''}{value.toFixed(2)}%
    </span>
  );
}

function SkeletonRows({ rows = 8 }: { rows?: number }) {
  return (
    <>
      {Array.from({ length: rows }, (_, index) => (
        <tr key={index} className="border-b border-bg-border">
          <td className="px-4 py-3">
            <div className="flex items-center gap-3">
              <div className="skeleton h-8 w-8" />
              <div className="space-y-1.5">
                <div className="skeleton h-3 w-16" />
                <div className="skeleton h-3 w-40" />
              </div>
            </div>
          </td>
          <td className="hidden px-4 py-3 lg:table-cell"><div className="skeleton h-5 w-28" /></td>
          <td className="px-4 py-3"><div className="skeleton ml-auto h-3 w-16" /></td>
          <td className="px-4 py-3"><div className="skeleton ml-auto h-5 w-16" /></td>
          <td className="hidden px-4 py-3 md:table-cell"><div className="skeleton h-6 w-20" /></td>
          <td className="hidden px-4 py-3 md:table-cell"><div className="skeleton ml-auto h-3 w-12" /></td>
          <td className="px-4 py-3"><div className="skeleton h-5 w-9" /></td>
          <td className="px-4 py-3"><div className="skeleton h-5 w-9" /></td>
          <td className="px-4 py-3"><div className="skeleton ml-auto h-7 w-16" /></td>
        </tr>
      ))}
    </>
  );
}

const fieldClass =
  'w-full rounded-md border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/20';

// =====================================================
// PAGE
// =====================================================

export default function CompaniesPage({ trackedOnly = false }: { trackedOnly?: boolean }) {
  const { hasPermission } = useAuth();
  const navigate = useNavigate();

  // Derive every capability from the live permission list
  const canCreate = hasPermission('create_companies');
  const canEdit = hasPermission('edit_companies');
  const canDelete = hasPermission('delete_companies');
  const canTrack = hasPermission('manage_tracked_companies'); // toggle tracking
  const canToggleActive = canEdit; // editing company status needs edit_companies

  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pendingIds, setPendingIds] = useState<Set<number>>(new Set());

  const [search, setSearch] = useState('');
  const [sectorFilter, setSectorFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [trackedFilter, setTrackedFilter] = useState<TrackedFilter>('all');
  const [sort, setSort] = useState<{ key: SortKey; dir: SortDir }>({ key: 'symbol', dir: 'asc' });

  const [showModal, setShowModal] = useState(false);
  const [editingCompany, setEditingCompany] = useState<Company | null>(null);
  const [form, setForm] = useState<CompanyForm>(emptyForm);
  const [formError, setFormError] = useState('');
  const [confirmDelete, setConfirmDelete] = useState<Company | null>(null);
  const [deleting, setDeleting] = useState(false);

  const [error, setError] = useState('');
  const [toast, setToast] = useState('');

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(''), 2500);
    return () => clearTimeout(timer);
  }, [toast]);

  // =====================================================
  // LOAD COMPANIES (every page — the API pages by 20)
  // =====================================================
  const loadCompanies = useCallback(async () => {
    try {
      setLoading(true);
      setError('');

      const all: Company[] = [];
      for (let page = 1; ; page += 1) {
        const response = await apiClient.get('/companies/', {
          params: { page, ...(trackedOnly ? { tracked_only: true } : {}) },
        });
        const data = response.data;
        if (Array.isArray(data)) {
          all.push(...data);
          break;
        }
        all.push(...(Array.isArray(data?.results) ? data.results : []));
        if (!data?.next) break;
      }
      setCompanies(all);
    } catch (err: any) {
      console.error('Failed to load companies:', err);
      setError(apiErrorMessage(err, 'Failed to load companies.'));
    } finally {
      setLoading(false);
    }
  }, [trackedOnly]);

  useEffect(() => {
    loadCompanies();
  }, [loadCompanies]);

  // =====================================================
  // DERIVED DATA
  // =====================================================
  const sectors = useMemo(
    () => Array.from(new Set(companies.map((company) => company.sector).filter(Boolean))).sort(),
    [companies]
  );

  const stats = useMemo(() => {
    const priceDates = companies
      .map((company) => company.latest_price_date)
      .filter((date): date is string => Boolean(date))
      .sort();
    return {
      total: companies.length,
      active: companies.filter((company) => company.is_active).length,
      tracked: companies.filter((company) => company.is_tracked).length,
      sectors: sectors.length,
      asOf: priceDates[priceDates.length - 1] ?? null,
    };
  }, [companies, sectors]);

  const filtersActive =
    search.trim() !== '' || sectorFilter !== 'all' || statusFilter !== 'all' || trackedFilter !== 'all';

  const clearFilters = () => {
    setSearch('');
    setSectorFilter('all');
    setStatusFilter('all');
    setTrackedFilter('all');
  };

  const visibleCompanies = useMemo(() => {
    const searchValue = search.toLowerCase().trim();

    const filtered = companies.filter((company) => {
      const matchesSearch =
        !searchValue ||
        company.symbol?.toLowerCase().includes(searchValue) ||
        company.name?.toLowerCase().includes(searchValue);
      const matchesSector = sectorFilter === 'all' || company.sector === sectorFilter;
      const matchesStatus =
        statusFilter === 'all' ||
        (statusFilter === 'active' && company.is_active) ||
        (statusFilter === 'inactive' && !company.is_active);
      const isTracked = company.is_tracked ?? false;
      const matchesTracked =
        trackedFilter === 'all' ||
        (trackedFilter === 'tracked' && isTracked) ||
        (trackedFilter === 'not_tracked' && !isTracked);
      return matchesSearch && matchesSector && matchesStatus && matchesTracked;
    });

    const direction = sort.dir === 'asc' ? 1 : -1;
    return filtered.sort((a, b) => {
      const left = sortValue(a, sort.key);
      const right = sortValue(b, sort.key);
      if (left === null && right === null) return a.symbol.localeCompare(b.symbol);
      if (left === null) return 1;
      if (right === null) return -1;
      const result =
        typeof left === 'number' && typeof right === 'number'
          ? left - right
          : String(left).localeCompare(String(right));
      return result * direction || a.symbol.localeCompare(b.symbol);
    });
  }, [companies, search, sectorFilter, statusFilter, trackedFilter, sort]);

  const onSort = (key: SortKey) =>
    setSort((current) =>
      current.key === key
        ? { key, dir: current.dir === 'asc' ? 'desc' : 'asc' }
        : // Text columns start A→Z; numbers start with the largest.
          { key, dir: key === 'symbol' || key === 'sector' ? 'asc' : 'desc' }
    );

  // =====================================================
  // MODAL
  // =====================================================
  const openAddModal = () => {
    setEditingCompany(null);
    setForm(emptyForm);
    setFormError('');
    setShowModal(true);
  };

  const openEditModal = (company: Company) => {
    setEditingCompany(company);
    setForm({
      symbol: company.symbol || '',
      name: company.name || '',
      sector: company.sector || '',
      is_active: company.is_active,
      is_tracked: company.is_tracked ?? false,
    });
    setFormError('');
    setShowModal(true);
  };

  const closeModal = useCallback(() => {
    if (saving) return;
    setShowModal(false);
    setEditingCompany(null);
    setForm(emptyForm);
    setFormError('');
  }, [saving]);

  // Escape closes whichever dialog is open.
  useEffect(() => {
    if (!showModal && !confirmDelete) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      if (confirmDelete && !deleting) setConfirmDelete(null);
      else if (showModal) closeModal();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [showModal, confirmDelete, deleting, closeModal]);

  // =====================================================
  // SAVE COMPANY
  // =====================================================
  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!form.symbol.trim()) {
      setFormError('Company symbol is required.');
      return;
    }
    if (!form.name.trim()) {
      setFormError('Company name is required.');
      return;
    }

    try {
      setSaving(true);
      setFormError('');

      const payload = {
        symbol: form.symbol.trim().toUpperCase(),
        name: form.name.trim(),
        sector: form.sector.trim(),
        is_active: form.is_active,
        is_tracked: form.is_tracked,
      };

      if (editingCompany) {
        await apiClient.patch(`/companies/${editingCompany.id}/`, payload);
        setToast(`${payload.symbol} updated.`);
      } else {
        await apiClient.post('/companies/', payload);
        setToast(`${payload.symbol} added.`);
      }

      setShowModal(false);
      setEditingCompany(null);
      setForm(emptyForm);
      await loadCompanies();
    } catch (err: any) {
      console.error('Failed to save company:', err);
      setFormError(apiErrorMessage(err, 'Failed to save company.'));
    } finally {
      setSaving(false);
    }
  };

  // =====================================================
  // INLINE TOGGLES (optimistic, one request per row at a time)
  // =====================================================
  const patchCompany = async (company: Company, changes: Partial<Company>, failure: string) => {
    if (pendingIds.has(company.id)) return;
    setPendingIds((current) => new Set(current).add(company.id));
    setError('');
    setCompanies((current) => current.map((item) => (item.id === company.id ? { ...item, ...changes } : item)));
    try {
      await apiClient.patch(`/companies/${company.id}/`, changes);
    } catch (err: any) {
      console.error(failure, err);
      // Roll back the optimistic change.
      setCompanies((current) => current.map((item) => (item.id === company.id ? company : item)));
      setError(apiErrorMessage(err, failure));
    } finally {
      setPendingIds((current) => {
        const next = new Set(current);
        next.delete(company.id);
        return next;
      });
    }
  };

  const toggleTracking = (company: Company) =>
    patchCompany(company, { is_tracked: !(company.is_tracked ?? false) }, 'Failed to update tracking status.');

  const toggleActive = (company: Company) =>
    patchCompany(company, { is_active: !company.is_active }, 'Failed to update company status.');

  // =====================================================
  // DELETE COMPANY
  // =====================================================
  const deleteCompany = async () => {
    if (!confirmDelete) return;
    const company = confirmDelete;
    try {
      setDeleting(true);
      setError('');
      await apiClient.delete(`/companies/${company.id}/`);
      setCompanies((current) => current.filter((item) => item.id !== company.id));
      setToast(`${company.symbol} deleted.`);
      setConfirmDelete(null);
    } catch (err: any) {
      console.error('Failed to delete company:', err);
      setError(apiErrorMessage(err, 'Failed to delete company.'));
      setConfirmDelete(null);
    } finally {
      setDeleting(false);
    }
  };

  const hasActions = canEdit || canDelete;

  return (
    <div className="space-y-5">
      {/* HEADER */}
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">{trackedOnly ? 'Watchlist' : 'Companies'}</h1>
          <p className="mt-1 text-sm text-text-secondary">
            {trackedOnly
              ? 'Tracked companies used by the crawlers.'
              : 'Company directory, latest prices and crawler tracking.'}
          </p>
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={loadCompanies}
            disabled={loading}
            className="btn-ghost inline-flex items-center gap-2 border border-bg-border disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
          {canCreate && (
            <button type="button" onClick={openAddModal} className="btn-primary inline-flex items-center gap-2">
              <Plus size={16} />
              Add company
            </button>
          )}
        </div>
      </div>

      {/* SUMMARY */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard icon={<Building2 size={18} />} label="Companies" value={loading ? '—' : stats.total} />
        <StatCard icon={<CheckCircle2 size={18} />} label="Active" value={loading ? '—' : stats.active} />
        <StatCard
          icon={<Eye size={18} />}
          label="Tracked by crawlers"
          value={loading ? '—' : stats.tracked}
        />
        <StatCard
          icon={<Layers size={18} />}
          label="Sectors"
          value={loading ? '—' : stats.sectors}
          hint={stats.asOf ? `Prices as of ${stats.asOf}` : undefined}
        />
      </div>

      {/* ERROR */}
      {error && (
        <div role="alert" className="flex items-start justify-between gap-4 rounded-md border border-down/30 bg-down/10 px-4 py-3 text-sm text-down">
          <span>{error}</span>
          <button type="button" onClick={() => setError('')} aria-label="Dismiss error">
            <X size={16} />
          </button>
        </div>
      )}

      {/* TABLE CARD */}
      <div className="card overflow-hidden p-0 hover:!border-bg-border hover:!shadow-none">
        {/* Toolbar */}
        <div className="flex flex-col gap-3 border-b border-bg-border p-4 xl:flex-row xl:items-center">
          <div className="relative xl:w-72">
            <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search symbol or name…"
              aria-label="Search companies"
              className={`${fieldClass} pl-9`}
            />
          </div>

          <select
            value={sectorFilter}
            onChange={(event) => setSectorFilter(event.target.value)}
            aria-label="Filter by sector"
            className={`${fieldClass} xl:w-56`}
          >
            <option value="all">All sectors</option>
            {sectors.map((sector) => (
              <option key={sector} value={sector}>{sector}</option>
            ))}
          </select>

          <div className="flex flex-wrap items-center gap-2">
            <Segmented<StatusFilter>
              label="Status"
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { value: 'all', label: 'All' },
                { value: 'active', label: 'Active' },
                { value: 'inactive', label: 'Inactive' },
              ]}
            />
            {!trackedOnly && (
              <Segmented<TrackedFilter>
                label="Tracking"
                value={trackedFilter}
                onChange={setTrackedFilter}
                options={[
                  { value: 'all', label: 'All' },
                  { value: 'tracked', label: 'Tracked' },
                  { value: 'not_tracked', label: 'Not tracked' },
                ]}
              />
            )}
          </div>

          <div className="flex items-center gap-3 xl:ml-auto">
            <span className="whitespace-nowrap text-xs text-text-muted">
              {loading ? 'Loading…' : `${visibleCompanies.length} of ${companies.length}`}
            </span>
            {filtersActive && (
              <button type="button" onClick={clearFilters} className="whitespace-nowrap text-xs font-medium text-accent-light hover:underline">
                Clear filters
              </button>
            )}
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left">
            <thead className="bg-bg-elevated">
              <tr className="border-b border-bg-border">
                <SortHeader label="Company" sortKey="symbol" sort={sort} onSort={onSort} />
                <SortHeader label="Sector" sortKey="sector" sort={sort} onSort={onSort} className="hidden lg:table-cell" />
                <SortHeader label="LTP" sortKey="price" sort={sort} onSort={onSort} align="right" />
                <SortHeader label="Change" sortKey="change" sort={sort} onSort={onSort} align="right" />
                <th className="hidden px-4 py-3 text-xs font-semibold uppercase tracking-wide text-text-muted md:table-cell">10 days</th>
                <SortHeader label="Volume" sortKey="volume" sort={sort} onSort={onSort} align="right" className="hidden md:table-cell" />
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-text-muted">Active</th>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-text-muted">Tracked</th>
                {hasActions && (
                  <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-text-muted">
                    <span className="sr-only">Actions</span>
                  </th>
                )}
              </tr>
            </thead>

            <tbody>
              {loading && companies.length === 0 ? (
                <SkeletonRows />
              ) : visibleCompanies.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-6 py-16 text-center">
                    <div className="mx-auto mb-3 w-fit rounded-full bg-bg-elevated p-3">
                      <Search size={20} className="text-text-muted" />
                    </div>
                    <h3 className="font-medium text-text-primary">
                      {companies.length === 0 ? 'No companies yet' : 'No companies match these filters'}
                    </h3>
                    <p className="mt-1 text-sm text-text-secondary">
                      {companies.length === 0
                        ? canCreate ? 'Add the first company to start tracking it.' : 'Nothing has been added yet.'
                        : 'Try a different search or clear the filters.'}
                    </p>
                    {filtersActive && (
                      <button type="button" onClick={clearFilters} className="btn-ghost mt-4 border border-bg-border">
                        Clear filters
                      </button>
                    )}
                  </td>
                </tr>
              ) : (
                visibleCompanies.map((company) => {
                  const tracked = company.is_tracked ?? false;
                  const pending = pendingIds.has(company.id);
                  const change = company.price_change_percent;
                  const sparkUp =
                    company.sparkline.length > 1
                      ? company.sparkline[company.sparkline.length - 1] >= company.sparkline[0]
                      : true;

                  return (
                    <tr
                      key={company.id}
                      onClick={() => navigate(`/companies/${company.symbol}`)}
                      className={`table-row cursor-pointer ${company.is_active ? '' : 'opacity-60'}`}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <CompanyLogo symbol={company.symbol} name={company.name} logoUrl={company.logo_url} size="md" />
                          <div className="min-w-0">
                            <Link
                              to={`/companies/${company.symbol}`}
                              onClick={(event) => event.stopPropagation()}
                              className="font-mono text-sm font-semibold text-accent-light hover:underline"
                            >
                              {company.symbol}
                            </Link>
                            <div className="max-w-[260px] truncate text-xs text-text-secondary" title={company.name}>
                              {company.name}
                            </div>
                          </div>
                        </div>
                      </td>

                      <td className="hidden px-4 py-3 lg:table-cell">
                        {company.sector ? (
                          <span className="badge border border-bg-border bg-bg-elevated text-text-secondary">{company.sector}</span>
                        ) : (
                          <span className="text-xs text-text-muted">—</span>
                        )}
                      </td>

                      <td className="px-4 py-3 text-right">
                        {company.latest_price !== null ? (
                          <span className="font-mono text-sm text-text-primary" title={company.latest_price_date ? `Close on ${company.latest_price_date}` : undefined}>
                            {priceFormat.format(company.latest_price)}
                          </span>
                        ) : (
                          <span className="text-xs text-text-muted">No price</span>
                        )}
                      </td>

                      <td className="px-4 py-3 text-right">
                        <ChangePill value={change} />
                      </td>

                      <td className="hidden px-4 py-3 md:table-cell">
                        {company.sparkline.length > 1 ? (
                          <Sparkline data={company.sparkline} width={84} height={26} positive={sparkUp} />
                        ) : (
                          <span className="text-xs text-text-muted">—</span>
                        )}
                      </td>

                      <td className="hidden px-4 py-3 text-right md:table-cell">
                        <span className="font-mono text-sm text-text-secondary">
                          {company.volume_24h !== null ? compactFormat.format(company.volume_24h) : '—'}
                        </span>
                      </td>

                      <td className="px-4 py-3">
                        <Switch
                          checked={company.is_active}
                          onChange={canToggleActive ? () => toggleActive(company) : undefined}
                          disabled={!canToggleActive || pending}
                          label={`${company.symbol} is ${company.is_active ? 'active' : 'inactive'}`}
                        />
                      </td>

                      <td className="px-4 py-3">
                        <Switch
                          checked={tracked}
                          onChange={canTrack ? () => toggleTracking(company) : undefined}
                          disabled={!canTrack || pending}
                          label={`${company.symbol} is ${tracked ? 'tracked' : 'not tracked'}`}
                        />
                      </td>

                      {hasActions && (
                        <td className="px-4 py-3">
                          <div className="flex justify-end gap-1">
                            {canEdit && (
                              <button
                                type="button"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  openEditModal(company);
                                }}
                                className="rounded-md p-2 text-text-muted transition hover:bg-blue-500/10 hover:text-text-primary"
                                title={`Edit ${company.symbol}`}
                                aria-label={`Edit ${company.symbol}`}
                              >
                                <Pencil size={15} />
                              </button>
                            )}
                            {canDelete && (
                              <button
                                type="button"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  setConfirmDelete(company);
                                }}
                                className="rounded-md p-2 text-text-muted transition hover:bg-down/10 hover:text-down"
                                title={`Delete ${company.symbol}`}
                                aria-label={`Delete ${company.symbol}`}
                              >
                                <Trash2 size={15} />
                              </button>
                            )}
                          </div>
                        </td>
                      )}
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ADD / EDIT MODAL — only rendered for users with create or edit permission */}
      {showModal && (canCreate || canEdit) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={closeModal}>
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="company-modal-title"
            onClick={(event) => event.stopPropagation()}
            className="w-full max-w-lg rounded-lg border border-bg-border bg-bg-secondary shadow-xl"
          >
            <div className="flex items-center justify-between border-b border-bg-border px-5 py-4">
              <div className="flex items-center gap-3">
                {editingCompany && (
                  <CompanyLogo symbol={editingCompany.symbol} name={editingCompany.name} logoUrl={editingCompany.logo_url} size="md" />
                )}
                <div>
                  <h2 id="company-modal-title" className="font-semibold text-text-primary">
                    {editingCompany ? `Edit ${editingCompany.symbol}` : 'Add company'}
                  </h2>
                  <p className="mt-0.5 text-xs text-text-secondary">
                    {editingCompany ? 'Update company details and status.' : 'Add a company to the directory.'}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={closeModal}
                aria-label="Close"
                className="rounded-md p-2 text-text-muted hover:bg-blue-500/10 hover:text-text-primary"
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4 p-5">
              {formError && (
                <div role="alert" className="rounded-md border border-down/30 bg-down/10 px-3 py-2 text-sm text-down">
                  {formError}
                </div>
              )}

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div>
                  <label htmlFor="company-symbol" className="mb-1.5 block text-sm font-medium text-text-secondary">Symbol</label>
                  <input
                    id="company-symbol"
                    type="text"
                    autoFocus
                    value={form.symbol}
                    onChange={(event) => setForm({ ...form, symbol: event.target.value })}
                    placeholder="NABIL"
                    className={`${fieldClass} font-mono uppercase`}
                  />
                </div>
                <div className="sm:col-span-2">
                  <label htmlFor="company-name" className="mb-1.5 block text-sm font-medium text-text-secondary">Company name</label>
                  <input
                    id="company-name"
                    type="text"
                    value={form.name}
                    onChange={(event) => setForm({ ...form, name: event.target.value })}
                    placeholder="Nabil Bank Limited"
                    className={fieldClass}
                  />
                </div>
              </div>

              <div>
                <label htmlFor="company-sector" className="mb-1.5 block text-sm font-medium text-text-secondary">Sector</label>
                <input
                  id="company-sector"
                  type="text"
                  list="company-sector-options"
                  value={form.sector}
                  onChange={(event) => setForm({ ...form, sector: event.target.value })}
                  placeholder="Commercial Banks"
                  className={fieldClass}
                />
                {/* Suggest existing sectors so the same sector isn't spelled two ways. */}
                <datalist id="company-sector-options">
                  {sectors.map((sector) => (
                    <option key={sector} value={sector} />
                  ))}
                </datalist>
              </div>

              <div className="divide-y divide-bg-border rounded-md border border-bg-border bg-bg-elevated">
                <div className="flex items-center justify-between gap-4 px-4 py-3">
                  <div>
                    <p className="text-sm font-medium text-text-primary">Active</p>
                    <p className="text-xs text-text-muted">Inactive companies are left out of crawls and market pages.</p>
                  </div>
                  <Switch
                    checked={form.is_active}
                    onChange={() => setForm({ ...form, is_active: !form.is_active })}
                    label="Active"
                  />
                </div>
                <div className="flex items-center justify-between gap-4 px-4 py-3">
                  <div>
                    <p className="text-sm font-medium text-text-primary">Tracked</p>
                    <p className="text-xs text-text-muted">Crawlers collect prices, floorsheet and news for it.</p>
                  </div>
                  <Switch
                    checked={form.is_tracked}
                    onChange={() => setForm({ ...form, is_tracked: !form.is_tracked })}
                    label="Tracked"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 border-t border-bg-border pt-4">
                <button type="button" onClick={closeModal} disabled={saving} className="btn-ghost disabled:opacity-50">
                  Cancel
                </button>
                <button type="submit" disabled={saving} className="btn-primary disabled:cursor-not-allowed disabled:opacity-50">
                  {saving ? 'Saving…' : editingCompany ? 'Save changes' : 'Add company'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DELETE CONFIRMATION */}
      {confirmDelete && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => !deleting && setConfirmDelete(null)}
        >
          <div
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="delete-company-title"
            onClick={(event) => event.stopPropagation()}
            className="w-full max-w-sm rounded-lg border border-bg-border bg-bg-secondary p-5 shadow-xl"
          >
            <div className="flex items-start gap-3">
              <div className="rounded-full bg-down/10 p-2 text-down">
                <Trash2 size={18} />
              </div>
              <div>
                <h2 id="delete-company-title" className="font-semibold text-text-primary">
                  Delete {confirmDelete.symbol}?
                </h2>
                <p className="mt-1 text-sm text-text-secondary">
                  {confirmDelete.name} and its stored prices, floorsheet and analysis will be removed. This can't be undone.
                </p>
              </div>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                autoFocus
                onClick={() => setConfirmDelete(null)}
                disabled={deleting}
                className="btn-ghost disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={deleteCompany}
                disabled={deleting}
                className="rounded bg-down px-3 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {deleting ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TOAST */}
      {toast && (
        <div
          role="status"
          className="fixed bottom-5 right-5 z-50 flex items-center gap-2 rounded-md border border-up/30 bg-bg-secondary px-4 py-3 text-sm text-up shadow-lg"
        >
          <CheckCircle2 size={16} />
          {toast}
        </div>
      )}
    </div>
  );
}
