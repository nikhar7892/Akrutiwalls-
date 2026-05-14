# Akrutiwalls MCA

Internal MCA compliance workspace for private limited companies. Phase 1 focuses on
**company master creation** with manual entry + document upload. Your team and your
clients log in to a per-company workspace; team members can be granted access to many
companies, while client users see exactly one.

> This is the foundation that later phases build on: parser (MOA/AOA/CIN), auto-
> generation of director report / financials / significant notes, AOC-4 / MGT-7
> extraction, Tally import, and the **Ask Anything** assistant over your universe.

## What's in Phase 1

| Area | Status |
| --- | --- |
| Company **Identity** (CIN, PAN, TAN, GSTIN, class, status, NIC, business nature) | ✅ |
| **Addresses** — versioned, multi-type (registered / corporate / branch …) | ✅ |
| **Capital structure** — append-only history (authorized, paid-up, face value, reason, filing ref) | ✅ |
| **Directors / KMP** — current + past, DIN-based, appointment & cessation | ✅ |
| **Shareholders & cap table** — append-only ledger; cap table computed as-of any date | ✅ |
| **Documents** — Master (MOA/AOA/CIN/PAN/TAN…) + Year-wise (ITR, financials, AOC-4, MGT-7…) | ✅ |
| **Filings log** — SRN, form, FY, status | ✅ |
| **Audit log** for every change | ✅ |
| **Multi-tenant auth** — staff has many memberships, clients have one | ✅ |
| Parser for MOA/AOA/CIN | ⏳ Phase 2 |
| Auto director report / financials / notes | ⏳ Phase 3 |
| AOC-4 / MGT-7 extraction, Tally import, Ask Anything | ⏳ Phase 4+ |

## Tech stack

- Next.js 14 (App Router, TypeScript, Server Actions)
- PostgreSQL + Prisma ORM (point-in-time history via `effectiveFrom`/`effectiveTo`)
- NextAuth (credentials, JWT sessions)
- Tailwind CSS
- Local disk storage for files (S3 driver swap path stubbed in `src/lib/storage.ts`)
- Docker + docker-compose for portable deployment

## Getting started (local dev)

```bash
cp .env.example .env
# edit DATABASE_URL and NEXTAUTH_SECRET

npm install
npx prisma migrate dev --name init   # creates DB schema and runs the seed
npm run dev                          # http://localhost:3000
```

Sign in with the seeded admin (defaults `admin@akrutiwalls.local` / `changeme123`),
go to **/admin** to create your first company and grant memberships.

## Getting started (Docker)

```bash
cp .env.example .env
docker compose up --build -d
docker compose exec app sh -c "npx prisma migrate deploy && npm run seed"
```

App on `http://localhost:3000`, Postgres on `5432`, uploads persisted in the
`storage-data` volume.

## User model

- `ADMIN` — your superuser (can create companies, users, grant memberships)
- `STAFF` — your team member (granted memberships to client companies)
- `CLIENT` — external user (typically one membership; client side)

A **Membership** is the join table `(user, company, role)` where role is OWNER /
EDITOR / VIEWER inside that company. A staff user with multiple memberships picks
the active company on login; switching = sign out and pick again. Session is
always bound to exactly one company at a time.

## Versioning model (why append-only)

MCA data is point-in-time:
- AOC-4 / MGT-7 need *as of 31 March of the FY*
- Director rotation needs *who was on the board on date X*
- Cap table queries need *what was the holding on date Y*

So **Address**, **CapitalHistory**, **Directorship**, and **ShareholdingEntry**
are append-only. Each row has `effectiveFrom` / `effectiveTo` (or `appointmentDate`
/ `cessationDate`). Adding a new "current" row auto-closes the prior open row.
Cap table is the running sum of share-movement entries up to the queried date.

## Documents

- **Master**: forever, no FY (MOA, AOA, CIN cert, PAN, TAN, GST cert, board seal,
  registered office proof, board resolutions).
- **Year-wise**: FY-tagged (ITR, audited financials, AOC-4, MGT-7, DIR-3 KYC,
  board report, AGM minutes, significant notes, auditor's report).
- **Filing attachments**: linked to a Filing row.

Stored locally under `./storage/<companyId>/<timestamp>-<sha>-<filename>`. Switch
to S3 by setting `STORAGE_DRIVER=s3` and implementing the driver branch in
`src/lib/storage.ts`.

## Hosting

The image is portable (`output: "standalone"`). Recommended for India clients:

- **Self-host on a VPS in an India region** (Hetzner Falkenstein has India PoP via
  CDN, or use Linode Mumbai / AWS Mumbai / DigitalOcean Bangalore) for data
  residency. Put the app behind Caddy / nginx with TLS.
- **Backups**: `pg_dump` on a cron + storage volume snapshot.
- **Secrets**: keep `NEXTAUTH_SECRET` and DB credentials in `.env` (root-only
  read on the server) or use the host's secret manager.

## Roadmap (post-Phase 1)

1. **Parser pipeline**: PDF text + tables → extract clauses (objects, capital,
   subscribers) → reviewable diff before applying to master.
2. **Auto director report / financials / notes**: templated generation from master
   + year-wise figures + previous year's docs.
3. **Form extraction**: derive AOC-4 / MGT-7 fields from master + Tally / financials.
4. **Ask Anything assistant**: tool-using LLM with tools like
   `get_cap_table(date)`, `get_documents(type, fy)`, `get_directors(date)`,
   `get_capital_history()` — answers either return data, tables, or the matching
   PDF. The current schema is already shaped to back these tools.
