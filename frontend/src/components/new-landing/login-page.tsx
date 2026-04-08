"use client";

import { useRouter } from "next/navigation";
import * as React from "react";

import { authClient } from "@/server/better-auth/client";

import { Button, GoogleIcon } from "./ui";

export function LoginPage() {
  const router = useRouter();

  const handleGoogleSignIn = async () => {
    await authClient.signIn.social({
      provider: "google",
      callbackURL: "/workspace",
    });
  };

  return (
    <div className="bg-background text-on-background flex min-h-screen flex-col">
      <header className="bg-surface fixed top-0 z-50 flex w-full items-center justify-between px-8 py-4">
        <div
          className="text-primary font-headline cursor-pointer text-xl font-bold tracking-tighter"
          onClick={() => router.push("/")}
        >
          AAPAS
        </div>
        <nav className="hidden items-center gap-8 md:flex">
          <span className="font-headline text-primary border-primary cursor-default border-b-2 pb-1 text-xs font-bold tracking-widest uppercase">
            Terminal Access
          </span>
        </nav>
        <div className="text-primary flex items-center gap-4">
          <button className="material-symbols-outlined scale-95 transition-transform active:scale-90">
            help_outline
          </button>
          <button className="material-symbols-outlined scale-95 transition-transform active:scale-90">
            settings_input_component
          </button>
        </div>
      </header>

      <main className="relative flex flex-grow items-center justify-center p-6 pt-20 pb-20">
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="bg-primary/5 absolute top-1/2 left-1/2 h-[600px] w-[600px] -translate-x-1/2 -translate-y-1/2 rounded-full blur-[120px]"></div>
        </div>

        <div className="bg-surface-container-high minimal-border relative z-10 w-full max-w-md rounded-xl p-8 shadow-2xl">
          <div className="mb-10 text-center">
            <div className="mb-6 flex justify-center">
              <div className="bg-surface-container-highest rounded-lg p-3">
                <span className="material-symbols-outlined text-primary text-4xl">
                  terminal
                </span>
              </div>
            </div>
            <h1 className="font-headline text-on-surface mb-2 text-3xl font-bold tracking-tight">
              Terminal Access
            </h1>
            <p className="text-primary-fixed-dim text-sm font-medium tracking-wide uppercase opacity-70">
              Automotive Intelligence Portal
            </p>
          </div>

          {/* Google Sign-in (only for sign-in mode) */}
          <div className="space-y-4">
            <Button
              className="bg-surface-container-highest hover:bg-surface-bright group relative flex w-full items-center justify-center gap-3 rounded px-4 py-3"
              onClick={handleGoogleSignIn}
            >
              <div className="border-primary/10 group-hover:border-primary/30 pointer-events-none absolute inset-0 rounded border transition-colors"></div>
              <GoogleIcon />
              <span className="text-on-surface text-sm font-medium">
                Sign in with Google
              </span>
            </Button>

            <div className="flex items-center gap-4 py-2">
              <div className="bg-outline-variant/20 h-[1px] flex-grow"></div>
              <span className="text-outline text-[10px] tracking-widest uppercase">
                Secondary Access
              </span>
              <div className="bg-outline-variant/20 h-[1px] flex-grow"></div>
            </div>

            <Button
              className="bg-surface-container-highest text-on-surface/70 hover:text-primary font-headline hover:bg-surface-bright border-primary/5 hover:border-primary/20 w-full rounded border py-3 text-[10px] font-semibold tracking-[0.2em] uppercase transition-all duration-300 active:scale-[0.95]"
              onClick={() => router.push("/workspace")}
            >
              Bypass Protocol
            </Button>
          </div>

          <div className="mt-8 text-center">
            <a
              className="text-on-surface-variant hover:text-primary text-[10px] tracking-widest uppercase transition-colors"
              href="#"
            >
              Request Access Upgrade
            </a>
          </div>
        </div>
      </main>

      <footer className="bg-surface fixed bottom-0 z-40 flex w-full flex-col items-center justify-between gap-4 border-t border-white/5 px-12 py-8 md:flex-row">
        <div className="font-body text-primary text-[10px] tracking-[0.2em] uppercase">
          © 2024 AAPAS KINETIC SYSTEMS. ALL RIGHTS RESERVED.
        </div>
        <div className="flex gap-8">
          <a
            className="font-body text-on-surface/30 hover:text-primary text-[10px] tracking-[0.2em] uppercase transition-opacity"
            href="#"
          >
            Security Protocol
          </a>
          <a
            className="font-body text-on-surface/30 hover:text-primary text-[10px] tracking-[0.2em] uppercase transition-opacity"
            href="#"
          >
            Privacy Policy
          </a>
          <a
            className="font-body text-on-surface/30 hover:text-primary text-[10px] tracking-[0.2em] uppercase transition-opacity"
            href="#"
          >
            Terminal Status
          </a>
        </div>
      </footer>
    </div>
  );
}
