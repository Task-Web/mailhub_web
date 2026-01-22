/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Google Sans", "Roboto", "Helvetica", "Arial", "sans-serif"],
        display: ["Space Grotesk", "IBM Plex Sans", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      colors: {
        mailhub: {
          red: "#EA4335",
          bg: "#F6F8FC",
          hover: "#F2F2F2",
          selected: "#C2DBFF",
          text: "#202124",
          secondary: "#5f6368",
        },
      },
    },
  },
  plugins: [],
};
