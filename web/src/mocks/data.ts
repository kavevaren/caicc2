/**
 * MSW mock data — the mockup's Indonesian sample data (docs/design/dashboard-mockup.html).
 *
 * Static "reference time": Thursday 29 October 2026, ~08:00 WIB (Asia/Jakarta, UTC+7).
 * All shapes are typed against the generated contract types (web/src/lib/api-types.ts),
 * so a contract change breaks this file until the mocks are updated.
 */
import type { components } from "../lib/api-types";

declare namespace S {
  export type Author = components["schemas"]["Author"];
  export type Event = components["schemas"]["Event"];
  export type User = components["schemas"]["User"];
  export type Me = components["schemas"]["Me"];
  export type AuthResponse = components["schemas"]["AuthResponse"];
  export type Subject = components["schemas"]["Subject"];
  export type Question = components["schemas"]["Question"];
  export type QuestionDetail = components["schemas"]["QuestionDetail"];
  export type QuestionList = components["schemas"]["QuestionList"];
  export type Document = components["schemas"]["Document"];
  export type Figure = components["schemas"]["Figure"];
  export type DocumentList = components["schemas"]["DocumentList"];
  export type Job = components["schemas"]["Job"];
  export type JobRef = components["schemas"]["JobRef"];
  export type Dashboard = components["schemas"]["Dashboard"];
  export type Leaderboard = components["schemas"]["Leaderboard"];
  export type NotificationList = components["schemas"]["NotificationList"];
  export type Suggestion = components["schemas"]["Suggestion"];
}

/* ------------------------------------------------------------------ authors */

export const meAuthor: S.Author = { username: "aldo", display_name: "Aldo" };
export const sari: S.Author = { username: "sari_r", display_name: "Sari Rahmawati" };
export const budi: S.Author = { username: "budi_w", display_name: "Budi Wijaya" };
export const liWei: S.Author = { username: "li_wei", display_name: "Li Wei" };
export const dewi: S.Author = { username: "dewi_p", display_name: "Dewi Puspita" };

/* ------------------------------------------------------------------- events */

export const evUtsKalkulus: S.Event = {
  id: 1,
  title: "UTS Kalkulus II",
  start_at: "2026-10-29T13:00:00+07:00",
  end_at: "2026-10-29T17:00:00+07:00",
  location: "Gedung B 302",
  description: "Ujian Tengah Semester Kalkulus II (limit, turunan, integral).",
  reminder_minutes: 60,
  source: "google",
  google_event_id: "g-mock-uts-kalkulus",
  created_at: "2026-10-27T08:00:00+07:00",
};

export const evTugasStrukturData: S.Event = {
  id: 2,
  title: "Tugas Struktur Data: binary tree",
  start_at: "2026-10-30T23:59:00+07:00",
  end_at: "2026-10-31T00:00:00+07:00",
  location: null,
  description: "Kumpulkan program binary tree (traversal in-order, pre-order, post-order).",
  reminder_minutes: 1440,
  source: "ai",
  google_event_id: null,
  created_at: "2026-10-29T03:00:00+07:00",
};

export const evMakalahAI: S.Event = {
  id: 3,
  title: "Makalah AI Ethics",
  start_at: "2026-10-31T23:59:00+07:00",
  end_at: "2026-11-01T00:00:00+07:00",
  location: null,
  description: "Makalah kelompok: bias dalam model bahasa besar.",
  reminder_minutes: 1440,
  source: "ai",
  google_event_id: null,
  created_at: "2026-10-29T06:00:00+07:00",
};

export const evKelasStatistika: S.Event = {
  id: 4,
  title: "Kelas Statistika: regresi linier",
  start_at: "2026-11-02T09:00:00+07:00",
  end_at: "2026-11-02T11:00:00+07:00",
  location: "Gedung C 205",
  description: null,
  reminder_minutes: 60,
  source: "google",
  google_event_id: "g-mock-kelas-stat",
  created_at: "2026-10-28T07:30:00+07:00",
};

