/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // "Field map" palette — deep survey-chart navy with a warm sodium
        // amber for the things you're looking for, and a quiet teal for
        // confirmed/located state. Avoids the generic dark-mode + neon-accent
        // default: this is closer to a printed topographic chart at night.
        chart: {
          950: '#0b1320',
          900: '#101a2c',
          800: '#16233a',
          700: '#1f2f4a',
          600: '#2c4163',
          500: '#3d5780',
          line: '#3a4d6b',
        },
        amber: {
          400: '#e8a23b',
          500: '#d68a23',
        },
        teal: {
          400: '#4fb3a9',
          500: '#3a9189',
        },
        paper: '#f3efe4',
      },
      fontFamily: {
        display: ['"Spectral"', 'Georgia', 'serif'],
        sans: ['"Inter"', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
}
