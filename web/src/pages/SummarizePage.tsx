import { useEffect, useRef, useState, type DragEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { FileText, X } from "lucide-react";
import { AtomLoader } from "../components/atom/AtomLoader";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ErrorBox } from "../components/ui/ErrorBox";
import { Input } from "../components/ui/Input";
import { Select } from "../components/ui/Select";
import { ApiError, api, watchJob } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { formatSize } from "../lib/date";
import { useFetch } from "../lib/useFetch";
import { addJob } from "../lib/jobStore";
import type { Job, Subject } from "../lib/types";

const ACCEPT = ".pdf,.pptx,.docx,.txt,.md,.png,.jpg,.jpeg";
const MAX_FILES = 10;
const STYLES = ["one_page", "structured_notes", "key_points", "qa_practice", "flashcards"] as const;

/** Mini paper preview of each summary format; accent lines mark headings or formulas. */
const THUMB_LINES: Record<Exclude<(typeof STYLES)[number], "flashcards">, string[]> = {
  one_page: ["", "", "", "", "", ""],
  structured_notes: ["acc", "", "", "acc", "", ""],
  key_points: ["", "", "", "box", "acc"],
  qa_practice: ["dark", "", "", "dark", "", ""],
};

function StyleThumb({ style }: { style: (typeof STYLES)[number] }) {
  if (style === "flashcards") {
    return (
      <span className="style-thumb style-thumb--cards" aria-hidden="true">
        <span className="mini-card back" />
        <span className="mini-card front">
          <i className="acc" />
          <i />
          <i />
        </span>
      </span>
    );
  }
  return (
    <span className="style-thumb" aria-hidden="true">
      {THUMB_LINES[style].map((kind, i) => (
        <i key={i} className={kind} />
      ))}
    </span>
  );
}
const STAGES = ["queued", "extract", "chunk", "map", "reduce", "check", "deadlines"];

type Phase =
  | { kind: "form" }
  | { kind: "uploading"; pct: number }
  | { kind: "running"; job: Job }
  | { kind: "error"; code: string };