export const mockEvents: S.Event[] = [evUtsKalkulus, evTugasStrukturData, evMakalahAI, evKelasStatistika];

/* ------------------------------------------------------------------- me/auth */

export const mockUser: S.User = {
  username: "aldo",
  display_name: "Aldo",
  lang: "id",
  theme: "system",
  reduce_motion: false,
  onboarding_done: true,
};

export const mockMe: S.Me = {
  user: mockUser,
  points: 128,
  rank: 4,
  unread: 3,
  onboarding_done: true,
};

export const mockAuthResponse: S.AuthResponse = {
  token: "mock-token-aldo-0001",
  user: mockUser,
};

/* ----------------------------------------------------------------- subjects */

export const mockSubjects: S.Subject[] = [
  { id: 1, name: "Kalkulus II", followed: true },
  { id: 2, name: "Struktur Data", followed: true },
  { id: 3, name: "Statistika", followed: true },
];

/* ----------------------------------------------------------------- questions */

const qTurunan: S.Question = {
  id: 41,
  title: "Turunan dari x^2 sin x pakai aturan perkalian?",
  body_md: "Apakah cukup langsung u = x^2, v = sin x, lalu 2x sin x + x^2 cos x?",
  subject: "Kalkulus II",
  subject_id: 1,
  tags: ["turunan", "aturan-perkalian"],
  author: sari,
  status: "answered",
  best_answer_id: 101,
  answers_count: 3,
  score: 12,
  excerpt: "Apakah cukup langsung u = x^2, v = sin x, lalu 2x sin x + x^2 cos x?",
  has_attachment: false,
  created_at: "2026-10-29T06:00:00+07:00",
  updated_at: "2026-10-29T07:30:00+07:00",
};

const qAvl: S.Question = {
  id: 42,
  title: "Cara rotasi AVL tree setelah insert yang benar?",
  body_md: "Kapan LL, RR, LR, atau RL? Contoh kasus yang sering bikin salah.",
  subject: "Struktur Data",
  subject_id: 2,
  tags: ["avl-tree", "rotasi"],
  author: dewi,
  status: "answered",
  best_answer_id: 104,
  answers_count: 5,
  score: 9,
  excerpt: "Kapan LL, RR, LR, atau RL? Contoh kasus yang sering bikin salah.",
  has_attachment: false,
  created_at: "2026-10-29T03:00:00+07:00",
  updated_at: "2026-10-29T07:45:00+07:00",
};

const qUjiT: S.Question = {
  id: 43,
  title: "Kapan pakai uji-t dan kapan ANOVA untuk 3 kelompok?",
  body_md: "Dosen bilang pakai ANOVA, tapi saya masih bingung dengan asumsi homogenitas variansnya.",
  subject: "Statistika",
  subject_id: 3,
  tags: ["uji-t", "anova"],
  author: liWei,
  status: "answered",
  best_answer_id: 108,
  answers_count: 1,
  score: 5,
  excerpt: "Dosen bilang pakai ANOVA, tapi saya masih bingung dengan asumsi homogenitas variansnya.",
  has_attachment: false,
  created_at: "2026-10-28T09:00:00+07:00",
  updated_at: "2026-10-28T13:00:00+07:00",
};

const qIntegral: S.Question = {
  id: 44,
  title: "Integral e^x cos x dx pakai integral parsial dua kali?",
  body_md: "Setiap kali saya melakukan parsial, integralnya muncul lagi. Terus bagaimana cara menyelesaikannya?",
  subject: "Kalkulus II",
  subject_id: 1,
  tags: ["integral-parsial"],
  author: meAuthor,
  status: "open",
  best_answer_id: null,
  answers_count: 0,
  score: 2,
  excerpt: "Setiap kali saya melakukan parsial, integralnya muncul lagi. Terus bagaimana cara menyelesaikannya?",
  has_attachment: false,
  created_at: "2026-10-27T10:00:00+07:00",
  updated_at: null,
};

