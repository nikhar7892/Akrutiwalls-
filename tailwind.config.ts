import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Firm branding — values come from CSS variables set per-request by the
        // root layout based on the resolved Firm. Fallbacks match the default firm.
        brand: {
          DEFAULT: "rgb(var(--brand-primary-rgb, 31 41 55) / <alpha-value>)",
          accent: "rgb(var(--brand-accent-rgb, 37 99 235) / <alpha-value>)",
        },
      },
    },
  },
  plugins: [],
};
export default config;
