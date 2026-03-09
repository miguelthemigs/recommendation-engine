import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#0f0f0f',
          card:    '#1a1a1a',
          raised:  '#242424',
          border:  '#2e2e2e',
        },
        accent: {
          DEFAULT: '#e50914',
          hover:   '#f40612',
          muted:   '#8b0000',
        },
        text: {
          primary:   '#f5f5f5',
          secondary: '#a3a3a3',
          muted:     '#6b7280',
        },
        score: {
          high:   '#22c55e',
          medium: '#eab308',
          low:    '#ef4444',
        },
      },
    },
  },
  plugins: [],
} satisfies Config
