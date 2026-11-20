import { createRootRoute, Link, Outlet } from "@tanstack/react-router";
import { TanStackRouterDevtools } from "@tanstack/react-router-devtools";

function RootLayout() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <Link className="brand" to="/">
          Torch Board
        </Link>
      </header>
      <main className="page-content">
        <Outlet />
      </main>
      {import.meta.env.DEV ? <TanStackRouterDevtools /> : null}
    </div>
  );
}

export const Route = createRootRoute({
  component: RootLayout,
  notFoundComponent: () => (
    <section className="state-panel" aria-labelledby="not-found-title">
      <h1 id="not-found-title">Page not found</h1>
      <p>The page you requested does not exist.</p>
      <Link to="/">Return to experiments</Link>
    </section>
  ),
});
