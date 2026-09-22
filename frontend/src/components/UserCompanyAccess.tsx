
import { useEffect, useMemo, useState } from "react";
import {
  getUserCompanyAccess,
  saveUserCompanyAccess,
  type CompanyAccess,
} from "../api/companyAccess";

interface UserCompanyAccessProps {
  userId: number | string | null;
  userName?: string;
  onClose?: () => void;
}

export default function UserCompanyAccess({
  userId,
  userName,
  onClose,
}: UserCompanyAccessProps) {
  const [companies, setCompanies] = useState<CompanyAccess[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!userId) {
      setCompanies([]);
      return;
    }

    loadCompanyAccess();
  }, [userId]);

  async function loadCompanyAccess() {
    if (!userId) return;

    setLoading(true);
    setError("");
    setSuccess("");

    try {
      const response = await getUserCompanyAccess(userId);

      setCompanies(response.company_access || []);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load company access."
      );
    } finally {
      setLoading(false);
    }
  }

  function toggleCompany(companyId: number) {
    setCompanies((current) =>
      current.map((company) =>
        company.company_id === companyId
          ? {
              ...company,
              status: company.status === 1 ? 0 : 1,
            }
          : company
      )
    );

    setSuccess("");
  }

  async function handleSave() {
    if (!userId) return;

    setSaving(true);
    setError("");
    setSuccess("");

    try {
      const payload = companies.map((company) => ({
        company_id: company.company_id,
        status: company.status,
      }));

      const response = await saveUserCompanyAccess(userId, payload);

      setCompanies(response.company_access || []);

      setSuccess("Company access saved successfully.");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to save company access."
      );
    } finally {
      setSaving(false);
    }
  }

  function enableAll() {
    setCompanies((current) =>
      current.map((company) => ({
        ...company,
        status: 1,
      }))
    );

    setSuccess("");
  }

  function disableAll() {
    setCompanies((current) =>
      current.map((company) => ({
        ...company,
        status: 0,
      }))
    );

    setSuccess("");
  }

  const filteredCompanies = useMemo(() => {
    const value = search.trim().toLowerCase();

    if (!value) {
      return companies;
    }

    return companies.filter(
      (company) =>
        company.company_name.toLowerCase().includes(value) ||
        company.company_symbol.toLowerCase().includes(value)
    );
  }, [companies, search]);

  const enabledCount = companies.filter(
    (company) => company.status === 1
  ).length;

  if (!userId) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-6">
        <p className="text-sm text-gray-500">
          Select a user to manage company access.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
      {/* Header */}
      <div className="border-b border-gray-200 p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              Company Access
            </h2>

            {userName && (
              <p className="mt-1 text-sm text-gray-500">
                Manage which companies{" "}
                <span className="font-medium text-gray-700">
                  {userName}
                </span>{" "}
                can access.
              </p>
            )}
          </div>

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="rounded-md px-3 py-1.5 text-sm text-gray-500 hover:bg-gray-100"
            >
              Close
            </button>
          )}
        </div>

        {/* Controls */}
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <input
            type="text"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search company or symbol..."
            className="min-w-[240px] flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-blue-500"
          />

          <button
            type="button"
            onClick={enableAll}
            disabled={loading || saving || companies.length === 0}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Enable All
          </button>

          <button
            type="button"
            onClick={disableAll}
            disabled={loading || saving || companies.length === 0}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Disable All
          </button>
        </div>

        {/* Summary */}
        <div className="mt-3 text-sm text-gray-500">
          {enabledCount} of {companies.length} companies enabled
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div className="mx-5 mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {success && (
        <div className="mx-5 mt-4 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
          {success}
        </div>
      )}

      {/* Company list */}
      <div className="p-5">
        {loading ? (
          <div className="py-10 text-center text-sm text-gray-500">
            Loading company access...
          </div>
        ) : filteredCompanies.length === 0 ? (
          <div className="py-10 text-center text-sm text-gray-500">
            {search
              ? "No companies match your search."
              : "No company access records found."}
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border border-gray-200">
            <div className="grid grid-cols-[1fr_180px] border-b border-gray-200 bg-gray-50 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
              <div>Company</div>
              <div className="text-center">Access</div>
            </div>

            <div className="divide-y divide-gray-100">
              {filteredCompanies.map((company) => {
                const enabled = company.status === 1;

                return (
                  <div
                    key={company.company_id}
                    className="grid grid-cols-[1fr_180px] items-center px-4 py-4 hover:bg-gray-50"
                  >
                    <div>
                      <div className="font-medium text-gray-900">
                        {company.company_name}
                      </div>

                      <div className="mt-1 text-xs text-gray-500">
                        {company.company_symbol}
                      </div>
                    </div>

                    <div className="flex justify-center">
                      <button
                        type="button"
                        role="switch"
                        aria-checked={enabled}
                        onClick={() =>
                          toggleCompany(company.company_id)
                        }
                        disabled={saving}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${
                          enabled
                            ? "bg-blue-600"
                            : "bg-gray-300"
                        } ${
                          saving
                            ? "cursor-not-allowed opacity-50"
                            : ""
                        }`}
                      >
                        <span
                          className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${
                            enabled
                              ? "translate-x-6"
                              : "translate-x-1"
                          }`}
                        />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-end gap-3 border-t border-gray-200 bg-gray-50 px-5 py-4">
        <button
          type="button"
          onClick={loadCompanyAccess}
          disabled={loading || saving}
          className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Refresh
        </button>

        <button
          type="button"
          onClick={handleSave}
          disabled={loading || saving}
          className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save Access"}
        </button>
      </div>
    </div>
  );
}

