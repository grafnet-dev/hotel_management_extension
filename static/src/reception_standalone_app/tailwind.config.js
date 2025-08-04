module.exports = {
  content: ["./src/**/*.{js,html,xml}", "./**/*.xml"],
  safelist: [
    'text-primary-50',
    'text-primary-100',
    'text-primary-200',
    'text-primary-300',
    'text-primary-400',
    'text-primary-600',
    'text-primary-700',
    'text-primary-800',
    'text-primary-900',
    'bg-gold',
    'text-gold',
    'bg-primary',
    'text-primary',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#005D7C",
          dark: "#00455D",
          light: "#007DA3",
          50: "#e6f4f8",
          100: "#bfe1ed",
          200: "#99cddf",
          300: "#66b8d0",
          400: "#33a3c1",
          600: "#00455D",
          700: "#00323F",
          800: "#001F26",
          900: "#000B0D",
        },
        gold: {
          DEFAULT: "#CE9226",
          light: "#FEDE32",
        },
        accent: {
          orange: "#E05A1B",
          brown: "#593B0B",
        },
      },
      fontFamily: {
        title: ["Bahnschrift", "sans-serif"],
        body: ["Arial", "sans-serif"],
      },
    },
  },
  plugins: [],
};
