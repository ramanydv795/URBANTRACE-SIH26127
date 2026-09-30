/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#F7F7F4",
        surface: "#FFFFFF",
        "surface-2": "#F1F1EE",
        border: "#E2E1DC",
        ink: "#1A1D1B",
        "ink-muted": "#6B6F6A",
        accent: {
          DEFAULT: "#2B5F63",
          strong: "#1E4548",
          soft: "#DCEAEA",
        },
        success: "#2E7D4F",
        warning: "#A6740A",
        danger: "#B3402A",
        inferred: "#6E5FA8",
      },
      fontFamily: {
        sans: ["Public Sans", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(26,29,27,0.06), 0 1px 1px rgba(26,29,27,0.04)",
      },
    },
  },
  plugins: [],
};
