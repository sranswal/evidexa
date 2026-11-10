import React, { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Logo } from "../components/brand/Logo";
import { ApiClientError } from "../api/client";

export const LoginPage: React.FC = () => {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [usernameOrEmail, setUsernameOrEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Determine redirection target
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || "/cases";

  React.useEffect(() => {
    if (isAuthenticated) {
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, navigate, from]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!usernameOrEmail.trim() || !password) {
      setError("Please provide both username/email and password.");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await login(usernameOrEmail.trim(), password);
      navigate(from, { replace: true });
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setError(err.message || "Invalid username or password.");
      } else {
        setError("Unable to authenticate. Please verify your credentials and try again.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#080808] px-4 py-12 text-[#FAFAFA] sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8 rounded-xl border border-[#27272A] bg-[#121214] p-8 shadow-2xl backdrop-blur-sm">
        <div className="flex flex-col items-center text-center">
          <Link to="/" className="focus:outline-none mb-4" title="Return to Home">
            <Logo variant="horizontal" size="lg" />
          </Link>
          <h2 className="text-2xl font-bold tracking-tight text-[#FAFAFA]">
            Forensic Investigator Portal
          </h2>
          <p className="mt-2 text-xs text-zinc-400">
            Enterprise Identity, Authentication & Authorization Gateway
          </p>
        </div>

        {error && (
          <div
            role="alert"
            className="rounded-lg border border-red-500/40 bg-red-950/40 p-3.5 text-xs text-red-200"
          >
            <div className="flex items-center gap-2">
              <svg className="h-4 w-4 shrink-0 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span>{error}</span>
            </div>
          </div>
        )}

        <form className="mt-6 space-y-5" onSubmit={handleSubmit}>
          <div>
            <label
              htmlFor="username-or-email"
              className="block text-xs font-semibold uppercase tracking-wider text-zinc-300"
            >
              Username or Corporate Email
            </label>
            <div className="mt-1.5">
              <input
                id="username-or-email"
                name="username-or-email"
                type="text"
                autoComplete="username"
                required
                value={usernameOrEmail}
                onChange={(e) => setUsernameOrEmail(e.target.value)}
                placeholder="examiner@agency.gov or username"
                className="block w-full rounded-lg border border-[#27272A] bg-[#0c0c0e] px-3.5 py-2.5 text-sm text-[#FAFAFA] placeholder-zinc-500 transition focus:border-[#FF6B00] focus:outline-none focus:ring-1 focus:ring-[#FF6B00]"
              />
            </div>
          </div>

          <div>
            <label
              htmlFor="password"
              className="block text-xs font-semibold uppercase tracking-wider text-zinc-300"
            >
              Password
            </label>
            <div className="mt-1.5">
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="block w-full rounded-lg border border-[#27272A] bg-[#0c0c0e] px-3.5 py-2.5 text-sm text-[#FAFAFA] placeholder-zinc-500 transition focus:border-[#FF6B00] focus:outline-none focus:ring-1 focus:ring-[#FF6B00]"
              />
            </div>
          </div>

          <div>
            <button
              type="submit"
              disabled={submitting}
              className="group relative flex w-full justify-center rounded-lg bg-[#FF6B00] hover:bg-[#FF7E1F] px-4 py-2.5 text-sm font-bold text-[#080808] shadow-lg transition focus:outline-none focus:ring-2 focus:ring-[#FF6B00] focus:ring-offset-2 focus:ring-offset-zinc-900 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? (
                <div className="flex items-center gap-2">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-black border-t-transparent" />
                  <span>Authenticating...</span>
                </div>
              ) : (
                "Sign In to Investigation Workspace"
              )}
            </button>
          </div>
        </form>

        <div className="border-t border-[#27272A] pt-4 text-center space-y-2">
          <p className="text-xs text-zinc-400">
            Need an investigator account?{" "}
            <Link to="/register" className="text-[#FF6B00] hover:underline font-semibold">
              Register local account
            </Link>
          </p>
          <p className="text-[11px] text-zinc-500 font-mono">
            Protected by Argon2id Password Hashing & Case-Scoped RBAC. Unauthorized access attempts are monitored and recorded in immutable audit logs.
          </p>
        </div>
      </div>
    </div>
  );
};

