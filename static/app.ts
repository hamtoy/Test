import { registerGlobalErrorHandlers } from "./utils.js";

// Entry point: 페이지별 초기화
document.addEventListener("DOMContentLoaded", () => {
    registerGlobalErrorHandlers();
    const path = window.location.pathname;
    if (path === "/qa") {
        import("./qa.js")
            .then(({ initQA }) => initQA())
            .catch((err) => console.error("QA 모듈 로드 실패:", err));
    } else if (path === "/workspace") {
        import("./workspace.js")
            .then(({ initWorkspace }) => initWorkspace())
            .catch((err) => console.error("Workspace 모듈 로드 실패:", err));
    } else if (path === "/eval") {
        import("./eval.js")
            .then(({ initEval }) => initEval())
            .catch((err) => console.error("Eval 모듈 로드 실패:", err));
    }
});
