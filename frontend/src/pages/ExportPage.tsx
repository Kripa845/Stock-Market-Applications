/**
 * ExportPage.tsx
 *
 * Export Data / Reports page.
 *
 * UI permission gate: renders the export form only when the current user
 * holds the "export_reports" permission (checked via the existing
 * useAuth().hasPermission() hook — same mechanism used by every other
 * permission-gated UI in the application).
 *
 * Backend permission gate: every API call is independently authorised
 * server-side by the existing HasAppPermission("export_reports") class.
 * Hiding the UI is NOT the security mechanism.
 *
 * The company dropdown is populated from /api/reports/export/companies/,
 * which also requires export_reports, so a non-permitted user would see
 * neither the UI nor get any data from the backend.
 */

import { useEffect, useState } from 'react';
import {
  Download,
  FileSpreadsheet,
  FileText,
  Filter,
  Lock,
} from 'lucide-react';

import PageHeader from '../components/common/PageHeader';
import { useAuth } from '../contexts/AuthContext';
import {
  exportsApi,
  type ExportCompany,
  type ExportDataType,
  type ExportFormat,
  type ExportParams,
  type SentimentFilter,
} from '../api/exports';

// ---------------------------------------------------------------------------
// Types / constants
// ---------------------------------------------------------------------------

interface FormState {
  dataType: ExportDataType;
  companyIds: number[];
  dateFrom: string;
  dateTo: string;
  sentiment: SentimentFilter;
  format: ExportFormat;
}

const DATA_TYPE_OPTIONS: { value: ExportDataType; label: string; description: string }[] = [
  { value: 'news',       label: 'News',             description: 'Articles, sources, sentiment, tags'         },
  { value: 'trading',    label: 'Trading Data',      description: 'Daily price, volume, turnover'              },
  { value: 'floorsheet', label: 'Floorsheet',        description: 'Transaction-level broker data'              },
  { value: 'report',     label: 'Analysis Report',   description: 'Combined trading, news & analysis summary'  },
];

// Which formats are available for each data type
const FORMAT_OPTIONS: Record<ExportDataType, ExportFormat[]> = {
  news:       ['csv', 'xlsx', 'pdf'],
  trading:    ['csv', 'xlsx', 'pdf'],
  floorsheet: ['csv', 'xlsx'],
  report:     ['pdf', 'xlsx'],
};

const FORMAT_LABELS: Record<ExportFormat, string> = {
  csv:  'CSV',
  xlsx: 'Excel (XLSX)',
  pdf:  'PDF',
};

