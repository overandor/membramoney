import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: {
          primary: "#0B0B0D",
          secondary: "#121216",
          tertiary: "#18181D",
          quaternary: "#202027",
        },
        orange: {
          primary: "#FF6A00",
          hot: "#FF8A1F",
          warning: "#E9441F",
        },
        text: {
          muted: "#A8A29E",
          main: "#F5F2EE",
        },
        border: "rgba(255, 106, 0, 0.18)",
      },
      boxShadow: {
        glow: "0 0 40px rgba(255, 106, 0, 0.25)",
        "glow-sm": "0 0 30px rgba(255, 106, 0, 0.35)",
      },
    },
  },
  plugins: [],
};
export default config;
