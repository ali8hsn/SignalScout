/** Theme tokens: cream/olive editorial-intelligence look (locked decision in plan.md). */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        cream: '#F5F3EC',
        card: '#FBFAF5',
        ink: '#1C1B16',
        'ink-soft': '#4A4638',
        'ink-faint': '#8A8574',
        olive: '#6B6B32',
        'olive-dark': '#565628',
        line: '#D8D4C4',
        'line-soft': '#E6E2D4',
      },
      fontFamily: {
        display: ['"Instrument Serif"', 'Georgia', '"Times New Roman"', 'serif'],
        mono: ['"SF Mono"', 'ui-monospace', 'Menlo', 'monospace'],
        body: ['Georgia', '"Times New Roman"', 'serif'],
      },
    },
  },
  plugins: [],
};
