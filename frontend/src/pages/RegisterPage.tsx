import { type ChangeEvent, type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";
import { useAuth } from "../context/AuthContext";
import type { RegisterPayload } from "../types";

const initialForm: RegisterPayload = {
  username: "",
  email: "",
  password: "",
  passwordConfirm: "",
  firstName: "",
  lastName: "",
};

type FormField = keyof RegisterPayload;

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState<RegisterPayload>(initialForm);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const update = (field: FormField) => (e: ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [field]: e.target.value });

  const handleSubmit = async (e: FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register(form);
      navigate("/login", { state: { registered: true } });
    } catch (err) {
      let message = "Registration failed.";
      if (axios.isAxiosError(err) && err.response?.data) {
        message = Object.values(err.response.data as Record<string, unknown>).flat().join(" ");
      }
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <h1>Create account</h1>
        <p className="auth-subtitle">New accounts start with the Viewer role.</p>

        {error && <div className="form-error">{error}</div>}

        <label>
          Username
          <input value={form.username} onChange={update("username")} required />
        </label>
        <label>
          Email
          <input type="email" value={form.email} onChange={update("email")} required />
        </label>
        <div className="form-row">
          <label>
            First name
            <input value={form.firstName} onChange={update("firstName")} />
          </label>
          <label>
            Last name
            <input value={form.lastName} onChange={update("lastName")} />
          </label>
        </div>
        <label>
          Password
          <input type="password" value={form.password} onChange={update("password")} required minLength={8} />
        </label>
        <label>
          Confirm password
          <input
            type="password"
            value={form.passwordConfirm}
            onChange={update("passwordConfirm")}
            required
          />
        </label>

        <button className="btn btn-primary" type="submit" disabled={submitting}>
          {submitting ? "Creating…" : "Create account"}
        </button>

        <p className="auth-footer">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </form>
    </div>
  );
}
