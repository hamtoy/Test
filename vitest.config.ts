import { defineConfig } from "vitest/config";

export default defineConfig({
    test: {
        include: ["static/__tests__/**/*.test.ts"],
        environment: "jsdom",  // Enable DOM APIs for component tests
        globals: true,
    },
});
