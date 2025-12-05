const purgecss = require("@fullhuman/postcss-purgecss");

const isProd = process.env.NODE_ENV === "production";

module.exports = {
    plugins: [
        isProd &&
            purgecss.default({
                content: [
                    "./templates/**/*.{html,htm,j2}",
                    "./static/**/*.ts",
                    "./static/**/*.css",
                ],
                safelist: {
                    standard: [
                        "btn",
                        "btn-small",
                        "qa-card",
                        "qa-type-badge",
                        "qa-section",
                        "qa-content",
                        "qa-header",
                        "progress-fill",
                        "progress-container",
                        "loading",
                        "toast",
                        /^toast--/,
                        /^qa-/,
                        /^workspace/,
                        /^mode-tab/,
                        "active",
                        "output-only",
                        "required-input",
                        "field-badge",
                        "status-text",
                        "copied",
                    ],
                },
                defaultExtractor: (content) =>
                    content.match(/[\w-/:]+(?<!:)/g) || [],
            }),
    ].filter(Boolean),
};
