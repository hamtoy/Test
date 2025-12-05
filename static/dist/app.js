import { initQA } from "./qa.js";
import { initWorkspace } from "./workspace.js";
import { initEval } from "./eval.js";
// Entry point: 페이지별 초기화
document.addEventListener("DOMContentLoaded", () => {
    const path = window.location.pathname;
    if (path === "/qa") {
        initQA();
    }
    else if (path === "/workspace") {
        initWorkspace();
    }
    else if (path === "/eval") {
        initEval();
    }
});
