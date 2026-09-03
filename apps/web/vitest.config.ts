import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

const dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(dirname, "src"),
      // Next.js's build swaps this in for server-only bundles; vitest has
      // no such build step, so route/server-module tests get a no-op here
      // instead of the real package's unconditional throw.
      "server-only": path.resolve(dirname, "src/test/server-only-stub.ts"),
    },
  },
});
