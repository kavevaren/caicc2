import { AlertTriangle } from "lucide-react";
import { useI18n } from "../../lib/i18n";
import { Button } from "./Button";

/** DESIGN §5: errors inline, translated, with "Coba lagi"; never a stack trace. */
export function ErrorBox({ code, onRetry }: { code: string; onRetry?: () => void }) {
  const { t } = useI18n();
  return (
    <div className="error-box" role="alert">
      <AlertTriangle size={18} strokeWidth={1.8} aria-hidden="true" />
      <div>
        <p>{t(`errors.${code}`)}</p>
        {onRetry && (
          <Button variant="secondary" onClick={onRetry}>
            {t("common.retry")}
          </Button>
        )}
      </div>
    </div>
  );
}
