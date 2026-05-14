import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#1f2937",
          accent: "#2563eb",
        },
      },
    },
  },
  plugins: [],
};
export default config;
