import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        glass: {
          white: 'rgba(255,255,255,0.06)',
          border: 'rgba(255,255,255,0.12)',
          hover:  'rgba(255,255,255,0.10)',
        },
        apple: {
          purple: '#BF5AF2',
          blue:   '#0A84FF',
          pink:   '#FF375F',
          gold:   '#FFD60A',
          green:  '#30D158',
          gray:   '#8E8E93',
        },
      },
      backdropBlur: {
        xs: '2px',
      },
      animation: {
        'gradient-shift': 'gradientShift 20s ease-in-out infinite alternate',
        'float-in':       'floatIn 0.6s cubic-bezier(0.16,1,0.3,1) forwards',
        'pulse-soft':     'pulseSoft 3s ease-in-out infinite',
      },
      keyframes: {
        gradientShift: {
          '0%':   { backgroundPosition: '0% 50%' },
          '100%': { backgroundPosition: '100% 50%' },
        },
        floatIn: {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        pulseSoft: {
          '0%,100%': { opacity: '0.6' },
          '50%':     { opacity: '1' },
        },
      },
      fontFamily: {
        sans: [
          '-apple-system', 'BlinkMacSystemFont', '"SF Pro Display"',
          '"Helvetica Neue"', 'sans-serif',
        ],
        mono: ['"SF Mono"', '"JetBrains Mono"', 'monospace'],
      },
      boxShadow: {
        glass: '0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.1)',
        glow:  '0 0 40px rgba(10,132,255,0.25)',
      },
    },
  },
  plugins: [],
}

export default config
