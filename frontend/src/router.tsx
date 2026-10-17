import { createRootRoute, createRoute, createRouter, Outlet, type RouterHistory } from "@tanstack/react-router"
import { AppLayout } from "./layouts/AppLayout"
import { AiSystemPage } from "./pages/AiSystem"
import { AiSystemsPage } from "./pages/AiSystems"
import { AssetsPage } from "./pages/Assets"
import { ControlDetailPage } from "./pages/ControlDetail"
import { NiaControlPage } from "./pages/NiaControl"
import { PoliciesPage } from "./pages/Policies"
import { AuditsPage } from "./pages/Audits"
import { AuditDetailPage } from "./pages/AuditDetail"
import { FindingPage } from "./pages/Finding"
import { FindingsPage } from "./pages/Findings"
import { MyTrainingPage } from "./pages/MyTraining"
import { UsersPage } from "./pages/Users"
import { TrainingPage } from "./pages/Training"
import { CourseEditorPage } from "./pages/CourseEditor"
import { CoursePlayerPage } from "./pages/CoursePlayer"
import { PrivacyPage } from "./pages/Privacy"
import { ProcessingActivityPage } from "./pages/ProcessingActivity"
import { BreachDetailPage } from "./pages/privacy/BreachDetail"
import { RequestDetailPage } from "./pages/privacy/RequestDetail"
import { DocumentDetailPage } from "./pages/DocumentDetail"
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
  validateSearch: (
    search: Record<string, unknown>,
  ): {
    framework?: "nia" | "iso42001" | "soc2"
    domain?: string
    theme?: string
    q?: string
    owner?: string
    status?: string
  } => ({
    status: typeof search.status === "string" && /^[a-z_]{2,20}$/.test(search.status) ? search.status : undefined,
    framework:
      search.framework === "nia" || search.framework === "iso42001" || search.framework === "soc2"
        ? search.framework
        : undefined,
    domain: typeof search.domain === "string" && /^[A-Z]{2}$/.test(search.domain) ? search.domain : undefined,
    theme: typeof search.theme === "string" && search.theme ? search.theme : undefined,
    q: typeof search.q === "string" && search.q ? search.q : undefined,
    owner: search.owner === "none" || search.owner === "me" ? search.owner : undefined,
  }),
  component: ControlsPage,
})
const controlRoute = createRoute({ getParentRoute: () => appRoute, path: "/controls/$code", component: ControlDetailPage })
const niaControlRoute = createRoute({ getParentRoute: () => appRoute, path: "/nia/$ref", component: NiaControlPage })
const auditsRoute = createRoute({ getParentRoute: () => appRoute, path: "/audits", component: AuditsPage })
const auditRoute = createRoute({ getParentRoute: () => appRoute, path: "/audits/$id", component: AuditDetailPage })
const findingsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/findings",
  validateSearch: (search: Record<string, unknown>): { overdue?: boolean } => ({
    overdue: search.overdue === true || search.overdue === "true" ? true : undefined,
  }),
  component: FindingsPage,
})
const findingRoute = createRoute({ getParentRoute: () => appRoute, path: "/findings/$id", component: FindingPage })
const myTrainingRoute = createRoute({ getParentRoute: () => appRoute, path: "/my-training", component: MyTrainingPage })
const trainingRoute = createRoute({ getParentRoute: () => appRoute, path: "/training", component: TrainingPage })
const courseRoute = createRoute({ getParentRoute: () => appRoute, path: "/training/$id", component: CourseEditorPage })
const coursePlayerRoute = createRoute({ getParentRoute: () => appRoute, path: "/my-training/$id", component: CoursePlayerPage })
const PRIVACY_TABS = ["activities", "inventory", "requests", "breaches", "processors", "pdppl"] as const
const privacyRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/privacy",
  validateSearch: (search: Record<string, unknown>): { tab?: (typeof PRIVACY_TABS)[number] } => ({
    tab: PRIVACY_TABS.includes(search.tab as (typeof PRIVACY_TABS)[number]) ? (search.tab as (typeof PRIVACY_TABS)[number]) : undefined,
  }),
  component: PrivacyPage,
})
const requestRoute = createRoute({ getParentRoute: () => appRoute, path: "/privacy/requests/$id", component: RequestDetailPage })
const breachRoute = createRoute({ getParentRoute: () => appRoute, path: "/privacy/breaches/$id", component: BreachDetailPage })
const activityRoute = createRoute({ getParentRoute: () => appRoute, path: "/privacy/$id", component: ProcessingActivityPage })
const usersRoute = createRoute({ getParentRoute: () => appRoute, path: "/users", component: UsersPage })
const policiesRoute = createRoute({ getParentRoute: () => appRoute, path: "/policies", component: PoliciesPage })
const documentRoute = createRoute({ getParentRoute: () => appRoute, path: "/policies/$id", component: DocumentDetailPage })
const evidenceRoute = createRoute({ getParentRoute: () => appRoute, path: "/evidence", component: ReviewQueuePage })
const risksRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/risks",
  validateSearch: (search: Record<string, unknown>): { status?: string; level?: string } => ({
    status: typeof search.status === "string" && /^[a-z_]{2,30}$/.test(search.status) ? search.status : undefined,
    level: typeof search.level === "string" && /^[a-z_]{2,30}$/.test(search.level) ? search.level : undefined,
  }),
  component: RisksPage,
})
const riskSnapshotsRoute = createRoute({ getParentRoute: () => appRoute, path: "/risks/snapshots", component: RiskSnapshotsPage })
const riskRoute = createRoute({ getParentRoute: () => appRoute, path: "/risks/$code", component: RiskDetailPage })
const riskNewRoute = createRoute({ getParentRoute: () => appRoute, path: "/risks/new", component: RiskNewPage })
const riskAssessRoute = createRoute({ getParentRoute: () => appRoute, path: "/risks/$code/assess", component: RiskWizardPage })
const assetsRoute = createRoute({ getParentRoute: () => appRoute, path: "/assets", component: AssetsPage })
const aiRoute = createRoute({ getParentRoute: () => appRoute, path: "/ai", component: AiSystemsPage })
const aiSystemRoute = createRoute({ getParentRoute: () => appRoute, path: "/ai/$id", component: AiSystemPage })
const soaRoute = createRoute({ getParentRoute: () => appRoute, path: "/soa", component: SoaPage })
const styleguideRoute = createRoute({ getParentRoute: () => appRoute, path: "/styleguide", component: Styleguide })

export const routeTree = rootRoute.addChildren([
  loginRoute,
  appRoute.addChildren([dashboardRoute, complianceRoute, controlsRoute, controlRoute, niaControlRoute, policiesRoute, documentRoute, auditsRoute, auditRoute, findingsRoute, findingRoute, myTrainingRoute, usersRoute, trainingRoute, courseRoute, coursePlayerRoute, privacyRoute, activityRoute, requestRoute, breachRoute, evidenceRoute, risksRoute, riskNewRoute, riskSnapshotsRoute, riskRoute, riskAssessRoute, assetsRoute,
    aiRoute,
    aiSystemRoute, soaRoute, styleguideRoute]),
])

export function createAppRouter(history?: RouterHistory) {
  return createRouter({ routeTree, history })
}

declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof createAppRouter>
  }
}
