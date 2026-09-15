
import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Activity, Eye, EyeOff, ArrowLeft } from 'lucide-react';
import { authApi } from '../api/auth';

const RegisterPage: React.FC = () => {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    username: '',
    email: '',
    password: '',
    password_confirm: '',
  });

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] =
    useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    setForm({
      ...form,
      [e.target.name]: e.target.value,
    });
  };

  const handleSubmit = async (
    e: React.FormEvent
  ) => {
    e.preventDefault();

    setError('');
    setSuccess('');

    if (
      !form.first_name ||
      !form.last_name ||
      !form.username ||
      !form.email ||
      !form.password ||
      !form.password_confirm
    ) {
      setError('Please fill in all fields.');
      return;
    }

    if (form.password !== form.password_confirm) {
      setError('Passwords do not match.');
      return;
    }

    if (form.password.length < 8) {
      setError(
        'Password must contain at least 8 characters.'
      );
      return;
    }

    try {
      setLoading(true);

      await authApi.register({
        ...form,

        // Public users are registered as viewer.
        // Admin can later change the role.
        role: 'viewer',
      });

      setSuccess(
        'Registration successful. Redirecting to login...'
      );

      setTimeout(() => {
        navigate('/login');
      }, 1200);
    } catch (err: any) {
      const data = err?.response?.data;

      if (typeof data === 'object' && data !== null) {
        const messages = Object.entries(data)
          .map(([field, value]) => {
            if (Array.isArray(value)) {
              return `${field}: ${value.join(', ')}`;
            }

            return `${field}: ${String(value)}`;
          })
          .join('\n');

        setError(
          messages || 'Registration failed.'
        );
      } else {
        setError(
          'Registration failed. Please try again.'
        );
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg-primary flex">

      {/* Left side */}
      <div className="hidden lg:flex lg:w-1/2
        bg-bg-secondary border-r border-bg-border
        items-center justify-center p-12">

        <div className="max-w-md">

          <div className="flex items-center gap-3 mb-8">
            <div className="w-11 h-11 rounded-xl
              bg-accent flex items-center justify-center">
              <Activity size={22} />
            </div>

            <span className="text-xl font-bold
              text-text-primary">
              StockScope
            </span>
          </div>

          <h1 className="text-4xl font-bold
            text-text-primary leading-tight">
            Market intelligence
            <span className="text-accent-light">
              {' '}from one place.
            </span>
          </h1>

          <p className="mt-5 text-text-secondary">
            Monitor companies, news, market data
            and trading behaviour through your
            StockScope account.
          </p>

        </div>
      </div>

      {/* Right side */}
      <div className="flex-1 flex items-center
        justify-center px-6 py-10">

        <div className="w-full max-w-md">

          <Link
            to="/"
            className="inline-flex items-center gap-2
              text-sm text-text-secondary
              hover:text-text-primary mb-8"
          >
            <ArrowLeft size={16} />
            Back to home
          </Link>

          <h2 className="text-3xl font-bold
            text-text-primary">
            Create account
          </h2>

          <p className="mt-2 text-text-secondary">
            Create your StockScope account.
          </p>

          {error && (
            <div className="mt-6 p-3 rounded-lg
              border border-red-500/30
              bg-red-500/10 text-red-400
              text-sm whitespace-pre-line">
              {error}
            </div>
          )}

          {success && (
            <div className="mt-6 p-3 rounded-lg
              border border-green-500/30
              bg-green-500/10 text-green-400
              text-sm">
              {success}
            </div>
          )}

          <form
            onSubmit={handleSubmit}
            className="mt-6 space-y-4"
          >

            {/* Name */}
            <div className="grid grid-cols-2 gap-3">

              <div>
                <label className="label">
                  First name
                </label>

                <input
                  type="text"
                  name="first_name"
                  value={form.first_name}
                  onChange={handleChange}
                  className="input text-black bg-white placeholder:text-gray-400"
                  placeholder="First name"
                />
              </div>

              <div>
                <label className="label">
                  Last name
                </label>

                <input
                  type="text"
                  name="last_name"
                  value={form.last_name}
                  onChange={handleChange}
                  className="input text-black bg-white placeholder:text-gray-400"
                  placeholder="Last name"
                />
              </div>

            </div>

            {/* Username */}
            <div>
              <label className="label">
                Username
              </label>

              <input
                type="text"
                name="username"
                value={form.username}
                onChange={handleChange}
                className="input text-black bg-white placeholder:text-gray-400"
                placeholder="Choose a username"
              />
            </div>

            {/* Email */}
            <div>
              <label className="label">
                Email
              </label>

              <input
                type="email"
                name="email"
                value={form.email}
                onChange={handleChange}
                className="input text-black bg-white placeholder:text-gray-400"
                placeholder="you@example.com"
              />
            </div>

            {/* Password */}
            <div>
              <label className="label">
                Password
              </label>

              <div className="relative">

                <input
                  type={
                    showPassword
                      ? 'text'
                      : 'password'
                  }
                  name="password"
                  value={form.password}
                  onChange={handleChange}
                  className="input pr-11 text-black bg-white placeholder:text-gray-400"
                  placeholder="Create a password"
                />

                <button
                  type="button"
                  onClick={() =>
                    setShowPassword(!showPassword)
                  }
                  className="absolute right-3
                    top-1/2 -translate-y-1/2
                    text-text-secondary"
                >
                  {showPassword ? (
                    <EyeOff size={18} />
                  ) : (
                    <Eye size={18} />
                  )}
                </button>

              </div>
            </div>

            {/* Confirm password */}
            <div>
              <label className="label">
                Confirm password
              </label>

              <div className="relative">

                <input
                  type={
                    showConfirmPassword
                      ? 'text'
                      : 'password'
                  }
                  name="password_confirm"
                  value={form.password_confirm}
                  onChange={handleChange}
                  className="input pr-11 text-black bg-white placeholder:text-gray-400"
                  placeholder="Confirm your password"
                />

                <button
                  type="button"
                  onClick={() =>
                    setShowConfirmPassword(
                      !showConfirmPassword
                    )
                  }
                  className="absolute right-3
                    top-1/2 -translate-y-1/2
                    text-text-secondary"
                >
                  {showConfirmPassword ? (
                    <EyeOff size={18} />
                  ) : (
                    <Eye size={18} />
                  )}
                </button>

              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full
                disabled:opacity-50
                disabled:cursor-not-allowed"
            >
              {loading
                ? 'Creating account...'
                : 'Create account'}
            </button>

          </form>

          <p className="text-center text-sm
            text-text-secondary mt-6">

            Already have an account?{' '}

            <Link
              to="/login"
              className="text-accent-light
                hover:underline"
            >
              Sign in
            </Link>

          </p>

        </div>
      </div>
    </div>
  );
};

export default RegisterPage;

