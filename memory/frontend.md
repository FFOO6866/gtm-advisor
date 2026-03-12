# Frontend Architecture — GTM Advisor Dashboard

## Two-Tier Product Model

### Free Tier (Teaser) — Route `/`
- Renders `Dashboard` component directly (NOT inside AppShell)
- Accessible to both unauthenticated AND authenticated users
- **Header**: uses `teaser` prop → always shows brand "GTM Advisor BETA" + "Upgrade" button; NEVER shows sign-out
- **Layout**: Header + ConversationPanel (left) + AgentNetwork (center) + ResultsPanel (right). NO sidebar.
- **OnboardingModal**: **always** opens on mount — `showOnboarding` initialises to `true` unconditionally (no sessionStorage check). Every visit to `/` shows the modal fresh, whether the user is authenticated or not.
- **ResultsPanel CTAs**: auth-aware — unauthenticated sees "Unlock Full Dashboard" + "Already have account? Sign in"; authenticated sees "Go to Dashboard" (→ `/today`).
- **ConversationPanel**: "Start by entering your company details" area is a clickable button that re-opens the OnboardingModal.

### Paid Tier (AppShell) — Routes `/today`, `/campaigns`, `/prospects`, etc.
- All wrapped in `<AppShell>` in `App.tsx`
- **Auth guard**: AppShell checks `localStorage.gtm_access_token`; redirects to `/login?next={path}` if absent
- **Header**: no `teaser` prop → shows sign-out button, no brand text, no upgrade button
- **Layout**: Header + SidebarNav (left) + `<Outlet>` (right)
- **Hydration**: AppShell reads `localStorage.gtm_company_id` → calls `GET /api/v1/companies/{id}` → sets CompanyContext. `isHydrating` initialised to `true` if a stored ID exists (prevents flash of empty state).

## Routing Map

```
/ (public)               → Dashboard (teaser)
/login (public)          → LoginPage
/register (public)       → RegisterPage
/agent/* (public)        → Agent workspace pages (no auth)

/today       ┐
/campaigns   │
/prospects   │
/content     │  AppShell (requires auth)
/insights    │
/results     │
/approvals   ├
/sequences   │
/workforce   │
/leads       │
/dashboard   │
/sequences   │
/playbooks   │
/settings    │
/why-us      ┘
```

## Key localStorage / sessionStorage Keys

| Key | Storage | Set by | Purpose |
|-----|---------|--------|---------|
| `gtm_access_token` | localStorage | LoginPage | JWT access token |
| `gtm_refresh_token` | localStorage | LoginPage | JWT refresh token |
| `gtm_company_id` | localStorage + sessionStorage | Teaser: sessionStorage (temp then real ID). LoginPage: localStorage (real ID). Both written so AppShell hydration can find it. | Active company UUID for AppShell hydration |
| `gtm_current_company` | sessionStorage | CompanyContext | Full serialised Company object (avoids re-fetch) |
| `gtm_has_onboarded` | sessionStorage | Dashboard (teaser) | Whether teaser onboarding was completed |
| `gtm_company_info` | sessionStorage | Dashboard (teaser) | Raw form data from OnboardingModal |
| `gtm_analysis_id` | sessionStorage | Dashboard (teaser) | Last teaser analysis UUID |
| `gtm_navigated_back` | sessionStorage | `handleAgentClick` (App.tsx) | Still SET when navigating to an agent workspace; still cleared on new analysis / login. No longer READ to gate `showOnboarding` (which is always `true` now). Effectively write-only. |

### Login Cleanup (LoginPage.tsx)
After successful login, ALL teaser sessionStorage keys are cleared so no stale data leaks into the paid app:
```typescript
sessionStorage.removeItem('gtm_has_onboarded');
sessionStorage.removeItem('gtm_company_info');
sessionStorage.removeItem('gtm_analysis_id');
sessionStorage.removeItem('gtm_navigated_back');
sessionStorage.removeItem('gtm_current_company');  // BUG 8 fix
```

