/**
 * Floating job tray (FEAT-02). Bottom-centre card, no animation.
 *
 * - One card per job: kind icon, label, translated stage, percent bar
 *   (role="progressbar", aria-live="polite"), "Lihat hasil" when done.
 * - 2+ jobs: a collapse pill "N proses berjalan" toggles the full list.
 * - A short toast when a job just finished (auto-dismissed).
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertCircle, CalendarDays, CheckCircle2, FileText, X } from "lucide-react";
import { useI18n } from "../lib/i18n";
import { clearFinished, dismissJob, useJobs } from "../lib/jobStore";
import type { Job } from "../lib/types";

const KIND_ICON: Record<string, typeof FileText> = {
  summary: FileText,
  schedule_import: CalendarDays,
};

function stageLabel(stage: string, t: (k: string) => string): string {
  const key = `jobs.stage.${stage}`;
  const raw = t(key);
  return raw === key ? stage : raw;
}

function resultHref(job: Job): string {
  if (job.kind === "summary" && job.result_document_id) return `/library/${job.result_document_id}`;
  if (job.kind === "schedule_import") return "/schedule";
  return "/library";
}

function JobCard({ job }: { job: Job }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const failed = job.status === "error";
  const done = job.status === "done";
  const Icon = failed ? AlertCircle : (KIND_ICON[job.kind] ?? FileText);
  const percent = done || failed ? 100 : (job.percent ?? 0);
  const label = job.label ?? t(`jobs.kind.${job.kind}`);
  const stage = failed ? t("jobs.stage.error") : stageLabel(job.stage, t);
  const errKey = job.error_code ? `errors.${job.error_code}` : "";
  const rawErr = errKey ? t(errKey) : "";
  const errMsg = failed ? (rawErr === errKey ? t("jobs.stage.error") : rawErr) : "";

  return (
    <div className={`job-card${done ? " job-card--done" : failed ? " job-card--error" : ""}`}>
      <Icon size={16} aria-hidden="true" className="job-card__icon" />
      <div className="job-card__body">
        <div className="job-card__row">
          <span className="job-card__label">{label}</span>
          <span className="job-card__stage" aria-live="polite">
            {done ? (
              <CheckCircle2 size={14} aria-hidden="true" />
            ) : (
              stage
            )}
          </span>
        </div>
        <div
          className="job-card__bar"
          role="progressbar"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={label}
        >
          <div className="job-card__fill" style={{ width: `${percent}%` }} />
        </div>
        <div className="job-card__row job-card__row--foot">
          {failed ? (
            <span className="job-card__err" title={errMsg}>
              {errMsg}
            </span>
          ) : (
            <span className="job-card__pct">{percent}%</span>
          )}
          {done && (
            <button type="button" className="job-card__link" onClick={() => navigate(resultHref(job))}>
              {t("jobs.tray.viewResult")}
            </button>
          )}
          <span className="job-card__spacer" />
          <button
            type="button"
            className="job-card__close"
            aria-label={t("jobs.tray.dismiss")}
            onClick={() => dismissJob(job.id)}
          >
            <X size={14} aria-hidden="true" />
          </button>
        </div>
      </div>
    </div>
  );
}

export function JobTray() {
  const { t } = useI18n();
  const { jobs, lastFinished } = useJobs();
  const [open, setOpen] = useState(true);
  const [toastGone, setToastGone] = useState(false);

  // Auto-dismiss the finished toast after 6 s.
  useEffect(() => {
    if (!lastFinished) {
      setToastGone(false);
      return;
    }
    setToastGone(false);
    const id = window.setTimeout(clearFinished, 6000);
    return () => window.clearTimeout(id);
  }, [lastFinished]);

  if (jobs.length === 0 && !(lastFinished && !toastGone)) return null;

  const active = jobs.filter((j) => j.status === "queued" || j.status === "running");
  const showList = open || active.length < 2 || jobs.length < 2;

  return (
    <div className="job-tray" role="region" aria-label={t("jobs.tray.title")}>
      {lastFinished && !toastGone && (
        <div className="job-tray__toast" role="status">
          <CheckCircle2 size={14} aria-hidden="true" />
          <span>{lastFinished.kind === "summary" ? t("jobs.tray.doneSummary") : t("jobs.tray.doneImport")}</span>
        </div>
      )}
      {jobs.length > 1 && (
        <button
          type="button"
          className="job-tray__pill"
          aria-expanded={showList}
          onClick={() => setOpen((v) => !v)}
        >
          {active.length >= 2
            ? t("jobs.tray.running", { n: active.length })
            : active.length === 1
              ? t("jobs.tray.running1")
              : t("jobs.tray.list")}
        </button>
      )}
      {showList && jobs.length > 0 && <div className="job-tray__list">{jobs.map((j) => <JobCard key={j.id} job={j} />)}</div>}
    </div>
  );
}
