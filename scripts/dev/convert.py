import csv
from pathlib import Path


def convert_qa_guide_to_csv(md_file, csv_file):
    """
    QA 작업 가이드를 CSV로 변환
    - 대분류(#), 중분류(##), 소분류(###) 구조를 보존
    """

    content = Path(md_file).read_text(encoding="utf-8")
    lines = content.split("\n")

    csv_data = []
    current_h1 = ""
    current_h2 = ""
    current_h3 = ""
    current_content = []

    for line in lines:
        # Notion aside 블록 제거
        if line.startswith("<aside>") or line.startswith("</aside>"):
            continue

        # 이미지 라인 제거
        if line.startswith("!["):
            continue

        # 헤딩 처리
        if line.startswith("### "):
            # 이전 내용 저장
            if current_h3:
                csv_data.append(
                    [
                        current_h1,
                        current_h2,
                        current_h3,
                        "\n".join(current_content).strip(),
                    ]
                )

            current_h3 = line.replace("### ", "").strip()
            current_content = []

        elif line.startswith("## "):
            if current_h3:
                csv_data.append(
                    [
                        current_h1,
                        current_h2,
                        current_h3,
                        "\n".join(current_content).strip(),
                    ]
                )

            current_h2 = line.replace("## ", "").strip()
            current_h3 = ""
            current_content = []

        elif line.startswith("# "):
            if current_h3:
                csv_data.append(
                    [
                        current_h1,
                        current_h2,
                        current_h3,
                        "\n".join(current_content).strip(),
                    ]
                )

            current_h1 = line.replace("# ", "").strip()
            current_h2 = ""
            current_h3 = ""
            current_content = []
        else:
            # 일반 내용 누적
            if line.strip():
                current_content.append(line)

    # 마지막 섹션 저장
    if current_h3:
        csv_data.append(
            [current_h1, current_h2, current_h3, "\n".join(current_content).strip()]
        )

    # CSV 저장
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["대분류", "중분류", "소분류", "내용"])
        writer.writerows(csv_data)

    print(f"✅ 변환 완료: {len(csv_data)}개 섹션")


# 사용
convert_qa_guide_to_csv("guide.md", "output.csv")
