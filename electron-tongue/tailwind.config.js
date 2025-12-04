/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'mit-red': '#D64545',
        'mit-red-dark': '#c0392b',
      },
    },
  },
  plugins: [],
}




