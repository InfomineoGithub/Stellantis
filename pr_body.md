## Summary
Refactored the authentication system to remove manual email/password registration and login, transitioning to a streamlined **Google OAuth** flow. This update enhances security and simplifies the user experience by leveraging standard identity providers.

## Key Changes
- **Authentication Backend**: Configured `better-auth` with Google Social Provider and disabled `emailAndPassword`.
- **JWT Integration**: Implemented the `jwt()` plugin in `better-auth` to facilitate secure communication between the frontend and backend.
- **Auth Client**: Introduced `auth-fetch.ts` with a `fetchWithAuth` helper that manages token retrieval, caching, and injection into outgoing requests.
- **Database**: Migrated session storage to a PostgreSQL pool using `pg` for better concurrency and reliability.
- **UI/UX**: Updated the landing and login pages to focus purely on the OAuth flow.

## Architecture Comparison
```mermaid
graph TD
    subgraph Old Flow
        A[User] -->|Manual Form| B[Next.js + better-auth]
        B -->|Local Session| C[DB]
    end
    subgraph New Flow
        D[User] -->|Google OAuth| E[Google Provider]
        E -->|Identity| F[Next.js + better-auth]
        F -->|JWT Bearer| G[Gateway / FastAPI Backend]
        F -->|Session| H[PostgreSQL Pool]
    end
```

## Authentication Flow
```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant BetterAuth as better-auth (Next.js)
    participant Google
    participant Backend as Gateway API

    User->>Frontend: Click Login with Google
    Frontend->>BetterAuth: Initiate OAuth
    BetterAuth->>Google: Redirect to Google Login
    Google-->>BetterAuth: Provide user profile
    BetterAuth-->>Frontend: Set session cookie
    Note right of Frontend: Background Token Fetch
    Frontend->>BetterAuth: GET /api/auth/token (+cookie)
    BetterAuth-->>Frontend: JSON { token: '...' }
    Frontend->>Backend: Request with Bearer token
    Backend-->>Frontend: Secure Data
```
