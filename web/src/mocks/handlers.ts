/**
 * MSW handlers for `npm run dev` (mock-backed app shell, no server needed).
 *
 * - Data comes from ./data.ts (the mockup's Indonesian sample data).
 * - Auth is not enforced: every endpoint answers as the logged-in mock user.
 * - P0 probe endpoints are kept so the deployed P0 page still works in dev.
 * - The job SSE stream emits stage/done events with a 400 ms cadence (faster
 *   than the real 15 s heartbeat) so P4 can develop the progress UI.
 */
import { http, HttpResponse, delay } from "msw";

import type { components } from "../lib/api-types";
import {
  docRegresi,
  mockAuthResponse,
  mockDashboard,
  mockDocumentList,
  mockDocuments,
  mockJob,
  mockJobId,
  mockJobRef,
  mockLeaderboard,
  mockMe,
  mockNotifications,
  mockQuestionDetails,
  mockQuestionList,
  mockSuggestions,
  mockUser,
  mockEvents,
  mockQuestions,
  mockSubjects,
} from "./data";

const delayMs = 120; // simulate network so loading states are visible

const ics = (id: number, title: string, startUtc: string, endUtc: string, location: string | null) =>
  [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Orvina//Mock//ID",
    "BEGIN:VEVENT",
    `UID:ev-${id}@orvina.mock`,
    "DTSTAMP:20261029T010000Z",
    `DTSTART:${startUtc}`,
    `DTEND:${endUtc}`,
    `SUMMARY:${title}`,
    ...(location ? [`LOCATION:${location}`] : []),
    "END:VEVENT",
    "END:VCALENDAR",
  ].join("\r\n");

const PNG_1x1 = Uint8Array.from(
  atob("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="),
  (c) => c.charCodeAt(0),
);

function sseStream(events: Array<{ event: string; data: unknown; delayMs?: number }>, doneDelayMs = 0) {
  const encoder = new TextEncoder();
  let i = 0;
  const push = (controller: ReadableStreamDefaultController) => {
    if (i >= events.length) {
      if (doneDelayMs > 0) setTimeout(() => controller.close(), doneDelayMs);
      else controller.close();
      return;
    }
    const e = events[i++];
    controller.enqueue(encoder.encode(`event: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`));
    setTimeout(() => push(controller), e.delayMs ?? 400);
  };
  return new ReadableStream({
    start(controller) {
      push(controller);
    },
  });
}