### Sign Out (Header.tsx)
```typescript
localStorage.removeItem('gtm_access_token');
localStorage.removeItem('gtm_refresh_token');
localStorage.removeItem('gtm_company_id');
sessionStorage.removeItem('gtm_company_info');
sessionStorage.removeItem('gtm_analysis_id');
sessionStorage.removeItem('gtm_current_company');
window.location.href = '/';
```

## CompanyContext

- Provided at the root (wraps both teaser and AppShell routes)
- `companyId` = `company?.id ?? null`
- Persists to `sessionStorage['gtm_current_company']`
- `useCompanyId()` — used by ALL paid-tier pages to scope API calls

## Header Component

```typescript
interface HeaderProps {
  companyName?: string;
  onNewAnalysis?: () => void;
  teaser?: boolean;  // ← KEY PROP
}

// teaser=true  → isAuthenticated forced to false → shows Zap logo + brand + "Upgrade"
// teaser=false → isAuthenticated from localStorage → shows ONLY sign-out (no logo, no brand)
```

- Teaser page: `<Header teaser />` — shows full logo + brand + upgrade button
- AppShell: `<Header companyName={...} />` — shows only utility actions (help/settings/sign-out); logo is hidden because SidebarNav already shows the workspace icon + company name

## AppShell Hydration Flow

1. Check `localStorage.gtm_company_id` **OR** `sessionStorage.gtm_company_id` (teaser flow writes to sessionStorage)
2. If found + no CompanyContext yet + token present: set `isHydrating=true` immediately (no flash)
3. Call `GET /api/v1/companies/{id}` with Bearer token
4. On success: `setCompany()` → `isHydrating=false` → Outlet renders with valid companyId
5. On failure: remove `gtm_company_id` from **localStorage only** (sessionStorage not touched), `isHydrating=false` → pages show "no company" state

**Critical**: `isHydrating` must be initialised to `true` (not `false`) when a stored ID exists. Otherwise pages mount briefly with `companyId=null` and render empty states.

## Known Backend Quirks

### `products` field in Company
The seed script stores `products` as a list of dicts (`[{name, description, type}]`) but `CompanyResponse` declares `products: list[str]`. Fixed in `company_to_response()`:
```python
products=[
    p if isinstance(p, str) else (p.get("name", str(p)) if isinstance(p, dict) else str(p))
    for p in (company.products or [])
],
```

### Leads API response
`GET /api/v1/companies/{id}/leads` returns `LeadListResponse`, NOT `Lead[]`:
```typescript
{ leads: Lead[], total: int, by_status: {...}, avg_fit_score: float, ... }
```
Always unwrap `.leads`. `fit_score` is 0–100 integer; divide by 100 for display percentages.

### Auth endpoints
- Login: `POST /api/v1/auth/login`
- Register: `POST /api/v1/auth/register`
- (NOT `/api/v1/login` or `/api/v1/register`)

### Company list redirect
`GET /api/v1/companies` (no trailing slash) → 307 → `/api/v1/companies/`. Use trailing slash to avoid redirect.

## Demo Seed Data

- **User**: `demo@himeetai.com` / `himeetai2024` (TIER1)
- **Company**: HiMeetAI Pte. Ltd. (id: `1136d3de-bb4e-4b00-b8ac-7230ff13eaa1`)
- **Data**: 10 leads (Singapore SMEs), 5 market insights, 2 draft campaigns
- **Run seed**: `uv run python scripts/seed_himeetai.py`
- **Important**: Only ONE company should be owned by the user. If the user runs a teaser analysis while logged in, a second owned company is created. Unlink it in SQLite: `UPDATE companies SET owner_id = NULL WHERE id = '{teaser_company_id}'`

## SidebarNav — "Analysis" Link

The "Analysis" entry in the secondary nav (`path: '/'`) is intentional — authenticated users click it to start a NEW analysis run. Because `showOnboarding` is always initialised to `true` on mount, the OnboardingModal opens immediately every time.

## Running Locally

```bash
# Backend (port 8000)
cd /Users/ssfoo/Documents/GitHub/gtm-advisor
uv run uvicorn services.gateway.src.main:app --host 0.0.0.0 --port 8000

# Frontend (port 3000)
cd services/dashboard
pnpm dev --port 3000
```