export default function SummarizePage() {
  const { t } = useI18n();
  const nav = useNavigate();
  const fileInput = useRef<HTMLInputElement>(null);

  const [files, setFiles] = useState<File[]>([]);
  const [over, setOver] = useState(false);
  const [title, setTitle] = useState("");
  const [subjectId, setSubjectId] = useState<string>("");
  const [newSubject, setNewSubject] = useState("");
  const [adding, setAdding] = useState(false);
  const [style, setStyle] = useState<(typeof STYLES)[number]>("structured_notes");
  const [outLang, setOutLang] = useState("id");
  const [detail, setDetail] = useState("standar");
  const [notes, setNotes] = useState("");
  const [includeDeadlines, setIncludeDeadlines] = useState(true);
  const [busy, setBusy] = useState(false);
  const [submitErr, setSubmitErr] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>({ kind: "form" });

  const subjects = useFetch<{ items: Subject[] }>(() => api.get("subjects"), []);

  // L7a: while a job runs, re-render once per second for the elapsed timer.
  const [nowTick, setNowTick] = useState(() => Date.now());
  useEffect(() => {
    if (phase.kind !== "running") return;
    const id = setInterval(() => setNowTick(Date.now()), 1000);
    return () => clearInterval(id);
  }, [phase.kind]);

  const addFiles = (list: File[]) => {
    setFiles((cur) => [...cur, ...list].slice(0, MAX_FILES));
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    addFiles(Array.from(e.dataTransfer.files));
  };

  const addSubject = async () => {
    const name = newSubject.trim();
    if (!name || adding) return;
    setAdding(true);
    try {
      const s = await api.post<Subject>("subjects", { name });
      setSubjectId(String(s.id));
      setNewSubject("");
      subjects.reload();
    } catch {
      // keep the input so the user can fix the name
    } finally {
      setAdding(false);
    }
  };

  const start = async () => {
    if (files.length === 0 || busy) return;
    setBusy(true);
    setSubmitErr(null);
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    if (title.trim()) fd.append("title", title.trim());
    if (subjectId) fd.append("subject_id", subjectId);
    fd.append("style", style);
    fd.append("lang", outLang);
    fd.append("detail", detail);
    if (notes.trim()) fd.append("notes", notes.trim());
    fd.append("include_deadlines", includeDeadlines ? "true" : "false");
    try {
      const res = await api.postFormProgress<{ job_id: string }>(
        "summaries",
        fd,
        (loaded, total) => setPhase({ kind: "uploading", pct: total > 0 ? Math.round((loaded / total) * 100) : 0 }),
      );
      // FEAT-02: register the job in the global tray store.
      addJob({ id: res.job_id, kind: "summary", label: files[0].name });
      const first = await api.get<Job>(`jobs/${res.job_id}`);
      setPhase({ kind: "running", job: first });
      watchJob(res.job_id, (j) => setPhase((p) => (p.kind === "running" ? { kind: "running", job: j } : p)))
        .then((job) => {
          if (job.status === "done" && job.result_document_id != null) nav(`/library/${job.result_document_id}`);
          else if (job.status === "error") setPhase({ kind: "error", code: job.error_code ?? "internal_error" });
        })
        .catch((error: unknown) => setPhase({ kind: "error", code: error instanceof ApiError ? error.code : "network_error" }));
    } catch (error) {
      setSubmitErr(error instanceof ApiError ? error.code : "internal_error");
    } finally {
      setBusy(false);
    }
  };

  const toForm = () => setPhase({ kind: "form" });

  if (phase.kind === "uploading") {
    return (
      <Card className="run-card">
        <AtomLoader size={64} />
        <p className="run-title">{t("jobs.kind.summary")}</p>
        <p className="run-stage" aria-live="polite">
          {t("jobs.stage.upload")}
        </p>
        <div className="run-meta">
          <div
            className="prog run-bar"
            role="progressbar"
            aria-label={t("summarize.progressAria")}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={phase.pct}
          >
            <div style={{ width: `${phase.pct}%` }} />
          </div>
          <p className="run-pct">{phase.pct}%</p>
        </div>
      </Card>
    );
  }

  if (phase.kind === "running") {
    const job = phase.job;
    const percent = job.percent ?? 0;
    const prog = job.progress ?? null;
    const label =
      job.stage === "map" && prog && prog.total > 0
        ? t("summarize.mapProgress", { done: Math.min(prog.done + 1, prog.total), total: prog.total })
        : STAGES.includes(job.stage)
          ? t(`summarize.stage.${job.stage}`)
          : t("summarize.running");
    const elapsedSec = Math.max(0, Math.floor((nowTick - new Date(job.created_at).getTime()) / 1000));
    const elapsed =
      Math.floor(elapsedSec / 60) > 0
        ? t("summarize.elapsedMin", { m: Math.floor(elapsedSec / 60), s: elapsedSec % 60 })
        : t("summarize.elapsedSec", { s: elapsedSec });
    const stalled = nowTick - new Date(job.updated_at).getTime() > 3 * 60 * 1000;
    return (
      <Card className="run-card">
        <AtomLoader size={64} />
        <p className="run-title">{t("summarize.running")}</p>
        <p className="run-stage">{label}</p>
        <div className="run-meta">
          <div
            className="prog run-bar"
            role="progressbar"
            aria-label={t("summarize.progressAria")}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percent}
          >
            <div style={{ width: `${percent}%` }} />
          </div>
          <p className="run-pct">{percent}%</p>
          <p className="run-elapsed">{t("summarize.elapsed", { time: elapsed })}</p>
          <p className="run-hint">
            {t("summarize.leaveHint")} <Link to="/library">{t("summarize.library")}</Link>
          </p>
          {stalled && <p className="run-stall">{t("summarize.stall")}</p>}
        </div>
      </Card>
    );
  }

  if (phase.kind === "error") {
    return <ErrorBox code={phase.code} onRetry={toForm} />;
  }

  return (
    <div className="sum-grid">
      <div className="sum-main">
      <Card title={t("summarize.upload")}>
        <div
          className={`drop ${over ? "over" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={onDrop}
          onClick={() => fileInput.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") fileInput.current?.click();
          }}
        >
          <p>{t("summarize.drop")}</p>
          <small>{t("summarize.dropHint")}</small>
        </div>
        <input
          ref={fileInput}
          type="file"
          multiple
          accept={ACCEPT}
          hidden
          onChange={(e) => {
            addFiles(e.target.files ? Array.from(e.target.files) : []);
            e.target.value = "";
          }}
        />
        {files.length > 0 && (
          <div className="file-list">
            {files.map((f, i) => (
              <span key={`${f.name}-${i}`} className="file-chip">
                <FileText className="i" size={14} aria-hidden="true" />
                <span>
                  {f.name} · {formatSize(f.size)}
                </span>
                <button
                  type="button"
                  aria-label={`${t("summarize.removeFile")}: ${f.name}`}
                  onClick={() => setFiles((cur) => cur.filter((_, j) => j !== i))}
                >
                  <X className="i" size={14} aria-hidden="true" />
                </button>
              </span>
            ))}
          </div>
        )}
      </Card>

      <Card title={t("summarize.style")}>
        <p className="style-sub">{t("summarize.styleHint")}</p>
        <div className="style-grid" role="group" aria-label={t("summarize.style")}>
          {STYLES.map((s) => (
            <button
              key={s}
              type="button"
              className={`style-card${s === "flashcards" ? " style-card--wide" : ""}`}
              aria-pressed={style === s}
              onClick={() => setStyle(s)}
            >
              <StyleThumb style={s} />
              <span>
                <b>{t(`summarize.style.${s}`)}</b>
                <small>{t(`summarize.style.${s}.desc`)}</small>
              </span>
            </button>
          ))}
        </div>
      </Card>
      </div>

      <Card title={t("summarize.options")}>
        <div className="options-form">
          <Input
            id="title"
            label={t("summarize.titleLabel")}
            placeholder={t("summarize.titlePlaceholder")}
            value={title}
            maxLength={150}
            onChange={(e) => setTitle(e.target.value)}
          />
          <div className="field">
            <span className="field-label">{t("summarize.subject")}</span>
            <select className="field-input" value={subjectId} onChange={(e) => setSubjectId(e.target.value)}>
              <option value="">—</option>
              {(subjects.data?.items ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            <div className="subject-add">
              <input
                className="field-input"
                placeholder={t("summarize.subjectNewPlaceholder")}
                value={newSubject}
                maxLength={50}
                onChange={(e) => setNewSubject(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    void addSubject();
                  }
                }}
              />
              <Button onClick={() => void addSubject()} disabled={adding || !newSubject.trim()}>
                {t("summarize.subjectAdd")}
              </Button>
            </div>
          </div>
          <Select id="outLang" label={t("summarize.lang")} value={outLang} onChange={(e) => setOutLang(e.target.value)}>
            <option value="id">{t("summarize.lang.id")}</option>
            <option value="en">{t("summarize.lang.en")}</option>
          </Select>
          <Select id="detail" label={t("summarize.detail")} value={detail} onChange={(e) => setDetail(e.target.value)}>
            <option value="singkat">{t("summarize.detail.singkat")}</option>
            <option value="standar">{t("summarize.detail.standar")}</option>
            <option value="detail">{t("summarize.detail.detail")}</option>
          </Select>
          <div className="field">
            <label className="field-label" htmlFor="notes">
              {t("summarize.note")}
            </label>
            <textarea
              id="notes"
              className="field-input"
              maxLength={500}
              placeholder={t("summarize.notePlaceholder")}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
            <span className="field-hint">
              {t("summarize.noteHint")} · {notes.length}/500
            </span>
          </div>
          <div className="field field--check">
            <label htmlFor="includeDeadlines" className="check">
              <input
                id="includeDeadlines"
                type="checkbox"
                checked={includeDeadlines}
                onChange={(e) => setIncludeDeadlines(e.target.checked)}
              />
              <span>{t("summarize.deadlines")}</span>
            </label>
            <span className="field-hint">{t("summarize.deadlinesHint")}</span>
          </div>
          {submitErr && <ErrorBox code={submitErr} />}
          <Button variant="primary" onClick={() => void start()} disabled={busy || files.length === 0}>
            {t("summarize.submit")}
          </Button>
        </div>
      </Card>
    </div>
  );
}
