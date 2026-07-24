# frontend/core

Entry point, top-level app shell, and global styling — the files directly under `frontend/src/` (not `api/`, `components/`, or `pages/`).

## frontend/src/main.jsx
Bootstraps the React app by mounting `<App />` into the `#root` DOM node inside `React.StrictMode`, and imports the global stylesheet.

- No exported components or functions — this is the Vite/React entry script.

## frontend/src/App.jsx
Renders the page header/nav and switches between the four tabs, firing a page-view analytics beacon on every tab change.

- `TABS` — `['Discover', 'Backtest', 'Digest', 'Pipeline']`.
- Each tab page (`Discover`/`Backtest`/`Digest`/`Pipeline`) is `React.lazy`-loaded via dynamic `import()` so the first Discover paint only ships Discover's chunk; the active page renders inside a `<Suspense>` boundary with a lightweight "Loading…" fallback.
- `App()` — renders the sticky header (title, tagline, tab nav), the active tab's page component, and a footer with the `AdminUnlock` control; on each tab change calls `api.pageView({ path, referrer })` (best-effort, errors are swallowed so analytics never break the UI).

## frontend/src/hooks/useAdmin.js
Operator ("admin") unlock state: the secret is kept only in `localStorage` and sent as the `X-Admin-Secret` header on operator-only calls, so spend/send controls stay hidden on the public UI.

- `getAdminSecret() -> string` / `setAdminSecret(value)` — read/write the stored secret (writing notifies subscribed components; storage errors are swallowed).
- `useAdmin() -> { secret, isAdmin, setAdminSecret }` — subscribes a component to admin-state changes so `AdminOnly`/`AdminUnlock` re-render on lock/unlock.

## frontend/src/hooks/useAsyncData.js
Shared data-loading hook consolidating the fetch/loading/error/reload boilerplate the tab pages repeated.

- `useAsyncData(loader)` — runs the async `loader` on mount, tracking a `'loading' | 'success' | 'error'` `state` and the returned `data`; returns `{ data, state, reload, setData }` where `reload()` re-runs the loader and `setData` lets callers patch the cached data (e.g. after a mutation). Expects a stable `loader` reference.

## frontend/src/index.css
Global stylesheet: imports Tailwind's base/components/utilities layers, sets the page body font/colors, and defines the shared `.label-mono` utility class used for small uppercase mono labels across components.
