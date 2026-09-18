/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],

  theme: {
    extend: {
      colors: {
        "bg-card": "#111527",
        "bg-elevated": "#171B2E",
        "bg-border": "#1E2538",
        "bg-primary": "#0B0E1A",
        "bg-secondary": "#161B2E",

        "accent": "#7C3AED",
        "accent-light": "#8B5CF6",
        "accent-glow": "#7C3AED33",

        "text-primary": "#E2E8F0",
        "text-secondary": "#94A3B8",
        "text-muted": "#64748B",

        "up": "#22C55E",
        "down": "#EF4444",
      },
    },
  },

  plugins: [],
};