export const mockQuestions: S.Question[] = [qTurunan, qAvl, qUjiT, qIntegral];

export const mockQuestionDetails: Record<number, S.QuestionDetail> = {
  41: {
    ...qTurunan,
    answers: [
      {
        id: 101,
        body_md:
          "Pakai aturan perkalian: d/dx[u·v] = u′v + uv′. Di sini u = x², v = sin x, jadi u′ = 2x dan v′ = cos x. Hasil akhirnya **2x sin x + x² cos x**. Jawabanmu sudah benar.",
        author: budi,
        score: 8,
        is_best: true,
        created_at: "2026-10-29T06:20:00+07:00",
        updated_at: null,
        attachments: [],
      },
      {
        id: 102,
        body_md: "Benar sekali, itu memang penerapan langsung aturan perkalian.",
        author: dewi,
        score: 3,
        is_best: false,
        created_at: "2026-10-29T06:40:00+07:00",
        updated_at: null,
        attachments: [],
      },
      {
        id: 103,
        body_md: "Jangan lupa bahwa urutan u dan v boleh ditukar; hasilnya tetap sama.",
        author: liWei,
        score: 1,
        is_best: false,
        created_at: "2026-10-29T07:30:00+07:00",
        updated_at: null,
        attachments: [],
      },
    ],
    following: true,
    votes_mine: 1,
    hints_remaining: 3,
  },
  42: {
    ...qAvl,
    answers: [
      {
        id: 104,
        body_md:
          "Lihat faktor keseimbangan node kakek: LL → rotasi kanan sekali, RR → rotasi kiri sekali, LR → rotasi kiri lalu kanan di anak, RL → rotasi kanan lalu kiri. Kuncinya adalah node yang paling dalam di subtree yang berat.",
        author: sari,
        score: 6,
        is_best: true,
        created_at: "2026-10-29T04:00:00+07:00",
        updated_at: null,
        attachments: [],
      },
      {
        id: 105,
        body_md: "Saran: gambar pohonnya dulu sebelum rotasi, jangan diimajinasikan.",
        author: budi,
        score: 2,
        is_best: false,
        created_at: "2026-10-29T04:30:00+07:00",
        updated_at: null,
        attachments: [],
      },
    ],
    following: false,
    votes_mine: 0,
    hints_remaining: 3,
  },
  43: {
    ...qUjiT,
    answers: [
      {
        id: 108,
        body_md:
          "Uji-t membandingkan **dua** kelompok; ANOVA untuk **tiga atau lebih**. Untuk 3 kelompok memang ANOVA satu arah, lalu lanjutkan uji post-hoc (Tukey HSD) jika signifikan.",
        author: sari,
        score: 5,
        is_best: true,
        created_at: "2026-10-28T13:00:00+07:00",
        updated_at: null,
        attachments: [],
      },
    ],
    following: false,
    votes_mine: 0,
    hints_remaining: 3,
  },
  44: {
    ...qIntegral,
    answers: [],
    following: true,
    votes_mine: 0,
    hints_remaining: 2,
  },
};

export const mockQuestionList: S.QuestionList = {
  items: mockQuestions,
  total: mockQuestions.length,
  page: 1,
  pages: 1,
};

/* ------------------------------------------------------------------ documents */

/** Document with a free-form `extra` (the contract types it as `Record<string, never>`; mocks widen it). */
export type DocumentMock = Omit<S.Document, "extra"> & { extra?: Record<string, unknown> };

/** Figure with a free-form `chart_spec` (the contract types it as `Record<string, never>`; mocks widen it). */
type FigureMock = Omit<S.Figure, "chart_spec"> & { chart_spec?: Record<string, unknown> | null };

const figChart: FigureMock = {
  ref_no: 1,
  kind: "chart",
  source_label: "Gambar 1",
  category: "Distribusi nilai",
  caption: "Distribusi nilai UTS Kalkulus II",
  relevance: 0.9,
  included: true,
  width: 640,
  height: 360,
  chart_spec: {
    type: "bar",
    labels: ["A", "B", "C", "D"],
    datasets: [{ label: "Jumlah mahasiswa", values: [4, 9, 12, 3] }],
  },
};

