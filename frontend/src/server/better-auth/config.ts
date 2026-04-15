import { betterAuth } from "better-auth";
import { jwt } from "better-auth/plugins";
import { Pool } from "pg";

import { env } from "../../env";

export const auth = betterAuth({
  baseURL: env.NEXT_PUBLIC_BACKEND_BASE_URL ?? "http://localhost:2026",
  database: new Pool({
    connectionString: env.DATABASE_URL ?? "",
  }),
  emailAndPassword: {
    enabled: false,
  },
  socialProviders: {
    google: {
      clientId: env.BETTER_AUTH_GOOGLE_CLIENT_ID ?? "",
      clientSecret: env.BETTER_AUTH_GOOGLE_CLIENT_SECRET ?? "",
    },
  },
  trustedOrigins: [
    "http://localhost:2026",
    "http://127.0.0.1:2026",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://35-233-7-70.nip.io:2026/",
    env.NEXT_PUBLIC_BACKEND_BASE_URL ?? ""
  ].filter(Boolean),
  plugins: [
    jwt()
  ]
});

export type Session = typeof auth.$Infer.Session;
