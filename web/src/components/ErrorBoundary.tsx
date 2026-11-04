import { Component, type ReactNode } from "react";
import { useI18n } from "../lib/i18n";

function Fallback() {
  const { t } = useI18n();
  return (
    <div className="page-fallback">
      <h1>Orvina</h1>
      <p>{t("errors.internal_error")}</p>
      <button type="button" className="btn" onClick={() => window.location.reload()}>
        {t("common.retry")}
      </button>
    </div>
  );
}

/** DESIGN §2: an error boundary showing a translated message. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) return <Fallback />;
    return this.props.children;
  }
}
