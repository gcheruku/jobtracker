/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Pipeline column accent colors (echoing the figma design).
        saved: "#6366f1",
        applied: "#0ea5e9",
        interviewing: "#f59e0b",
        offer: "#10b981",
        rejected: "#ef4444",
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};