export const handlers = [
  /* ------------------------------------------------------------- health/probe */
  http.get("/api/health", () =>
    HttpResponse.json({
      server: "ok",
      modelscope: "ok",
      modelscope_latency_ms: 980,
      whisper: "disabled",
      version: "0.2.0-p1-mock",
    }),
  ),

  http.get("/api/probe/config", () => HttpResponse.json({ public_app_url: "" })),

  http.post("/api/probe/upload", async ({ request }) => {
    const buf = await request.arrayBuffer();
    const declared = request.headers.get("content-length");
    return HttpResponse.json({ received_bytes: buf.byteLength, declared_bytes: declared ? Number(declared) : null });
  }),

  http.get("/api/probe/sse", () => {
    const ticks = Array.from({ length: 20 }, (_, i) => ({ event: "tick", data: { n: i + 1, t: Date.now() }, delayMs: 1000 }));
    ticks.push({ event: "done", data: { n: 20, t: Date.now() }, delayMs: 1000 });
    return new HttpResponse(sseStream(ticks), {
      headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
    });
  }),

  http.post("/api/probe/whisper", () => HttpResponse.json({ whisper: "ready" })),

  /* ------------------------------------------------------------------ auth */
  http.post("/api/auth/register", async () => {
    await delay(delayMs);
    return HttpResponse.json(mockAuthResponse, { status: 201 });
  }),

  http.post("/api/auth/login", async () => {
    await delay(delayMs);
    return HttpResponse.json(mockAuthResponse);
  }),

  http.post("/api/auth/logout", () => new HttpResponse(null, { status: 204 })),

  http.post("/api/stream-ticket", () => HttpResponse.json({ ticket: "mock-ticket-0001", expires_in: 60 })),

  /* -------------------------------------------------------------------- me */
  http.get("/api/me", () => HttpResponse.json(mockMe)),

  http.patch("/api/me", async ({ request }) => {
    await delay(delayMs);
    const body = (await request.json()) as Partial<typeof mockUser>;
    return HttpResponse.json({ ...mockMe, user: { ...mockUser, ...body } });
  }),

  http.post("/api/me/password", () => new HttpResponse(null, { status: 204 })),

  http.post("/api/me/onboarding", ({ request }) =>
    request.json().then((body) => HttpResponse.json({ ...mockUser, lang: (body as { lang?: string }).lang ?? mockUser.lang })),
  ),

  /* -------------------------------------------------------------- subjects */
  http.get("/api/subjects", () => HttpResponse.json(mockSubjects)),

  http.post("/api/subjects", async ({ request }) => {
    await delay(delayMs);
    const body = (await request.json()) as { name: string };
    const existing = mockSubjects.find((s) => s.name.toLowerCase() === body.name.toLowerCase());
    if (existing) return HttpResponse.json(existing);
    return HttpResponse.json({ id: mockSubjects.length + 1, name: body.name, followed: true }, { status: 201 });
  }),

  /* ------------------------------------------------------------- dashboard */
  http.get("/api/dashboard", async () => {
    await delay(200);
    return HttpResponse.json(mockDashboard);
  }),

  /* ------------------------------------------------------------------ jobs */
  http.get("/api/jobs/:jobId", ({ params }) => {
    const job = params.jobId === mockJobId ? mockJob : { ...mockJob, id: String(params.jobId), status: "done" };
    return HttpResponse.json(job);
  }),

  http.get("/api/jobs/:jobId/stream", ({ params }) => {
    const job = params.jobId === mockJobId ? mockJob : { ...mockJob, id: String(params.jobId) };
    const events: { event: string; data: Record<string, unknown> }[] = job.stages.map((stage: string) => ({
      event: "stage",
      data: { job_id: job.id, stage, stages: job.stages },
    }));
    events.push({ event: "done", data: { job_id: job.id, result_document_id: job.result_document_id } });
    return new HttpResponse(sseStream(events), {
      headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
    });
  }),

  /* ------------------------------------------------------ summaries / F1 */
  http.post("/api/summaries", async () => {
    await delay(delayMs * 2);
    return HttpResponse.json(mockJobRef, { status: 202 });
  }),

  http.get("/api/documents", ({ request }) => {
    const url = new URL(request.url);
    const q = url.searchParams.get("q")?.toLowerCase() ?? "";
    const kind = url.searchParams.get("kind");
    const items = mockDocuments.filter(
      (d) => (kind ? d.kind === kind : true) && (q ? d.title.toLowerCase().includes(q) : true),
    );
    return HttpResponse.json({ ...mockDocumentList, items, total: items.length });
  }),

  http.get("/api/documents/:id", ({ params }) => {
    const doc = mockDocuments.find((d) => d.id === Number(params.id));
    if (!doc) return HttpResponse.json({ error: { code: "not_found", message_key: "errors.not_found" } }, { status: 404 });
    return HttpResponse.json(doc);
  }),

  http.patch("/api/documents/:id", async ({ params, request }) => {
    await delay(delayMs);
    const doc = mockDocuments.find((d) => d.id === Number(params.id));
    if (!doc) return HttpResponse.json({ error: { code: "not_found", message_key: "errors.not_found" } }, { status: 404 });
    const body = (await request.json()) as { title?: string };
    return HttpResponse.json({ ...doc, title: body.title ?? doc.title });
  }),

  http.delete("/api/documents/:id", () => new HttpResponse(null, { status: 204 })),

  http.patch("/api/documents/:id/figures/:ref", async ({ params }) => {
    await delay(delayMs);
    const doc = mockDocuments.find((d) => d.id === Number(params.id));
    if (!doc) return HttpResponse.json({ error: { code: "not_found", message_key: "errors.not_found" } }, { status: 404 });
    const figures = ((doc.extra?.figures as Array<Record<string, unknown>>) ?? []).map((f) =>
      String(f.ref_no) === String(params.ref) ? { ...f, included: !f.included } : f,
    );
    return HttpResponse.json({ ...doc, extra: { ...doc.extra, figures } });
  }),

  http.get("/api/documents/:id/export", ({ request, params }) => {
    const url = new URL(request.url);
    const format = url.searchParams.get("format") ?? "md";
    const doc = mockDocuments.find((d) => d.id === Number(params.id)) ?? docRegresi;
    const base = doc.title.toLowerCase().replace(/[^a-z0-9]+/g, "-");
    if (format === "html") {
      return new HttpResponse(`<pre>${doc.content_md}</pre>`, {
        headers: { "Content-Type": "text/html; charset=utf-8", "Content-Disposition": `attachment; filename="${base}.html"` },
      });
    }
    // The real server sends a zip (summary.md + images/); the mock sends the markdown as the body.
    return new HttpResponse(doc.content_md, {
      headers: { "Content-Type": "application/zip", "Content-Disposition": `attachment; filename="${base}.zip"` },
    });
  }),

  http.get("/api/figures/:id.png", () =>
    new HttpResponse(PNG_1x1, { headers: { "Content-Type": "image/png" } }),
  ),

  /* ------------------------------------------------------- transcripts / F2 */
  http.post("/api/transcripts", async () => {
    await delay(delayMs * 2);
    return HttpResponse.json(mockJobRef, { status: 202 });
  }),

  /* --------------------------------------------------------- schedule / F3 */
  http.get("/api/events", () => HttpResponse.json({ items: mockEvents })),

  http.post("/api/events", async ({ request }) => {
    await delay(delayMs);
    const body = (await request.json()) as { title: string; start_at: string; end_at: string; location?: string | null };
    if (body.end_at <= body.start_at) {
      return HttpResponse.json({ error: { code: "invalid_time_range", message_key: "errors.invalid_time_range" } }, { status: 400 });
    }
    return HttpResponse.json({
      id: 100,
      title: body.title,
      start_at: body.start_at,
      end_at: body.end_at,
      location: body.location ?? null,
      description: null,
      reminder_minutes: null,
      source: "manual",
      google_event_id: null,
      created_at: new Date().toISOString(),
    });
  }),

  http.patch("/api/events/:id", async ({ params, request }) => {
    await delay(delayMs);
    const ev = mockEvents.find((e) => e.id === Number(params.id));
    if (!ev) return HttpResponse.json({ error: { code: "not_found", message_key: "errors.not_found" } }, { status: 404 });
    const body = (await request.json()) as Partial<typeof ev>;
    return HttpResponse.json({ ...ev, ...body });
  }),

  http.delete("/api/events/:id", () => new HttpResponse(null, { status: 204 })),

  http.get("/api/events/:id.ics", ({ params }) => {
    const ev = mockEvents.find((e) => e.id === Number(params.id));
    if (!ev) return HttpResponse.json({ error: { code: "not_found", message_key: "errors.not_found" } }, { status: 404 });
    return new HttpResponse(ics(ev.id, ev.title, ev.start_at.replace("+07:00", "Z"), ev.end_at.replace("+07:00", "Z"), ev.location ?? null), {
      headers: { "Content-Type": "text/calendar", "Content-Disposition": `attachment; filename="orvina-ev${ev.id}.ics"` },
    });
  }),

  http.get("/api/suggestions", () => HttpResponse.json({ items: mockSuggestions })),

  http.post("/api/suggestions/:id/accept", ({ params }) => {
    const s = mockSuggestions.find((x) => x.id === Number(params.id));
    if (!s) return HttpResponse.json({ error: { code: "not_found", message_key: "errors.not_found" } }, { status: 404 });
    return HttpResponse.json({
      id: 101,
      title: s.title,
      start_at: s.start_at,
      end_at: s.end_at ?? s.start_at,
      location: null,
      description: s.evidence,
      reminder_minutes: null,
      source: "ai",
      google_event_id: null,
      created_at: new Date().toISOString(),
    } as never, { status: 201 });
  }),

  http.post("/api/suggestions/:id/dismiss", () => new HttpResponse(null, { status: 204 })),

  http.get("/api/google/connect", () =>
    HttpResponse.json({ url: "/api/google/callback?code=mock-code&state=mock-state" }),
  ),

  http.get("/api/google/callback", () =>
    new HttpResponse(
      "<!doctype html><html lang='id'><meta charset='utf-8'><title>Orvina</title>" +
        "<body style='font-family:sans-serif;display:grid;place-items:center;height:100vh'>" +
        "<div style='text-align:center'><h1>Google Calendar terhubung</h1>" +
        "<p>Tab ini boleh ditutup.</p></div></body></html>",
      { headers: { "Content-Type": "text/html; charset=utf-8" } },
    ),
  ),

  http.delete("/api/google", () => new HttpResponse(null, { status: 204 })),

  /* ------------------------------------------------------------- forum / F4 */
  http.get("/api/questions", ({ request }) => {
    const url = new URL(request.url);
    const q = url.searchParams.get("q")?.toLowerCase() ?? "";
    const items = mockQuestions.filter((x) => (q ? x.title.toLowerCase().includes(q) : true));
    return HttpResponse.json({ ...mockQuestionList, items, total: items.length });
  }),

  http.post("/api/questions", async ({ request }) => {
    await delay(delayMs * 2);
    const form = await request.formData();
    const title = String(form.get("title") ?? "Pertanyaan baru");
    return HttpResponse.json({
      ...mockQuestions[0],
      id: 900,
      title,
      body_md: String(form.get("body_md") ?? ""),
      author: { username: "aldo", display_name: "Aldo" },
      status: "open",
      best_answer_id: null,
      answers_count: 0,
      score: 2,
      excerpt: String(form.get("body_md") ?? "").slice(0, 160),
      has_attachment: form.getAll("files").length > 0,
      created_at: new Date().toISOString(),
      updated_at: null,
    } as never, { status: 201 });
  }),

  http.get("/api/questions/:id", ({ params }) => {
    const detail = mockQuestionDetails[Number(params.id)];
    if (!detail) return HttpResponse.json({ error: { code: "not_found", message_key: "errors.not_found" } }, { status: 404 });
    return HttpResponse.json(detail);
  }),

  http.patch("/api/questions/:id", async ({ params, request }) => {
    await delay(delayMs);
    const detail = mockQuestionDetails[Number(params.id)];
    if (!detail) return HttpResponse.json({ error: { code: "not_found", message_key: "errors.not_found" } }, { status: 404 });
    const body = (await request.json()) as { title?: string; body_md?: string };
    return HttpResponse.json({ ...detail, ...body });
  }),

  http.delete("/api/questions/:id", () => new HttpResponse(null, { status: 204 })),

  http.post("/api/questions/similar", () => HttpResponse.json({ ids: [41, 44] })),

  http.post("/api/questions/tags", () => HttpResponse.json({ tags: ["turunan", "kalkulus", "turunan-parsial"] })),

  http.post("/api/questions/:id/answers", async ({ params }) => {
    await delay(delayMs * 2);
    const detail = mockQuestionDetails[Number(params.id)];
    if (!detail) return HttpResponse.json({ error: { code: "not_found", message_key: "errors.not_found" } }, { status: 404 });
    return HttpResponse.json({
      id: 901,
      body_md: "Jawaban baru (mock).",
      author: { username: "aldo", display_name: "Aldo" },
      score: 0,
      is_best: false,
      created_at: new Date().toISOString(),
      updated_at: null,
      attachments: [],
    } as never, { status: 201 });
  }),

  http.post("/api/questions/:id/best", async ({ params, request }) => {
    await delay(delayMs);
    const detail = mockQuestionDetails[Number(params.id)];
    if (!detail) return HttpResponse.json({ error: { code: "not_found", message_key: "errors.not_found" } }, { status: 404 });
    const body = (await request.json()) as { answer_id: number };
    return HttpResponse.json({
      ...detail,
      status: "answered",
      best_answer_id: body.answer_id,
      answers: detail.answers.map((a: components["schemas"]["Answer"]) => ({ ...a, is_best: a.id === body.answer_id })),
    });
  }),

  http.post("/api/questions/:id/follow", async ({ request }) => {
    await delay(delayMs);
    let following = true;
    try {
      const body = (await request.json()) as { following?: boolean };
      following = body.following ?? true;
    } catch {
      /* toggle */
    }
    return HttpResponse.json({ following });
  }),

  http.post("/api/questions/:id/hint", () =>
    HttpResponse.json({
      hint_md:
        "**Petunjuk AI, bukan jawaban:** pilih u = eˣ dan dv = cos x dx, lalu lakukan integral parsial sekali lagi dan pindahkan ruas yang berulang.",
      remaining: 2,
    }),
  ),

  http.patch("/api/answers/:id", async ({ params, request }) => {
    await delay(delayMs);
    const body = (await request.json()) as { body_md: string };
    return HttpResponse.json({
      id: Number(params.id),
      body_md: body.body_md,
      author: { username: "aldo", display_name: "Aldo" },
      score: 0,
      is_best: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      attachments: [],
    } as never);
  }),

  http.delete("/api/answers/:id", () => new HttpResponse(null, { status: 204 })),

  http.post("/api/votes", () => HttpResponse.json({ score: 9 })),

  /* ----------------------------------------------------------------- points */
  http.get("/api/leaderboard", ({ request }) => {
    const url = new URL(request.url);
    const window = url.searchParams.get("window") ?? "week";
    return HttpResponse.json({ ...mockLeaderboard, window });
  }),

  /* ---------------------------------------------------------- notifications */
  http.get("/api/notifications", () => HttpResponse.json(mockNotifications)),

  http.post("/api/notifications/:id/read", () => new HttpResponse(null, { status: 204 })),

  http.post("/api/notifications/read-all", () => new HttpResponse(null, { status: 204 })),

  /* ------------------------------------------------------------------ files */
  http.get("/api/files/:attachmentId", () =>
    new HttpResponse("Lampiran contoh (mock).", {
      headers: {
        "Content-Type": "application/octet-stream",
        "Content-Disposition": 'attachment; filename="contoh-lampiran.txt"',
      },
    }),
  ),
];
