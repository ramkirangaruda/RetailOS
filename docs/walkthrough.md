# RetailOS Frontend Walkthrough

A Next.js (App Router, TypeScript) dashboard consuming the FastAPI backend
at `http://localhost:8000`. Updated to reflect the current state after a
later fix session added API authentication and wired up two previously
unused components.

## What's built

### 1. TypeScript types
**File:** `frontend/src/types/kpi.ts`

`DailyRevenue`, `CitySales`, `StockoutRisk`, `CustomerDistribution`,
`ProductPair`, `AIDecision`.

### 2. API service layer
**File:** `frontend/src/services/api.ts`

- `fetchApi<T>()` sends every request with an `X-API-Key` header (see
  "Authentication" below) - a prior version of this file had no auth at
  all, which broke once the backend started requiring it.
- Typed functions: `getDailyRevenue()`, `getCitySales()`,
  `getStockoutRisks()`, `getCustomerDistribution()`,
  `getTopProductPairs()`, `getAIDecisions()`.
- Custom `ApiError` class for structured error handling.

### 3. `useApi` hook
**File:** `frontend/src/hooks/useApi.ts`

Generic hook providing `data`/`loading`/`error`, with cleanup on unmount.

### 4. Dashboard components
**Directory:** `frontend/src/components/dashboard/`

| Component | Renders on the main page? |
|---|---|
| `StatCard.tsx` | ✅ |
| `RevenueChart.tsx` | ✅ |
| `CitySalesChart.tsx` | ✅ |
| `StockoutTable.tsx` | ✅ |
| `CustomerChart.tsx` | ✅ |
| `ProductPairsTable.tsx` | ✅ (new - market basket pairs) |
| `AIDecisionFeed.tsx` | ✅ (previously built but never rendered - see below) |
| `LoadingSkeleton.tsx` (`SkeletonCard`/`SkeletonChart`/`SkeletonTable`) | used throughout |

**Fixed in this pass:** `frontend/src/app/page.tsx` previously imported
and rendered `CustomerChart` but then had a static
`<p>Coming soon...</p>` placeholder where product-pair and AI-decision
panels should have gone - despite `ProductPair`/`AIDecision` types,
`getTopProductPairs()`/`getAIDecisions()`, and even the fully-built
`AIDecisionFeed.tsx` component already existing and the backend already
returning real data. Added `ProductPairsTable.tsx` and wired both into
`page.tsx`.

### 5. Main dashboard page
**File:** `frontend/src/app/page.tsx`

- Four stat cards (total revenue, avg daily revenue, active cities, total
  customers) computed from the fetched data.
- Revenue + city-sales charts, customer distribution, product-pairs table,
  stockout table, AI decision feed - all fetching real data, all with
  loading skeletons and a top-level error banner.

### 6. Environment configuration
**File:** `frontend/.env.local`

```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_KEY=demo-analyst-key
```

`NEXT_PUBLIC_API_KEY` is new (added alongside the backend's auth layer).
See the note in `api.ts` and `docs/STORAGE.md`: shipping an API key in a
`NEXT_PUBLIC_*` var means it's visible in the browser bundle, which is
fine for demonstrating that the backend enforces roles, but is not how a
production app should handle a real secret (should proxy through a
server-side Next.js route instead).

## Design

- Dark theme (`bg-gray-900`/`bg-gray-800`, `border-gray-700`)
- Responsive grid: 1 column mobile, 2 tablet, 4 desktop (stat cards)
- Indian Rupee (₹) formatting via `toLocaleString('en-IN')`

## Running it

```bash
# Backend first
uvicorn src.api.server:app --reload

# Then the frontend
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
echo "NEXT_PUBLIC_API_KEY=demo-analyst-key" >> .env.local
npm run dev
```

Dashboard at `http://localhost:3000`. If it shows no data, check the
browser console for `401`/`403` - that means the API key is missing/wrong
or doesn't have the required role (see `docs/STORAGE.md`).

## Verified

```bash
cd frontend
npx tsc --noEmit   # passes, no type errors
npm run build      # succeeds
```

## Not yet done
- `getInventoryTurnover()`/`getDeliveryPerformance()` have no frontend
  type, API function, or component yet - the backend endpoints
  (`/api/kpi/inventory-turnover`, `/api/kpi/delivery-performance`) are
  real and working, just not surfaced in the UI.
- API key currently ships in the client bundle (see above) - a production
  version should proxy through a server-side route instead.
