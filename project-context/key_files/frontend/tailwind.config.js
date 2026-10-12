/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],

  theme: {
    extend: {
      colors: {
        "bg-card": "#161a25",
        "bg-elevated": "#1b1f2a",
        "bg-border": "#242832",
        "bg-primary": "#0d0e14",
        "bg-secondary": "#11141c",

        "accent": "#7C3AED",
        "accent-light": "#A78BFA",
        "accent-glow": "#7C3AED24",

        "text-primary": "#d1d4dc",
        "text-secondary": "#787b86",
        "text-muted": "#787b86",

        "up": "#26a69a",
        "down": "#ef5350",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "SFMono-Regular", "Consolas", "monospace"],
      },
    },
  },

  plugins: [],
};
