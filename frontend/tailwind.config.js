/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        void: '#0a0d14',
        surface: '#12161f',
        surface2: '#171c28',
        border: '#242b3a',
        ink: '#e7e9ee',
        muted: '#8b93a7',
        faint: '#5a6376',
        vector: {
          50: '#f1efff',
          200: '#c9c0ff',
          400: '#9a8bff',
          500: '#7c6fff',
          600: '#6552f0',
          700: '#5140c9',
        },
        amber: {
          400: '#ffb86b',
          500: '#ff9f4d',
        },
        signal: {
          green: '#4ade80',
          red: '#ff6b6b',
        },
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'sans-serif'],
        body: ['"Inter"', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      backgroundImage: {
        'grain': "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.035'/%3E%3C/svg%3E\")",
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(14px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'pulse-ring': {
          '0%': { boxShadow: '0 0 0 0 rgba(124,111,255,0.5)' },
          '100%': { boxShadow: '0 0 0 12px rgba(124,111,255,0)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.6s cubic-bezier(0.16, 1, 0.3, 1) both',
        'pulse-ring': 'pulse-ring 1.6s cubic-bezier(0.4,0,0.6,1) infinite',
      },
    },
  },
  plugins: [],
}
