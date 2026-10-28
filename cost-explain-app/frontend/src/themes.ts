// The five themes, for the picker. Colours here are only the preview swatch; the full token sets live in
// styles.css (one block per theme) — keep the two in step when a theme changes.
export const THEMES = [
  {
    key: "marunouchi", name: "Marunouchi", tag: "Corporate light",
    description: "Crisp white surfaces, ink type and a signal-red accent and primary action. The default.",
    swatch: { side: "#ffffff", bg: "#f5f6f8", panel: "#ffffff", ink: "#0e1116", accent: "#c8102e", up: "#c8102e", down: "#2a78d6" },
  },
  {
    key: "otemachi", name: "Otemachi Night", tag: "Trading-floor dark",
    description: "Near-black, compact and high-contrast for long sessions on trading-desk monitors.",
    swatch: { side: "#07090c", bg: "#0a0c10", panel: "#11141a", ink: "#e9ecf1", accent: "#f0434f", up: "#f04a5a", down: "#3987e5" },
  },
  {
    key: "washi", name: "Washi", tag: "Warm paper, editorial",
    description: "Paper tones, sumi-ink type, vermilion accent and serif headings — board-pack calm.",
    swatch: { side: "#ebe4d5", bg: "#f3efe6", panel: "#fbf8f2", ink: "#1d1a16", accent: "#c53d1f", up: "#c53d1f", down: "#2f5aa8" },
  },
  {
    key: "kon", name: "Kon", tag: "Executive indigo",
    description: "Deep indigo navigation, soft elevated cards and a red signal — private-banking polish.",
    swatch: { side: "#0f1f3d", bg: "#f1f4f9", panel: "#ffffff", ink: "#0c1a33", accent: "#ff3347", up: "#d0021b", down: "#2f6fd1" },
  },
  {
    key: "sumi", name: "Sumi", tag: "Monochrome, high contrast",
    description: "Black on white with hard rules; colour only where the data needs it. Print-friendly.",
    swatch: { side: "#ffffff", bg: "#ffffff", panel: "#ffffff", ink: "#000000", accent: "#000000", up: "#c4001a", down: "#1f4e9c" },
  },
] as const;

export type ThemeKey = (typeof THEMES)[number]["key"];
export const DEFAULT_THEME: ThemeKey = "marunouchi";
export const isTheme = (v: unknown): v is ThemeKey => THEMES.some((t) => t.key === v);
