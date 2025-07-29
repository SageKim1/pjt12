import json
import random
import re
from typing import List, Optional, Union
import streamlit as st
from pydantic import BaseModel, Field
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
    options: Optional[List[str]] = Field(default_factory=list)  # ✅ 빈 리스트 기본값
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
        """안전하게 JSON 문자열을 파싱"""
        if not raw:
            st.error("빈 RAW 데이터가 입력되었습니다.")
            return None
        
        # 코드 블록 제거 (```json 또는 ```)
        raw = raw.strip()
        raw = re.sub(r'```(?:json)?\s*|\s*```', '', raw, flags=re.DOTALL | re.IGNORECASE)
        
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                st.error(f"파싱된 데이터가 리스트 형식이 아닙니다. 원본 데이터: {raw}")
                return None
            return parsed
        except json.JSONDecodeError as e:
            st.error(f"JSON 파싱 실패: {str(e)}")
            st.write("🔎 **원본 RAW 데이터 (디버그용)**:", raw)
            return None

    def _get_difficulty_guideline(self, difficulty: str) -> str:
        if difficulty == "쉬움":
            return "쉬운 난이도: 정답이 명확히 드러나고 헷갈리지 않게 출제."
        elif difficulty == "보통":
            return "보통 난이도: 개념 응용이 필요한 문제."
        elif difficulty == "어려움":
            return "어려운 난이도: 추론과 종합적 사고가 필요한 문제."
        return "일반 난이도: 균형 있게 출제."

    def _normalize_options(self, options):
        """옵션을 문자열 리스트로 강제 변환"""
        if isinstance(options, dict):
            st.write("🔎 **options가 딕셔너리 형태로 입력됨**: ", options)
            return [str(options.get(str(i), options.get(i, ""))) for i in range(len(options))]
        elif isinstance(options, list):
            return [str(v) for v in options]
        else:
            st.write("⚠️ **options가 예상치 못한 형태**: ", options)
            return []

    def generate(self, subject_name: str, n=5, difficulty="보통", topic="", quiz_type="혼합"):
        ctx = self._get_context(subject_name, topic)
        if not ctx:
            st.error(f"{subject_name} 과목의 자료가 없습니다. PDF를 업로드한 후 다시 시도하세요.")
            return []

        guideline = self._get_difficulty_guideline(difficulty)

        prompt = f"""
너는 '{subject_name}' 과목의 강의자료 기반 퀴즈 생성기야.
아래 context 내용을 참고하여 {n}개의 {difficulty} 난이도 퀴즈를 생성해.
- 객관식은 보기(options)를 반드시 4개 포함하고 correct_answer는 보기의 인덱스(0~3)로 지정.
- OX는 options ["O","X"], correct_answer는 0(O) 또는 1(X)만 가능.
- 주관식은 correct_answer를 문자열로.
- options는 반드시 리스트 형태로 출력 (딕셔너리 불가).
- 반드시 JSON 배열 형식만 출력. 추가 설명 문장은 출력하지 마세요.

예시:
[
{{"type": "multiple", "question": "문제", "options": ["A", "B", "C", "D"], "correct_answer": 0, "explanation": "해설", "subject": "{subject_name}"}},
{{"type": "short", "question": "문제", "correct_answer": "정답단어", "explanation": "해설", "subject": "{subject_name}"}},
{{"type": "ox", "question": "문제", "options": ["O", "X"], "correct_answer": 0, "explanation": "해설", "subject": "{subject_name}"}}
]

context:
{ctx}
"""

        with st.spinner(f"{subject_name} {difficulty} 퀴즈 생성 중..."):
            try:
                raw = self.llm.invoke(prompt).content.strip()
            except Exception as e:
                st.error(f"LLM 호출 실패: {str(e)}. API 키나 네트워크를 확인하세요.")
                return []

            data = self._safe_parse_json(raw)
            if not data or not isinstance(data, list):
                st.error(f"퀴즈 파싱 실패.")
                st.write("🔎 **LLM RAW 응답 (디버그용)**:")
                st.code(raw)
                return []

            valid_quizzes = []
            for q in data:
                try:
                    if not isinstance(q, dict):
                        st.write(f"⚠️ 문제 형식이 딕셔너리가 아님: {q}")
                        continue
                    q_type = q.get("type", "").lower()
                    question = str(q.get("question", "")).strip()
                    explanation = q.get("explanation") or "해설이 제공되지 않았습니다."
                    options = self._normalize_options(q.get("options", []))
                    correct_answer = q.get("correct_answer")

                    # 객관식
                    if q_type == "multiple" and len(options) >= 2:
                        if isinstance(correct_answer, str) and correct_answer in options:
                            correct_answer = options.index(correct_answer)
                        if isinstance(correct_answer, (int, float)) and 0 <= int(correct_answer) < len(options):
                            valid_quizzes.append(
                                Quiz(type=q_type, question=question, options=options,
                                     correct_answer=correct_answer, explanation=explanation, subject=subject_name)
                            )
                    # 주관식
                    elif q_type == "short" and isinstance(correct_answer, str):
                        valid_quizzes.append(
                            Quiz(type=q_type, question=question, options=[],
                                 correct_answer=correct_answer, explanation=explanation, subject=subject_name)
                        )
                    # OX
                    elif q_type == "ox" and [opt.upper() for opt in options] == ["O", "X"] and correct_answer in [0, 1]:
                        valid_quizzes.append(
                            Quiz(type=q_type, question=question, options=options,
                                 correct_answer=correct_answer, explanation=explanation, subject=subject_name)
                        )
                except Exception as e:
                    st.write(f"⚠️ 문제 검증 중 오류: {e}, 문제={q}")

            return valid_quizzes

