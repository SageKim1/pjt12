from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from config import Config
from vector_store import MultiSubjectVectorStoreManager

PROMPT_TEMPLATE = """당신은 대학 강의자료 기반 AI 튜터입니다.

{context}

학생 질문: {question}

- 강의자료에 없는 내용은 "자료에 없습니다"라고 답변
- 한국어, 친절, 예시 포함

답변:"""

class MultiSubjectChatbot:
    def __init__(self, vs_manager: MultiSubjectVectorStoreManager):
        self.vs_manager = vs_manager
        self.llm = ChatOpenAI(
            openai_api_key=Config.OPENAI_API_KEY,
            model_name=Config.LLM_MODEL,
            temperature=Config.TEMPERATURE,
        )
        self.qa_chains = {}

    def create_qa_chain(self, subject_name: str):
        retriever = self.vs_manager.get_retriever(subject_name)
        if not retriever:
            return None
        prompt = PromptTemplate(
            template=PROMPT_TEMPLATE,
            input_variables=["context", "question"]
        )
        qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=retriever,
            chain_type_kwargs={"prompt": prompt},
            return_source_documents=True,
        )
        self.qa_chains[subject_name] = qa_chain
        return qa_chain

    def ask(self, subject_name: str, question: str):
        if subject_name not in self.qa_chains:
            qa_chain = self.create_qa_chain(subject_name)
            if not qa_chain:
                return f"{subject_name} 과목의 자료가 없습니다. PDF를 먼저 업로드해주세요.", []
        qa_chain = self.qa_chains[subject_name]
        try:
            # 핵심: .invoke, 변수는 {"query": question}만 넘김
            result = qa_chain.invoke({"query": question})
            return result["result"], result["source_documents"]
        except Exception as e:
            return f"오류가 발생했습니다: {str(e)}", []
