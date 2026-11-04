import { useI18n } from "../../lib/i18n";
import type { WeekDay } from "../../lib/types";

/**
 * The week as a STATIC orbit (redesign §3, _LEAN §3: no rotation or zoom).
 * Seven labeled day dots on an ellipse; today gets a double ring and a bold
 * label. Dot colour follows the dominant agenda kind of that day:
 * Kelas = hollow blue circle, Belajar = accent-mid dot, Tenggat = accent dot.
 * Labels are pushed radially outward and clamped so they never overlap a dot
 * (BUG-18).
 */
const CX = 200;
const CY = 112;
const RX = 158;
const RY = 60;

function pos(i: number): { x: number; y: number } {
  const theta = ((270 + i * (360 / 7)) * Math.PI) / 180;
  return { x: CX + RX * Math.cos(theta), y: CY + RY * Math.sin(theta) };
}

/** Radial label offset: further out where the ellipse is flat, so the text
 *  clears the dots and its neighbours (BUG-18). The widened viewBox
 *  (-44 … 444) gives the edge labels room, so the only clamps are the ones
 *  that keep each label clear of its own dot and today ring. */
function labelPos(i: number): { x: number; y: number; anchor: "start" | "end" | "middle" } {
  const { x, y } = pos(i);
  const dx = x - CX;
  const dy = y - CY;
  const len = Math.hypot(dx, dy) || 1;
  const anchor: "start" | "end" | "middle" = dx > 12 ? "start" : dx < -12 ? "end" : "middle";
  // Push 34px outward on a circular basis, then keep at least 19 px
  // (today ring r 13 + 6) between the label edge and the dot centre.
  const raw = x + (dx / len) * 34;
  let lx = raw;
  if (anchor === "start") lx = Math.max(raw, x + 19);
  if (anchor === "end") lx = Math.min(raw, x - 19);
  let ly = y + (dy / len) * 30;
  if (anchor === "middle" && Math.abs(ly - y) < 22) ly = y + (dy < 0 ? -22 : 22);
  return { x: Math.min(440, Math.max(-40, lx)), y: Math.min(236, Math.max(10, ly)), anchor };
}

function kindOf(day: WeekDay): "kelas" | "belajar" | "tenggat" | "acara" | null {
  if (day.events.length === 0) return null;
  const has = (k: string) => day.events.some((e) => e.kind === k);
  if (has("tenggat")) return "tenggat";
  if (has("kelas")) return "kelas";
  if (has("belajar")) return "belajar";
  return "acara";
}

export function WeekOrbit({ week, todayISO }: { week: WeekDay[]; todayISO: string }) {
  const { list, t } = useI18n();
  const days = list("week.short");

  const items = week.map((day, i) => {
    const { x, y } = pos(i);
    const lp = labelPos(i);
    const kind = kindOf(day);
    const isToday = day.date === todayISO;
    const busy = day.events.length > 0;
    const label = days[i] ? `${days[i]} ${Number(day.date.slice(8))}` : day.date;
    const aria = busy
      ? t("schedule.planetBusy", { day: label, n: day.events.length })
      : t("schedule.planetFree", { day: label });
    return { day, i, x, y, lp, kind, isToday, busy, label, aria };
  });

  return (
    <div className="hero-orbit">
      <svg className="orbit-svg" viewBox="-44 0 488 246" role="img" aria-label={t("dashboard.orbitAria")}>
        <ellipse className="o-ring2" cx={CX} cy={CY} rx={RX + 14} ry={RY + 22} transform={`rotate(-16 ${CX} ${CY})`} />
        <ellipse className="o-ring" cx={CX} cy={CY} rx={RX} ry={RY} />
        <circle className="o-halo" cx={CX} cy={CY} r={26} />
        <circle className="o-nucleus" cx={CX} cy={CY} r={13} />
        {items.map((d) => (
          <g key={d.day.date}>
            {d.isToday && (
              <>
                <circle className="o-today" cx={d.x} cy={d.y} r={15} />
                <circle className="o-today2" cx={d.x} cy={d.y} r={19} />
              </>
            )}
            <circle className={`o-dot${d.kind ? ` ${d.kind}` : ""}`} cx={d.x} cy={d.y} r={d.busy ? 9 : 7} />
            <title>{d.aria}</title>
            <text className={d.isToday ? "on" : ""} x={d.lp.x} y={d.lp.y} textAnchor={d.lp.anchor}>
              {d.label}
            </text>
          </g>
        ))}
      </svg>
      <div className="orbit-legend" aria-hidden="true">
        <span>
          <i className="lg-kelas" /> {t("dashboard.legendKelas")}
        </span>
        <span>
          <i className="lg-belajar" /> {t("dashboard.legendBelajar")}
        </span>
        <span>
          <i className="lg-tenggat" /> {t("dashboard.legendTenggat")}
        </span>
      </div>
    </div>
  );
}
