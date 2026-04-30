"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";

import { authClient } from "@/server/better-auth/client";

import { Button, GoogleIcon } from "./ui";

export function HomePage() {
  const router = useRouter();

  const handleGoogleSignIn = async () => {
    await authClient.signIn.social({
      provider: "google",
      callbackURL: "/workspace",
    });
  };

  return (
    <div className="bg-surface text-on-surface font-body selection:bg-primary/30 flex min-h-screen flex-col">
      <nav className="bg-surface/80 fixed top-0 right-0 left-0 z-50 border-b border-white/5 backdrop-blur-md">
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-8 py-6">
          <div className="text-on-surface font-headline text-2xl font-bold tracking-tight">
            Stellantis AI
          </div>
          <div className="flex items-center gap-4">
            <Link
              href="/login"
              className="text-on-surface/80 font-medium transition-colors duration-300 hover:text-white"
            >
              Sign In
            </Link>
          </div>
        </div>
      </nav>

      <main className="relative flex-grow overflow-hidden pt-32 pb-24">
        <div className="pointer-events-none absolute top-1/2 right-0 -z-10 h-full w-3/4 -translate-y-1/2 overflow-hidden opacity-[0.03] select-none">
          <img
            alt="abstract technical wireframe"
            className="h-full w-full object-contain object-right"
            src="https://lh3.googleusercontent.com/aida-public/AB6AXuCFizt-9Ob4uzeiPN54NI7zi0hhlDSUPWguCruZmUdPHBBMC_U0NDSqeOt7je4hraBtg71UrO9gvW_TIc0CmOKhzTTjahkqxqYOkgp78G0rlmHafjV-R7kea3srRrKOB_jdryfvIHBTnEIZ4YOKjj3nNO9gIbJ5mZXjBOxbtpJ7ZxwEdygdKm6FcNh7FF9HJOqms_pXjYjq6_yNWp3jk7ssnDVc7LQgGTL8sONYF-xPUWRuSJrVLNk46OFr5_bVUTTLt2TflgSN2in0"
          />
        </div>

        <div className="mx-auto grid max-w-7xl items-center gap-20 px-8 py-12 lg:grid-cols-2 lg:py-24">
          <div className="flex flex-col gap-10">
            <div className="space-y-6">
              <h1 className="font-headline text-on-surface text-5xl leading-[1.1] font-bold tracking-tight lg:text-6xl">
                AAPAS: Automotive Parameter Acquisition System
              </h1>
              <p className="text-on-surface-variant max-w-lg text-xl leading-relaxed font-light">
                Transform quarterly vehicle research from weeks of manual
                reading and video review into an automated, supervised workflow.
              </p>
            </div>
            <div className="flex flex-wrap gap-16">
              <div className="space-y-1">
                <div className="font-headline text-primary text-4xl font-bold">
                  160
                </div>
                <div className="text-on-surface-variant/60 text-xs font-medium tracking-widest uppercase">
                  Parameters Extracted
                </div>
              </div>
              <div className="space-y-1">
                <div className="font-headline text-primary text-4xl font-bold">
                  10
                </div>
                <div className="text-on-surface-variant/60 text-xs font-medium tracking-widest uppercase">
                  Parallel Car Processing
                </div>
              </div>
              <div className="space-y-1">
                <div className="font-headline text-primary text-4xl font-bold">
                  100%
                </div>
                <div className="text-on-surface-variant/60 text-xs font-medium tracking-widest uppercase">
                  Source Traceability
                </div>
              </div>
            </div>
          </div>

          <div className="flex justify-center lg:justify-end">
            <div className="bg-surface-container-low minimal-border w-full max-w-md rounded-xl p-10 shadow-sm">
              <div className="space-y-8">
                <div className="space-y-2 text-center">
                  <h2 className="font-headline text-2xl font-bold">
                    Terminal Access
                  </h2>
                  <p className="text-on-surface-variant text-sm">
                    Automotive Intelligence Portal
                  </p>
                </div>
                <div className="space-y-6">
                  <Button
                    onClick={handleGoogleSignIn}
                    className="bg-surface-container-highest hover:bg-surface-bright group flex w-full items-center justify-center gap-4 rounded border border-white/5 px-6 py-4"
                  >
                    <GoogleIcon className="h-5 w-5" />
                    <span className="text-on-surface text-sm font-bold tracking-wide">
                      Sign in with Google
                    </span>
                  </Button>

                  <div className="pt-4">
                    <Button
                      onClick={() => router.push("/workspace")}
                      className="bg-surface-container-highest text-on-surface/70 hover:text-primary font-headline hover:bg-surface-bright w-full rounded border border-white/5 py-4 text-xs font-semibold tracking-[0.2em] uppercase transition-all duration-300 active:scale-[0.98]"
                    >
                      Bypass Protocol
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <section className="relative z-10 mx-auto mt-12 max-w-7xl px-8">
          <div className="feature-box rounded-2xl p-12 lg:p-16">
            <div className="grid gap-16 md:grid-cols-3">
              <div className="space-y-4">
                <h3 className="font-headline text-primary text-lg font-bold">
                  Automated Research & Extraction
                </h3>
                <p className="text-on-surface-variant text-sm leading-relaxed font-light">
                  AI agents automatically find, download, and read approved
                  PDFs, web pages, and YouTube videos to extract vehicle
                  parameters.
                </p>
              </div>
              <div className="space-y-4">
                <h3 className="font-headline text-primary text-lg font-bold">
                  Human-in-the-Loop Control
                </h3>
                <p className="text-on-surface-variant text-sm leading-relaxed font-light">
                  Analysts are empowered to approve sources, validate live
                  results, and trigger targeted AI corrections through a simple
                  dashboard.
                </p>
              </div>
              <div className="space-y-4">
                <h3 className="font-headline text-primary text-lg font-bold">
                  Seamless Excel Export
                </h3>
                <p className="text-on-surface-variant text-sm leading-relaxed font-light">
                  Completed research is exported directly into the standard
                  quarterly Excel template with a full audit trail for every
                  value.
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="bg-surface relative z-20 mt-auto border-t border-white/5">
        <div className="mx-auto flex w-full max-w-7xl flex-col items-center justify-between gap-6 px-8 py-12 md:flex-row">
          <div className="flex flex-col items-center gap-2 md:items-start">
            <div className="text-on-surface font-headline text-lg font-bold">
              Stellantis AI
            </div>
            <p className="text-on-surface-variant text-xs opacity-60">
              © 2024 AAPAS Intelligence System.
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-8">
            <a
              className="text-on-surface-variant/60 text-sm transition-colors hover:text-white"
              href="#"
            >
              Privacy
            </a>
            <a
              className="text-on-surface-variant/60 text-sm transition-colors hover:text-white"
              href="#"
            >
              Terms
            </a>
            <a
              className="text-on-surface-variant/60 text-sm transition-colors hover:text-white"
              href="#"
            >
              Security
            </a>
            <a
              className="text-on-surface-variant/60 text-sm transition-colors hover:text-white"
              href="#"
            >
              Contact
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
