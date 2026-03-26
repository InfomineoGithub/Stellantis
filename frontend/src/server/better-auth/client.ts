import { createAuthClient } from "better-auth/react";
import { jwtClient } from "better-auth/client/plugins";

export const authClient = createAuthClient({
  plugins: [
    jwtClient()
  ]
});

export type Session = typeof authClient.$Infer.Session;
