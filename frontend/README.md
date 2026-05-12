# Frontend — Birthday Tracker Dashboard

Next.js 16 App Router (TypeScript + Tailwind + shadcn/ui) dashboard for the
Birthday Tracker backend.

## Stack

- **Next.js 16** — App Router, Server + Client Components
- **Tailwind CSS** + **shadcn/ui** (base-ui variant)
- **openapi-fetch** — typed API client generated from the backend's OpenAPI schema
- **react-hook-form** + **Zod** — form validation
- **Vitest** + **@testing-library/react** — unit tests
- **TypeDoc** — API documentation

## Commands

```bash
npm install          # install dependencies
npm run dev          # http://localhost:3000
npm run lint         # ESLint
npm run typecheck    # tsc --noEmit
npm test             # Vitest (unit tests)
npm run build        # production build
npm run gen:api      # regenerate lib/api-types.ts from openapi.json
npm run docs         # generate TypeDoc into docs/
```

## Pages

| Route | Description |
|---|---|
| `/` | Upcoming birthdays (next 30 days) |
| `/contacts` | Contact list with add-contact dialog |
| `/contacts/new` | Issue a collection-request form link |
| `/form/[token]` | Public self-serve form for contacts |

## Environment

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend base URL |
