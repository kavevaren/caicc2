import { lazy, Suspense } from "react";
import { HashRouter, Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";
import { AtomLoader } from "./components/atom/AtomLoader";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Shell } from "./components/shell/Shell";
import { getToken } from "./lib/api";
import { I18nProvider } from "./lib/i18n";

const LoginPage = lazy(() => import("./pages/LoginPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const SummarizePage = lazy(() => import("./pages/SummarizePage"));
const LibraryPage = lazy(() => import("./pages/LibraryPage"));
const ProjectPage = lazy(() => import("./pages/ProjectPage"));
const DocumentViewPage = lazy(() => import("./pages/DocumentViewPage"));
const SchedulePage = lazy(() => import("./pages/SchedulePage"));
const ChatPage = lazy(() => import("./pages/ChatPage"));
const ChatConvoPage = lazy(() =>
  import("./pages/ChatPage").then((m) => ({ default: m.ChatConvoPage })),
);
const ForumPage = lazy(() => import("./pages/ForumPage"));
const ForumAskPage = lazy(() => import("./pages/ForumAskPage"));
const ForumQuestionPage = lazy(() => import("./pages/ForumQuestionPage"));

/** Public routes redirect to /login; authenticated routes render inside the Shell. */
function RequireAuth() {
  const loc = useLocation();
  if (!getToken()) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  return <Shell />;
}

function Fallback() {
  return (
    <div className="page-fallback" aria-busy="true">
      <AtomLoader size={48} />
    </div>
  );
}

/** One ChatConvoPage mount per chat id, so its state resets on thread switch. */
function ChatConvoRoute() {
  const { id } = useParams();
  return <ChatConvoPage key={id ?? "?"} />;
}

export default function App() {
  return (
    <I18nProvider>
      <ErrorBoundary>
        <HashRouter>
          <Suspense fallback={<Fallback />}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route element={<RequireAuth />}>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/summarize" element={<SummarizePage />} />
                <Route path="/library" element={<LibraryPage />} />
                <Route path="/library/:id" element={<DocumentViewPage />} />
                <Route path="/projects/:id" element={<ProjectPage />} />
                <Route path="/schedule" element={<SchedulePage />} />
                <Route path="/chat" element={<ChatPage />} />
                <Route path="/chat/:id" element={<ChatConvoRoute />} />
                <Route path="/forum" element={<ForumPage />} />
                <Route path="/forum/ask" element={<ForumAskPage />} />
                <Route path="/forum/q/:id" element={<ForumQuestionPage />} />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </HashRouter>
      </ErrorBoundary>
    </I18nProvider>
  );
}