export const docRegresi: DocumentMock = {
  id: 1,
  kind: "summary",
  title: "Ringkasan regresi linier berganda",
  subject_id: 3,
  subject: "Statistika",
  source_files: [{ name: "statistika-regresi-ppt.pdf", size_bytes: 2457600 }],
  content_md:
    "# Ringkasan: Regresi Linier Berganda\n\n## Definisi\nModel regresi linier berganda memprediksi variabel dependen `Y` dari beberapa variabel independen `X1, X2, ..., Xk`:\n\n`Y = b0 + b1*X1 + b2*X2 + ... + bk*Xk + e`\n\n## Cara baca\n- **Koefisien**: arah dan besarnya pengaruh tiap X terhadap Y.\n- **R²**: proporsi variasi Y yang dijelaskan model.\n- **Asumsi**: linearitas, independensi error, homogenitas varians, normalitas.\n\n## Deadline\n- Makalah AI Ethics: **31 Oktober 23.59**\n",
  extra: {
    figures: [figChart],
    sources: [{ label: "Slide 12", text: "Asumsi klasik regresi linier berganda." }],
    ai_calls: [
      { model: "FAST", role: "map", tokens_in: 1200, tokens_out: 300 },
      { model: "SLOW", role: "reduce", tokens_in: 1400, tokens_out: 500 },
    ],
  },
  created_at: "2026-10-29T06:00:00+07:00",
  updated_at: null,
};

export const docTranskrip9: DocumentMock = {
  id: 2,
  kind: "transcript",
  title: "Transkrip pertemuan 9",
  subject_id: 2,
  subject: "Struktur Data",
  source_files: [{ name: "pertemuan-9.webm", size_bytes: 18874368 }],
  content_md:
    "# Transkrip: Struktur Data — Pertemuan 9 (Binary Tree)\n\n**00:00** — Pembagian tugas: binary tree.\n**00:05** — Definisi: node, akar, daun, tinggi pohon.\n**00:22** — Traversal in-order: kiri, akar, kanan.\n**00:41** — Traversal pre-order: akar, kiri, kanan.\n**01:02** — Kuis singkat di kelas.\n",
  extra: {
    segments: [
      { start: 0, end: 5, text: "Pembagian tugas: binary tree." },
      { start: 300, end: 320, text: "Traversal in-order: kiri, akar, kanan." },
    ],
    translations: {},
    meeting: {
      summary_md: "Materi binary tree: definisi, jenis traversal, dan kuis.",
      decisions: ["Tugas: program traversal in/pre/post-order"],
      action_items: ["Kumpulkan program sebelum 30 Oktober 23.59"],
    },
    ai_calls: [{ model: "WHISPER", role: "transcribe", tokens_in: 0, tokens_out: 0 }],
  },
  created_at: "2026-10-29T03:00:00+07:00",
  updated_at: null,
};

export const docBayes: DocumentMock = {
  id: 3,
  kind: "summary",
  title: "Ringkasan teorema Bayes",
  subject_id: 3,
  subject: "Statistika",
  source_files: [{ name: "bayes-lecture-notes.pdf", size_bytes: 1204224 }],
  content_md:
    "# Ringkasan: Teorema Bayes\n\n`P(A|B) = P(B|A) * P(A) / P(B)`\n\n- **Prior**: P(A)\n- **Likelihood**: P(B|A)\n- **Posterior**: P(A|B)\n\nContoh: diagnosis penyakit dari hasil tes (sensitivity/specificity).\n",
  extra: { figures: [], sources: [], ai_calls: [] },
  created_at: "2026-10-28T15:00:00+07:00",
  updated_at: null,
};

