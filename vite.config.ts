import { defineConfig } from "vite";
import { fileURLToPath } from "url";
import { dirname, resolve } from "path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

export default defineConfig({
    base: "/static/dist/",
    build: {
        outDir: "static/dist",
        emptyOutDir: true,
        sourcemap: true,
        // OPT-1: Bundle optimization settings
        minify: "esbuild", // Fast minification
        target: "es2020", // Modern browsers for smaller bundles
        chunkSizeWarningLimit: 500, // KB warning threshold
        rollupOptions: {
            input: resolve(__dirname, "static/app.ts"),
            output: {
                entryFileNames: "[name].[hash].js",
                chunkFileNames: "chunks/[name].[hash].js",
                assetFileNames: "assets/[name].[hash][extname]",
                // Manual chunks for better caching
                manualChunks: (id) => {
                    // Separate vendor chunks for better caching
                    if (id.includes("node_modules")) {
                        return "vendor";
                    }
                    // Group related modules
                    if (id.includes("/utils")) {
                        return "utils";
                    }
                },
            },
            // Tree-shaking optimization
            treeshake: {
                moduleSideEffects: false,
                propertyReadSideEffects: false,
            },
        },
    },
    // Optimize dependencies
    optimizeDeps: {
        include: [], // Pre-bundle common dependencies
    },
    publicDir: false,
});
