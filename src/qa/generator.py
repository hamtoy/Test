import json
import logging
import os
import re
import sys

from openai import OpenAI

# ==========================================
# 0. 설정 및 프롬프트 로드
# ==========================================
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

QUERY_COUNT = 4  # 3 또는 4로 설정

# API Client Setup
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    logger.warning("GEMINI_API_KEY environment variable not found.")
    # You might want to handle this more gracefully or try OPENAI_API_KEY
    api_key = os.environ.get("OPENAI_API_KEY")

if not api_key:
    logger.error("No API Key found. Please set GEMINI_API_KEY.")
    sys.exit(1)

client = OpenAI(
    api_key=api_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# 파일에서 시스템 프롬프트 로드
try:
    with open("질의 생성.txt", "r", encoding="utf-8") as f:
        SYSTEM_PROMPT_QUERY = f.read()
    with open("답변 생성 - 복사본.txt", "r", encoding="utf-8") as f:
        SYSTEM_PROMPT_ANSWER = f.read()
except FileNotFoundError:
    logger.error("오류: 프롬프트 파일(.txt)을 찾을 수 없습니다.")
    sys.exit(1)

# 테스트용 OCR 텍스트 (사용자님의 예시 텍스트)
ocr_text = """
글로벌 주식시장 변화와 전망
미 증시, 완화적 Fed Speak 에 반발 매수 유입... (중략) ...
"""

# ==========================================
# 1. 질의 생성 (Query Generation)
# ==========================================

# 3개일 때와 4개일 때 요청할 유형 정의
if QUERY_COUNT == 4:
    type_instruction = """
    다음 4가지 유형의 질의를 순서대로 생성하세요:
    1. [전체 설명]: 전체 맥락을 아우르는 포괄적 설명 요청
    2. [추론]: 텍스트 내 근거를 바탕으로 한 미래 전망이나 논리적 추론
    3. [이미지 내 타겟(단답형)]: 특정 수치나 팩트를 묻는 질문
    4. [이미지 내 타겟(서술형)]: 특정 항목(예: 특징종목)에 대한 상세 기술 요청
    """
else:  # 3개일 때
    type_instruction = """
    다음 3가지 유형의 질의를 순서대로 생성하세요:
    1. [전체 설명]: 전체 맥락을 아우르는 포괄적 설명 요청
    2. [추론]: 텍스트 내 근거를 바탕으로 한 미래 전망이나 논리적 추론
    3. [이미지 내 타겟(서술형)]: 특정 항목에 대한 상세 기술 요청
    """


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """Gemini 3 Pro Preview로 고정된 LLM 호출."""
    try:
        response = client.chat.completions.create(
            model="gemini-flash-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )
        content = response.choices[0].message.content or ""
        return str(content)
    except Exception as e:  # noqa: BLE001
        logger.error("LLM 호출 오류: %s", e)
        return ""


logger.info("--- [Step 1] 질의 생성 시작 (%d개 모드) ---", QUERY_COUNT)

# 질의 생성 요청
query_user_message = f"""
<input_text>
{ocr_text}
</input_text>

<request>
{type_instruction}
</request>
"""

raw_questions = call_llm(SYSTEM_PROMPT_QUERY, query_user_message)

if not raw_questions:
    logger.error("질의 생성 실패")
    sys.exit(1)

# 결과 파싱 (1. 2. 같은 번호 제거하고 리스트로 변환)
questions = []
for line in raw_questions.strip().split("\n"):
    line = line.strip()
    if (
        line
        and not line.startswith("#")
        and not line.startswith("```")
        and not line.startswith("<")
    ):
        # "1. 질문내용" 형태에서 숫자 제거
        clean_line = re.sub(r"^\d+\.\s*", "", line)
        # 따옴표 제거
        clean_line = clean_line.replace('"', "").replace("'", "")
        if clean_line.strip():  # Ensure not empty after cleaning
            questions.append(clean_line)

logger.info("생성된 질의: %s", questions)


# ==========================================
# 2. 답변 생성 (Answer Generation)
# ==========================================
logger.info("--- [Step 2] 답변 생성 시작 ---")

qa_pairs = []

for idx, question in enumerate(questions):
    logger.info("처리 중... (%d/%d): %s", idx + 1, len(questions), question)

    answer_user_message = f"""
    <input_text>
    {ocr_text}
    </input_text>
    
    <instruction>
    {question}
    </instruction>
    """

    answer = call_llm(SYSTEM_PROMPT_ANSWER, answer_user_message)

    qa_pairs.append({"id": idx + 1, "question": question, "answer": answer})

# ==========================================
# 3. 결과 저장
# ==========================================
output_filename = f"qa_result_{QUERY_COUNT}pairs.json"
with open(output_filename, "w", encoding="utf-8") as f:
    json.dump(qa_pairs, f, ensure_ascii=False, indent=2)

logger.info("완료! '%s'에 저장되었습니다.", output_filename)

# Markdown 저장
output_md_filename = f"qa_result_{QUERY_COUNT}pairs.md"
with open(output_md_filename, "w", encoding="utf-8") as f:
    f.write(f"# QA Results ({QUERY_COUNT} pairs)\n\n")
    for item in qa_pairs:
        f.write(f"## Q{item['id']}. {item['question']}\n\n")
        f.write(f"{item['answer']}\n\n")
        f.write("---\n\n")

logger.info("완료! '%s'에 저장되었습니다.", output_md_filename)
