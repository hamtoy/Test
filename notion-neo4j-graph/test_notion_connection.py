import os

import pytest
from dotenv import load_dotenv

pytest.importorskip("notion_client")
from notion_client import Client  # noqa: E402

load_dotenv()

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
notion = Client(auth=NOTION_TOKEN) if NOTION_TOKEN else None


@pytest.mark.skipif(
    not all([NOTION_TOKEN, os.environ.get("PAGE_ID_1")]),
    reason="Notion 환경 변수가 설정되지 않아 연결 테스트를 건너뜁니다.",
)
def test_connection():
    """Notion API 연결 테스트."""
    assert notion is not None

    page1_id = os.environ["PAGE_ID_1"]
    page1 = notion.pages.retrieve(page1_id)

    # 제목 추출
    title = page1["properties"].get("title") or page1["properties"].get("Name", {})
    if title and "title" in title and title["title"]:
        title_text = "".join([t["plain_text"] for t in title["title"]])
    else:
        title_text = "제목 없음"

    assert title_text

    page2_id = os.environ.get("PAGE_ID_2")
    if page2_id:
        page2 = notion.pages.retrieve(page2_id)
        title2 = page2["properties"].get("title") or page2["properties"].get("Name", {})
        if title2 and "title" in title2 and title2["title"]:
            title_text2 = "".join([t["plain_text"] for t in title2["title"]])
        else:
            title_text2 = "제목 없음"
        assert title_text2


if __name__ == "__main__":
    test_connection()
