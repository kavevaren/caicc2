import { useNavigate } from "react-router-dom";
import { ChevronRight, FileText, Library as LibraryIcon, MessagesSquare } from "lucide-react";
import { WeekOrbit } from "../components/shell/WeekOrbit";
import { ErrorBox } from "../components/ui/ErrorBox";
import { api, qs } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { initials, useDate } from "../lib/date";
import { useFetch } from "../lib/useFetch";
import type { Dashboard, ProjectItem, QuestionList, WeekDay } from "../lib/types";

/** The dominant agenda kind of a day (for the tile chip colour). */
function kindOf(day: WeekDay): "kelas" | "belajar" | "acara" | "tenggat" | null {
  if (day.events.length === 0) return null;
  const has = (k: string) => day.events.some((e) => e.kind === k);
  if (has("tenggat")) return "tenggat";
  if (has("kelas")) return "kelas";
  if (has("belajar")) return "belajar";
  return "acara";
}

/** "2 sampai 8 November" / "2 to 8 November" (per language). */
function weekRange(startISO: string, endISO: string, months: string[], until: string): string {
  const a = new Date(`${startISO}T00:00:00Z`);
  const b = new Date(`${endISO}T00:00:00Z`);
  if (a.getUTCMonth() === b.getUTCMonth()) {
    if (b.getUTCDate() === a.getUTCDate()) {
      return `${a.getUTCDate()} ${months[a.getUTCMonth()]}`;
    }
    return `${a.getUTCDate()} ${until} ${b.getUTCDate()} ${months[b.getUTCMonth()]}`;
  }
  return `${a.getUTCDate()} ${months[a.getUTCMonth()]} ${until} ${b.getUTCDate()} ${months[b.getUTCMonth()]}`;
}

