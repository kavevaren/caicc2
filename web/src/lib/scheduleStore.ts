/**
 * Shared schedule store (BUG-21: one source of truth).
 *
 * Dashboard, SchedulePage and the job tray all read events + pending
 * suggestions from here. When a job finishes the job store calls
 * `invalidate()` so the calendar refetches exactly once — no page ever
 * polls /api/events on its own.
 */
import { useSyncExternalStore } from "react";
import { api } from "./api";
import type { EventItem, EventSuggestion } from "./types";

type ScheduleState = {
  events: EventItem[];
  suggestions: EventSuggestion[];
  notes: string | null; // last import notes (FEAT-01, import-meta)
  loaded: boolean;
  loading: boolean;
  error: boolean;
};

let state: ScheduleState = {
  events: [],
  suggestions: [],
  notes: null,
  loaded: false,
  loading: false,
  error: false,
};
const listeners = new Set<() => void>();
let inFlight: Promise<void> | null = null;

function emit(): void {
  for (const l of listeners) l();
}

function subscribe(l: () => void): () => void {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
}

const getSnapshot = (): ScheduleState => state;

export function useSchedule(): ScheduleState {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

/** Fetch events + suggestions + import-meta. Concurrent calls share one flight. */
export function load(): Promise<void> {
  if (inFlight) return inFlight;
  state = { ...state, loading: true, error: false };
  emit();
  inFlight = (async () => {
    try {
      const [ev, su, meta] = await Promise.all([
        api.get<{ items: EventItem[] }>("events"),
        api.get<{ items: EventSuggestion[] }>("suggestions"),
        api
          .get<{ notes: string | null }>("schedule/import-meta")
          .catch(() => ({ notes: null })),
      ]);
      state = {
        events: ev.items,
        suggestions: su.items,
        notes: meta.notes ?? null,
        loaded: true,
        loading: false,
        error: false,
      };
    } catch {
      state = { ...state, loading: false, error: !state.loaded };
    } finally {
      inFlight = null;
      emit();
    }
  })();
  return inFlight;
}

/** Refetch (idempotent while a load is running). Called on app start, on
 *  route change into the schedule pages, and when a job finishes. */
export function invalidate(): void {
  void load();
}

/* --- local writes: apply optimistically, then refetch to settle --- */

export function upsertEvent(ev: EventItem): void {
  const rest = state.events.filter((e) => e.id !== ev.id);
  state = { ...state, events: [ev, ...rest] };
  emit();
  void load();
}

export function removeEvent(id: number): void {
  state = { ...state, events: state.events.filter((e) => e.id !== id) };
  emit();
  void load();
}

export function patchSuggestion(id: number, patch: Partial<EventSuggestion>): void {
  state = {
    ...state,
    suggestions: state.suggestions.map((s) => (s.id === id ? { ...s, ...patch } : s)),
  };
  emit();
  void load();
}

export function removeSuggestion(id: number): void {
  state = {
    ...state,
    suggestions: state.suggestions.filter((s) => s.id !== id),
  };
  emit();
  void load();
}

export function clearSuggestions(ids: number[]): void {
  const drop = new Set(ids);
  state = { ...state, suggestions: state.suggestions.filter((s) => !drop.has(s.id)) };
  emit();
  void load();
}
