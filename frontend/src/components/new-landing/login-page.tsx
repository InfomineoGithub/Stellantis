"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { authClient } from "@/server/better-auth/client";
import { clearJwtTokenCache } from "@/core/api/auth-fetch";
import { Button, GoogleIcon } from "./ui";

export function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [mode, setMode] = React.useState<"signin" | "signup">("signin");

  const handleGoogleSignIn = async () => {
    await authClient.signIn.social({
      provider: "google",
      callbackURL: "/workspace",
    });
  };

  const handleEmailSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      // Clear any stale cached JWT before signing in
      clearJwtTokenCache();
      const result = await authClient.signIn.email({
        email,
        password,
        callbackURL: "/workspace",
      });
      if (result.error) {
        setError(result.error.message ?? "Sign in failed");
      } else {
        router.push("/workspace");
      }
    } catch (err: any) {
      setError(err?.message ?? "Sign in failed");
    } finally {
      setLoading(false);
    }
  };

  const handleEmailSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      clearJwtTokenCache();
      const result = await authClient.signUp.email({
        email,
        password,
        name: email.split("@").at(0) ?? email,
        callbackURL: "/workspace",
      });
      if (result.error) {
        setError(result.error.message ?? "Sign up failed");
      } else {
        router.push("/workspace");
      }
    } catch (err: any) {
      setError(err?.message ?? "Sign up failed");
    } finally {
      setLoading(false);
    }
  };

  const isSignUp = mode === "signup";

  return (
    <div className="bg-background text-on-background min-h-screen flex flex-col">
      <header className="bg-surface flex justify-between items-center w-full px-8 py-4 fixed top-0 z-50">
        <div
          className="text-xl font-bold tracking-tighter text-primary font-headline cursor-pointer"
          onClick={() => router.push("/")}
        >
          AAPAS
        </div>
        <nav className="hidden md:flex gap-8 items-center">
          <span className="font-headline uppercase tracking-widest text-xs font-bold text-primary border-b-2 border-primary pb-1 cursor-default">
            Terminal Access
          </span>
        </nav>
        <div className="flex items-center gap-4 text-primary">
          <button className="material-symbols-outlined scale-95 active:scale-90 transition-transform">
            help_outline
          </button>
          <button className="material-symbols-outlined scale-95 active:scale-90 transition-transform">
            settings_input_component
          </button>
        </div>
      </header>

      <main className="flex-grow flex items-center justify-center p-6 relative pt-20 pb-20">
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-primary/5 rounded-full blur-[120px]"></div>
        </div>

        <div className="w-full max-w-md bg-surface-container-high p-8 shadow-2xl relative z-10 rounded-xl minimal-border">
          <div className="mb-10 text-center">
            <div className="flex justify-center mb-6">
              <div className="p-3 bg-surface-container-highest rounded-lg">
                <span className="material-symbols-outlined text-primary text-4xl">
                  terminal
                </span>
              </div>
            </div>
            <h1 className="font-headline text-3xl font-bold tracking-tight text-on-surface mb-2">
              {isSignUp ? "Create Account" : "Terminal Access"}
            </h1>
            <p className="text-primary-fixed-dim text-sm font-medium tracking-wide uppercase opacity-70">
              Automotive Intelligence Portal
            </p>
          </div>

          {/* Google Sign-in (only for sign-in mode) */}
          {!isSignUp && (
            <Button
              className="w-full flex items-center justify-center gap-3 bg-surface-container-highest py-3 px-4 hover:bg-surface-bright group relative mb-8 rounded"
              onClick={handleGoogleSignIn}
            >
              <div className="absolute inset-0 border border-primary/10 pointer-events-none group-hover:border-primary/30 transition-colors rounded"></div>
              <GoogleIcon />
              <span className="font-medium text-on-surface text-sm">
                Sign in with Google
              </span>
            </Button>
          )}

          {!isSignUp && (
            <div className="flex items-center gap-4 mb-8">
              <div className="h-[1px] flex-grow bg-outline-variant/20"></div>
              <span className="text-[10px] uppercase tracking-widest text-outline">
                Standard Protocol
              </span>
              <div className="h-[1px] flex-grow bg-outline-variant/20"></div>
            </div>
          )}

          {/* Error message */}
          {error && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-xs font-mono">
              {error}
            </div>
          )}

          <form
            className="space-y-6"
            onSubmit={isSignUp ? handleEmailSignUp : handleEmailSignIn}
          >
            <div className="space-y-1">
              <label
                className="block text-[10px] font-bold uppercase tracking-[0.15em] text-primary-fixed-dim"
                htmlFor="terminal-id"
              >
                Terminal ID (Email)
              </label>
              <input
                className="w-full bg-surface-container-lowest border-none border-b border-transparent focus:border-b focus:border-primary focus:ring-0 text-on-surface placeholder:text-on-surface-variant/30 py-3 transition-all duration-300 font-mono text-sm px-4 rounded-t"
                id="terminal-id"
                placeholder="user@kinetic-systems.com"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1">
              <label
                className="block text-[10px] font-bold uppercase tracking-[0.15em] text-primary-fixed-dim"
                htmlFor="passcode"
              >
                Passcode
              </label>
              <input
                className="w-full bg-surface-container-lowest border-none border-b border-transparent focus:border-b focus:border-primary focus:ring-0 text-on-surface placeholder:text-on-surface-variant/30 py-3 transition-all duration-300 font-mono text-sm px-4 rounded-t"
                id="passcode"
                placeholder="••••••••"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
              />
            </div>
            <div className="pt-4">
              <Button
                className="w-full bg-gradient-to-r from-primary to-primary-container text-on-primary font-headline font-bold uppercase tracking-widest py-4 hover:opacity-90 active:scale-[0.98] rounded shadow-lg"
                type="submit"
                disabled={loading}
              >
                {loading
                  ? isSignUp
                    ? "Creating..."
                    : "Authenticating..."
                  : isSignUp
                    ? "Create Account"
                    : "Authenticate"}
              </Button>

              {/* Mode toggle */}
              <div className="pt-4 text-center">
                <button
                  type="button"
                  className="text-[10px] uppercase tracking-widest text-on-surface-variant hover:text-primary transition-colors"
                  onClick={() => {
                    setMode(isSignUp ? "signin" : "signup");
                    setError(null);
                  }}
                >
                  {isSignUp
                    ? "Already have access? Sign In"
                    : "New user? Create Account"}
                </button>
              </div>

              <div className="pt-4 border-t border-primary/5 mt-4">
                <Button
                  className="w-full bg-surface-container-highest text-on-surface/70 hover:text-primary font-headline font-semibold uppercase tracking-[0.2em] py-3 hover:bg-surface-bright active:scale-[0.95] rounded border border-primary/5 hover:border-primary/20 transition-all duration-300 text-[10px]"
                  onClick={() => router.push("/workspace")}
                >
                  Bypass Protocol
                </Button>
              </div>
            </div>
          </form>

          <div className="mt-8 text-center">
            <a
              className="text-[10px] uppercase tracking-widest text-on-surface-variant hover:text-primary transition-colors"
              href="#"
            >
              Request Access Upgrade
            </a>
          </div>
        </div>
      </main>

      <footer className="bg-surface fixed bottom-0 w-full flex flex-col md:flex-row justify-between items-center px-12 py-8 gap-4 z-40 border-t border-white/5">
        <div className="font-body text-[10px] tracking-[0.2em] uppercase text-primary">
          © 2024 AAPAS KINETIC SYSTEMS. ALL RIGHTS RESERVED.
        </div>
        <div className="flex gap-8">
          <a
            className="font-body text-[10px] tracking-[0.2em] uppercase text-on-surface/30 hover:text-primary transition-opacity"
            href="#"
          >
            Security Protocol
          </a>
          <a
            className="font-body text-[10px] tracking-[0.2em] uppercase text-on-surface/30 hover:text-primary transition-opacity"
            href="#"
          >
            Privacy Policy
          </a>
          <a
            className="font-body text-[10px] tracking-[0.2em] uppercase text-on-surface/30 hover:text-primary transition-opacity"
            href="#"
          >
            Terminal Status
          </a>
        </div>
      </footer>
    </div>
  );
}
