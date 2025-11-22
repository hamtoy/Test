import os
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

# Notion 클라이언트 생성
try:
    notion = Client(auth=os.environ["NOTION_TOKEN"])
except KeyError:
    print("❌ Error: NOTION_TOKEN not found in .env file")
    exit(1)


def test_connection():
    """Notion API 연결 테스트"""
    print("🔄 Notion API 연결 테스트 시작...")
    try:
        # 페이지 1 테스트
        page1_id = os.environ.get("PAGE_ID_1")
        if not page1_id:
            print("⚠️ PAGE_ID_1 not found in .env")
            return False

        print(f"📄 페이지 1 조회 중... ({page1_id})")
        page1 = notion.pages.retrieve(page1_id)

        # 제목 추출
        title = page1["properties"].get("title") or page1["properties"].get("Name", {})
        if title and "title" in title and title["title"]:
            title_text = "".join([t["plain_text"] for t in title["title"]])
        else:
            title_text = "제목 없음"

        print(f"✅ 페이지 1 연결 성공!")
        print(f"   제목: {title_text}")
        print(f"   URL: {page1.get('url', 'N/A')}")

        # 페이지 2 테스트
        page2_id = os.environ.get("PAGE_ID_2")
        if not page2_id:
            print("⚠️ PAGE_ID_2 not found in .env")
        else:
            print(f"\n📄 페이지 2 조회 중... ({page2_id})")
            page2 = notion.pages.retrieve(page2_id)

            title2 = page2["properties"].get("title") or page2["properties"].get(
                "Name", {}
            )
            if title2 and "title" in title2 and title2["title"]:
                title_text2 = "".join([t["plain_text"] for t in title2["title"]])
            else:
                title_text2 = "제목 없음"

            print(f"✅ 페이지 2 연결 성공!")
            print(f"   제목: {title_text2}")
            print(f"   URL: {page2.get('url', 'N/A')}")

        return True

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        print("\n해결 방법:")
        print("1. .env 파일의 NOTION_TOKEN이 올바른지 확인")
        print(
            "2. Integration이 페이지에 연결되었는지 확인 (페이지 우상단 ... > Connections > Connect to)"
        )
        print("3. 페이지 ID가 정확한지 확인")
        return False


if __name__ == "__main__":
    test_connection()
