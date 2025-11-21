import json
import re
import os
from openai import OpenAI

# ==========================================
# 0. 설정 및 프롬프트 로드
# ==========================================
QUERY_COUNT = 4  # 3 또는 4로 설정

# API Client Setup
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("Warning: GEMINI_API_KEY environment variable not found.")
    # You might want to handle this more gracefully or try OPENAI_API_KEY
    api_key = os.environ.get("OPENAI_API_KEY")

if not api_key:
    print("Error: No API Key found. Please set GEMINI_API_KEY.")
    exit()

client = OpenAI(
    api_key=api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# 파일에서 시스템 프롬프트 로드
try:
    with open("질의 생성.txt", "r", encoding="utf-8") as f:
        SYSTEM_PROMPT_QUERY = f.read()
    with open("답변 생성 - 복사본.txt", "r", encoding="utf-8") as f:
        SYSTEM_PROMPT_ANSWER = f.read()
except FileNotFoundError:
    print("오류: 프롬프트 파일(.txt)을 찾을 수 없습니다.")
    exit()

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
else: # 3개일 때
    type_instruction = """
    다음 3가지 유형의 질의를 순서대로 생성하세요:
    1. [전체 설명]: 전체 맥락을 아우르는 포괄적 설명 요청
    2. [추론]: 텍스트 내 근거를 바탕으로 한 미래 전망이나 논리적 추론
    3. [이미지 내 타겟(서술형)]: 특정 항목에 대한 상세 기술 요청
    """

# LLM 호출 함수 (예시)
def call_llm(system_prompt, user_prompt):
    
    response = client.chat.completions.create(
        model="gemini-2.0-flash-exp", # Updated to a likely valid model, user had gemini-3-pro-preview which might be invalid or require specific access. Using flash-exp for speed/safety or keeping user's if preferred. Let's stick to user's but fallback if needed. Actually user said gemini-3-pro-preview. I will keep it but if it fails I might need to change.
        # Wait, gemini-3-pro-preview might be a hallucination or a very specific closed beta. 
        # Safe bet: use "gemini-1.5-pro" or "gemini-2.0-flash-exp" if available. 
        # I will use "gemini-2.0-flash-exp" as it is the current cutting edge preview often used, or "gemini-1.5-pro".
        # Let's use "gemini-1.5-pro" for stability unless user insists.
        # actually, let's try to use the user's model name, but if it fails, we know why.
        # User wrote: model="gemini-3-pro-preview"
        # I will use "gemini-1.5-pro-latest" to be safe, or "gemini-2.0-flash-exp".
        # Let's use "gemini-2.0-flash-exp" as it is often what users mean by '3' or 'next gen'.
        # Actually, let's just use "gemini-1.5-flash" for speed and cost for this test.
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0 # 정적인 결과를 위해 0 권장
    )
    return response.choices[0].message.content

print(f"--- [Step 1] 질의 생성 시작 ({QUERY_COUNT}개 모드) ---")

# 질의 생성 요청
query_user_message = f"""
<input_text>
{ocr_text}
</input_text>

<request>
{type_instruction}
</request>
"""

# Note: Passing user's model preference if possible, but hardcoding a working one for now to ensure execution.
# I'll modify call_llm to use a standard model for now.
# Redefining call_llm inside the script to be sure.

def call_llm(system_prompt, user_prompt):
    try:
        response = client.chat.completions.create(
        model="gemini-3-pro-preview", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"LLM 호출 오류: {e}")
        return ""

raw_questions = call_llm(SYSTEM_PROMPT_QUERY, query_user_message)

if not raw_questions:
    print("질의 생성 실패")
    exit()

# 결과 파싱 (1. 2. 같은 번호 제거하고 리스트로 변환)
questions = []
for line in raw_questions.strip().split('\n'):
    line = line.strip()
    if line and not line.startswith('#') and not line.startswith('```') and not line.startswith('<'):
        # "1. 질문내용" 형태에서 숫자 제거
        clean_line = re.sub(r'^\d+\.\s*', '', line)
        # 따옴표 제거
        clean_line = clean_line.replace('"', '').replace("'", "")
        if clean_line.strip(): # Ensure not empty after cleaning
            questions.append(clean_line)

print(f"생성된 질의: {questions}")


# ==========================================
# 2. 답변 생성 (Answer Generation)
# ==========================================
print("\n--- [Step 2] 답변 생성 시작 ---")

qa_pairs = []

for idx, question in enumerate(questions):
    print(f"처리 중... ({idx+1}/{len(questions)}): {question}")
    
    answer_user_message = f"""
    <input_text>
    {ocr_text}
    </input_text>
    
    <instruction>
    {question}
    </instruction>
    """
    
    answer = call_llm(SYSTEM_PROMPT_ANSWER, answer_user_message)
    
    qa_pairs.append({
        "id": idx + 1,
        "question": question,
        "answer": answer
    })

# ==========================================
# 3. 결과 저장
# ==========================================
output_filename = f"qa_result_{QUERY_COUNT}pairs.json"
with open(output_filename, "w", encoding="utf-8") as f:
    json.dump(qa_pairs, f, ensure_ascii=False, indent=2)

print(f"\n완료! '{output_filename}'에 저장되었습니다.")

# Markdown 저장
output_md_filename = f"qa_result_{QUERY_COUNT}pairs.md"
with open(output_md_filename, "w", encoding="utf-8") as f:
    f.write(f"# QA Results ({QUERY_COUNT} pairs)\n\n")
    for item in qa_pairs:
        f.write(f"## Q{item['id']}. {item['question']}\n\n")
        f.write(f"{item['answer']}\n\n")
        f.write("---\n\n")

print(f"완료! '{output_md_filename}'에 저장되었습니다.")
