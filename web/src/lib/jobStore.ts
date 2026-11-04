/**
 * Global job store (FEAT-02).
 *
 * One module-level store that the floating tray renders from. It loads
 * `GET /api/jobs?active=1` on app start (so progress survives a refresh)
 * and polls every 2 s while any job is queued/running. When a job flips
 * to done it invalidates the schedule store (new suggestions / imported
 * events) so the calendar refetches exactly once.
 */
import { useSyncExternalStore } from "react";
import { api } from "./api";
import type { Job } from "./types";
import { invalidate as scheduleInvalidate } from "./scheduleStore";

type JobState = {
  jobs: Job[];
  loading: boolean;
  error: boolean;
  /** The most recent job that flipped to done since app load (tray toast). */
  lastFinished: Job | null;
};

let state: JobState = { jobs: [], loading: false, error: false, lastFinished: null };
const listeners = new Set<() => void>();
let timer: number | null = null;
let inFlight = false;
let started = false;

function emit(): void {
  for (const l of listeners) l();
}

function setState(patch: Partial<JobState>): void {
  state = { ...state, ...patch };
  emit();
}

function isActive(j: Job): boolean {
  return j.status === "queued" || j.status === "running";
}

function syncPolling(): void {
  const should = state.jobs.some(isActive);
  if (should && timer === null) {
    timer = window.setInterval(refresh, 2000);
  } else if (!should && timer !== null) {
    window.clearInterval(timer);
    timer = null;
  }
}

async function refresh(): Promise<void> {
  if (inFlight) return;
  inFlight = true;
  try {
    const res = await api.get<{ items: Job[] }>("jobs?active=1");
    const prev = state.jobs;
    const prevById = new Map(prev.map((j) => [j.id, j]));
    const seen = new Set(res.items.map((j) => j.id));
    // Keep locally-added jobs the feed has not returned yet.
    const merged: Job[] = [...res.items];
    for (const j of prev) if (!seen.has(j.id)) merged.push(j);
    let lastFinished = state.lastFinished;
    for (const j of merged) {
      const old = prevById.get(j.id);
      if (old && isActive(old) && j.status === "done") {
        lastFinished = j;
        scheduleInvalidate(); // new summary / imported events may exist
      }
    }
    setState({ jobs: merged, loading: false, error: false, lastFinished });
    syncPolling();
  } catch {
    if (state.jobs.length === 0) setState({ loading: false, error: true });
  } finally {
    inFlight = false;
  }
}

/** Kick the store off (call once from the shell after login). */
export function startJobs(): void {
  if (started) return;
  started = true;
  void refresh();
}

/** Optimistically add a job right after its 202 response, then refetch. */
export function addJob(partial: Pick<Job, "id" | "kind" | "label">): void {
  const now = new Date().toISOString();
  const job: Job = {
    id: partial.id,
    kind: partial.kind,
    status: "queued",
    stage: "queued",
    stages: [],
    label: partial.label,
    notes: null,
    percent: 0,
    progress: null,
    result_document_id: null,
    error_code: null,
    created_at: now,
    updated_at: now,
  };
  if (state.jobs.some((j) => j.id === job.id)) return;
  setState({ jobs: [job, ...state.jobs], lastFinished: null });
  syncPolling();
  void refresh();
}

/** Hide a finished job from the tray (local only). */
export function dismissJob(id: string): void {
  setState({ jobs: state.jobs.filter((j) => j.id !== id) });
  syncPolling();
}

/** Forget the "done" toast (called by the tray after it faded). */
export function clearFinished(): void {
  if (state.lastFinished) setState({ lastFinished: null });
}

export function useJobs(): JobState {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => {
        listeners.delete(l);
      };
    },
    () => state,
    () => state,
  );
}
