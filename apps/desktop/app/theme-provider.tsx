"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

type Theme = "light" | "dark";

interface ThemeContextValue {
  theme: Theme;
  toggle: () => void;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);
const STORAGE_KEY = "avos-theme";

function applyThemeClass(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
}

/**
 * Light by default (per the person's own choice), with a persisted
 * override and a toggle in the Topbar. The class this flips (`dark` on
 * <html>) is exactly what globals.css's `@custom-variant dark` and every
 * shadcn/ui primitive already key off - no separate light/dark component
 * variants are needed anywhere else in the app.
 *
 * A blocking inline script in the document head (see layout.tsx) applies
 * the stored/system theme before first paint, so there is no light-mode
 * flash for a person who has chosen dark.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("light");

  useEffect(() => {
    // Read back whatever the pre-paint inline script (or the default)
    // already applied, so React's state matches the DOM with no flash.
    // This one-time sync from an external system (the DOM class set
    // before hydration) can't happen during render - the server has no
    // DOM to read - so it deliberately runs here instead.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setThemeState(document.documentElement.classList.contains("dark") ? "dark" : "light");
  }, []);

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next);
    applyThemeClass(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Private browsing / storage disabled - theme just won't persist.
    }
  }, []);

  const toggle = useCallback(() => {
    setTheme(theme === "dark" ? "light" : "dark");
  }, [theme, setTheme]);

  return <ThemeContext.Provider value={{ theme, toggle, setTheme }}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}

/** Runs before hydration (see layout.tsx <head>) - stringified once here
 * so the provider and the inline bootstrap script can't drift apart. */
export const THEME_BOOTSTRAP_SCRIPT = `
(function () {
  try {
    var stored = localStorage.getItem("${STORAGE_KEY}");
    var theme = stored === "dark" || stored === "light" ? stored : "light";
    if (theme === "dark") document.documentElement.classList.add("dark");
  } catch (e) {}
})();
`;
