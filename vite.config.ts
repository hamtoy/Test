import { defineConfig } from "vite";
import path from "path";

export default defineConfig({
    build: {
        outDir: "static/dist",
        emptyOutDir: true,
        sourcemap: true,
        rollupOptions: {
            input: path.resolve(__dirname, "static/app.ts"),
            output: {
                entryFileNames: "[name].js",
                chunkFileNames: "chunks/[name].js",
                assetFileNames: "assets/[name][extname]",
            },
        },
    },
    publicDir: false,
});
