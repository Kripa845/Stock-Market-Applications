/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],

  theme: {
    extend: {
      colors: {
        // Dark theme (default). The light theme overrides these in index.css.
        "bg-card": "#1A1433",
        "bg-elevated": "#221A40",
        "bg-border": "#2E2654",
        "bg-primary": "#0A0718",
        "bg-secondary": "#130E28",

        "accent": "#7C3AED",
        "accent-light": "#A78BFA",
        "accent-glow": "#7C3AED24",
        "cyan": "#22D3EE",

        "text-primary": "#E2E8F0",
        "text-secondary": "#A1A1C2",
        "text-muted": "#A1A1C2",

        "up": "#10B981",
        "down": "#EF4444",
      },
      keyframes: {
        "panel-in": { from: { transform: "translateX(100%)" }, to: { transform: "translateX(0)" } },
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
      },
      animation: {
        "panel-in": "panel-in 180ms ease-out",
        "fade-in": "fade-in 180ms ease-out",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "SFMono-Regular", "Consolas", "monospace"],
        devanagari: ["Noto Sans Devanagari", "Nirmala UI", "Mangal", "sans-serif"],
      },
    },
  },

  plugins: [],
};
