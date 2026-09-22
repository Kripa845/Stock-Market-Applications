
export interface CompanyAccess {
  company_id: number;
  company_symbol: string;
  company_name: string;
  status: number;
}

export interface CompanyAccessResponse {
  company_access: CompanyAccess[];
}

export interface SaveCompanyAccessPayload {
  company_access: {
    company_id: number;
    status: number;
  }[];
}

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function getAuthHeaders(): HeadersInit {
  const token =
    localStorage.getItem("access_token") ||
    localStorage.getItem("accessToken");

  return {
    "Content-Type": "application/json",
    Accept: "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

/**
 * Get company access for a specific user.
 */
export async function getUserCompanyAccess(
  userId: number | string
): Promise<CompanyAccessResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/users/admin/users/${userId}/company-access/`,
    {
      method: "GET",
      headers: getAuthHeaders(),
    }
  );

  if (!response.ok) {
    let message = `Failed to load company access (${response.status})`;

    try {
      const data = await response.json();
      message = data.detail || data.message || message;
    } catch {
      // Keep default error message.
    }

    throw new Error(message);
  }

  return response.json();
}

/**
 * Replace the complete company-access configuration for a user.
 */
export async function saveUserCompanyAccess(
  userId: number | string,
  companyAccess: { company_id: number; status: number }[]
): Promise<CompanyAccessResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/users/admin/users/${userId}/company-access/`,
    {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        company_access: companyAccess,
      }),
    }
  );

  if (!response.ok) {
    let message = `Failed to save company access (${response.status})`;

    try {
      const data = await response.json();
      message = data.detail || data.message || message;
    } catch {
      // Keep default error message.
    }

    throw new Error(message);
  }

  return response.json();
}