# ===== 링크 기반 퀴즈 생성 =====
def generate_quiz_from_link(url: str, n: int = 3):
    content = fetch_link_content(url)
    if content.startswith("오류 발생"):
        st.error("링크 크롤링 실패.")
        return []

    prompt = f"""
다음 링크 내용을 기반으로 총 {n}개의 혼합형 퀴즈(객관식, 주관식, OX)를 생성해.
- 객관식은 보기(options)를 반드시 4개 포함하고 correct_answer는 보기의 인덱스(0~3)로 지정.
- OX는 options를 정확히 ["O", "X"]로 설정하고, correct_answer는 0(O) 또는 1(X)만 가능.
- 주관식은 correct_answer를 문자열로.
- options는 반드시 리스트 형태로 출력 (딕셔너리 불가).
- 반드시 JSON 배열 형식만 출력. 추가 설명 문장은 출력하지 마.

예시:
[
{{"type": "multiple", "question": "문제", "options": ["A", "B", "C", "D"], "correct_answer": 0, "explanation": "해설", "subject": "링크퀴즈"}},
{{"type": "short", "question": "문제", "correct_answer": "정답단어", "explanation": "해설", "subject": "링크퀴즈"}},
{{"type": "ox", "question": "문제", "options": ["O", "X"], "correct_answer": 0, "explanation": "해설", "subject": "링크퀴즈"}}
]

내용:
{content}
"""
    try:
        raw = llm.invoke(prompt).content.strip()
    except Exception as e:
        st.error(f"LLM 호출 실패: {str(e)}. API 키나 네트워크를 확인하세요.")
        return []

    generator = MultiSubjectQuizGen(vs_manager=None)
    data = generator._safe_parse_json(raw)
    if not data or not isinstance(data, list):
        st.error(f"퀴즈 파싱 실패.")
        st.write("🔎 **LLM RAW 응답 (디버그용)**:")
        st.code(raw)
        return []

    valid_quizzes = []
    for q in data:
        try:
            if not isinstance(q, dict):
                st.write(f"⚠️ 문제 형식이 딕셔너리가 아님: {q}")
                continue
            q_type = q.get("type", "").lower()
            question = str(q.get("question", "")).strip()
            explanation = q.get("explanation") or "해설이 제공되지 않았습니다."
            options = generator._normalize_options(q.get("options", []))
            correct_answer = q.get("correct_answer")

            # 객관식
            if q_type == "multiple" and len(options) >= 2:
                if isinstance(correct_answer, str) and correct_answer in options:
                    correct_answer = options.index(correct_answer)
                if isinstance(correct_answer, (int, float)) and 0 <= int(correct_answer) < len(options):
                    valid_quizzes.append(
                        Quiz(type=q_type, question=question, options=options,
                             correct_answer=correct_answer, explanation=explanation, subject="링크퀴즈")
                    )
            # 주관식
            elif q_type == "short" and isinstance(correct_answer, str):
                valid_quizzes.append(
                    Quiz(type=q_type, question=question, options=[],
                         correct_answer=correct_answer, explanation=explanation, subject="링크퀴즈")
                )
            # OX
            elif q_type == "ox" and [opt.upper() for opt in options] == ["O", "X"] and correct_answer in [0, 1]:
                valid_quizzes.append(
                    Quiz(type=q_type, question=question, options=options,
                         correct_answer=correct_answer, explanation=explanation, subject="링크퀴즈")
                )
        except Exception as e:
            st.write(f"⚠️ 문제 검증 중 오류: {e}, 문제={q}")

    return valid_quizzes
