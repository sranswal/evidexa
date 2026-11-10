import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Logo } from "../components/brand/Logo";
import { registerUser } from "../api/auth";
import { ApiClientError } from "../api/client";

export const RegisterPage: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  React.useEffect(() => {
    if (isAuthenticated) {
      navigate("/cases", { replace: true });
    }
  }, [isAuthenticated, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim() || !username.trim() || !email.trim() || !password) {
      setError("Please complete all required fields.");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await registerUser(email.trim(), username.trim(), password, fullName.trim());
      setSuccess(true);
      setTimeout(() => {
        navigate("/login", { replace: true });
      }, 1500);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setError(err.message || "Registration failed. Please check your details.");
      } else {
        setError("Unable to register account. Username or email may already be registered.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#080808] px-4 py-12 text-[#FAFAFA] sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8 rounded-xl border border-[#27272A] bg-[#121214] p-8 shadow-2xl backdrop-blur-sm">
        <div className="flex flex-col items-center text-center">
          <Link to="/" className="focus:outline-none mb-4">
            <Logo variant="horizontal" size="lg" />
          </Link>
          <h2 className="text-2xl font-bold tracking-tight text-[#FAFAFA]">
            Create Investigator Account
          </h2>
          <p className="mt-2 text-xs text-zinc-400">
            Local & Development Identity Enrollment
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

        {success && (
          <div
            role="status"
            className="rounded-lg border border-emerald-500/40 bg-emerald-950/40 p-3.5 text-xs text-emerald-200"
          >
            Account created successfully. Redirecting to login...
          </div>
        )}

        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
          <div>
            <label
              htmlFor="full-name"
              className="block text-xs font-semibold uppercase tracking-wider text-zinc-300"
            >
              Full Name
            </label>
            <div className="mt-1">
              <input
                id="full-name"
                name="full-name"
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Agent Sarah Vance"
                className="block w-full rounded-lg border border-[#27272A] bg-[#0c0c0e] px-3.5 py-2.5 text-sm text-[#FAFAFA] placeholder-zinc-500 transition focus:border-[#FF6B00] focus:outline-none focus:ring-1 focus:ring-[#FF6B00]"
              />
            </div>
          </div>

          <div>
            <label
              htmlFor="username"
              className="block text-xs font-semibold uppercase tracking-wider text-zinc-300"
            >
              Username
            </label>
            <div className="mt-1">
              <input
                id="username"
                name="username"
                type="text"
                autoComplete="username"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="svance"
                className="block w-full rounded-lg border border-[#27272A] bg-[#0c0c0e] px-3.5 py-2.5 text-sm text-[#FAFAFA] placeholder-zinc-500 transition focus:border-[#FF6B00] focus:outline-none focus:ring-1 focus:ring-[#FF6B00]"
              />
            </div>
          </div>

          <div>
            <label
              htmlFor="email"
              className="block text-xs font-semibold uppercase tracking-wider text-zinc-300"
            >
              Corporate / Agency Email
            </label>
            <div className="mt-1">
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="svance@agency.local"
                className="block w-full rounded-lg border border-[#27272A] bg-[#0c0c0e] px-3.5 py-2.5 text-sm text-[#FAFAFA] placeholder-zinc-500 transition focus:border-[#FF6B00] focus:outline-none focus:ring-1 focus:ring-[#FF6B00]"
              />
            </div>
          </div>

          <div>
            <label
              htmlFor="password"
              className="block text-xs font-semibold uppercase tracking-wider text-zinc-300"
            >
              Password (min 8 characters)
            </label>
            <div className="mt-1">
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="new-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="block w-full rounded-lg border border-[#27272A] bg-[#0c0c0e] px-3.5 py-2.5 text-sm text-[#FAFAFA] placeholder-zinc-500 transition focus:border-[#FF6B00] focus:outline-none focus:ring-1 focus:ring-[#FF6B00]"
              />
            </div>
          </div>

          <div className="pt-2">
            <button
              type="submit"
              disabled={submitting || success}
              className="group relative flex w-full justify-center rounded-lg bg-[#FF6B00] hover:bg-[#FF7E1F] px-4 py-2.5 text-sm font-bold text-[#080808] shadow-lg transition focus:outline-none focus:ring-2 focus:ring-[#FF6B00] focus:ring-offset-2 focus:ring-offset-zinc-900 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? "Registering..." : "Create Account"}
            </button>
          </div>
        </form>

        <div className="border-t border-[#27272A] pt-4 text-center space-y-2">
          <p className="text-xs text-zinc-400">
            Already registered?{" "}
            <Link to="/login" className="text-[#FF6B00] hover:underline font-semibold">
              Sign in to workspace
            </Link>
          </p>
          <p className="text-[11px] text-zinc-500 font-mono">
            Protected by Argon2id password hashing. Automatically assigned to default tenant.
          </p>
        </div>
      </div>
    </div>
  );
};