export const docAturanPerkalian: DocumentMock = {
  id: 4,
  kind: "summary",
  title: "Ringkasan aturan perkalian turunan",
  subject_id: 1,
  subject: "Kalkulus II",
  source_files: [{ name: "turunan-bab3.pdf", size_bytes: 983040 }],
  content_md:
    "# Ringkasan: Aturan Perkalian\n\n`(u·v)′ = u′v + uv′`\n\nUrutan u dan v bebas. Contoh: d/dx[x² sin x] = 2x sin x + x² cos x.\n",
  extra: { figures: [], sources: [], ai_calls: [] },
  created_at: "2026-10-27T11:00:00+07:00",
  updated_at: null,
};

export const docBinaryTree: DocumentMock = {
  id: 5,
  kind: "transcript",
  title: "Rekaman kelas: binary tree",
  subject_id: 2,
  subject: "Struktur Data",
  source_files: [{ name: "rekaman-binary-tree.mp4", size_bytes: 52428800 }],
  content_md: "# Transkrip: Binary Tree\n\n**00:00** — Pengantar pohon biner.\n**00:15** — Binary search tree: properti kiri < akar < kanan.\n",
  extra: { segments: [], translations: {}, meeting: null, ai_calls: [] },
  created_at: "2026-10-26T13:00:00+07:00",
  updated_at: null,
};

export const docIntegralParsial: DocumentMock = {
  id: 6,
  kind: "summary",
  title: "Ringkasan integral parsial",
  subject_id: 1,
  subject: "Kalkulus II",
  source_files: [{ name: "integral-parsial.pdf", size_bytes: 768000 }],
  content_md:
    "# Ringkasan: Integral Parsial\n\n`∫ u dv = uv − ∫ v du`\n\nTips: pilih u dengan tabel LIATE (Log, Invers trig, Aljabar, Trig, Eksponensial).\n",
  extra: { figures: [], sources: [], ai_calls: [] },
  created_at: "2026-10-25T10:00:00+07:00",
  updated_at: null,
};

export const mockDocuments: DocumentMock[] = [
  docRegresi,
  docTranskrip9,
  docBayes,
  docAturanPerkalian,
  docBinaryTree,
  docIntegralParsial,
];

export const mockDocumentList: Omit<S.DocumentList, "items"> & { items: DocumentMock[] } = {
  items: mockDocuments,
  total: 17,
  page: 1,
  pages: 1,
};

/* --------------------------------------------------------------------- job */

export const mockJobId = "7f3a9c2e-4b1d-4e6a-9c0f-2a8b5d6e7f10";

export const mockJob: S.Job = {
  id: mockJobId,
  kind: "summary",
  status: "done",
  stage: "deadlines",
  stages: ["extract", "figures", "chunk", "map", "reduce", "format_check", "deadlines"],
  result_document_id: 1,
  error_code: null,
  created_at: "2026-10-29T05:40:00+07:00",
  updated_at: "2026-10-29T06:00:00+07:00",
};

export const mockJobRef: S.JobRef = { job_id: mockJobId };

/* ---------------------------------------------------------------- dashboard */

const week: S.Dashboard["week"] = [
  { date: "2026-10-26", events: [] },
  { date: "2026-10-27", events: [] },
  { date: "2026-10-28", events: [] },
  { date: "2026-10-29", events: [evUtsKalkulus] },
  { date: "2026-10-30", events: [evTugasStrukturData] },
  { date: "2026-10-31", events: [evMakalahAI] },
  { date: "2026-11-01", events: [] },
];

