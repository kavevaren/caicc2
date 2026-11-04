import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ChevronLeft,
  ChevronRight,
  Download,
  Lightbulb,
  Pencil,
  Plus,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorBox } from "../components/ui/ErrorBox";
import { usePageAction } from "../lib/pageAction";
import { ApiError, api, downloadEventIcs } from "../lib/api";
import { useDate } from "../lib/date";
import { useI18n } from "../lib/i18n";
import { addJob } from "../lib/jobStore";
import {
  clearSuggestions,
  load as scheduleLoad,
  removeEvent,
  useSchedule,
} from "../lib/scheduleStore";
import type { EventItem, EventSuggestion } from "../lib/types";

const KINDS = ["kelas", "belajar", "acara", "tenggat"] as const;
type Kind = (typeof KINDS)[number];
const SUBKINDS = ["tugas", "kuis", "ujian"] as const;
type Subkind = (typeof SUBKINDS)[number] | "";

const IMPORT_EXTS = [".pdf", ".png", ".jpg", ".jpeg", ".docx", ".xlsx", ".ics"];
const IMPORT_MAX_FILES = 5;
const IMPORT_ACCEPT = IMPORT_EXTS.join(",");

const two = (n: number) => String(n).padStart(2, "0");
const isoAddDays = (iso: string, n: number) => {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
};
const mondayOf = (iso: string) => isoAddDays(iso, -((new Date(`${iso}T00:00:00Z`).getUTCDay() + 6) % 7));

/* ------------------------------------------------------------------ */
/* Modal form (BUG-13: per-field validation)                          */
/* ------------------------------------------------------------------ */

type FormState = {
  title: string;
  kind: Kind;
  subkind: Subkind;
  date: string;
  start: string;
  end: string;
  loc: string;
  repeat: "none" | "weekly";
};

type FormErrors = { title?: string; date?: string; end?: string };

