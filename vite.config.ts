// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - TanStack devtools (dev-only, first), tanstackStart, viteReact, tailwindcss, tsConfigPaths,
//     nitro (build-only using cloudflare as a default target), VITE_* env injection, @ path alias,
//     React/TanStack dedupe, error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

const backendUrl = process.env["CONTROL_TOWER_API_URL"] ?? "http://127.0.0.1:8000";

export default defineConfig({
  vite: {
    server: {
      proxy: {
        "/api": { target: backendUrl, changeOrigin: true },
        "/health": { target: backendUrl, changeOrigin: true },
      },
    },
  },
  tanstackStart: {
    // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
    // nitro/vite builds from this
    server: { entry: "server" },
  },
  // Deployment target: Cloudflare is the default (Lovable preview/sandbox keeps it),
  // Vercel is selected automatically when building on Vercel (VERCEL=1) or when
  // NITRO_PRESET is set. NITRO_PRESET always wins if you need to force a target.
  ...(() => {
    const preset = process.env["NITRO_PRESET"] ?? (process.env["VERCEL"] ? "vercel" : undefined);
    return preset ? { nitro: { preset } } : {};
  })(),
});