export const mockDashboard: S.Dashboard = {
  week,
  next_event: evUtsKalkulus,
  stats: { summaries: 12, transcripts: 5, my_unanswered: 2, points: 128, rank: 4 },
  points_ring: { current: 128, target: 156, rank: 4 },
  questions_for_you: mockQuestions,
  reminders: [
    {
      kind: "event_soon",
      text_key: "reminder.event_soon",
      text_params: { title: "Makalah AI Ethics", days: 2 },
      created_at: "2026-10-29T07:00:00+07:00",
    },
    {
      kind: "new_answer",
      text_key: "reminder.answer_voted",
      text_params: { votes: 5, topic: "regresi" },
      created_at: "2026-10-29T06:30:00+07:00",
    },
    {
      kind: "rank_change",
      text_key: "reminder.rank_up",
      text_params: { from: 7, to: 4 },
      created_at: "2026-10-28T18:00:00+07:00",
    },
  ],
  top5: [
    { rank: 1, username: "sari_r", display_name: "Sari Rahmawati", points: 214, answers: 18, best_answers: 9, is_me: false },
    { rank: 2, username: "budi_w", display_name: "Budi Wijaya", points: 187, answers: 15, best_answers: 8, is_me: false },
    { rank: 3, username: "li_wei", display_name: "Li Wei", points: 156, answers: 12, best_answers: 7, is_me: false },
    { rank: 4, username: "aldo", display_name: "Aldo", points: 128, answers: 10, best_answers: 5, is_me: true },
    { rank: 5, username: "dewi_p", display_name: "Dewi Puspita", points: 112, answers: 9, best_answers: 4, is_me: false },
  ],
  me_row: { rank: 4, username: "aldo", display_name: "Aldo", points: 128, answers: 10, best_answers: 5, is_me: true },
  recent: [
    { kind: "summary", title: "Ringkasan regresi linier berganda", subject: "Statistika", created_at: "2026-10-29T06:00:00+07:00" },
    { kind: "transcript", title: "Transkrip pertemuan 9", subject: "Struktur Data", created_at: "2026-10-29T03:00:00+07:00" },
    { kind: "summary", title: "Ringkasan teorema Bayes", subject: "Statistika", created_at: "2026-10-28T15:00:00+07:00" },
  ],
};

/* --------------------------------------------------------------- leaderboard */

export const mockLeaderboard: S.Leaderboard = {
  items: mockDashboard.top5,
  me: mockDashboard.me_row,
  window: "week",
  subject: null,
};

/* -------------------------------------------------------------- notifications */

export const mockNotifications: S.NotificationList = {
  items: [
    {
      id: 31,
      kind: "event_soon",
      text_key: "notif.event_soon",
      text_params: { title: "Makalah AI Ethics", when: "Sabtu, 31 Oktober" },
      link: "/jadwal",
      is_read: false,
      created_at: "2026-10-29T07:00:00+07:00",
    },
    {
      id: 30,
      kind: "new_answer",
      text_key: "notif.answer_voted",
      text_params: { votes: 5, topic: "regresi" },
      link: "/forum/q/43",
      is_read: false,
      created_at: "2026-10-29T06:30:00+07:00",
    },
    {
      id: 29,
      kind: "rank_change",
      text_key: "notif.rank_up",
      text_params: { from: 7, to: 4 },
      link: "/leaderboard",
      is_read: false,
      created_at: "2026-10-28T18:00:00+07:00",
    },
    {
      id: 28,
      kind: "best_answer",
      text_key: "notif.best_answer",
      text_params: { question: "Kapan pakai uji-t dan kapan ANOVA" },
      link: "/forum/q/43",
      is_read: true,
      created_at: "2026-10-28T13:05:00+07:00",
    },
  ],
  unread: 3,
};

/* ---------------------------------------------------------------- suggestions */

export const mockSuggestions: S.Suggestion[] = [
  {
    id: 11,
    document_id: 1,
    title: "Makalah AI Ethics: 31 Oktober 23.59",
    start_at: "2026-10-31T23:59:00+07:00",
    end_at: "2026-11-01T00:00:00+07:00",
    evidence: "“Dikumpulkan 31 Oktober pukul 23.59” (slide 2).",
    status: "pending",
  },
  {
    id: 12,
    document_id: 2,
    title: "Tugas Struktur Data: 30 Oktober 23.59",
    start_at: "2026-10-30T23:59:00+07:00",
    end_at: "2026-10-31T00:00:00+07:00",
    evidence: "“Kumpulkan program sebelum 30 Oktober 23.59” (transkrip 00:41).",
    status: "pending",
  },
];
