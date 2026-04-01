"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { authClient } from "@/server/better-auth/client";
import { Button, GoogleIcon } from "./ui";

export function LoginPage() {
  const router = useRouter();
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const handleGoogleSignIn = async () => {
    await authClient.signIn.social({
      provider: "google",
      callbackURL: "/workspace",
    });
  };



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
              Terminal Access
            </h1>
            <p className="text-primary-fixed-dim text-sm font-medium tracking-wide uppercase opacity-70">
              Automotive Intelligence Portal
            </p>
          </div>

          {/* Google Sign-in (only for sign-in mode) */}
          <div className="space-y-4">
            <Button
              className="w-full flex items-center justify-center gap-3 bg-surface-container-highest py-3 px-4 hover:bg-surface-bright group relative rounded"
              onClick={handleGoogleSignIn}
            >
              <div className="absolute inset-0 border border-primary/10 pointer-events-none group-hover:border-primary/30 transition-colors rounded"></div>
              <GoogleIcon />
              <span className="font-medium text-on-surface text-sm">
                Sign in with Google
              </span>
            </Button>

            <div className="flex items-center gap-4 py-2">
              <div className="h-[1px] flex-grow bg-outline-variant/20"></div>
              <span className="text-[10px] uppercase tracking-widest text-outline">
                Secondary Access
              </span>
              <div className="h-[1px] flex-grow bg-outline-variant/20"></div>
            </div>

            <Button
              className="w-full bg-surface-container-highest text-on-surface/70 hover:text-primary font-headline font-semibold uppercase tracking-[0.2em] py-3 hover:bg-surface-bright active:scale-[0.95] rounded border border-primary/5 hover:border-primary/20 transition-all duration-300 text-[10px]"
              onClick={() => router.push("/workspace")}
            >
              Bypass Protocol
            </Button>
          </div>

          {/* Error message */}
          {error && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-xs font-mono">
              {error}
            </div>
          )}



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
