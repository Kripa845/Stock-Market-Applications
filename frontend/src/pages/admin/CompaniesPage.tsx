import { useEffect, useMemo, useState } from 'react';
import {
  Plus,
  Search,
  Pencil,
  Trash2,
  RefreshCw,
  ToggleLeft,
  ToggleRight,
  X,
} from 'lucide-react';

import apiClient from '../../api/client';
import { useAuth } from '../../contexts/AuthContext';

interface Company {
  id: number;
  symbol: string;
  name: string;
  sector: string;
  is_active: boolean;
  is_tracked?: boolean;
  created_at?: string;
}

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

export default function CompaniesPage({ trackedOnly = false }: { trackedOnly?: boolean }) {
  const { hasPermission } = useAuth();

  // Derive every capability from the live permission list
  const canCreate  = hasPermission('create_companies');
  const canEdit    = hasPermission('edit_companies');
  const canDelete  = hasPermission('delete_companies');
  const canTrack   = hasPermission('manage_tracked_companies');  // toggle tracking
  const canToggleActive = canEdit; // editing company status needs edit_companies

  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [search, setSearch] = useState('');
  const [sectorFilter, setSectorFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [trackedFilter, setTrackedFilter] = useState('all');

  const [showModal, setShowModal] = useState(false);
  const [editingCompany, setEditingCompany] =
    useState<Company | null>(null);

  const [form, setForm] = useState<CompanyForm>(emptyForm);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // =====================================================
  // LOAD COMPANIES
  // =====================================================
  const loadCompanies = async () => {
    try {
      setLoading(true);
      setError('');

      const response = await apiClient.get('/companies/', {
        params: trackedOnly ? { tracked_only: true } : undefined,
      });

      const data = response.data;

      if (Array.isArray(data)) {
        setCompanies(data);
      } else if (Array.isArray(data.results)) {
        setCompanies(data.results);
      } else {
        setCompanies([]);
      }
    } catch (err: any) {
      console.error('Failed to load companies:', err);

      setError(
        err?.response?.data?.detail ||
          'Failed to load companies.'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCompanies();
  }, [trackedOnly]);

  // =====================================================
  // UNIQUE SECTORS
  // =====================================================
  const sectors = useMemo(() => {
    const values = companies
      .map((company) => company.sector)
      .filter(Boolean);

    return Array.from(new Set(values)).sort();
  }, [companies]);

  // =====================================================
  // FILTER COMPANIES
  // =====================================================
  const filteredCompanies = useMemo(() => {
    return companies.filter((company) => {
      const searchValue = search.toLowerCase().trim();

      const matchesSearch =
        !searchValue ||
        company.symbol
          ?.toLowerCase()
          .includes(searchValue) ||
        company.name
          ?.toLowerCase()
          .includes(searchValue);

      const matchesSector =
        sectorFilter === 'all' ||
        company.sector === sectorFilter;

      const matchesStatus =
        statusFilter === 'all' ||
        (statusFilter === 'active' && company.is_active) ||
        (statusFilter === 'inactive' && !company.is_active);

      const isTracked = company.is_tracked ?? false;

      const matchesTracked =
        trackedFilter === 'all' ||
        (trackedFilter === 'tracked' && isTracked) ||
        (trackedFilter === 'not_tracked' && !isTracked);

      return (
        matchesSearch &&
        matchesSector &&
        matchesStatus &&
        matchesTracked
      );
    });
  }, [
    companies,
    search,
    sectorFilter,
    statusFilter,
    trackedFilter,
  ]);

  // =====================================================
  // OPEN ADD MODAL
  // =====================================================
  const openAddModal = () => {
    setEditingCompany(null);
    setForm(emptyForm);
    setError('');
    setSuccess('');
    setShowModal(true);
  };

  // =====================================================
  // OPEN EDIT MODAL
  // =====================================================
  const openEditModal = (company: Company) => {
    setEditingCompany(company);

    setForm({
      symbol: company.symbol || '',
      name: company.name || '',
      sector: company.sector || '',
      is_active: company.is_active,
      is_tracked: company.is_tracked ?? false,
    });

    setError('');
    setSuccess('');
    setShowModal(true);
  };

  // =====================================================
  // CLOSE MODAL
  // =====================================================
  const closeModal = () => {
    if (saving) return;

    setShowModal(false);
    setEditingCompany(null);
    setForm(emptyForm);
    setError('');
  };

  // =====================================================
  // SAVE COMPANY
  // =====================================================
  const handleSubmit = async (
    event: React.FormEvent<HTMLFormElement>
  ) => {
    event.preventDefault();

    if (!form.symbol.trim()) {
      setError('Company symbol is required.');
      return;
    }

    if (!form.name.trim()) {
      setError('Company name is required.');
      return;
    }

    try {
      setSaving(true);
      setError('');

      const payload = {
        symbol: form.symbol.trim().toUpperCase(),
        name: form.name.trim(),
        sector: form.sector.trim(),
        is_active: form.is_active,
        is_tracked: form.is_tracked,
      };

      if (editingCompany) {
        await apiClient.patch(
          `/companies/${editingCompany.id}/`,
          payload
        );

        setSuccess('Company updated successfully.');
      } else {
        await apiClient.post('/companies/', payload);

        setSuccess('Company created successfully.');
      }

      await loadCompanies();

      setTimeout(() => {
        setShowModal(false);
        setEditingCompany(null);
        setForm(emptyForm);
        setSuccess('');
      }, 700);
    } catch (err: any) {
      console.error('Failed to save company:', err);

      const data = err?.response?.data;

      if (typeof data === 'object' && data !== null) {
        const firstError = Object.values(data)[0];

        if (Array.isArray(firstError)) {
          setError(String(firstError[0]));
        } else {
          setError(String(firstError));
        }
      } else {
        setError('Failed to save company.');
      }
    } finally {
      setSaving(false);
    }
  };

  // =====================================================
  // TOGGLE TRACKING
  // =====================================================
  const toggleTracking = async (company: Company) => {
    const currentTracked = company.is_tracked ?? false;

    try {
      setError('');

      await apiClient.patch(
        `/companies/${company.id}/`,
        {
          is_tracked: !currentTracked,
        }
      );

      setCompanies((current) =>
        current.map((item) =>
          item.id === company.id
            ? {
                ...item,
                is_tracked: !currentTracked,
              }
            : item
        )
      );
    } catch (err: any) {
      console.error('Failed to update tracking:', err);

      setError(
        err?.response?.data?.detail ||
          'Failed to update tracking status.'
      );
    }
  };

  // =====================================================
  // TOGGLE ACTIVE STATUS
  // =====================================================
  const toggleActive = async (company: Company) => {
    try {
      setError('');

      await apiClient.patch(
        `/companies/${company.id}/`,
        {
          is_active: !company.is_active,
        }
      );

      setCompanies((current) =>
        current.map((item) =>
          item.id === company.id
            ? {
                ...item,
                is_active: !company.is_active,
              }
            : item
        )
      );
    } catch (err: any) {
      console.error('Failed to update company status:', err);

      setError(
        err?.response?.data?.detail ||
          'Failed to update company status.'
      );
    }
  };

  // =====================================================
  // DELETE COMPANY
  // =====================================================
  const deleteCompany = async (company: Company) => {
    const confirmed = window.confirm(
      `Are you sure you want to delete ${company.name} (${company.symbol})?`
    );

    if (!confirmed) return;

    try {
      setError('');

      await apiClient.delete(
        `/companies/${company.id}/`
      );

      setCompanies((current) =>
        current.filter((item) => item.id !== company.id)
      );

      setSuccess('Company deleted successfully.');

      setTimeout(() => {
        setSuccess('');
      }, 2000);
    } catch (err: any) {
      console.error('Failed to delete company:', err);

      setError(
        err?.response?.data?.detail ||
          'Failed to delete company.'
      );
    }
  };

  return (
    <div className="space-y-6">
      {/* =================================================
          HEADER
          ================================================= */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">
            {trackedOnly ? 'Watchlist' : 'Companies'}
          </h1>

          <p className="mt-1 text-sm text-text-secondary">
            {trackedOnly ? 'Manage tracked companies used by crawlers.' : 'Manage the company directory and tracking status.'}
          </p>
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={loadCompanies}
            disabled={loading}
            className="btn-ghost inline-flex items-center justify-center gap-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw
              size={16}
              className={loading ? 'animate-spin' : ''}
            />

            Refresh
          </button>

          {canCreate && (
            <button
              type="button"
              onClick={openAddModal}
              className="btn-primary inline-flex items-center justify-center gap-2"
            >
              <Plus size={17} />
              Add Company
            </button>
          )}
        </div>
      </div>


      {/* =================================================
          ALERTS
          ================================================= */}
      {error && (
        <div className="mb-4 flex items-start justify-between rounded-lg border border-down/30 bg-down/10 px-4 py-3 text-sm text-down">
          <span>{error}</span>

          <button
            type="button"
            onClick={() => setError('')}
            className="ml-4"
          >
            <X size={17} />
          </button>
        </div>
      )}

      {success && (
        <div className="mb-4 rounded-lg border border-up/30 bg-up/10 px-4 py-3 text-sm text-up">
          {success}
        </div>
      )}


      {/* =================================================
          FILTERS
          ================================================= */}
      <div className="card p-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4">

          {/* Search */}
          <div className="relative">
            <Search
              size={17}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
            />

            <input
              type="text"
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
              placeholder="Search symbol or company..."
              className="w-full rounded-lg border border-bg-border bg-bg-card py-2.5 pl-10 pr-3 text-sm text-text-primary outline-none transition focus:border-accent"
            />
          </div>


          {/* Sector */}
          <select
            value={sectorFilter}
            onChange={(event) =>
              setSectorFilter(event.target.value)
            }
            className="rounded-lg border border-bg-border bg-bg-card px-3 py-2.5 text-sm text-text-primary outline-none focus:border-accent"
          >
            <option value="all">All sectors</option>

            {sectors.map((sector) => (
              <option
                key={sector}
                value={sector}
              >
                {sector}
              </option>
            ))}
          </select>


          {/* Status */}
          <select
            value={statusFilter}
            onChange={(event) =>
              setStatusFilter(event.target.value)
            }
            className="rounded-lg border border-bg-border bg-bg-card px-3 py-2.5 text-sm text-text-primary outline-none focus:border-accent"
          >
            <option value="all">All statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>


          {/* Tracking */}
          <select
            value={trackedFilter}
            onChange={(event) =>
              setTrackedFilter(event.target.value)
            }
            className="rounded-lg border border-bg-border bg-bg-card px-3 py-2.5 text-sm text-text-primary outline-none focus:border-accent"
          >
            <option value="all">All tracking</option>
            <option value="tracked">Tracked</option>
            <option value="not_tracked">
              Not tracked
            </option>
          </select>

        </div>
      </div>


      {/* =================================================
          TABLE
          ================================================= */}
      <div className="card overflow-hidden">

        <div className="flex items-center justify-between border-b border-bg-border px-5 py-4">
          <div>
            <h2 className="font-semibold text-text-primary">
              Company Watchlist
            </h2>

            <p className="mt-1 text-xs text-text-muted">
              {filteredCompanies.length} companies
            </p>
          </div>
        </div>


        {loading ? (
          <div className="flex min-h-[300px] items-center justify-center">
              <div className="text-sm text-text-secondary">
              Loading companies...
            </div>
          </div>
        ) : filteredCompanies.length === 0 ? (
          <div className="flex min-h-[300px] flex-col items-center justify-center px-6 text-center">
            <div className="mb-3 rounded-full bg-bg-elevated p-3">
              <Search
                size={22}
                className="text-slate-400"
              />
            </div>

              <h3 className="font-medium text-text-primary">
              No companies found
            </h3>

            <p className="mt-1 text-sm text-text-secondary">
              Try changing your search or filters.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-left">

              <thead className="border-b border-bg-border bg-bg-elevated">
                <tr>
                  <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Symbol
                  </th>

                  <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Company
                  </th>

                  <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Sector
                  </th>

                  <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Status
                  </th>

                  <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Tracking
                  </th>

                  <th className="px-5 py-3 text-right text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Actions
                  </th>
                </tr>
              </thead>

              <tbody className="divide-y divide-bg-border">

                {filteredCompanies.map((company) => {
                  const tracked =
                    company.is_tracked ?? false;

                  return (
                    <tr
                      key={company.id}
                      className="transition hover:bg-bg-elevated/70"
                    >

                      <td className="px-5 py-4">
                        <span className="font-semibold text-accent-light">
                          {company.symbol}
                        </span>
                      </td>


                      <td className="px-5 py-4">
                        <span className="text-sm text-text-primary">
                          {company.name}
                        </span>
                      </td>


                      <td className="px-5 py-4">
                        <span className="text-sm text-text-secondary">
                          {company.sector || '—'}
                        </span>
                      </td>

                      <td className="px-5 py-4">
                        {canToggleActive ? (
                          <button
                            type="button"
                            onClick={() => toggleActive(company)}
                            className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                              company.is_active
                                ? 'bg-blue-500/10 text-blue-300 border border-blue-500/20'
                                : 'bg-bg-elevated text-text-muted border border-bg-border'
                            }`}
                          >
                            {company.is_active ? 'Active' : 'Inactive'}
                          </button>
                        ) : (
                          <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                            company.is_active
                              ? 'bg-blue-500/10 text-blue-300 border border-blue-500/20'
                              : 'bg-bg-elevated text-text-muted border border-bg-border'
                          }`}>
                            {company.is_active ? 'Active' : 'Inactive'}
                          </span>
                        )}
                      </td>


                      <td className="px-5 py-4">
                        {canTrack ? (
                          <button
                            type="button"
                            onClick={() => toggleTracking(company)}
                            className="inline-flex items-center gap-2 rounded-lg px-2 py-1 text-sm font-medium text-text-secondary transition hover:bg-bg-elevated"
                          >
                            {tracked ? (
                              <><ToggleRight size={22} className="text-blue-600" /><span className="text-blue-700">Tracked</span></>
                            ) : (
                              <><ToggleLeft size={22} className="text-slate-400" /><span className="text-slate-500">Not tracked</span></>
                            )}
                          </button>
                        ) : (
                          <span className="inline-flex items-center gap-2 px-2 py-1 text-sm text-text-muted">
                            {tracked ? (
                              <><ToggleRight size={22} className="text-blue-600 opacity-50" /><span className="text-blue-700 opacity-50">Tracked</span></>
                            ) : (
                              <><ToggleLeft size={22} className="text-slate-400 opacity-50" /><span className="text-slate-500 opacity-50">Not tracked</span></>
                            )}
                          </span>
                        )}
                      </td>


                      <td className="px-5 py-4">
                        <div className="flex justify-end gap-2">
                          {canEdit && (
                            <button
                              type="button"
                              onClick={() => openEditModal(company)}
                              className="rounded-lg border border-bg-border p-2 text-text-muted transition hover:bg-bg-elevated hover:text-text-primary"
                              title="Edit company"
                            >
                              <Pencil size={16} />
                            </button>
                          )}
                          {canDelete && (
                            <button
                              type="button"
                              onClick={() => deleteCompany(company)}
                              className="rounded-lg border border-down/30 p-2 text-down transition hover:bg-down/10"
                              title="Delete company"
                            >
                              <Trash2 size={16} />
                            </button>
                          )}
                          {!canEdit && !canDelete && (
                            <span className="text-xs text-text-muted px-2 py-1">View only</span>
                          )}
                        </div>
                      </td>

                    </tr>
                  );
                })}

              </tbody>

            </table>
          </div>
        )}

      </div>


      {/* =================================================
      {/* =================================================
          ADD / EDIT MODAL — only rendered for users with create or edit permission
          ================================================= */}
      {showModal && (canCreate || canEdit) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">

          <div className="w-full max-w-lg rounded-2xl border border-bg-border bg-bg-secondary shadow-xl">

            {/* Modal header */}
            <div className="flex items-center justify-between border-b border-bg-border px-5 py-4">
              <div>
                <h2 className="font-semibold text-text-primary">
                  {editingCompany ? 'Edit Company' : 'Add Company'}
                </h2>
                <p className="mt-1 text-xs text-text-secondary">
                  {editingCompany
                    ? 'Update company information.'
                    : 'Add a company to the system.'}
                </p>
              </div>

              <button
                type="button"
                onClick={closeModal}
                className="rounded-lg p-2 text-text-muted hover:bg-bg-elevated hover:text-text-primary"
              >
                <X size={19} />
              </button>

            </div>


            {/* Form */}
            <form
              onSubmit={handleSubmit}
              className="space-y-4 p-5"
            >

              {error && (
                <div className="rounded-lg border border-down/30 bg-down/10 px-3 py-2 text-sm text-down">
                  {error}
                </div>
              )}

              {success && (
                <div className="rounded-lg border border-up/30 bg-up/10 px-3 py-2 text-sm text-up">
                  {success}
                </div>
              )}


              {/* Symbol */}
              <div>
                <label className="mb-1.5 block text-sm font-medium text-text-secondary">
                  Symbol
                </label>

                <input
                  type="text"
                  value={form.symbol}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      symbol: event.target.value,
                    })
                  }
                  placeholder="e.g. NABIL"
                  className="w-full rounded-lg border border-bg-border bg-bg-card px-3 py-2.5 text-sm uppercase text-text-primary outline-none focus:border-accent"
                />
              </div>


              {/* Company name */}
              <div>
                <label className="mb-1.5 block text-sm font-medium text-text-secondary">
                  Company Name
                </label>

                <input
                  type="text"
                  value={form.name}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      name: event.target.value,
                    })
                  }
                  placeholder="e.g. Nabil Bank Limited"
                  className="w-full rounded-lg border border-bg-border bg-bg-card px-3 py-2.5 text-sm text-text-primary outline-none focus:border-accent"
                />
              </div>


              {/* Sector */}
              <div>
                <label className="mb-1.5 block text-sm font-medium text-text-secondary">
                  Sector
                </label>

                <input
                  type="text"
                  value={form.sector}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      sector: event.target.value,
                    })
                  }
                  placeholder="e.g. Commercial Bank"
                  className="w-full rounded-lg border border-bg-border bg-bg-card px-3 py-2.5 text-sm text-text-primary outline-none focus:border-accent"
                />
              </div>


              {/* Options */}
              <div className="space-y-3 rounded-lg bg-bg-elevated p-4">

                <label className="flex cursor-pointer items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-text-primary">
                      Active
                    </p>

                    <p className="text-xs text-text-muted">
                      Company is active in the system.
                    </p>
                  </div>

                  <input
                    type="checkbox"
                    checked={form.is_active}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        is_active: event.target.checked,
                      })
                    }
                    className="h-4 w-4"
                  />
                </label>


                <label className="flex cursor-pointer items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-text-primary">
                      Track Company
                    </p>

                    <p className="text-xs text-text-muted">
                      Include this company in the watchlist.
                    </p>
                  </div>

                  <input
                    type="checkbox"
                    checked={form.is_tracked}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        is_tracked: event.target.checked,
                      })
                    }
                    className="h-4 w-4"
                  />
                </label>

              </div>


              {/* Buttons */}
              <div className="flex justify-end gap-3 border-t border-bg-border pt-4">

                <button
                  type="button"
                  onClick={closeModal}
                  disabled={saving}
                  className="btn-ghost disabled:opacity-50"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={saving}
                  className="btn-primary disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {saving
                    ? 'Saving...'
                    : editingCompany
                    ? 'Update Company'
                    : 'Add Company'}
                </button>

              </div>

            </form>

          </div>

        </div>
      )}

    </div>
  );
}