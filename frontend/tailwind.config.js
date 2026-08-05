/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          violet: "#8b5cf6",
          indigo: "#6366f1",
        },
      },
    },
  },
  plugins: [],
};
