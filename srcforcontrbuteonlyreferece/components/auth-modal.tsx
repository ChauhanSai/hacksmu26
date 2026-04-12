"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth-context";

interface AuthModalProps {
  onClose: () => void;
}

export function AuthModal({ onClose }: AuthModalProps) {
  const { login } = useAuth();
  const [tab, setTab] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    login(email || undefined);
    onClose();
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="relative w-full max-w-sm rounded-2xl border border-violet-500/20 bg-zinc-900 p-8 shadow-2xl shadow-violet-500/10">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 text-zinc-500 transition-colors hover:text-white"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
          </svg>
        </button>

        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 h-10 w-10 rounded-xl bg-violet-600 flex items-center justify-center">
            <span className="text-white font-bold">BB</span>
          </div>
          <h2 className="text-xl font-bold text-white">
            {tab === "login" ? "Welcome back" : "Create account"}
          </h2>
          <p className="mt-1 text-sm text-zinc-400">
            {tab === "login" ? "Sign in to access the marketplace" : "Join the raffle marketplace"}
          </p>
        </div>

        <div className="mb-6 flex rounded-lg bg-zinc-800 p-1">
          <button
            type="button"
            onClick={() => setTab("login")}
            className={`flex-1 rounded-md py-2 text-sm font-semibold transition-colors ${
              tab === "login" ? "bg-violet-600 text-white" : "text-zinc-400 hover:text-white"
            }`}
          >
            Log In
          </button>
          <button
            type="button"
            onClick={() => setTab("signup")}
            className={`flex-1 rounded-md py-2 text-sm font-semibold transition-colors ${
              tab === "signup" ? "bg-violet-600 text-white" : "text-zinc-400 hover:text-white"
            }`}
          >
            Sign Up
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-zinc-400">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="h-11 w-full rounded-xl border border-zinc-700 bg-zinc-800 px-3 text-sm text-white placeholder-zinc-500 transition-colors focus:border-violet-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-zinc-400">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="h-11 w-full rounded-xl border border-zinc-700 bg-zinc-800 px-3 text-sm text-white placeholder-zinc-500 transition-colors focus:border-violet-500 focus:outline-none"
            />
          </div>

          <button
            type="submit"
            className="mt-2 h-11 w-full rounded-xl bg-violet-600 text-sm font-semibold text-white transition-colors hover:bg-violet-700"
          >
            {tab === "login" ? "Log In" : "Create Account"}
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-zinc-500">
          By continuing you agree to our Terms of Service and Privacy Policy.
        </p>
      </div>
    </div>
  );
}