const FORMAT_ICONS: Record<ExportFormat, React.ReactNode> = {
  csv:  <FileText size={15} className="shrink-0" />,
  xlsx: <FileSpreadsheet size={15} className="shrink-0" />,
  pdf:  <FileText size={15} className="shrink-0" />,
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ExportPage() {
  const { hasPermission } = useAuth();
  const canExport = hasPermission('export_reports');

  // ── state ────────────────────────────────────────────────────────────────
  const [companies, setCompanies] = useState<ExportCompany[]>([]);
  const [loadingCompanies, setLoadingCompanies] = useState(false);

  const [form, setForm] = useState<FormState>({
    dataType:  'news',
    companyIds: [],
    dateFrom:  '',
    dateTo:    '',
    sentiment: '',
    format:    'csv',
  });

  const [submitting, setSubmitting] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  // ── load company list (only if user has permission) ──────────────────────
  useEffect(() => {
    if (!canExport) return;
    setLoadingCompanies(true);
    exportsApi
      .getCompanies()
      .then(setCompanies)
      .catch(() => {
        // Non-fatal — dropdown will just be empty; user can still export all
      })
      .finally(() => setLoadingCompanies(false));
  }, [canExport]);

  // ── keep format valid when data type changes ─────────────────────────────
  useEffect(() => {
    const validFormats = FORMAT_OPTIONS[form.dataType];
    if (!validFormats.includes(form.format)) {
      setForm((prev) => ({ ...prev, format: validFormats[0] }));
    }
  }, [form.dataType]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── helpers ──────────────────────────────────────────────────────────────
  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setSuccessMsg('');
    setErrorMsg('');
  };

  const validate = (): string | null => {
    if (form.dateFrom && form.dateTo && form.dateFrom > form.dateTo) {
      return '"From" date must not be after "To" date.';
    }
    if (form.dataType === 'floorsheet' && form.format === 'pdf') {
      return 'Floorsheet export does not support PDF format.';
    }
    if (form.dataType === 'report' && form.format === 'csv') {
      return 'Analysis report does not support CSV format.';
    }
    return null;
  };

  // ── submit ────────────────────────────────────────────────────────────────
  const handleExport = async () => {
    setSuccessMsg('');
    setErrorMsg('');

    const validationError = validate();
    if (validationError) {
      setErrorMsg(validationError);
      return;
    }

    const params: ExportParams = {
      company_ids: form.companyIds.length ? form.companyIds : undefined,
      date_from:  form.dateFrom  || undefined,
      date_to:    form.dateTo    || undefined,
      sentiment:  form.sentiment || undefined,
      format:     form.format,
    };

    setSubmitting(true);
    try {
      switch (form.dataType) {
        case 'news':
          await exportsApi.exportNews(params, companies);
          break;
        case 'trading':
          await exportsApi.exportTrading(params, companies);
          break;
        case 'floorsheet':
          await exportsApi.exportFloorsheet(params, companies);
          break;
        case 'report':
          await exportsApi.exportReport(params, companies);
          break;
      }
      setSuccessMsg('Export complete — your file has been downloaded.');
    } catch (err: unknown) {
      // The backend returns 204 when filters match no data; axios treats it
      // as a resolved response (no error), so we only land here on real errors.
      const axiosErr = err as { response?: { status?: number; data?: Blob } };
      const httpStatus = axiosErr?.response?.status;

      if (httpStatus === 204) {
        setErrorMsg('No data found for the selected filters. Try a wider date range or different company.');
      } else if (httpStatus === 403) {
        setErrorMsg('You do not have permission to export data.');
      } else if (httpStatus === 400) {
        // Parse the blob error body for the backend's message
        const blob = axiosErr?.response?.data;
        if (blob instanceof Blob) {
          const text = await blob.text();
          try {
            const json = JSON.parse(text) as { error?: string };
            setErrorMsg(json.error ?? 'Invalid export parameters.');
          } catch {
            setErrorMsg('Invalid export parameters.');
          }
        } else {
          setErrorMsg('Invalid export parameters.');
        }
      } else {
        setErrorMsg('Export failed. Please try again or contact support.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  // ── render: no permission ────────────────────────────────────────────────
  if (!canExport) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Export Data / Reports"
          subtitle="Download market data and analysis reports."
        />
        <div className="card flex flex-col items-center gap-4 py-20">
          <Lock size={48} className="text-text-muted" />
          <div className="text-center">
            <p className="text-lg font-semibold text-text-primary">Access Restricted</p>
            <p className="text-sm text-text-secondary mt-1">
              You do not have the{' '}
              <span className="font-medium text-text-primary">Export Reports</span>{' '}
              permission. Contact your administrator to request access.
            </p>
          </div>
        </div>
      </div>
    );
  }

  // ── render: full export UI ────────────────────────────────────────────────
  const availableFormats = FORMAT_OPTIONS[form.dataType];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Export Data / Reports"
        subtitle="Download market data and analysis reports in CSV, Excel, or PDF format."
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* ── LEFT PANEL: form ──────────────────────────────────────── */}
        <div className="lg:col-span-2 space-y-5">

          {/* Data type selector */}
          <div className="card space-y-3">
            <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
              <Filter size={15} className="text-text-muted" />
              Data Type
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {DATA_TYPE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => set('dataType', opt.value)}
                  className={[
                    'flex flex-col items-start text-left px-4 py-3 rounded-lg border transition-colors',
                    form.dataType === opt.value
                      ? 'border-accent bg-accent/10 text-accent-light'
                      : 'border-bg-border bg-bg-secondary hover:bg-bg-elevated text-text-secondary hover:text-text-primary',
                  ].join(' ')}
                >
                  <span className="text-sm font-medium">{opt.label}</span>
                  <span className="text-xs mt-0.5 opacity-70">{opt.description}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Filters */}
          <div className="card space-y-4">
            <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
              <Filter size={15} className="text-text-muted" />
              Filters
            </h3>

            {/* Companies */}
            <div className="space-y-1">
              <label className="text-xs font-medium text-text-secondary uppercase tracking-wide">
                Companies
              </label>
              {loadingCompanies ? (
                <div className="text-sm text-text-muted py-2">Loading companies…</div>
              ) : (
                <div className="border border-bg-border rounded-lg max-h-48 overflow-y-auto p-2 space-y-1">
                  {companies.map((c) => (
                    <label
                      key={c.id}
                      className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-bg-secondary cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        className="accent-accent"
                        checked={form.companyIds.includes(c.id)}
                        onChange={(e) => {
                          const ids = e.target.checked
                            ? [...form.companyIds, c.id]
                            : form.companyIds.filter((id) => id !== c.id);
                          set('companyIds', ids);
                        }}
                      />
                      <span className="text-sm text-text-primary">
                        {c.symbol} — {c.name}
                      </span>
                    </label>
                  ))}
                </div>
              )}
            </div>

            {/* Date range */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-medium text-text-secondary uppercase tracking-wide">
                  From
                </label>
                <input
                  type="date"
                  className="input w-full"
                  value={form.dateFrom}
                  max={form.dateTo || undefined}
                  onChange={(e) => set('dateFrom', e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-text-secondary uppercase tracking-wide">
                  To
                </label>
                <input
                  type="date"
                  className="input w-full"
                  value={form.dateTo}
                  min={form.dateFrom || undefined}
                  onChange={(e) => set('dateTo', e.target.value)}
                />
              </div>
            </div>

            {/* Sentiment (news only) */}
            {form.dataType === 'news' && (
              <div className="space-y-1">
                <label className="text-xs font-medium text-text-secondary uppercase tracking-wide">
                  Sentiment
                </label>
                <select
                  className="input w-full"
                  value={form.sentiment}
                  onChange={(e) => set('sentiment', e.target.value as SentimentFilter)}
                >
                  <option value="">All Sentiments</option>
                  <option value="positive">Positive</option>
                  <option value="neutral">Neutral</option>
                  <option value="negative">Negative</option>
                </select>
              </div>
            )}
          </div>

          {/* Format selector */}
          <div className="card space-y-3">
            <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
              <FileSpreadsheet size={15} className="text-text-muted" />
              Export Format
            </h3>
            <div className="flex flex-wrap gap-2">
              {availableFormats.map((fmt) => (
                <button
                  key={fmt}
                  type="button"
                  onClick={() => set('format', fmt)}
                  className={[
                    'flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-medium transition-colors',
                    form.format === fmt
                      ? 'border-accent bg-accent/10 text-accent-light'
                      : 'border-bg-border bg-bg-secondary hover:bg-bg-elevated text-text-secondary',
                  ].join(' ')}
                >
                  {FORMAT_ICONS[fmt]}
                  {FORMAT_LABELS[fmt]}
                </button>
              ))}
            </div>
          </div>

          {/* Feedback */}
          {errorMsg && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
              {errorMsg}
            </div>
          )}
          {successMsg && (
            <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-3 text-sm text-green-400">
              {successMsg}
            </div>
          )}

          {/* Export button */}
          <button
            type="button"
            onClick={handleExport}
            disabled={submitting}
            className="btn-primary flex items-center gap-2 px-6 py-2.5 w-full sm:w-auto justify-center"
          >
            {submitting ? (
              <>
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Exporting…
              </>
            ) : (
              <>
                <Download size={16} />
                {form.dataType === 'report' ? 'Generate Report' : 'Export'}
              </>
            )}
          </button>
        </div>

        {/* ── RIGHT PANEL: summary / info ──────────────────────────── */}
        <div className="space-y-4">
          <div className="card space-y-4">
            <h3 className="text-sm font-semibold text-text-primary">Export Summary</h3>

            <div className="space-y-2 text-sm">
              <Row
                label="Data type"
                value={DATA_TYPE_OPTIONS.find((o) => o.value === form.dataType)?.label ?? '—'}
              />
              <Row
                label="Company"
                value={
                    form.companyIds.length
                      ? form.companyIds
                          .map((cid) => companies.find((c) => c.id === cid)?.symbol ?? String(cid))
                          .join(", ")
                      : "All"
                  }
              />
              <Row label="From"   value={form.dateFrom || 'No limit'} />
              <Row label="To"     value={form.dateTo   || 'No limit'} />
              {form.dataType === 'news' && (
                <Row
                  label="Sentiment"
                  value={form.sentiment ? capitalize(form.sentiment) : 'All'}
                />
              )}
              <Row label="Format" value={FORMAT_LABELS[form.format]} />
            </div>
          </div>

          {/* Format notes */}
          <div className="card space-y-3 text-xs text-text-secondary">
            <p className="font-semibold text-text-primary text-sm">Format Notes</p>
            <p>
              <span className="font-medium text-text-primary">CSV</span> — Raw tabular data,
              compatible with Excel and any spreadsheet app.
            </p>
            <p>
              <span className="font-medium text-text-primary">Excel (XLSX)</span> — Formatted
              workbook with column headers and auto-sized columns.
            </p>
            <p>
              <span className="font-medium text-text-primary">PDF</span> — Formatted report
              suitable for sharing or printing.
            </p>
            <p className="border-t border-bg-border pt-3 text-text-muted">
              Large exports are capped at a maximum row count to ensure performance.
              Use date filters to narrow the result.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-center gap-2">
      <span className="text-text-muted">{label}</span>
      <span className="text-text-primary font-medium truncate max-w-[60%] text-right">{value}</span>
    </div>
  );
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
