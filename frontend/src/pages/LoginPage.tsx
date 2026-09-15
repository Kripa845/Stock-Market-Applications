
import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Activity,
  Eye,
  EyeOff,
  ArrowLeft,
} from 'lucide-react';
import { authApi } from '../api/auth';

const LoginPage: React.FC = () => {
  const navigate = useNavigate();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const [showPassword, setShowPassword] =
    useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (
    e: React.FormEvent
  ) => {
    e.preventDefault();

    setError('');

    if (!username || !password) {
      setError(
        'Please enter your username and password.'
      );
      return;
    }

    try {
      setLoading(true);

      const response = await authApi.login(
        username,
        password
      );

      /*
       * Store JWT tokens
       */
      localStorage.setItem(
        'access_token',
        response.access
      );

      localStorage.setItem(
        'refresh_token',
        response.refresh
      );

      /*
       * Store logged-in user
       */
      localStorage.setItem(
        'user',
        JSON.stringify(response.user)
      );

      /*
       * Redirect according to role
       */
      switch (response.user.role) {
        case 'admin':
          navigate('/admin', {
            replace: true,
          });
          break;

        case 'analyst':
          navigate('/analyst', {
            replace: true,
          });
          break;

        case 'viewer':
        default:
          navigate('/viewer', {
            replace: true,
          });
          break;
      }

    } catch (err: any) {
      const data = err?.response?.data;

      if (data?.detail) {
        setError(data.detail);
      } else if (data?.non_field_errors) {
        setError(
          Array.isArray(data.non_field_errors)
            ? data.non_field_errors.join(', ')
            : String(data.non_field_errors)
        );
      } else {
        setError(
          'Invalid username or password.'
        );
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg-primary flex">

      {/* =====================================================
          LEFT SIDE
      ====================================================== */}

      <div
        className="
          hidden lg:flex lg:w-1/2
          bg-bg-secondary
          border-r border-bg-border
          items-center justify-center
          p-12
        "
      >

        <div className="max-w-md">

          {/* Logo */}

          <div className="flex items-center gap-3 mb-8">

            <div
              className="
                w-11 h-11
                rounded-xl
                bg-accent
                flex items-center justify-center
              "
            >
              <Activity size={22} />
            </div>

            <span
              className="
                text-xl font-bold
                text-text-primary
              "
            >
              StockScope
            </span>

          </div>

          {/* Heading */}

          <h1
            className="
              text-4xl font-bold
              text-text-primary
              leading-tight
            "
          >
            Welcome back to

            <span className="text-accent-light">
              {' '}StockScope.
            </span>

          </h1>

          <p className="mt-5 text-text-secondary">
            Sign in to access your market
            intelligence dashboard.
          </p>

        </div>
      </div>


      {/* =====================================================
          RIGHT SIDE
      ====================================================== */}

      <div
        className="
          flex-1
          flex items-center justify-center
          px-6
        "
      >

        <div className="w-full max-w-md">

          {/* Back to home */}

          <Link
            to="/"
            className="
              inline-flex
              items-center
              gap-2
              text-sm
              text-text-secondary
              hover:text-text-primary
              mb-8
              transition-colors
            "
          >
            <ArrowLeft size={16} />

            Back to home
          </Link>


          {/* Heading */}

          <h2
            className="
              text-3xl font-bold
              text-text-primary
            "
          >
            Sign in
          </h2>

          <p
            className="
              mt-2
              text-text-secondary
            "
          >
            Enter your credentials to continue.
          </p>


          {/* Error */}

          {error && (
            <div
              className="
                mt-6
                p-3
                rounded-lg
                border
                border-red-500/30
                bg-red-500/10
                text-red-400
                text-sm
              "
            >
              {error}
            </div>
          )}


          {/* Form */}

          <form
            onSubmit={handleSubmit}
            className="mt-6 space-y-5"
          >

            {/* Username */}

            <div>

              <label className="label">
                Username
              </label>

              <input
                type="text"
                value={username}
                onChange={(e) =>
                  setUsername(e.target.value)
                }
                className="input"
                placeholder="Enter your username"
                autoComplete="username"
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
                  value={password}
                  onChange={(e) =>
                    setPassword(e.target.value)
                  }
                  className="input pr-11"
                  placeholder="Enter your password"
                  autoComplete="current-password"
                />

                <button
                  type="button"
                  onClick={() =>
                    setShowPassword(
                      !showPassword
                    )
                  }
                  className="
                    absolute
                    right-3
                    top-1/2
                    -translate-y-1/2
                    text-text-secondary
                    hover:text-text-primary
                    transition-colors
                  "
                >
                  {showPassword ? (
                    <EyeOff size={18} />
                  ) : (
                    <Eye size={18} />
                  )}
                </button>

              </div>

            </div>


            {/* Login button */}

            <button
              type="submit"
              disabled={loading}
              className="
                btn-primary
                w-full
                disabled:opacity-50
                disabled:cursor-not-allowed
              "
            >
              {loading
                ? 'Signing in...'
                : 'Sign in'}
            </button>

          </form>


          {/* Register */}

          <p
            className="
              text-center
              text-sm
              text-text-secondary
              mt-6
            "
          >
            Don't have an account?{' '}

            <Link
              to="/register"
              className="
                text-accent-light
                hover:underline
              "
            >
              Create account
            </Link>

          </p>

        </div>

      </div>

    </div>
  );
};

export default LoginPage;

