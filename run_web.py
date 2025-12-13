"""웹 서버 실행 스크립트."""

import webbrowser
from threading import Timer

import uvicorn


def open_browser() -> None:
    """1초 후 브라우저 자동 오픈."""
    webbrowser.open("http://localhost:8000/qa")


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Gemini QA System - Web Server")
    print("=" * 60)
    print("📍 URL: http://localhost:8000")
    print("🔄 Hot Reload: Enabled")
    print("⚡ Local Only: 127.0.0.1")
    print("=" * 60)

    # 1초 후 브라우저 열기
    Timer(1.5, open_browser).start()

    # 서버 시작
    uvicorn.run(
        "src.web.api:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
    )
