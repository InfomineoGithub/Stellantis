import { betterAuth } from "better-auth";
import { jwt } from "better-auth/plugins";
import { Pool } from "pg";

import { env } from "../../env";

export const auth = betterAuth({
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
  plugins: [
    jwt()
  ]
});

export type Session = typeof auth.$Infer.Session;
