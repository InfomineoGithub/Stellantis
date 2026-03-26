"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authClient } from "@/server/better-auth/client";
import { Button, GoogleIcon } from "./ui";

export function HomePage() {
  const router = useRouter();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  const handleGoogleSignIn = async () => {
    await authClient.signIn.social({
      provider: "google",
      callbackURL: "/workspace",
    });
  };

  const handleEmailSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await authClient.signIn.email({
        email,
        password,
        callbackURL: "/workspace",
      });
    } catch (error) {
      console.error("Sign in failed", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-surface text-on-surface font-body selection:bg-primary/30 min-h-screen flex flex-col">
      <nav className="fixed top-0 left-0 right-0 z-50 bg-surface/80 backdrop-blur-md border-b border-white/5">
        <div className="flex justify-between items-center w-full px-8 py-6 max-w-7xl mx-auto">
          <div className="text-2xl font-bold text-on-surface font-headline tracking-tight">
            Stellantis AI
          </div>
          <div className="flex items-center gap-4">
            <Link
              href="/login"
              className="text-on-surface/80 hover:text-white transition-colors duration-300 font-medium"
            >
              Sign In
            </Link>
          </div>
        </div>
      </nav>

      <main className="relative flex-grow pt-32 pb-24 overflow-hidden">
        <div className="absolute top-1/2 right-0 -translate-y-1/2 -z-10 w-3/4 h-full opacity-[0.03] pointer-events-none overflow-hidden select-none">
          <img
            alt="abstract technical wireframe"
            className="w-full h-full object-contain object-right"
            src="https://lh3.googleusercontent.com/aida-public/AB6AXuCFizt-9Ob4uzeiPN54NI7zi0hhlDSUPWguCruZmUdPHBBMC_U0NDSqeOt7je4hraBtg71UrO9gvW_TIc0CmOKhzTTjahkqxqYOkgp78G0rlmHafjV-R7kea3srRrKOB_jdryfvIHBTnEIZ4YOKjj3nNO9gIbJ5mZXjBOxbtpJ7ZxwEdygdKm6FcNh7FF9HJOqms_pXjYjq6_yNWp3jk7ssnDVc7LQgGTL8sONYF-xPUWRuSJrVLNk46OFr5_bVUTTLt2TflgSN2in0"
          />
        </div>

        <div className="max-w-7xl mx-auto px-8 py-12 lg:py-24 grid lg:grid-cols-2 gap-20 items-center">
          <div className="flex flex-col gap-10">
            <div className="space-y-6">
              <h1 className="font-headline text-5xl lg:text-6xl font-bold tracking-tight leading-[1.1] text-on-surface">
                AAPAS: Automotive Parameter Acquisition System
              </h1>
              <p className="text-xl text-on-surface-variant max-w-lg leading-relaxed font-light">
                Transform quarterly vehicle research from weeks of manual reading
                and video review into an automated, supervised workflow.
              </p>
            </div>
            <div className="flex flex-wrap gap-16">
              <div className="space-y-1">
                <div className="text-4xl font-headline font-bold text-primary">
                  160
                </div>
                <div className="text-xs uppercase tracking-widest text-on-surface-variant/60 font-medium">
                  Parameters Extracted
                </div>
              </div>
              <div className="space-y-1">
                <div className="text-4xl font-headline font-bold text-primary">
                  10
                </div>
                <div className="text-xs uppercase tracking-widest text-on-surface-variant/60 font-medium">
                  Parallel Car Processing
                </div>
              </div>
              <div className="space-y-1">
                <div className="text-4xl font-headline font-bold text-primary">
                  100%
                </div>
                <div className="text-xs uppercase tracking-widest text-on-surface-variant/60 font-medium">
                  Source Traceability
                </div>
              </div>
            </div>
          </div>

          <div className="flex justify-center lg:justify-end">
            <div className="w-full max-w-md bg-surface-container-low p-10 rounded-xl minimal-border shadow-sm">
              <div className="space-y-8">
                <div className="text-center space-y-2">
                  <h2 className="text-2xl font-headline font-bold">
                    Terminal Access
                  </h2>
                  <p className="text-on-surface-variant text-sm">
                    Automotive Intelligence Portal
                  </p>
                </div>
                <div className="space-y-6">
                  <Button
                    onClick={handleGoogleSignIn}
                    className="w-full flex items-center justify-center gap-4 py-4 px-6 bg-surface-container-highest border border-white/5 rounded hover:bg-surface-bright group"
                  >
                    <GoogleIcon className="w-5 h-5" />
                    <span className="font-bold text-on-surface text-sm tracking-wide">
                      Sign in with Google
                    </span>
                  </Button>

                  <div className="relative py-2">
                    <div className="absolute inset-0 flex items-center">
                      <div className="w-full border-t border-white/5"></div>
                    </div>
                    <div className="relative flex justify-center text-xs uppercase tracking-widest text-on-surface-variant/40">
                      <span className="bg-surface-container-low px-3 italic">
                        or
                      </span>
                    </div>
                  </div>

                  <form className="space-y-4" onSubmit={handleEmailSignIn}>
                    <div className="space-y-1">
                      <label className="text-xs uppercase tracking-widest text-on-surface-variant/60 ml-1">
                        Terminal ID (Email)
                      </label>
                      <input
                        className="w-full bg-surface-container-lowest border border-white/5 focus:border-primary/50 focus:ring-0 transition-all py-3.5 px-4 text-sm placeholder:text-on-surface-variant/30 rounded"
                        placeholder="user@kinetic-systems.com"
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs uppercase tracking-widest text-on-surface-variant/60 ml-1">
                        Passcode
                      </label>
                      <input
                        className="w-full bg-surface-container-lowest border border-white/5 focus:border-primary/50 focus:ring-0 transition-all py-3.5 px-4 text-sm placeholder:text-on-surface-variant/30 rounded"
                        placeholder="Enter password"
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                      />
                    </div>
                    <Button
                      type="submit"
                      disabled={loading}
                      className="w-full bg-primary text-on-primary-container font-bold py-4 rounded hover:bg-primary/90 shadow-lg mt-4"
                    >
                      {loading ? "Authenticating..." : "Authenticate"}
                    </Button>
                  </form>
                </div>
              </div>
            </div>
          </div>
        </div>

        <section className="max-w-7xl mx-auto px-8 mt-12 relative z-10">
          <div className="feature-box p-12 lg:p-16 rounded-2xl">
            <div className="grid md:grid-cols-3 gap-16">
              <div className="space-y-4">
                <h3 className="font-headline text-lg font-bold text-primary">
                  Automated Research & Extraction
                </h3>
                <p className="text-sm text-on-surface-variant leading-relaxed font-light">
                  AI agents automatically find, download, and read approved PDFs,
                  web pages, and YouTube videos to extract vehicle parameters.
                </p>
              </div>
              <div className="space-y-4">
                <h3 className="font-headline text-lg font-bold text-primary">
                  Human-in-the-Loop Control
                </h3>
                <p className="text-sm text-on-surface-variant leading-relaxed font-light">
                  Analysts are empowered to approve sources, validate live
                  results, and trigger targeted AI corrections through a simple
                  dashboard.
                </p>
              </div>
              <div className="space-y-4">
                <h3 className="font-headline text-lg font-bold text-primary">
                  Seamless Excel Export
                </h3>
                <p className="text-sm text-on-surface-variant leading-relaxed font-light">
                  Completed research is exported directly into the standard
                  quarterly Excel template with a full audit trail for every
                  value.
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="bg-surface border-t border-white/5 mt-auto relative z-20">
        <div className="flex flex-col md:flex-row justify-between items-center w-full px-8 py-12 max-w-7xl mx-auto gap-6">
          <div className="flex flex-col items-center md:items-start gap-2">
            <div className="text-lg font-bold text-on-surface font-headline">
              Stellantis AI
            </div>
            <p className="text-on-surface-variant text-xs opacity-60">
              © 2024 AAPAS Intelligence System.
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-8">
            <a
              className="text-on-surface-variant/60 hover:text-white transition-colors text-sm"
              href="#"
            >
              Privacy
            </a>
            <a
              className="text-on-surface-variant/60 hover:text-white transition-colors text-sm"
              href="#"
            >
              Terms
            </a>
            <a
              className="text-on-surface-variant/60 hover:text-white transition-colors text-sm"
              href="#"
            >
              Security
            </a>
            <a
              className="text-on-surface-variant/60 hover:text-white transition-colors text-sm"
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
