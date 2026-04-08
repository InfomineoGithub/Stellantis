import { betterAuth } from "better-auth";
import { jwt } from "better-auth/plugins";
import { Pool } from "pg";

import { env } from "../../env";

export const auth = betterAuth({
  database: new Pool({
    connectionString: env.DATABASE_URL ?? "",
  }),
  baseURL: process.env.BETTER_AUTH_URL ?? "http://localhost:2026",
  trustedOrigins: [
    process.env.BETTER_AUTH_URL ?? "http://localhost:2026",
    "http://localhost:3000",
  ],
  emailAndPassword: {
    enabled: false,
  },
  socialProviders: {
    google: {
      clientId: env.BETTER_AUTH_GOOGLE_CLIENT_ID ?? "",
      clientSecret: env.BETTER_AUTH_GOOGLE_CLIENT_SECRET ?? "",
    },
  },
  plugins: [jwt()],
});

export type Session = typeof auth.$Infer.Session;
