import json
import random
import re
import ast
from typing import List, Optional, Union
import streamlit as st
from pydantic import BaseModel
from config import Config
from vector_store import MultiSubjectVectorStoreManager
from utils.web_tools import fetch_link_content

# ✅ LLM 모델 자동 선택
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
        model=Config.LLM_MODEL(),
        temperature=0.3,
        max_tokens=1500
    )
else:
    raise ValueError("지원하지 않는 MODEL_TYPE입니다. (openai 또는 claude)")

# ----- Quiz 데이터 모델 -----
class Quiz(BaseModel):
    type: str  # "multiple", "short", "ox"
    question: str
    options: Optional[List[str]] = None
    correct_answer: Union[str, int]
    explanation: str
    subject: str

# ----- MultiSubjectQuizGen -----
class MultiSubjectQuizGen:
    def __init__(self, vs_manager: Optional[MultiSubjectVectorStoreManager]):
        self.vs_manager = vs_manager
        self.llm = llm

    def _get_context(self, subject_name: str, topic: str = "", k: int = 8):
        store = self.vs_manager.get_store(subject_name) if self.vs_manager else None
        if not store:
            st.warning(f"{subject_name} 과목의 벡터 스토어가 없습니다. PDF 자료를 업로드하세요.")
            return ""
        if topic:
            docs = self.vs_manager.search(subject_name, topic, k)
        else:
            all_docs = list(store.docstore._dict.values())
            if not all_docs:
                st.warning(f"{subject_name} 과목에 자료가 없습니다. PDF를 업로드하세요.")
                return ""
            docs = random.sample(all_docs, min(k, len(all_docs)))
        return "\n".join(d.page_content for d in docs)

    def _safe_parse_json(self, raw: str):
        raw = raw.strip()
        raw = re.sub(r'``````', '', raw, flags=re.DOTALL | re.IGNORECASE)
        match = re.search(r'(\[[\s\S]*?\]|\{[\s\S]*?\})', raw)
        if match:
            raw = match.group(0)
        open_count, close_count = raw.count("{"), raw.count("}")
        if close_count < open_count:
            raw += "}" * (open_count - close_count)
        open_arr, close_arr = raw.count("["), raw.count("]")
        if close_arr < open_arr:
            raw += "]" * (open_arr - close_arr)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            try:
                return ast.literal_eval(raw)
            except Exception:
                return None

    def _get_difficulty_guideline(self, difficulty: str) -> str:
        if difficulty == "쉬움":
            return "쉬운 난이도: 정답이 명확히 드러나고 헷갈리지 않게 출제."
        elif difficulty == "보통":
            return "보통 난이도: 개념 응용이 필요한 문제."
        elif difficulty == "어려움":
            return "어려운 난이도: 추론과 종합적 사고가 필요한 문제."
        return "일반 난이도: 균형 있게 출제."

    def generate(self, subject_name: str, n=5, difficulty="보통", topic="", quiz_type="객관식"):
        ctx = self._get_context(subject_name, topic)
        if not ctx:
            st.error(f"{subject_name} 과목의 자료가 없습니다. PDF를 업로드하세요.")
            return [Quiz(type="ox", question="테스트 OX 문제", options=["O", "X"], correct_answer=0, explanation="테스트 해설", subject=subject_name)]

        guideline = self._get_difficulty_guideline(difficulty)
        type_desc = {
            "혼합": "객관식, 주관식, OX를 섞어서 생성.",
            "주관식": "모두 주관식 (short answer).",
            "OX": "모두 OX 퀴즈 (options: ['O', 'X'], correct_answer: 0 또는 1).",
            "객관식": "모두 객관식 (multiple choice)."
        }.get(quiz_type, "모두 객관식 (multiple choice).")

        prompt = f"""
너는 '{subject_name}' 과목의 강의자료 기반 퀴즈 생성기야.
아래 context 내용으로 {n}개의 {difficulty} 난이도 퀴즈를 생성해. 유형: {type_desc}
출제 규칙: {guideline}
반드시 JSON 배열 형식으로만 출력해.

각 퀴즈의 type: "multiple", "short", "ox"
예시 출력:
[
  {{"type": "multiple", "question": "문제", "options": ["A","B","C","D"], "correct_answer": 0, "explanation": "해설", "subject": "{subject_name}"}},
  {{"type": "short", "question": "문제", "correct_answer": "정답단어", "explanation": "해설", "subject": "{subject_name}"}},
  {{"type": "ox", "question": "문제", "options": ["O","X"], "correct_answer": 0, "explanation": "해설", "subject": "{subject_name}"}}
]

context:
{ctx}
"""
        with st.spinner(f"{subject_name} {difficulty} 퀴즈 생성 중..."):
            try:
                raw = self.llm.invoke(prompt).content.strip()
            except Exception as e:
                st.error(f"LLM 호출 실패: {str(e)}")
                return []
            data = self._safe_parse_json(raw)
            if not data or not isinstance(data, list):
                st.error(f'퀴즈 파싱 실패.\n--- LLM 응답 ---\n{raw}')
                return []

            valid_quizzes = []
            for q in data:
                try:
                    if q["type"] == "multiple" and len(q.get("options", [])) == 4:
                        valid_quizzes.append(Quiz(**q))
                    elif q["type"] == "short" and isinstance(q["correct_answer"], str):
                        valid_quizzes.append(Quiz(**q))
                    elif q["type"] == "ox" and q.get("options") == ["O", "X"]:
                        valid_quizzes.append(Quiz(**q))
                except Exception:
                    continue

            if not valid_quizzes:
                st.warning("생성된 유효 퀴즈가 없습니다.")
            return valid_quizzes

# ===== 링크 기반 퀴즈 생성 =====
def generate_quiz_from_link(url: str, n: int = 3):
    content = fetch_link_content(url)
    if content.startswith("오류 발생"):
        st.error("링크 크롤링 실패.")
        return []

    prompt = f"""
다음 링크 내용을 기반으로 총 {n}개의 혼합형 퀴즈를 생성해.
객관식, 주관식, OX를 섞어 JSON 배열로만 출력.

내용:
{content}
"""
    raw = llm.invoke(prompt).content.strip()
    generator = MultiSubjectQuizGen(vs_manager=None)
    data = generator._safe_parse_json(raw)
    if not data or not isinstance(data, list):
        st.error(f'퀴즈 파싱 실패.\n--- LLM 응답 ---\n{raw}')
        return []

    valid_quizzes = []
    for q in data:
        try:
            if q["type"] == "multiple" and len(q.get("options", [])) == 4:
                valid_quizzes.append(Quiz(**q))
            elif q["type"] == "short":
                valid_quizzes.append(Quiz(**q))
            elif q["type"] == "ox" and q.get("options") == ["O", "X"]:
                valid_quizzes.append(Quiz(**q))
        except Exception:
            continue
    return valid_quizzes
