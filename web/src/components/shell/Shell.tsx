import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { CalendarDays, FileText, LayoutDashboard, Library, Menu, MessagesSquare, Moon, Sun } from "lucide-react";
import { AtomLoader } from "../atom/AtomLoader";
import { BrandLockup } from "./Brand";
import { api, setToken } from "../../lib/api";
import { useI18n } from "../../lib/i18n";
import { initials, useDate } from "../../lib/date";
import { useFetch } from "../../lib/useFetch";
import { startJobs } from "../../lib/jobStore";
import { load as scheduleLoad } from "../../lib/scheduleStore";
import { PageActionProvider, usePageActionNode } from "../../lib/pageAction";
import { JobTray } from "../JobTray";
import type { Health, Me } from "../../lib/types";

const NAV = [
  { to: "/", label: "nav.dashboard", icon: LayoutDashboard },
  { to: "/summarize", label: "nav.summarize", icon: FileText },
  { to: "/library", label: "nav.library", icon: Library },
  { to: "/schedule", label: "nav.schedule", icon: CalendarDays },
  { to: "/forum", label: "nav.forum", icon: MessagesSquare },
];

function HealthBanner() {
  const { t } = useI18n();
  const { data, loading } = useFetch<Health>(() => api.get("health"), []);
  const status = loading ? "checking" : data?.modelscope;
  if (status === "ok" || status === undefined) return null;
  if (status === "checking") {
    return (
      <div className="banner primary" role="status">
        <AtomLoader size={20} />
        {t("banner.starting")}
      </div>
    );
  }
  return (
    <div className="banner danger" role="alert">
      {status === "invalid_token" ? t("banner.tokenInvalid") : t("banner.unreachable")}
    </div>
  );
}

export function Shell() {
  return (
    <PageActionProvider>
      <ShellInner />
    </PageActionProvider>
  );
}

function ShellInner() {
  const { t, lang, setLang } = useI18n();
  const { fullDate } = useDate();
  const navigate = useNavigate();
  const route = useLocation().pathname;
  const [open, setOpen] = useState(false);
  const pageAction = usePageActionNode();

  const me = useFetch<Me>(() => api.get("me"), []);
  const user = me.data?.user;

  // Sync the language from the user profile once loaded.
  useEffect(() => {
    if (user && (user.lang === "id" || user.lang === "en")) setLang(user.lang);
  }, [user, setLang]);

  // Apply the stored theme on first login (before the user chooses locally).
  useEffect(() => {
    if (!user) return;
    let saved = "";
    try {
      saved = localStorage.getItem("orvina-theme") ?? "";
    } catch {
      saved = "";
    }
    if (!saved && (user.theme === "light" || user.theme === "dark")) {
      document.documentElement.dataset.theme = user.theme;
    }
  }, [user]);

  // FEAT-02 / BUG-21: start the job + schedule stores once logged in.
  useEffect(() => {
    if (user) {
      startJobs();
      void scheduleLoad();
    }
  }, [user]);

  // Refresh schedule data when entering the schedule page (shared store).
  useEffect(() => {
    if (route.startsWith("/schedule")) void scheduleLoad();
  }, [route]);

  // Close the drawer on navigation; close on Escape.
  useEffect(() => setOpen(false), [route]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const toggleTheme = () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("orvina-theme", next);
    } catch {
      // storage blocked: the choice still applies for this page load
    }
    api.patch("me", { theme: next }).catch(() => {});
  };

  const logout = async () => {
    try {
      await api.post("auth/logout");
    } catch {
      // the session may already be gone; clear locally either way
    }
    setToken(null);
    navigate("/login", { replace: true });
  };

  const name = user?.display_name || user?.username || "";
  const isDash = route === "/";
  const subKey = route.startsWith("/library")
    ? "library"
    : route.startsWith("/summarize")
      ? "summarize"
      : route.startsWith("/schedule")
        ? "schedule"
        : route.startsWith("/forum")
          ? "forum"
          : route.startsWith("/projects")
            ? "project"
            : route.startsWith("/chat")
              ? "chat"
              : "";
  const title = isDash ? t("greeting", { name }) : t(`${subKey}.title`);
  const sub = isDash ? fullDate(new Date().toISOString()) : t(`${subKey}.subtitle`);

  return (
    <div className="app">
      <a className="sr-only" href="#main">
        {t("common.skipToContent")}
      </a>
      <div className={`scrim ${open ? "show" : ""}`} onClick={() => setOpen(false)} />
      <aside className={`sidebar ${open ? "open" : ""}`} aria-label={t("nav.aria")}>
        <div className="brand">
          <BrandLockup />
        </div>
        <nav>
          <ul className="nav">
            {NAV.map((item) => (
              <li key={item.to}>
                <NavLink to={item.to} end={item.to === "/"}>
                  <item.icon className="i" aria-hidden="true" />
                  {t(item.label)}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <div className="me">
          <span className="avatar" aria-hidden="true">
            {initials(name)}
          </span>
          <div className="who">
            <strong>{name}</strong>
            <span>{user?.username ?? "…"}</span>
          </div>
          <button type="button" className="logout" onClick={logout}>
            {t("nav.logout")}
          </button>
        </div>
      </aside>

      <main className="main" id="main">
        <header className="top">
          <button
            type="button"
            className="icon-btn menu-btn burger"
            aria-label={t("common.menu")}
            aria-controls="sidebar"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            <Menu className="i" aria-hidden="true" />
          </button>
          <div>
            <h1>{title}</h1>
            <p className="date">{sub}</p>
          </div>
          <div className="tools">
            {pageAction}
            <div className="lang" role="group" aria-label={t("login.language")}>
              <button type="button" aria-pressed={lang === "id"} onClick={() => setLang("id")}>
                ID
              </button>
              <button type="button" aria-pressed={lang === "en"} onClick={() => setLang("en")}>
                EN
              </button>
            </div>
            <button
              type="button"
              className="icon-btn theme-btn"
              aria-label={document.documentElement.dataset.theme === "dark" ? t("theme.toLight") : t("theme.toDark")}
              onClick={toggleTheme}
            >
              <Sun className="i sun" aria-hidden="true" />
              <Moon className="i moon" aria-hidden="true" />
            </button>
          </div>
        </header>
        <HealthBanner />
        <Outlet />
        <JobTray />
      </main>
    </div>
  );
}
