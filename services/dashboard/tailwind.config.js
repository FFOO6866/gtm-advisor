/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Custom brand colors
        brand: {
          50: '#f0f7ff',
          100: '#e0efff',
          200: '#baddff',
          300: '#7cc2ff',
          400: '#36a3ff',
          500: '#0c87ff',
          600: '#0068db',
          700: '#0052b0',
          800: '#004591',
          900: '#003a78',
          950: '#00244f',
        },
        // Agent colors
        agent: {
          strategist: '#8B5CF6',
          market: '#10B981',
          competitor: '#F59E0B',
          customer: '#EC4899',
          leads: '#3B82F6',
          campaign: '#EF4444',
        },
        // Dark mode surfaces
        surface: {
          DEFAULT: '#0a0a0f',
          50: '#16161f',
          100: '#1a1a24',
          200: '#22222e',
          300: '#2d2d3a',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        display: ['Cal Sans', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Menlo', 'monospace'],
      },
      animation: {
        // Aurora background animation
        'aurora': 'aurora 60s linear infinite',
        // Pulse glow for active agents
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
        // Subtle float for cards
        'float': 'float 6s ease-in-out infinite',
        // Connection line pulse
        'connection-pulse': 'connection-pulse 1.5s ease-in-out infinite',
        // Thinking indicator
        'thinking': 'thinking 1.4s ease-in-out infinite',
        // Shimmer effect
        'shimmer': 'shimmer 2s linear infinite',
        // Scale in
        'scale-in': 'scale-in 0.2s ease-out',
        // Fade up
        'fade-up': 'fade-up 0.5s ease-out',
        // Spin slow
        'spin-slow': 'spin 8s linear infinite',
        // Border beam
        'border-beam': 'border-beam 4s linear infinite',
      },
      keyframes: {
        aurora: {
          '0%': { backgroundPosition: '50% 50%, 50% 50%' },
          '100%': { backgroundPosition: '350% 50%, 350% 50%' },
        },
        'pulse-glow': {
          '0%, 100%': {
            opacity: 1,
            boxShadow: '0 0 20px 0 var(--glow-color, rgba(139, 92, 246, 0.5))',
          },
          '50%': {
            opacity: 0.8,
            boxShadow: '0 0 40px 10px var(--glow-color, rgba(139, 92, 246, 0.7))',
          },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        'connection-pulse': {
          '0%': { strokeDashoffset: 24, opacity: 0.3 },
          '50%': { opacity: 1 },
          '100%': { strokeDashoffset: 0, opacity: 0.3 },
        },
        thinking: {
          '0%': { transform: 'scale(0.95)', opacity: 0.5 },
          '50%': { transform: 'scale(1)', opacity: 1 },
          '100%': { transform: 'scale(0.95)', opacity: 0.5 },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'scale-in': {
          '0%': { transform: 'scale(0.95)', opacity: 0 },
          '100%': { transform: 'scale(1)', opacity: 1 },
        },
        'fade-up': {
          '0%': { transform: 'translateY(10px)', opacity: 0 },
          '100%': { transform: 'translateY(0)', opacity: 1 },
        },
        'border-beam': {
          '0%': { offsetDistance: '0%' },
          '100%': { offsetDistance: '100%' },
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic': 'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
        'aurora-gradient': `
          repeating-linear-gradient(100deg, #3b82f6 10%, #8b5cf6 15%, #ec4899 20%, #10b981 25%, #3b82f6 30%),
          repeating-linear-gradient(100deg, #0a0a0f 0%, #0a0a0f 7%, transparent 10%, transparent 12%, #0a0a0f 16%)
        `,
        'shimmer-gradient': 'linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent)',
      },
      boxShadow: {
        'glow-sm': '0 0 15px -3px var(--glow-color, rgba(139, 92, 246, 0.4))',
        'glow': '0 0 25px -5px var(--glow-color, rgba(139, 92, 246, 0.5))',
        'glow-lg': '0 0 40px -10px var(--glow-color, rgba(139, 92, 246, 0.6))',
        'inner-glow': 'inset 0 0 20px -5px var(--glow-color, rgba(139, 92, 246, 0.3))',
        'glass': '0 8px 32px 0 rgba(0, 0, 0, 0.37)',
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
}