export default function DashboardPage() {
  const { t, list } = useI18n();
  const d = useDate();
  const nav = useNavigate();

  const dash = useFetch<Dashboard>(() => api.get("dashboard"), []);
  const projects = useFetch<{ items: ProjectItem[] }>(() => api.get("projects"), []);
  const questions = useFetch<QuestionList>(() => api.get(`questions${qs({ page: 1 })}`), []);

  if (dash.error) {
    return <ErrorBox code={dash.error} onRetry={dash.reload} />;
  }

  const data = dash.data;

  if (dash.loading || !data) {
    return (
      <div className="dash-grid" aria-busy="true">
        <div className="dash-main">
          <div className="card hero sk-card">
            <span className="skeleton" />
            <span className="skeleton" />
            <span className="skeleton" />
          </div>
          <div className="card sk-card">
            <span className="skeleton" />
            <span className="skeleton" />
          </div>
        </div>
        <div className="dash-side">
          <div className="card sk-card">
            <span className="skeleton" />
            <span className="skeleton" />
          </div>
          <div className="card sk-card">
            <span className="skeleton" />
            <span className="skeleton" />
          </div>
        </div>
      </div>
    );
  }

  const months = list("week.months");
  const week = data.week;
  const today = d.todayWib();

  const all = week.flatMap((w) => w.events);
  const count = all.length;
  const countKelas = all.filter((e) => e.kind === "kelas").length;
  const countBelajar = all.filter((e) => e.kind === "belajar").length;
  const countTenggat = all.filter((e) => e.kind === "tenggat").length;

  // BUG-07: the count, the empty text and the next-event block all come from
  // the same `week` payload, so they can never contradict each other.
  const next = data.next_event;
  const nextDay = next
    ? (d.wibDay(next.start_at) === today
      ? t("time.today")
      : d.wibDay(next.start_at) === tomorrowOf(today)
        ? t("time.tomorrow")
        : d.wibShortDay(d.wibDay(next.start_at)))
    : "";

  function tomorrowOf(iso: string): string {
    const dt = new Date(`${iso}T00:00:00Z`);
    dt.setUTCDate(dt.getUTCDate() + 1);
    return dt.toISOString().slice(0, 10);
  }

  const rangeLabel = week.length === 7 ? weekRange(week[0].date, week[6].date, months, t("week.until")) : "";

  return (
    <div className="dash-grid">
      <div className="dash-main">
        {/* hero: this week */}
        <section className="card hero" aria-label={t("dashboard.heroWeek", { range: rangeLabel })}>
          <div>
            <p className="hero-week">
              {t("dashboard.heroWeek", { range: rangeLabel })}
            </p>
            <div className="hero-count">
              <span className="hero-num">{count}</span>
              <span className="hero-word">{t(count === 1 ? "dashboard.agenda1" : "dashboard.agendaN")}</span>
            </div>
            <div className="hero-stats">
              <div>
                <span className="lbl">{t("dashboard.statKelas")}</span>
                <b>{countKelas}</b>
              </div>
              <div>
                <span className="lbl">{t("dashboard.statBelajar")}</span>
                <b>{countBelajar}</b>
              </div>
              <div>
                <span className="lbl">{t("dashboard.statTenggat")}</span>
                <b>{countTenggat}</b>
              </div>
            </div>
            {next ? (
              <>
                <p className="hero-time">{d.wibTime(next.start_at)}</p>
                <p className="hero-next-lbl">
                  {t("dashboard.nextLabel", {
                    kind: t(`schedule.kind.${next.kind ?? "belajar"}`),
                    day: nextDay,
                  })}
                </p>
                <p className="hero-next-title">{next.title}</p>
              </>
            ) : (
              <p className="hero-empty">{t("dashboard.emptyWeek")}</p>
            )}
          </div>
          <WeekOrbit week={week} todayISO={today} />
        </section>

        {/* next 7 days */}
        <section className="card">
          <div className="card-head">
            <h2>{t("dashboard.weekTitle")}</h2>
            <a className="more" href="#/schedule">
              {t("dashboard.weekOpen")}
            </a>
          </div>
          <div className="w7-grid">
            {week.map((day) => {
              const i = new Date(`${day.date}T00:00:00Z`).getUTCDay();
              const dow = list("week.short")[(i + 6) % 7];
              const kind = kindOf(day);
              const first = day.events[0];
              return (
                <button
                  key={day.date}
                  type="button"
                  className={`w7-tile${day.date === today ? " today" : ""}`}
                  onClick={() => nav(`/schedule?date=${day.date}`)}
                  aria-label={`${dow} ${Number(day.date.slice(8))}: ${day.events.length} ${t("dashboard.agendaN").toLowerCase()}`}
                >
                  <span className="dow">{dow}</span>
                  <span className="num">{Number(day.date.slice(8))}</span>
                  {first && <span className={`chip${kind ? ` ${kind}` : ""}`}>{first.title}</span>}
                </button>
              );
            })}
          </div>
          <p className="w7-cap">{t("dashboard.week7Caption")}</p>
        </section>
      </div>

      <div className="dash-side">
        {/* library */}
        <section className="card">
          <div className="card-head">
            <h2>
              <LibraryIcon className="i" size={18} aria-hidden="true" />
              {t("dashboard.libTitle")}
            </h2>
            <a className="more" href="#/library">
              {t("dashboard.libAll")}
            </a>
          </div>
          {(projects.data?.items ?? []).length === 0 ? (
            <p className="meta">{t("dashboard.libEmpty")}</p>
          ) : (
            <ul className="mini-list">
              {(projects.data?.items ?? []).slice(0, 4).map((p, i) => (
                <li key={p.id}>
                  <button type="button" className="mini-row" onClick={() => nav(`/projects/${p.id}`)}>
                    <span className={`folder-ic c${i % 4}`} aria-hidden="true">
                      <FileText size={18} />
                    </span>
                    <span className="mini-main">
                      <span className="mini-title">{p.title}</span>
                      <span className="mini-meta">{t("dashboard.projMeta", { n: p.doc_count, time: d.relative(p.updated_at) })}</span>
                    </span>
                    <ChevronRight className="chev" size={16} aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* forum */}
        <section className="card">
          <div className="card-head">
            <h2>
              <MessagesSquare className="i" size={18} aria-hidden="true" />
              {t("dashboard.forumTitle")}
            </h2>
            <a className="more" href="#/forum">
              {t("dashboard.forumOpen")}
            </a>
          </div>
          {(questions.data?.items ?? []).length === 0 ? (
            <p className="meta">{t("dashboard.forumEmpty")}</p>
          ) : (
            <ul className="mini-list">
              {(questions.data?.items ?? []).slice(0, 4).map((q) => (
                <li key={q.id}>
                  <button type="button" className="mini-row" onClick={() => nav(`/forum/q/${q.id}`)}>
                    <span className="avatar" aria-hidden="true">
                      {initials(q.author.display_name || q.author.username)}
                    </span>
                    <span className="mini-main">
                      <span className="mini-title">{q.title}</span>
                      <span className="mini-meta">{q.excerpt ?? ""}</span>
                    </span>
                    <span className="mini-time">{d.relative(q.created_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
