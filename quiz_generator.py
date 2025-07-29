import json
import random
import re
import ast
from typing import List
import streamlit as st
from pydantic import BaseModel, Field
from langchain_anthropic import ChatAnthropic
from config import Config
from vector_store import MultiSubjectVectorStoreManager
from utils.web_tools import fetch_link_content


if Config.MODEL_TYPE == "openai":
    from langchain.chat_models import ChatOpenAI
    llm = ChatOpenAI(
        openai_api_key=Config.OPENAI_API_KEY,
        model_name=Config.LLM_MODEL(),
        temperature=Config.TEMPERATURE
    )
elif Config.MODEL_TYPE == "claude":
    from langchain_anthropic import ChatAnthropic
    llm = ChatAnthropic(
        anthropic_api_key=Config.ANTHROPIC_API_KEY,
        model=Config.LLM_MODEL(),  # ✅ () 붙이기
        temperature=0.3,
        max_tokens=1500
    )
else:
    raise ValueError("지원하지 않는 MODEL_TYPE입니다. (openai 또는 claude)")


class Quiz(BaseModel):
    question: str
    options: List[str] = Field(min_items=4, max_items=4)
    correct_answer: int
    explanation: str
    subject: str


class MultiSubjectQuizGen:
    def __init__(self, vs_manager: MultiSubjectVectorStoreManager):
        self.vs_manager = vs_manager
        self.llm = llm

    def _get_context(self, subject_name: str, topic: str = "", k: int = 8):
        store = self.vs_manager.get_store(subject_name)
        if not store:
            return ""
        if topic:
            docs = self.vs_manager.search(subject_name, topic, k)
        else:
            all_docs = list(store.docstore._dict.values())
            docs = random.sample(all_docs, min(k, len(all_docs)))
        return "\n".join(d.page_content for d in docs)

    def _safe_parse_json(self, raw: str):
        raw = raw.strip()
        import re, json, ast

        # JSON 객체만 추출
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            json_str = match.group(0)  # 첫 번째 { ... } 블록만 추출
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        # 리스트 형태 추출 (예: [ {...}, {...} ])
        quizzes_match = re.search(r'\[\s*\{.*\}\s*\]', raw, re.DOTALL)
        if quizzes_match:
            try:
                quizzes_raw = quizzes_match.group(0)
                return {"quizzes": json.loads(quizzes_raw)}
            except Exception:
                pass

        # 마지막 fallback
        try:
            return ast.literal_eval(raw)
        except Exception:
            return None


    def generate(self, subject_name: str, n=5, difficulty="보통", topic=""):
        ctx = self._get_context(subject_name, topic)
        if not ctx:
            st.error(f"{subject_name} 과목의 자료가 없습니다.")
            return []

        prompt = f"""
너는 {subject_name} 과목의 강의자료 기반 객관식 퀴즈 생성기야.
주어진 context로 JSON 구조의 퀴즈 {n}문제를 생성해줘.

예시:
{{
  "quizzes": [
    {{
      "question": "문제문장",
      "options": ["보기1", "보기2", "보기3", "보기4"],
      "correct_answer": 0,
      "explanation": "간단한 해설",
      "subject": "{subject_name}"
    }}
  ]
}}
context:
{ctx}
"""
        raw = self.llm.invoke(prompt).content.strip()
        data = self._safe_parse_json(raw)

        if not data or "quizzes" not in data:
            try:
                data = json.loads(re.search(r"\{[\s\S]*\}", raw).group(0))  # 재시도
            except:
                st.error(f'퀴즈 파싱 실패.\n--- LLM 응답 ---\n{raw}')
                return []

        valid_quizzes = []
        for q in data["quizzes"]:
            if "answer" in q and "correct_answer" not in q:
                q["correct_answer"] = q.pop("answer")
            if all(k in q for k in ["question", "options", "correct_answer", "explanation", "subject"]):
                valid_quizzes.append(Quiz(**q))

        return valid_quizzes


# ✅ 링크 기반 퀴즈 생성 함수 추가
def generate_quiz_from_link(url: str, n: int = 3):
    """외부 링크 내용을 기반으로 퀴즈 생성"""
    content = fetch_link_content(url)
    if content.startswith("오류 발생"):
        st.error("링크 크롤링 실패.")
        return []

    llm = ChatAnthropic(
        anthropic_api_key=Config.ANTHROPIC_API_KEY,
        model=Config.LLM_MODEL(),  # ✅ () 붙이기
        temperature=0.3,
        max_tokens=1500
    )

    prompt = f"""
다음 링크 내용을 기반으로 객관식 퀴즈 {n}개를 JSON 형태로 생성해줘.
형식은 아래 예시와 동일하게 "quizzes" 키만 포함된 JSON으로 출력.

예시:
{{
  "quizzes": [
    {{
      "question": "문제문장",
      "options": ["보기1", "보기2", "보기3", "보기4"],
      "correct_answer": 0,
      "explanation": "간단한 해설",
      "subject": "링크퀴즈"
    }}
  ]
}}

내용:
{content}
"""
    raw = llm.invoke(prompt).content.strip()

    # 동일한 파서 재사용
    generator = MultiSubjectQuizGen(vs_manager=None)  # vs_manager 필요 없음
    data = generator._safe_parse_json(raw)

    if not data or "quizzes" not in data:
        try:
            data = json.loads(re.search(r"\{[\s\S]*\}", raw).group(0))  # 재시도
        except:
            st.error(f'퀴즈 파싱 실패.\n--- LLM 응답 ---\n{raw}')
            return []

    valid_quizzes = []
    for q in data["quizzes"]:
        if "answer" in q and "correct_answer" not in q:
            q["correct_answer"] = q.pop("answer")
        if all(k in q for k in ["question", "options", "correct_answer", "explanation", "subject"]):
            valid_quizzes.append(Quiz(**q))

    return valid_quizzes
