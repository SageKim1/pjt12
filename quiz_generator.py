import json
import random
from typing import List
import streamlit as st
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from config import Config
from vector_store import MultiSubjectVectorStoreManager

class Quiz(BaseModel):
    question: str
    options: List[str] = Field(min_items=4, max_items=4)
    correct_answer: int
    explanation: str
    subject: str

class MultiSubjectQuizGen:
    def __init__(self, vs_manager: MultiSubjectVectorStoreManager):
        self.vs_manager = vs_manager
        self.llm = ChatOpenAI(
            openai_api_key=Config.OPENAI_API_KEY,
            model_name=Config.LLM_MODEL,
            temperature=0.3,
        )

    def _get_context(self, subject_name: str, topic="", k=8):
        store = self.vs_manager.get_store(subject_name)
        if not store:
            return ""
        if topic:
            docs = self.vs_manager.search(subject_name, topic, k)
        else:
            all_docs = list(store.docstore._dict.values())
            docs = random.sample(all_docs, min(k, len(all_docs)))
        return "\n".join(d.page_content for d in docs)

    def generate(self, subject_name: str, n=5, difficulty="보통", topic=""):
        ctx = self._get_context(subject_name, topic)
        if not ctx:
            st.error(f"{subject_name} 과목의 자료가 없습니다.")
            return []
        prompt = f"""
너는 {subject_name} 과목의 강의자료 기반 객관식 퀴즈 생성기야.
주어진 context(강의자료)로 아래 예시와 정확히 같은 JSON 구조로
{n}문제, 난이도:{difficulty}의 객관식(4지선다) 퀴즈를 생성해줘.

**예시**
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

꼭 위 예시처럼 "quizzes" 키 ONLY, 설명·텍스트 없이 JSON만 순수하게 출력!
context:
{ctx}
"""
        raw = self.llm.invoke(prompt).content
        try:
            data = json.loads(raw)
            if "quizzes" not in data:
                st.error(f'"quizzes" 키가 존재하지 않음.\n--- LLM 응답 ---\n{raw}')
                return []
            quizzes = []
            for q_data in data["quizzes"]:
                q_data["subject"] = subject_name
                quizzes.append(Quiz(**q_data))
            return quizzes
        except Exception as e:
            st.error(f'퀴즈 파싱 실패: {type(e).__name__}: {e}\n--- LLM 응답 ---\n{raw}')
            return []