function AgendaModal({
  initial,
  editing,
  onClose,
}: {
  initial: FormState;
  editing: EventItem | null;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const [f, setF] = useState(initial);
  const [errs, setErrs] = useState<FormErrors>({});
  const [busy, setBusy] = useState(false);

  const validate = (s: FormState): FormErrors => {
    const e: FormErrors = {};
    if (s.title.trim().length < 3) e.title = t("schedule.vTitle");
    if (!s.date) e.date = t("schedule.vDate");
    if (s.end && s.date && s.end <= s.start) e.end = t("schedule.vEnd");
    return e;
  };

  const submit = async () => {
    const e = validate(f);
    setErrs(e);
    if (Object.keys(e).length > 0) return;
    setBusy(true);
    const base = {
      title: f.title.trim(),
      kind: f.kind,
      subkind: f.kind === "tenggat" ? (f.subkind || null) : null,
      location: f.loc.trim() || null,
    };
    try {
      if (editing) {
        await api.patch(`events/${editing.id}`, {
          ...base,
          start_at: `${f.date}T${f.start}`,
          end_at: f.end ? `${f.date}T${f.end}` : null,
        });
      } else if (f.repeat === "weekly") {
        // weekly: 8 rows, one per week (the kelas category is weekly-repeatable)
        for (let i = 0; i < 8; i++) {
          await api.post("events", {
            ...base,
            start_at: `${isoAddDays(f.date, 7 * i)}T${f.start}`,
            end_at: f.end ? `${isoAddDays(f.date, 7 * i)}T${f.end}` : undefined,
          });
        }
      } else {
        await api.post("events", {
          ...base,
          start_at: `${f.date}T${f.start}`,
          end_at: f.end ? `${f.date}T${f.end}` : undefined,
        });
      }
      void scheduleLoad();
      onClose();
    } catch (err) {
      setErrs({ title: err instanceof ApiError ? t(`errors.${err.code}`) : t("errors.network_error") });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-scrim" onClick={() => !busy && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={t("schedule.modalTitle")} onClick={(e) => e.stopPropagation()}>
        <h2>{editing ? t("schedule.editTitle") : t("schedule.modalTitle")}</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
          noValidate
        >
          <div className="field">
            <label className="field-label" htmlFor="f-title">
              {t("schedule.fieldTitle")}
            </label>
            <input
              id="f-title"
              className="field-input"
              value={f.title}
              maxLength={150}
              placeholder={t("schedule.titlePlaceholder")}
              onChange={(e) => setF({ ...f, title: e.target.value })}
            />
            {errs.title && (
              <p className="field-error" role="alert">
                {errs.title}
              </p>
            )}
          </div>

          <div className="field">
            <span className="field-label" id="f-kind-label">
              {t("schedule.fieldKind")}
            </span>
            <div className="chips-row" role="group" aria-labelledby="f-kind-label">
              {KINDS.map((k) => (
                <button key={k} type="button" className="chip-btn" aria-pressed={f.kind === k} onClick={() => setF({ ...f, kind: k, subkind: "" })}>
                  {t(`schedule.kind.${k}`)}
                </button>
              ))}
            </div>
            {f.kind === "tenggat" && (
              <div className="chips-row" role="group" aria-label={t("schedule.fieldSubkind")} style={{ marginTop: 8 }}>
                {SUBKINDS.map((k) => (
                  <button key={k} type="button" className="chip-btn" aria-pressed={f.subkind === k} onClick={() => setF({ ...f, subkind: k })}>
                    {t(`schedule.subkind.${k}`)}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="add-grid">
            <div className="field">
              <label className="field-label" htmlFor="f-date">
                {t("schedule.fieldDate")}
              </label>
              <input id="f-date" type="date" className="field-input" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} />
              {errs.date && (
                <p className="field-error" role="alert">
                  {errs.date}
                </p>
              )}
            </div>
            <div className="field">
              <label className="field-label" htmlFor="f-start">
                {t("schedule.fieldStart")}
              </label>
              <input id="f-start" type="time" className="field-input" value={f.start} onChange={(e) => setF({ ...f, start: e.target.value })} />
            </div>
            <div className="field">
              <label className="field-label" htmlFor="f-end">
                {t("schedule.fieldEnd")}
              </label>
              <input id="f-end" type="time" className="field-input" value={f.end} onChange={(e) => setF({ ...f, end: e.target.value })} />
              {errs.end && (
                <p className="field-error" role="alert">
                  {errs.end}
                </p>
              )}
            </div>
            <div className="field">
              <label className="field-label" htmlFor="f-loc">
                {t("schedule.fieldLocation")}
              </label>
              <input id="f-loc" className="field-input" value={f.loc} maxLength={150} onChange={(e) => setF({ ...f, loc: e.target.value })} />
            </div>
          </div>

          <div className="field">
            <span className="field-label" id="f-repeat-label">
              {t("schedule.fieldRepeat")}
            </span>
            <div className="chips-row" role="group" aria-labelledby="f-repeat-label">
              <button type="button" className="chip-btn" aria-pressed={f.repeat === "none"} onClick={() => setF({ ...f, repeat: "none" })}>
                {t("schedule.repeatNone")}
              </button>
              <button type="button" className="chip-btn" aria-pressed={f.repeat === "weekly"} onClick={() => setF({ ...f, repeat: "weekly" })}>
                {t("schedule.repeatWeekly")}
              </button>
            </div>
          </div>

          <div className="form-actions">
            <Button variant="primary" type="submit" disabled={busy}>
              {editing ? t("common.save") : t("schedule.saveSchedule")}
            </Button>
            <Button type="button" onClick={onClose} disabled={busy}>
              {t("common.cancel")}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                               */
/* ------------------------------------------------------------------ */

export default function SchedulePage() {
  const { t, list } = useI18n();
  const d = useDate();
  const short = list("week.short");
  const months = list("week.months");

  const today = d.todayWib();
  const { events, suggestions, notes, loading, error } = useSchedule();

  const [params] = useSearchParams();
  const paramDate = params.get("date");

  const [calYM, setCalYM] = useState(() => (paramDate ?? today).slice(0, 7));
  const [calView, setCalView] = useState<"month" | "week">("month");
  const [selected, setSelected] = useState<string | null>(paramDate);
  const [filter, setFilter] = useState<"semua" | Kind>("semua");
  const [selEvent, setSelEvent] = useState<number | null>(null);

  const [modal, setModal] = useState<{ initial: FormState; editing: EventItem | null } | null>(null);

  /* ---- suggestions: checkboxes + inline edits (FEAT-01 review) ---- */
  const [checked, setChecked] = useState<Record<number, boolean>>({});
  const [edits, setEdits] = useState<Record<number, { title: string; date: string; time: string; kind: Kind }>>({});

  /* ---- import ---- */
  const [files, setFiles] = useState<File[]>([]);
  const [impNotes, setImpNotes] = useState("");
  const [impFileErr, setImpFileErr] = useState("");
  const [impError, setImpError] = useState("");
  const [impOver, setImpOver] = useState(false);
  const [impPosting, setImpPosting] = useState(false);
  const impInput = useRef<HTMLInputElement>(null);

  // Reuse the last import notes (import-meta, FEAT-01).
  useEffect(() => {
    if (notes && files.length === 0) setImpNotes(notes);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [notes]);

  const importBusy = impPosting;

  const byDay = useMemo(() => {
    const m = new Map<string, EventItem[]>();
    for (const ev of events) {
      const day = d.wibDay(ev.start_at);
      const l = m.get(day) ?? [];
      l.push(ev);
      m.set(day, l);
    }
    for (const l of m.values()) l.sort((a, b) => (a.start_at < b.start_at ? -1 : 1));
    return m;
  }, [events, d]);

  /* ---- month / week grid ---- */
  const [calY, calM] = calYM.split("-").map(Number);
  const calCells = useMemo(() => {
    const first = new Date(Date.UTC(calY, calM - 1, 1));
    const lead = (first.getUTCDay() + 6) % 7;
    const start = new Date(first);
    start.setUTCDate(1 - lead);
    return Array.from({ length: 42 }, (_, i) => {
      const dd = new Date(start);
      dd.setUTCDate(start.getUTCDate() + i);
      const iso = dd.toISOString().slice(0, 10);
      return { iso, num: dd.getUTCDate(), inMonth: dd.getUTCMonth() === calM - 1, evs: byDay.get(iso) ?? [] };
    });
  }, [calY, calM, byDay]);

  const weekStart = mondayOf(selected ?? today);
  const weekDays = useMemo(() => Array.from({ length: 7 }, (_, i) => isoAddDays(weekStart, i)), [weekStart]);

  const shiftYM = (n: number) => {
    const dd = new Date(Date.UTC(calY, calM - 1 + n, 1));
    setCalYM(`${dd.getUTCFullYear()}-${two(dd.getUTCMonth() + 1)}`);
  };

  const goToday = () => {
    setSelected(today);
    setCalYM(today.slice(0, 7));
  };

  const pickDay = (iso: string) => {
    setSelected(selected === iso ? null : iso);
    setCalYM(iso.slice(0, 7));
  };

  /* ---- semua agenda: grouped, from today only (BUG-06), kind filter ---- */
  const agenda = useMemo(() => {
    let items = events.filter((e) => d.wibDay(e.start_at) >= today);
    if (selected) items = items.filter((e) => d.wibDay(e.start_at) === selected);
    if (filter !== "semua") items = items.filter((e) => e.kind === filter);
    items.sort((a, b) => (a.start_at < b.start_at ? -1 : 1));
    const groups: { day: string; items: EventItem[] }[] = [];
    for (const e of items) {
      const day = d.wibDay(e.start_at);
      const g = groups[groups.length - 1];
      if (g && g.day === day) g.items.push(e);
      else groups.push({ day, items: [e] });
    }
    return groups;
  }, [events, d, today, selected, filter]);

  /* ---- actions ---- */
  const remove = async (ev: EventItem) => {
    if (!window.confirm(t("schedule.deleteConfirm"))) return;
    removeEvent(ev.id); // optimistic
    try {
      await api.del(`events/${ev.id}`);
      void scheduleLoad();
    } catch {
      void scheduleLoad(); // settle back to the server truth
    }
    setSelEvent(null);
  };

  const acceptOne = async (s: EventSuggestion) => {
    const ed = edits[s.id];
    if (ed) {
      try {
        await api.patch(`suggestions/${s.id}`, {
          title: ed.title,
          start_at: `${ed.date}T${ed.time || "00:00"}`,
          kind: ed.kind,
        });
      } catch {
        // the suggestion keeps its old values; accept below still works
      }
    }
    try {
      await api.post(`suggestions/${s.id}/accept`);
      clearSuggestions([s.id]);
      setCalYM(`${ed?.date ?? s.start_at.slice(0, 7)}`);
      void scheduleLoad();
    } catch {
      // stays pending; the card remains
    }
  };

  const dismissOne = async (s: EventSuggestion) => {
    try {
      await api.post(`suggestions/${s.id}/dismiss`);
      clearSuggestions([s.id]);
    } catch {
      // stays pending
    }
  };

  const acceptBatch = async () => {
    const ids = suggestions.filter((s) => (checked[s.id] ?? true)).map((s) => s.id);
    if (ids.length === 0) return;
    for (const s of suggestions) {
      const ed = edits[s.id];
      if (ed && ids.includes(s.id)) {
        await api.patch(`suggestions/${s.id}`, { title: ed.title, start_at: `${ed.date}T${ed.time || "00:00"}`, kind: ed.kind }).catch(() => null);
      }
    }
    try {
      await api.post("suggestions/accept-batch", { ids });
      clearSuggestions(ids);
      void scheduleLoad();
    } catch {
      // individual items stay
    }
  };

  const dismissBatch = async () => {
    const ids = suggestions.map((s) => s.id);
    if (ids.length === 0) return;
    try {
      await api.post("suggestions/dismiss-batch", { ids });
      clearSuggestions(ids);
    } catch {
      // stays
    }
  };

  /* ---- import (FEAT-01 + BUG-03: one handler per file set) ---- */
  const pickFiles = (incoming: File[]) => {
    if (incoming.length === 0) return;
    const ok: File[] = [];
    for (const f of incoming) {
      const dot = f.name.lastIndexOf(".");
      const ext = dot >= 0 ? f.name.slice(dot).toLowerCase() : "";
      if (IMPORT_EXTS.includes(ext)) ok.push(f);
    }
    if (ok.length !== incoming.length) {
      setImpFileErr(t("schedule.importBadExt"));
      return;
    }
    if (ok.length > IMPORT_MAX_FILES) {
      setImpFileErr(t("schedule.importTooMany"));
      return;
    }    setImpFileErr("");
    setImpError("");
    setFiles(ok);
  };

  const startImport = async () => {
    if (files.length === 0 || importBusy) return;
    setImpPosting(true);
    setImpError("");
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    if (impNotes.trim()) fd.append("notes", impNotes.trim());
    try {
      const res = await api.postFormProgress<{ job_id: string }>("schedule/import", fd);
      // FEAT-02: the global tray tracks the job from here.
      addJob({ id: res.job_id, kind: "schedule_import", label: files[0].name });
      setFiles([]);
    } catch (err) {
      setImpError(err instanceof ApiError ? `errors.${err.code}` : "errors.network_error");
    } finally {
      setImpPosting(false);
    }
  };

  /* ---- page header action ---- */
  const openNew = () =>
    setModal({
      initial: { title: "", kind: "kelas", subkind: "", date: today, start: "08:00", end: "", loc: "", repeat: "none" },
      editing: null,
    });
  const openEdit = (ev: EventItem) => {
    const st = new Date(new Date(ev.start_at).getTime() + 7 * 3600 * 1000);
    setModal({
      initial: {
        title: ev.title,
        kind: ev.kind,
        subkind: (ev.subkind as Subkind) ?? "",
        date: d.wibDay(ev.start_at),
        start: `${two(st.getUTCHours())}:${two(st.getUTCMinutes())}`,
        end: ev.end_at ? `${two(new Date(new Date(ev.end_at).getTime() + 7 * 3600 * 1000).getUTCHours())}:${two(new Date(new Date(ev.end_at).getTime() + 7 * 3600 * 1000).getUTCMinutes())}` : "",
        loc: ev.location ?? "",
        repeat: "none",
      },
      editing: ev,
    });
  };
  usePageAction(
    <Button variant="primary" icon={<Plus className="i" size={16} aria-hidden="true" />} onClick={openNew}>
      {t("schedule.newAgenda")}
    </Button>,
  );

  /* ---- render helpers ---- */
  const chipRange = (ev: EventItem) => {
    const start = d.wibTime(ev.start_at);
    const end = d.wibTime(ev.end_at);
    const range = ev.end_at && end !== start ? t("schedule.range", { a: start, b: end }) : start;
    return t("schedule.kindChip", { kind: t(`schedule.kind.${ev.kind}`), range });
  };

  const srcLabel = (ev: EventItem) =>
    ev.source === "ringkasan" ? t("common.fromSummary") : ev.source === "impor" ? t("schedule.fromImport") : t("schedule.manual");

  if (error) {
    return <ErrorBox code="network_error" onRetry={() => void scheduleLoad()} />;
  }

  return (
    <div className="sched-grid">
      <div className="sched-main">
        {/* upload card */}
        <Card>
          <div
            className={`up-drop${impOver ? " over" : ""}`}
            role="button"
            tabIndex={0}
            aria-label={t("schedule.uploadTitle")}
            onClick={() => impInput.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                impInput.current?.click();
              }
            }}
            onDragOver={(e) => {
              e.preventDefault();
              setImpOver(true);
            }}
            onDragLeave={() => setImpOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setImpOver(false);
              pickFiles(Array.from(e.dataTransfer.files)); // single fire (BUG-03)
            }}
          >
            <span className="up-ic" aria-hidden="true">
              <Upload size={28} />
            </span>
            <p className="up-title">{t("schedule.uploadTitle")}</p>
            <p className="up-desc">{t("schedule.uploadDesc")}</p>
            <div className="up-actions">
              <Button variant="black" onClick={() => impInput.current?.click()}>
                {t("schedule.uploadPick")}
              </Button>
            </div>
          </div>
          <input
            ref={impInput}
            type="file"
            multiple
            accept={IMPORT_ACCEPT}
            hidden
            onChange={(e) => {
              if (e.target.files) pickFiles(Array.from(e.target.files));
              e.target.value = "";
            }}
          />

          {files.length > 0 && (
            <div className="up-files">
              {files.map((f, i) => (
                <div key={`${f.name}-${i}`} className="file-chip">
                  <span className="file-main">
                    <span className="file-name">{f.name}</span>
                    <span className="file-status">{f.size ? `${(f.size / 1024).toFixed(0)} KB` : ""}</span>
                  </span>
                  <button type="button" aria-label={t("common.delete")} onClick={() => setFiles(files.filter((_, k) => k !== i))}>
                    <X size={16} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {files.length > 0 && (
            <div className="up-notes">
              <div className="field">
                <label className="field-label" htmlFor="imp-notes">
                  {t("schedule.impNotes")}
                </label>
                <textarea
                  id="imp-notes"
                  className="field-input"
                  maxLength={500}
                  placeholder={t("schedule.impNotesPlaceholder")}
                  value={impNotes}
                  onChange={(e) => setImpNotes(e.target.value)}
                />
                <span className="field-hint">
                  {t("schedule.impNotesHint")} · {impNotes.length}/500
                </span>
              </div>
              <div className="up-actions" style={{ justifyContent: "flex-start" }}>
                <Button variant="primary" disabled={importBusy} onClick={() => void startImport()}>
                  {t("schedule.impProcess")}
                </Button>
              </div>
            </div>
          )}

          {impFileErr && (
            <p className="form-error" role="alert">
              {impFileErr}
            </p>
          )}
          {impError && (
            <p className="form-error" role="alert">
              {t(impError)}
            </p>
          )}
        </Card>

        {/* calendar */}
        <Card className="cal-card">
          <div className="cal-top">
            <button type="button" className="icon-btn" aria-label={t("schedule.calPrev")} onClick={() => shiftYM(-1)}>
              <ChevronLeft size={18} aria-hidden="true" />
            </button>
            <button type="button" className="icon-btn" aria-label={t("schedule.calNext")} onClick={() => shiftYM(1)}>
              <ChevronRight size={18} aria-hidden="true" />
            </button>
            <span className="cal-month">
              {months[calM - 1]} {calY}
            </span>
            <Button onClick={goToday}>{t("schedule.calToday")}</Button>
            <div className="seg" role="group" aria-label={t("schedule.calView")}>
              <button type="button" aria-pressed={calView === "month"} onClick={() => setCalView("month")}>
                {t("schedule.viewMonth")}
              </button>
              <button type="button" aria-pressed={calView === "week"} onClick={() => setCalView("week")}>
                {t("schedule.viewWeek")}
              </button>
            </div>
          </div>

          {calView === "month" ? (
            <div className="cal-grid" role="grid" aria-label={t("schedule.title")}>
              {short.map((s) => (
                <span key={s} className="cal-dow" aria-hidden="true">
                  {s}
                </span>
              ))}
              {calCells.map((c) => (
                <button
                  key={c.iso}
                  type="button"
                  role="gridcell"
                  className={`cal-cell${c.inMonth ? "" : " out"}${c.iso === today ? " today" : ""}`}
                  aria-pressed={selected === c.iso}
                  aria-label={d.fullDateOnly(c.iso)}
                  onClick={() => pickDay(c.iso)}
                >
                  <span className="cal-num">{c.num}</span>
                  <span className="cal-chips">
                    {c.evs.slice(0, 2).map((ev) => (
                      <span key={ev.id} className={`cal-chip${ev.kind === "kelas" ? " kelas" : ev.kind === "tenggat" ? " tenggat" : ""}`}>
                        {ev.title}
                      </span>
                    ))}
                    {c.evs.length > 2 && <span className="cal-plus">+{c.evs.length - 2}</span>}
                  </span>
                  <span className="cal-dots" aria-hidden="true">
                    {c.evs.slice(0, 3).map((ev) => (
                      <i key={ev.id} />
                    ))}
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <div className="cal-week">
              {weekDays.map((iso) => (
                <div key={iso} className={`cal-col${iso === today ? " today" : ""}`}>
                  <span className="cal-dow">{short[(new Date(`${iso}T00:00:00Z`).getUTCDay() + 6) % 7]}</span>
                  <span className="cal-num">{Number(iso.slice(8))}</span>
                  <span className="cal-chips">
                    {(byDay.get(iso) ?? []).map((ev) => (
                      <span key={ev.id} className={`cal-chip${ev.kind === "kelas" ? " kelas" : ev.kind === "tenggat" ? " tenggat" : ""}`}>
                        {d.wibTime(ev.start_at)} {ev.title}
                      </span>
                    ))}
                  </span>
                </div>
              ))}
            </div>
          )}

          {selected && (
            <p className="meta" style={{ marginTop: 12 }}>
              {t("schedule.selectedDay", { day: d.fullDateOnly(selected) })}{" "}
              <button type="button" className="btn ghost sm" onClick={() => setSelected(null)}>
                {t("common.cancel")}
              </button>
            </p>
          )}
        </Card>
      </div>

      <div className="sched-side">
        {/* suggestions */}
        <section className="saran-card" aria-label={t("schedule.saranTitle")}>
          <h2>
            <Lightbulb size={18} aria-hidden="true" />
            {t("schedule.saranTitle")}
          </h2>
          {suggestions.length === 0 ? (
            <p className="meta">{t("schedule.saranEmpty")}</p>
          ) : (
            <>
              <ul className="saran-list">
                {suggestions.map((s) => {
                  const ed = edits[s.id] ?? {
                    title: s.title,
                    date: d.wibDay(s.start_at),
                    time: d.wibTime(s.start_at),
                    kind: s.kind,
                  };
                  return (
                    <li key={s.id} className="saran-item">
                      <div className="saran-head">
                        <input
                          type="checkbox"
                          checked={checked[s.id] ?? true}
                          aria-label={s.title}
                          onChange={(e) => setChecked({ ...checked, [s.id]: e.target.checked })}
                        />
                        <span className="saran-head-main">
                          <label className="sr-only" htmlFor={`st-${s.id}`}>
                            {t("schedule.fieldTitle")}
                          </label>
                          <input id={`st-${s.id}`} className="field-input saran-title" value={ed.title} onChange={(e) => setEdits({ ...edits, [s.id]: { ...ed, title: e.target.value } })} />
                          <span className="saran-meta">
                            {d.wibShortDay(ed.date)}
                            {s.evidence ? `, ${t("schedule.saranFrom", { src: s.evidence })}` : ""}
                          </span>
                        </span>
                      </div>
                      <div className="saran-edit">
                        <div className="saran-edit-row">
                          <input type="date" className="field-input" value={ed.date} aria-label={t("schedule.fieldDate")} onChange={(e) => setEdits({ ...edits, [s.id]: { ...ed, date: e.target.value } })} />
                          <input type="time" className="field-input" value={ed.time} aria-label={t("schedule.fieldStart")} onChange={(e) => setEdits({ ...edits, [s.id]: { ...ed, time: e.target.value } })} />
                        </div>
                        <div className="saran-edit-row">
                          <select className="field-input" value={ed.kind} aria-label={t("schedule.fieldKind")} onChange={(e) => setEdits({ ...edits, [s.id]: { ...ed, kind: e.target.value as Kind } })}>
                            {KINDS.map((k) => (
                              <option key={k} value={k}>
                                {t(`schedule.kind.${k}`)}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                      <div className="saran-foot">
                        <Button variant="primary" className="sm" onClick={() => void acceptOne(s)}>
                          {t("schedule.saranAdd")}
                        </Button>
                        <button type="button" className="icon-btn" aria-label={t("schedule.saranDismiss")} onClick={() => void dismissOne(s)}>
                          <X size={16} aria-hidden="true" />
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
              <div className="saran-actions">
                <Button variant="primary" onClick={() => void acceptBatch()}>
                  {t("schedule.saranAddAll", { n: suggestions.filter((s) => (checked[s.id] ?? true)).length })}
                </Button>
                <Button variant="ghost" onClick={() => void dismissBatch()}>
                  {t("schedule.saranDismissAll")}
                </Button>
              </div>
            </>
          )}
        </section>

        {/* semua agenda */}
        <Card title={t("schedule.allTitle")}>
          <div className="agenda-filters" role="group" aria-label={t("schedule.fieldKind")}>
            <button type="button" className="chip-btn" aria-pressed={filter === "semua"} onClick={() => setFilter("semua")}>
              {t("common.all")}
            </button>
            {(["kelas", "belajar", "tenggat"] as Kind[]).map((k) => (
              <button key={k} type="button" className="chip-btn" aria-pressed={filter === k} onClick={() => setFilter(k)}>
                {t(`schedule.kind.${k}`)}
              </button>
            ))}
          </div>

          {loading ? (
            <>
              <span className="skeleton" />
              <span className="skeleton" />
              <span className="skeleton" />
            </>
          ) : agenda.length === 0 ? (
            <EmptyState title={t("schedule.allEmpty")} />
          ) : (
            <div>
              {agenda.map((g) => (
                <div key={g.day} className="ag-group">
                  <p className="ag-day">
                    {d.wibDayHeading(g.day)}
                    {g.day === today && <span className="pill-today">{t("time.today")}</span>}
                  </p>
                  {g.items.map((ev) => (
                    <div key={ev.id}>
                      <button type="button" className={`ag-row${selEvent === ev.id ? " sel" : ""}`} onClick={() => setSelEvent(selEvent === ev.id ? null : ev.id)} aria-expanded={selEvent === ev.id}>
                        <span className="ag-time">{d.wibTime(ev.start_at)}</span>
                        <span className="ag-main">
                          <span className="ag-title">{ev.title}</span>
                          <span className="ag-meta">
                            <span className={`chip${ev.kind === "tenggat" ? " tenggat" : ev.kind === "kelas" ? " kelas" : ""}`}>{chipRange(ev)}</span>
                            <span className="ag-src">{srcLabel(ev)}</span>
                          </span>
                        </span>
                      </button>
                      {selEvent === ev.id && (
                        <div className="ag-detail">
                          <div className="dd-row">
                            <span>{t("schedule.fieldDate")}</span>
                            <span>{d.fullDateOnly(ev.start_at)}</span>
                          </div>
                          <div className="dd-row">
                            <span>{t("schedule.fieldStart")} – {t("schedule.fieldEnd")}</span>
                            <span>
                              {d.wibTime(ev.start_at)} – {d.wibTime(ev.end_at)}
                            </span>
                          </div>
                          {ev.location && (
                            <div className="dd-row">
                              <span>{t("schedule.fieldLocation")}</span>
                              <span>{ev.location}</span>
                            </div>
                          )}
                          <div className="dd-actions">
                            <Button className="sm" icon={<Pencil className="i" size={14} aria-hidden="true" />} onClick={() => openEdit(ev)}>
                              {t("schedule.edit")}
                            </Button>
                            <Button className="sm" icon={<Download className="i" size={14} aria-hidden="true" />} onClick={() => downloadEventIcs(ev.id, ev.title).catch(() => {})}>
                              {t("schedule.ics")}
                            </Button>
                            <Button variant="danger" className="sm" icon={<Trash2 className="i" size={14} aria-hidden="true" />} onClick={() => void remove(ev)}>
                              {t("common.delete")}
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {modal && <AgendaModal initial={modal.initial} editing={modal.editing} onClose={() => setModal(null)} />}
    </div>
  );
}
