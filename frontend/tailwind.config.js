/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        blueprint: {
          800: "#16323F",
          900: "#0F2530",
        },
        paper: {
          DEFAULT: "#ECE7DC",
          ink: "#15201D",
          raised: "#F5F0E7",
          muted: "#8A8478",
        },
        civic: {
          orange: "#D6541A",
          red: "#C43E1D",
          amber: "#C99A2E",
          teal: "#3F7D6B",
          blue: "#3E6E8E",
        },
      },
      fontFamily: {
        display: ["Space Grotesk", "sans-serif"],
        body: ["IBM Plex Sans", "sans-serif"],
        mono: ["IBM Plex Mono", "monospace"],
      },
      boxShadow: {
        paper: "0 1px 0 rgba(21,32,29,.08), 0 6px 14px rgba(21,32,29,.06)",
      },
    },
  },
  plugins: [],
};
