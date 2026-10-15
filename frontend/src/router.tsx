import { createRootRoute, createRoute, createRouter, Outlet, type RouterHistory } from "@tanstack/react-router"
import { AppLayout } from "./layouts/AppLayout"
import { AssetsPage } from "./pages/Assets"
import { ControlDetailPage } from "./pages/ControlDetail"
import { ControlsPage } from "./pages/Controls"
import { DashboardPage } from "./pages/Dashboard"
import { CompliancePage } from "./pages/Compliance"
import { LoginPage } from "./pages/Login"
import { ReviewQueuePage } from "./pages/ReviewQueue"
import { RiskDetailPage } from "./pages/RiskDetail"
import { RiskNewPage } from "./pages/RiskNew"
import { RiskWizardPage } from "./pages/RiskWizard"
import { RisksPage } from "./pages/Risks"
import { RiskSnapshotsPage } from "./pages/RiskSnapshots"
import { SoaPage } from "./pages/Soa"
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
const complianceRoute = createRoute({ getParentRoute: () => appRoute, path: "/compliance", component: CompliancePage })
const controlsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/controls",
  validateSearch: (search: Record<string, unknown>): { theme?: string; q?: string; owner?: string } => ({
    theme: typeof search.theme === "string" && search.theme ? search.theme : undefined,
    q: typeof search.q === "string" && search.q ? search.q : undefined,
    owner: search.owner === "none" || search.owner === "me" ? search.owner : undefined,
  }),
  component: ControlsPage,
})
const controlRoute = createRoute({ getParentRoute: () => appRoute, path: "/controls/$code", component: ControlDetailPage })
const evidenceRoute = createRoute({ getParentRoute: () => appRoute, path: "/evidence", component: ReviewQueuePage })
const risksRoute = createRoute({ getParentRoute: () => appRoute, path: "/risks", component: RisksPage })
const riskSnapshotsRoute = createRoute({ getParentRoute: () => appRoute, path: "/risks/snapshots", component: RiskSnapshotsPage })
const riskRoute = createRoute({ getParentRoute: () => appRoute, path: "/risks/$code", component: RiskDetailPage })
const riskNewRoute = createRoute({ getParentRoute: () => appRoute, path: "/risks/new", component: RiskNewPage })
const riskAssessRoute = createRoute({ getParentRoute: () => appRoute, path: "/risks/$code/assess", component: RiskWizardPage })
const assetsRoute = createRoute({ getParentRoute: () => appRoute, path: "/assets", component: AssetsPage })
const soaRoute = createRoute({ getParentRoute: () => appRoute, path: "/soa", component: SoaPage })
const styleguideRoute = createRoute({ getParentRoute: () => appRoute, path: "/styleguide", component: Styleguide })

export const routeTree = rootRoute.addChildren([
  loginRoute,
  appRoute.addChildren([dashboardRoute, complianceRoute, controlsRoute, controlRoute, evidenceRoute, risksRoute, riskNewRoute, riskSnapshotsRoute, riskRoute, riskAssessRoute, assetsRoute, soaRoute, styleguideRoute]),
])

export function createAppRouter(history?: RouterHistory) {
  return createRouter({ routeTree, history })
}

declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof createAppRouter>
  }
}
