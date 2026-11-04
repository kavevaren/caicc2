/**
 * Tiny i18n (no i18next, per _LEAN §4): `t(key, params)` reads the JSON
 * locales; the language comes from the user (me.lang) or localStorage.
 */
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import id from "../locales/id.json";
import en from "../locales/en.json";

export type Lang = "id" | "en";

const DICTS: Record<Lang, unknown> = { id, en };
const LANG_KEY = "orvina-lang";

function lookup(dict: unknown, path: string): unknown {
  const parts = path.split(".");
  let cur: unknown = dict;
  for (let i = 0; i < parts.length; i++) {
    if (!cur || typeof cur !== "object") return undefined;
    // A flat dotted key stored in the JSON wins over descending into a
    // nested prefix ("style" + "style.one_page" must resolve the flat one).
    const rest = parts.slice(i).join(".");
    if (rest in (cur as Record<string, unknown>)) {
      return (cur as Record<string, unknown>)[rest];
    }
    if (parts[i] in (cur as Record<string, unknown>)) {
      cur = (cur as Record<string, unknown>)[parts[i]];
    } else {
      return undefined;
    }
  }
  return cur;
}

type I18n = {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
  list: (key: string) => string[];
};

const I18nCtx = createContext<I18n | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    try {
      const s = localStorage.getItem(LANG_KEY);
      return s === "en" || s === "id" ? s : "id";
    } catch {
      return "id";
    }
  });

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(LANG_KEY, l);
    } catch {
      // in-memory only
    }
  }, []);

  const t = useCallback(
    (key: string, params?: Record<string, string | number>) => {
      let raw: unknown = lookup(DICTS[lang], key);
      if (typeof raw !== "string") raw = lookup(DICTS.id, key);
      let out = typeof raw === "string" ? raw : key;
      if (params) for (const [k, v] of Object.entries(params)) out = out.split(`{${k}}`).join(String(v));
      return out;
    },
    [lang],
  );

  const list = useCallback(
    (key: string) => {
      const v = lookup(DICTS[lang], key) ?? lookup(DICTS.id, key);
      return Array.isArray(v) ? v.map(String) : [];
    },
    [lang],
  );

  const value = useMemo(() => ({ lang, setLang, t, list }), [lang, setLang, t, list]);
  return <I18nCtx.Provider value={value}>{children}</I18nCtx.Provider>;
}

export function useI18n(): I18n {
  const ctx = useContext(I18nCtx);
  if (!ctx) throw new Error("useI18n must be used inside I18nProvider");
  return ctx;
}
