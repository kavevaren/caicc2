import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { BrandLockup } from "../components/shell/Brand";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Tabs } from "../components/ui/Tabs";
import { ApiError, api, setToken } from "../lib/api";
import { useI18n } from "../lib/i18n";

type FieldErrors = { username?: string; password?: string; terms?: string };

export default function LoginPage() {
  const { t, lang, setLang } = useI18n();
  const nav = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [terms, setTerms] = useState(false);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [err, setErr] = useState<FieldErrors>({});

  const switchMode = (m: "login" | "register") => {
    setMode(m);
    setFormError(null);
    setErr({});
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setFormError(null);
    setErr({});
    try {
      const res =
        mode === "login"
          ? await api.post<{ token: string }>("auth/login", { username, password })
          : await api.post<{ token: string }>("auth/register", {
              username,
              display_name: displayName.trim() || username,
              password,
              lang,
              accept_terms: terms,
            });
      setToken(res.token);
      nav("/", { replace: true });
    } catch (error) {
      const code = error instanceof ApiError ? error.code : "internal_error";
      if (code === "invalid_username" || code === "username_taken") setErr({ username: t(`errors.${code}`) });
      else if (code === "weak_password") setErr({ password: t(`errors.${code}`) });
      else if (code === "terms_required") setErr({ terms: t(`errors.${code}`) });
      else setFormError(t(`errors.${code}`));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-wrap">
      <div className="card auth">
        <div className="lang" role="group" aria-label={t("login.language")}>
          <button type="button" aria-pressed={lang === "id"} onClick={() => setLang("id")}>
            ID
          </button>
          <button type="button" aria-pressed={lang === "en"} onClick={() => setLang("en")}>
            EN
          </button>
        </div>
        <div className="brand">
          <BrandLockup size={40} />
        </div>
        <p className="tagline">{t("login.tagline")}</p>
        <Tabs
          tabs={[
            { id: "login", label: t("login.tabLogin") },
            { id: "register", label: t("login.tabRegister") },
          ]}
          value={mode}
          onChange={(id) => switchMode(id as "login" | "register")}
        />
        <form className="form" onSubmit={submit} noValidate>
          <Input
            id="username"
            label={t("login.username")}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            error={err.username}
          />
          {mode === "register" && (
            <Input
              id="displayName"
              label={t("login.displayName")}
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              autoComplete="name"
            />
          )}
          <Input
            id="password"
            label={t("login.password")}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            error={err.password}
          />
          {mode === "register" && (
            <div className="field">
              <label className="check">
                <input type="checkbox" checked={terms} onChange={(e) => setTerms(e.target.checked)} />
                <span>{t("login.terms")}</span>
              </label>
              {err.terms && (
                <span className="field-error" role="alert">
                  {err.terms}
                </span>
              )}
            </div>
          )}
          {formError && (
            <p className="form-error" role="alert">
              {formError}
            </p>
          )}
          <Button variant="primary" type="submit" disabled={busy}>
            {mode === "login" ? t("login.submitLogin") : t("login.submitRegister")}
          </Button>
        </form>
      </div>
    </div>
  );
}
