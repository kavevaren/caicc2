/** Lean API types — mirror the contract shapes as served by the lean server. */

export type Health = {
  server: string;
  modelscope: string; // ok | invalid_token | unreachable | checking
  modelscope_latency_ms: number;
  whisper: string;
  version: string;
};

export type User = {
  username: string;
  display_name: string;
  lang: string;
  theme: string;
  reduce_motion: boolean;
  onboarding_done: boolean;
};

export type Me = {
  user: User;
  points: number;
  rank: number;
  unread: number;
  onboarding_done: boolean;
};

export type Subject = {
  id: number;
  name: string;
  followed: boolean;
};

export type Job = {
  id: string;
  kind: "summary" | "transcript" | "schedule_import";
  status: "queued" | "running" | "done" | "error";
  stage: string;
  stages: string[];
  label?: string | null;
  notes?: string | null;
  result_document_id?: number | null;
  error_code?: string | null;
  progress?: { done: number; total: number } | null;
  percent?: number;
  created_at: string;
  updated_at: string;
};

export type Deadline = {
  title: string;
  kind: "kelas" | "belajar" | "acara" | "tenggat";
  subkind?: "tugas" | "kuis" | "ujian" | null;
  start_at: string;
  end_at: string | null;
  evidence: string;
};

export type AiCall = {
  feature: string;
  role: string;
  model: string;
  latency_ms: number;
  retries: number;
  ok: boolean;
};

export type DocExtra = {
  figures?: unknown[];
  sources?: { label: string; text?: string }[];
  deadlines?: Deadline[];
  warnings?: string[];
  ai_calls?: AiCall[];
  warning?: boolean;
};

export type Document = {
  id: number;
  kind: "summary" | "transcript";
  title: string;
  subject_id?: number | null;
  subject?: string | null;
  project?: string | null;
  project_id?: number | null;
  source_files?: { name: string; size_bytes?: number }[];
  content_md: string;
  extra?: DocExtra;
  created_at: string;
  updated_at?: string | null;
};

export type DocumentList = {
  items: Document[];
  total: number;
  page: number;
  pages: number;
};

export type WeekDay = {
  date: string;
  events: {
    id: number;
    title: string;
    start_at: string;
    end_at?: string;
    source?: string;
    kind?: "kelas" | "belajar" | "acara" | "tenggat";
    subkind?: "tugas" | "kuis" | "ujian" | null;
  }[];
};

export type EventItem = {
  id: number;
  title: string;
  start_at: string;
  end_at: string;
  location: string | null;
  description: string | null;
  reminder_minutes: number | null;
  source: "manual" | "ringkasan" | "impor" | "google";
  kind: "kelas" | "belajar" | "acara" | "tenggat";
  subkind?: "tugas" | "kuis" | "ujian" | null;
  google_event_id: string | null;
  created_at: string;
};

export type Todo = {
  id: number;
  title: string;
  done: boolean;
  due_date: string | null;
  created_at: string;
};

export type EventSuggestion = {
  id: number;
  document_id: number | null;
  title: string;
  start_at: string;
  end_at: string | null;
  location?: string | null;
  evidence: string;
  status: string;
  kind: "kelas" | "belajar" | "acara" | "tenggat";
  subkind?: "tugas" | "kuis" | "ujian" | null;
  source?: "ringkasan" | "impor";
};

export type ProjectItem = {
  id: number;
  title: string;
  subject?: string | null;
  doc_count: number;
  updated_at: string;
};

export type ProjectDoc = {
  id: number;
  kind: "summary" | "transcript";
  title: string;
  subject?: string | null;
  position: number;
  added_at: string;
};

export type ProjectDetail = {
  id: number;
  title: string;
  subject?: string | null;
  doc_count: number;
  docs: ProjectDoc[];
  created_at: string;
  updated_at: string;
};

export type ChatItem = {
  id: number;
  title: string;
  project_id: number | null;
  project_title: string | null;
  updated_at: string;
};

export type ChatMessage = {
  id: number;
  role: "user" | "ai";
  content_md: string;
  created_at: string;
};

export type ChatDetail = {
  id: number;
  title: string;
  project_id: number | null;
  project_title: string | null;
  messages: ChatMessage[];
  created_at: string;
  updated_at: string;
};

export type Author = {
  username: string;
  display_name: string;
};

export type Question = {
  id: number;
  title: string;
  body_md: string | null;
  subject: string;
  subject_id: number | null;
  tags: string[];
  author: Author;
  status: "open" | "answered";
  best_answer_id: number | null;
  answers_count: number;
  score: number;
  excerpt: string | null;
  has_attachment: boolean;
  created_at: string;
  updated_at: string | null;
};

export type QuestionDetail = Question & {
  answers: Answer[];
};

export type QuestionList = {
  items: Question[];
  total: number;
  page: number;
  pages: number;
};

export type Answer = {
  id: number;
  body_md: string;
  author: Author;
  score: number;
  is_best: boolean;
  created_at: string;
  updated_at: string | null;
  attachments: unknown[];
};

export type Dashboard = {
  week: WeekDay[];
  next_event: {
    id: number;
    title: string;
    start_at: string;
    kind?: "kelas" | "belajar" | "acara" | "tenggat";
    subkind?: "tugas" | "kuis" | "ujian" | null;
  } | null;
  stats: {
    summaries: number;
    transcripts: number;
    my_unanswered: number;
    points: number;
    rank: number;
  };
  points_ring: unknown; // cut: always null
  questions_for_you: unknown[]; // cut: always []
  reminders: unknown[]; // cut: always []
  top5: unknown[]; // cut: always []
  me_row: unknown; // cut: always null
  recent: {
    id: number;
    kind: "summary" | "transcript";
    title: string;
    subject?: string | null;
    created_at: string;
  }[];
};
