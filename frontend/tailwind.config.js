/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        evidexa: {
          midnight: "#080808",
          charcoal: "#121214",
          slate: "#27272A",
          cyan: "#FF6B00",
          orange: "#FF6B00",
          aqua: "#FFA34D",
          reticle: "#00F0FF",
          blue: "#18181B",
          dark: "#050505",
        },
        status: {
          confirmed: "#10B981",
          candidate: "#F59E0B",
          contradicted: "#EF4444",
          unresolved: "#6B7280",
        },
      },
      fontFamily: {
        sans: ["Space Grotesk", "Inter", "Noto Sans Devanagari", "system-ui", "-apple-system", "sans-serif"],
        mono: ["IBM Plex Mono", "JetBrains Mono", "monospace"],
      },
      boxShadow: {
        glow: "0 0 16px -2px rgba(255, 107, 0, 0.35)",
        card: "0 4px 20px -2px rgba(0, 0, 0, 0.8)",
      },
    },
  },
  plugins: [],
};

