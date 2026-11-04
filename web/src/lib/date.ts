import { useCallback } from "react";
import { useI18n, type Lang } from "./i18n";

const two = (n: number) => String(n).padStart(2, "0");

function dayIndex(date: Date): number {
  // Monday = 0 .. Sunday = 6 (the dashboard week starts on Monday).
  return (date.getDay() + 6) % 7;
}

/** Day-of-week from a date-only ISO string (no local-TZ drift). */
function isoDayIndex(iso: string): number {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  return (d.getUTCDay() + 6) % 7;
}

/** Date and time formatting per the DESIGN §7 copy rules (per language). */
export function useDate() {
  const { lang, t, list } = useI18n();
  const short = list("week.short");
  const long = list("week.long");
  const months = list("week.months");

  const time = useCallback(
    (iso: string) => {
      const d = new Date(iso);
      return lang === "id" ? `${two(d.getHours())}.${two(d.getMinutes())}` : `${two(d.getHours())}:${two(d.getMinutes())}`;
    },
    [lang],
  );

  const fullDate = useCallback(
    (iso: string) => {
      const d = new Date(iso);
      return `${long[dayIndex(d)]}, ${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
    },
    [lang, long, months],
  );

  const fullDateOnly = useCallback(
    (iso: string) => {
      const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
      return `${long[isoDayIndex(iso)]}, ${d.getUTCDate()} ${months[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
    },
    [long, months],
  );

  const shortDay = useCallback(
    (iso: string) => {
      if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) {
        const d = new Date(`${iso}T00:00:00Z`);
        return `${short[isoDayIndex(iso)]} ${d.getUTCDate()}`;
      }
      const d = new Date(iso);
      return `${short[dayIndex(d)]} ${d.getDate()}`;
    },
    [short],
  );

  const todayISO = useCallback(() => {
    const d = new Date();
    return `${d.getFullYear()}-${two(d.getMonth() + 1)}-${two(d.getDate())}`;
  }, []);

  // The server stores UTC and treats the range in Asia/Jakarta (UTC+7, no
  // DST). These helpers mirror that so grouping matches the server, whatever
  // the client's local timezone is.
  const WIB_MS = 7 * 3600 * 1000;

  const wibDay = useCallback((iso: string) => {
    const d = new Date(new Date(iso).getTime() + WIB_MS);
    return `${d.getUTCFullYear()}-${two(d.getUTCMonth() + 1)}-${two(d.getUTCDate())}`;
  }, []);

  const wibTime = useCallback(
    (iso: string) => {
      const d = new Date(new Date(iso).getTime() + WIB_MS);
      return lang === "id" ? `${two(d.getUTCHours())}.${two(d.getUTCMinutes())}` : `${two(d.getUTCHours())}:${two(d.getUTCMinutes())}`;
    },
    [lang],
  );

  const todayWib = useCallback(() => {
    const d = new Date(Date.now() + WIB_MS);
    return `${d.getUTCFullYear()}-${two(d.getUTCMonth() + 1)}-${two(d.getUTCDate())}`;
  }, []);

  const wibShortDay = useCallback(
    (day: string) => {
      const d = new Date(`${day}T00:00:00Z`);
      return `${short[isoDayIndex(day)]} ${d.getUTCDate()}`;
    },
    [short],
  );

  /** Group heading for a YYYY-MM-DD WIB day: "Kam, 5 November" (year only
   *  when it differs from the current WIB year). */
  const wibDayHeading = useCallback(
    (day: string) => {
      const year = Number(day.slice(0, 4));
      const month = Number(day.slice(5, 7));
      const dom = Number(day.slice(8, 10));
      const head = `${short[isoDayIndex(day)]}, ${dom} ${months[month - 1]}`;
      const wibNowYear = new Date(Date.now() + WIB_MS).getUTCFullYear();
      return year === wibNowYear ? head : `${head} ${year}`;
    },
    [short, months],
  );

  const relative = useCallback(
    (iso: string) => {
      const diff = Date.now() - new Date(iso).getTime();
      const min = Math.round(diff / 60000);
      if (min < 1) return t("time.justNow");
      if (min < 60) return min === 1 ? t("time.minAgo1") : t("time.minAgo", { n: min });
      const h = Math.round(min / 60);
      if (h < 24) return h === 1 ? t("time.hourAgo1") : t("time.hourAgo", { n: h });
      const days = Math.round(h / 24);
      if (days === 1) return t("time.yesterday");
      return t("time.dayAgo", { n: days });
    },
    [t],
  );

  return { time, fullDate, fullDateOnly, shortDay, todayISO, wibDay, wibTime, todayWib, wibShortDay, wibDayHeading, relative, lang };
}

export function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${bytes} B`;
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p[0]?.toUpperCase() ?? "").join("") || "?";
}

export type { Lang };
