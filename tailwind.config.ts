import type { Config } from "tailwindcss";

// Phase 9 executive design system. shadcn's semantic vars are re-aliased to the
// approved palette in web/src/styles/tokens.css, so the vendored primitives
// inherit the premium look automatically. Extra tokens (canvas/ink/brand/gain…)
// are exposed as first-class utilities for the bespoke executive components.
export default {
  darkMode: ["class"],
  content: ["./web/index.html", "./web/src/**/*.{ts,tsx}"],
  theme: {
    container: { center: true, padding: "2rem", screens: { "2xl": "1400px" } },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: { DEFAULT: "hsl(var(--primary))", foreground: "hsl(var(--primary-foreground))" },
        secondary: { DEFAULT: "hsl(var(--secondary))", foreground: "hsl(var(--secondary-foreground))" },
        destructive: { DEFAULT: "hsl(var(--destructive))", foreground: "hsl(var(--destructive-foreground))" },
        muted: { DEFAULT: "hsl(var(--muted))", foreground: "hsl(var(--muted-foreground))" },
        accent: { DEFAULT: "hsl(var(--accent))", foreground: "hsl(var(--accent-foreground))" },
        popover: { DEFAULT: "hsl(var(--popover))", foreground: "hsl(var(--popover-foreground))" },
        card: { DEFAULT: "hsl(var(--card))", foreground: "hsl(var(--card-foreground))" },
        // Executive palette (semantic)
        canvas: "hsl(var(--canvas))",
        surface: { DEFAULT: "hsl(var(--surface))", sunken: "hsl(var(--surface-sunken))" },
        ink: { DEFAULT: "hsl(var(--ink))", muted: "hsl(var(--ink-muted))", faint: "hsl(var(--ink-faint))" },
        hairline: "hsl(var(--hairline))",
        brand: { DEFAULT: "hsl(var(--brand))", weak: "hsl(var(--brand-weak))" },
        gain: "hsl(var(--gain))",
        loss: "hsl(var(--loss))",
        warn: "hsl(var(--warn))",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["Fraunces", "Georgia", "serif"],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
        card: "var(--r-card)",
        control: "var(--r-control)",
      },
      boxShadow: {
        e1: "var(--e-1)",
        e2: "var(--e-2)",
      },
      keyframes: {
        "accordion-down": { from: { height: "0" }, to: { height: "var(--radix-accordion-content-height)" } },
        "accordion-up": { from: { height: "var(--radix-accordion-content-height)" }, to: { height: "0" } },
        "fade-in": { from: { opacity: "0", transform: "translateY(6px)" }, to: { opacity: "1", transform: "translateY(0)" } },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "fade-in": "fade-in 0.18s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
} satisfies Config;
