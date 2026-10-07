import { createRootRoute, createRoute, createRouter, Outlet, type RouterHistory } from "@tanstack/react-router"
import { AppLayout } from "./layouts/AppLayout"
import { ControlsPage } from "./pages/Controls"
import { DashboardPage } from "./pages/Dashboard"
import { LoginPage } from "./pages/Login"
import { Styleguide } from "./pages/Styleguide"

const rootRoute = createRootRoute({ component: () => <Outlet /> })

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  validateSearch: (search: Record<string, unknown>): { next?: string } => ({
    next: typeof search.next === "string" ? search.next : undefined,
  }),
  component: LoginPage,
})

const appRoute = createRoute({ getParentRoute: () => rootRoute, id: "app", component: AppLayout })
const dashboardRoute = createRoute({ getParentRoute: () => appRoute, path: "/", component: DashboardPage })
const controlsRoute = createRoute({ getParentRoute: () => appRoute, path: "/controls", component: ControlsPage })
const styleguideRoute = createRoute({ getParentRoute: () => appRoute, path: "/styleguide", component: Styleguide })

export const routeTree = rootRoute.addChildren([
  loginRoute,
  appRoute.addChildren([dashboardRoute, controlsRoute, styleguideRoute]),
])

export function createAppRouter(history?: RouterHistory) {
  return createRouter({ routeTree, history })
}

declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof createAppRouter>
  }
}
