
import { useEffect, useMemo, useState, type ChangeEvent } from "react";
import "./FinancialReports.css";

const API: string = import.meta.env.VITE_API_BASE_URL || "";

interface Company {
  symbol: string;
  name: string;
  sector: string | null;
}

interface FilterOptions {
  sectors: string[];
  companies: Company[];
  fiscal_years: string[];
  durations: string[];
}

interface Filters {
  sector: string;
  company: string;
  fiscalYear: string;
  duration: string;
}

interface ReportRow {
  sn: number;
  date: string;
  symbol: string;
  fiscal_year: string;
  duration: string;
  title: string;
  file_url: string | null;
}

interface ReportsResponse {
  results: ReportRow[];
  page: number;
  num_pages: number;
  total: number;
}

const EMPTY: Filters = {
  sector: "",
  company: "",
  fiscalYear: "",
  duration: "",
};

const EMPTY_OPTIONS: FilterOptions = {
  sectors: [],
  companies: [],
  fiscal_years: [],
  durations: [],
};

const EMPTY_DATA: ReportsResponse = {
  results: [],
  page: 1,
  num_pages: 0,
  total: 0,
};

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export default function FinancialReports() {
  const [options, setOptions] = useState<FilterOptions>(EMPTY_OPTIONS);
  const [draft, setDraft] = useState<Filters>(EMPTY);
  const [applied, setApplied] = useState<Filters>(EMPTY);
  const [page, setPage] = useState<number>(1);
  const [data, setData] = useState<ReportsResponse>(EMPTY_DATA);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");

  // Load filter dropdown options.
  useEffect(() => {
    fetchJson<FilterOptions>(`${API}/api/financial-reports/filters/`)
      .then(setOptions)
      .catch(() => setError("Could not load filter options."));
  }, []);

  // Load reports when filters or page change.
  useEffect(() => {
    let cancelled = false;

    const params = new URLSearchParams({
      sector: applied.sector,
      company: applied.company,
      fiscal_year: applied.fiscalYear,
      duration: applied.duration,
      page: String(page),
    });

    setLoading(true);
    setError("");

    fetchJson<ReportsResponse>(
      `${API}/api/financial-reports/?${params}`
    )
      .then((json) => {
        if (!cancelled) setData(json);
      })
      .catch(() => {
        if (!cancelled) {
          setError("Could not load reports. Please try again.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [applied, page]);

  // Show only companies belonging to the selected sector.
  const companyOptions = useMemo(
    () =>
      options.companies.filter(
        (company) =>
          !draft.sector || company.sector === draft.sector
      ),
    [options.companies, draft.sector]
  );

  const change =
    (key: keyof Filters) =>
    (event: ChangeEvent<HTMLSelectElement>): void => {
      const value = event.target.value;

      setDraft((current) => ({
        ...current,
        [key]: value,
        ...(key === "sector" ? { company: "" } : {}),
      }));
    };

  const search = (): void => {
    setPage(1);
    setApplied({ ...draft });
  };

  const reset = (): void => {
    setDraft(EMPTY);
    setPage(1);
    setApplied(EMPTY);
  };

  // Display up to five page numbers.
  const pages = useMemo(() => {
    if (data.num_pages <= 1) return [];

    const first = Math.max(
      1,
      Math.min(data.page - 2, data.num_pages - 4)
    );

    const last = Math.min(data.num_pages, first + 4);

    return Array.from(
      { length: last - first + 1 },
      (_, index) => first + index
    );
  }, [data.page, data.num_pages]);

  return (
    <div className="fr-page">
      {/* Page heading */}
      <div className="fr-heading">
        <div>
          <div className="fr-eyebrow">
            STOCKSCOPE <span /> RESEARCH CENTER
          </div>

          <h1 className="fr-title">Financial Reports</h1>

          <p className="fr-subtitle">
            Explore and access company financial statements,
            quarterly reports, and disclosures.
          </p>
        </div>

        <div className="fr-report-count">
          <span className="fr-count-label">AVAILABLE REPORTS</span>
          <strong>{data.total.toLocaleString()}</strong>
          <span className="fr-count-caption">Reports in database</span>
        </div>
      </div>

      {/* Filters */}
      <section className="fr-filter-card">
        <div className="fr-section-heading">
          <div>
            <span className="fr-section-kicker">REFINE RESULTS</span>
            <h2>Report Filters</h2>
          </div>

          <span className="fr-filter-hint">
            Select your criteria below
          </span>
        </div>

        <div className="fr-filters">
          <label className="fr-field">
            <span>Sector</span>
            <select
              value={draft.sector}
              onChange={change("sector")}
            >
              <option value="">All Sectors</option>
              {options.sectors.map((sector) => (
                <option key={sector} value={sector}>
                  {sector}
                </option>
              ))}
            </select>
          </label>

          <label className="fr-field">
            <span>Company</span>
            <select
              value={draft.company}
              onChange={change("company")}
            >
              <option value="">All Companies</option>
              {companyOptions.map((company) => (
                <option
                  key={company.symbol}
                  value={company.symbol}
                >
                  {company.symbol} - {company.name}
                </option>
              ))}
            </select>
          </label>

          <label className="fr-field">
            <span>Fiscal Year</span>
            <select
              value={draft.fiscalYear}
              onChange={change("fiscalYear")}
            >
              <option value="">All Fiscal Years</option>
              {options.fiscal_years.map((year) => (
                <option key={year} value={year}>
                  {year} BS
                </option>
              ))}
            </select>
          </label>

          <label className="fr-field">
            <span>Report Duration</span>
            <select
              value={draft.duration}
              onChange={change("duration")}
            >
              <option value="">All Durations</option>
              {options.durations.map((duration) => (
                <option key={duration} value={duration}>
                  {duration}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="fr-filter-actions">
          <span className="fr-filter-note">
            Filters are applied when you click Search.
          </span>

          <div className="fr-action-buttons">
            <button
              type="button"
              className="fr-reset"
              onClick={reset}
            >
              Reset filters
            </button>

            <button
              type="button"
              className="fr-search"
              onClick={search}
            >
              <span>⌕</span> Search Reports
            </button>
          </div>
        </div>
      </section>

      {/* Reports table */}
      <section className="fr-results-card">
        <div className="fr-results-heading">
          <div>
            <span className="fr-section-kicker">DATABASE</span>
            <h2>Available Reports</h2>
            <p>
              Browse financial documents published by tracked companies.
            </p>
          </div>

          <div className="fr-results-meta">
            <span className="fr-live-dot" />
            {loading ? "Updating..." : "Report records"}
          </div>
        </div>

        {error && (
          <div className="fr-error">
            <strong>Unable to load data</strong>
            <span>{error}</span>
          </div>
        )}

        <div className="fr-table-wrapper">
          <table className="fr-table">
            <thead>
              <tr>
                <th className="fr-number-col">#</th>
                <th>Date</th>
                <th>Company</th>
                <th>Fiscal Year</th>
                <th>Duration</th>
                <th>Report Title</th>
                <th className="fr-view-col">Document</th>
              </tr>
            </thead>

            <tbody>
              {loading && data.results.length === 0 && (
                <tr>
                  <td colSpan={7} className="fr-empty">
                    <span className="fr-loader" />
                    Loading financial reports...
                  </td>
                </tr>
              )}

              {!loading &&
                !error &&
                data.results.length === 0 && (
                  <tr>
                    <td colSpan={7} className="fr-empty">
                      <div className="fr-empty-icon">▤</div>
                      <strong>No reports found</strong>
                      <span>
                        Try changing your filters or resetting them.
                      </span>
                    </td>
                  </tr>
                )}

              {data.results.map((report) => (
                <tr
                  key={`${report.sn}-${report.symbol}-${report.title}`}
                >
                  <td className="fr-number">
                    {report.sn}
                  </td>

                  <td className="fr-date">
                    {report.date} BS
                  </td>

                  <td>
                    <span className="fr-symbol">
                      {report.symbol}
                    </span>
                  </td>

                  <td className="fr-year">
                    {report.fiscal_year} BS
                  </td>

                  <td>
                    <span className="fr-duration">
                      {report.duration}
                    </span>
                  </td>

                  <td className="fr-report-title">
                    {report.title}
                  </td>

                  {/* Original PDF link with source attribution */}
                  <td className="fr-document-cell">
                    {report.file_url ? (
                      <div className="fr-pdf-wrapper">
                        <a
                          className="fr-pdf"
                          href={report.file_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          aria-label={`View original financial report for ${report.symbol} on NepaliPaisa`}
                        >
                          <span>↗</span> View Original PDF
                        </a>

                        <span className="fr-source">
                          Source: NepaliPaisa
                        </span>
                      </div>
                    ) : (
                      <span className="fr-muted">
                        PDF unavailable
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="fr-table-footer">
          <span className="fr-pagination-info">
            Showing page{" "}
            <strong>{data.num_pages > 0 ? data.page : 0}</strong>
            {" "}of{" "}
            <strong>{data.num_pages}</strong>
            {" "}·{" "}
            <strong>{data.total}</strong> total reports
          </span>

          {pages.length > 0 && (
            <div className="fr-pager">
              <button
                type="button"
                className="fr-page-arrow"
                disabled={data.page <= 1 || loading}
                onClick={() => setPage(data.page - 1)}
              >
                ‹
              </button>

              {pages.map((pageNumber) => (
                <button
                  type="button"
                  key={pageNumber}
                  className={
                    pageNumber === data.page
                      ? "fr-page-number active"
                      : "fr-page-number"
                  }
                  disabled={loading}
                  onClick={() => setPage(pageNumber)}
                >
                  {pageNumber}
                </button>
              ))}

              <button
                type="button"
                className="fr-page-arrow"
                disabled={
                  data.page >= data.num_pages || loading
                }
                onClick={() => setPage(data.page + 1)}
              >
                ›
              </button>
            </div>
          )}
        </div>
      </section>

      <div className="fr-footer-note">
        <span>STOCKSCOPE</span>
        <span>Financial data for research and analysis</span>
      </div>
    </div>
  );
}
