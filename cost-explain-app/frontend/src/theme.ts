// Theme choice — one of the five in themes.ts — stored per browser and applied as <html data-theme>.
// index.html applies the saved (or ?theme=) choice before first paint, so there is no flash of the wrong theme.
import { useEffect, useState } from "react";
import { DEFAULT_THEME, isTheme, type ThemeKey } from "./themes";

const KEY = "ce-theme";
const EVENT = "ce-theme-change";

function current(): ThemeKey {
  const t = document.documentElement.dataset.theme;
  return isTheme(t) ? t : DEFAULT_THEME;
}

export function useTheme(): [ThemeKey, (t: ThemeKey) => void] {
  const [theme, setTheme] = useState<ThemeKey>(current);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(KEY, theme);
    } catch {
      /* storage unavailable (private mode): the choice lasts for this page only */
    }
    window.dispatchEvent(new Event(EVENT));
  }, [theme]);
  return [theme, setTheme];
}

// Resolved values of CSS custom properties, for chart code that needs concrete colours. Re-read whenever the
// theme changes.
export function useCssVars<K extends string>(names: readonly K[]): Record<K, string> {
  const [, bump] = useState(0);
  useEffect(() => {
    const update = () => bump((n) => n + 1);
    window.addEventListener(EVENT, update);
    return () => window.removeEventListener(EVENT, update);
  }, []);
  const cs = getComputedStyle(document.documentElement);
  return Object.fromEntries(names.map((n) => [n, cs.getPropertyValue(`--${n}`).trim()])) as Record<K, string>;
}
