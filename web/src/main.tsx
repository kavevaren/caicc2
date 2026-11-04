import React from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/poppins/400.css";
import "@fontsource/poppins/500.css";
import "@fontsource/poppins/600.css";
import "@fontsource/poppins/700.css";
import "./styles/tokens.css";
import "./styles/app.css";
import "./styles/app-pages.css";
import "./styles/app-social.css";
import App from "./App";

/**
 * Theme init (DESIGN §1.1): a saved choice wins; otherwise follow the
 * system preference. Shell.tsx applies the server theme on first login.
 */
function initTheme(): void {
  let saved = "";
  try {
    saved = localStorage.getItem("orvina-theme") ?? "";
  } catch {
    saved = "";
  }
  const theme =
    saved === "light" || saved === "dark"
      ? saved
      : window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";
  document.documentElement.dataset.theme = theme;
}

initTheme();

/**
 * Dev only: MSW mocks, unless VITE_NO_MSW=1 (click-through against the real
 * local server via the vite /api proxy). Production builds never import it.
 */
async function enableMocks(): Promise<void> {
  if (!import.meta.env.DEV) return;
  if (import.meta.env.VITE_NO_MSW === "1") return;
  const { worker } = await import("./mocks/browser");
  await worker.start({ quiet: true, onUnhandledRequest: "bypass" });
}

enableMocks().then(() => {
  createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
});
