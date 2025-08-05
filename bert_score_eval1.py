import os
from openai import OpenAI
import anthropic
import pandas as pd
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer, util
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

# ===========================
# 0️⃣ .env 로드
# ===========================
load_dotenv()

# 🔑 API 키 불러오기
openai_api_key = os.getenv("OPENAI_API_KEY")
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

# OpenAI / Anthropic 클라이언트 초기화
client = OpenAI(api_key=openai_api_key)
anthropic_client = anthropic.Anthropic(api_key=anthropic_api_key)

# ===========================
# 1️⃣ 임베딩 및 BERT 모델 로드
# ===========================
embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
bert_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# ===========================
# 2️⃣ 과목명 & 질문 설정
# ===========================
subject = "PLC"
question = "melsec plc 디바이스 구성에 대해 알려줘"

# 모델 리스트
models = {
    "gpt-3.5-turbo": "openai",
    "gpt-4o": "openai",
    "claude-3-haiku-20240307": "anthropic",
    "claude-3-5-sonnet-20241022": "anthropic"
}

# ===========================
# 3️⃣ FAISS 로드 & 문서 검색
# ===========================
faiss_path = f"./faiss_subjects/{subject}"
vs = FAISS.load_local(faiss_path, embedding_model, allow_dangerous_deserialization=True)

docs = vs.similarity_search(question, k=3)
rag_context = "\n\n".join([doc.page_content for doc in docs])
print("\n[🔍 RAG 검색 문서 미리보기]\n", rag_context[:500], "...\n")

# ===========================
# 4️⃣ API 호출: Non-RAG & RAG
# ===========================
non_rag_responses = {}
rag_responses = {}

for model_name, provider in models.items():
    # ---- Non-RAG 응답 ----
    print(f"[요청 중] {model_name} ({provider}) - Non-RAG")
    if provider == "openai":
        completion = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": question}],
            timeout=60  # 타임아웃 설정
        )
        non_rag_responses[model_name] = completion.choices[0].message.content
    else:
        completion = anthropic_client.messages.create(
            model=model_name,
            max_tokens=500,
            messages=[{"role": "user", "content": question}],
            timeout=60
        )
        non_rag_responses[model_name] = completion.content[0].text
    print(f"[완료] {model_name} - Non-RAG")

    # ---- RAG 응답 ----
    rag_prompt = f"다음 문서를 참고하여 질문에 답변하세요.\n\n문서:\n{rag_context}\n\n질문: {question}"
    print(f"[요청 중] {model_name} ({provider}) - RAG")
    if provider == "openai":
        completion = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": rag_prompt}],
            timeout=60
        )
        rag_responses[model_name] = completion.choices[0].message.content
    else:
        completion = anthropic_client.messages.create(
            model=model_name,
            max_tokens=500,
            messages=[{"role": "user", "content": rag_prompt}],
            timeout=60
        )
        rag_responses[model_name] = completion.content[0].text
    print(f"[완료] {model_name} - RAG")

# ===========================
# 5️⃣ BERTScore 계산 및 저장
# ===========================
emb_q = bert_model.encode(question, convert_to_tensor=True)
results = []

for model_name in models.keys():
    score_non_rag = util.cos_sim(emb_q, bert_model.encode(non_rag_responses[model_name], convert_to_tensor=True)).item()
    score_rag = util.cos_sim(emb_q, bert_model.encode(rag_responses[model_name], convert_to_tensor=True)).item()

    results.append({
        "Model": model_name,
        "Type": "Non-RAG",
        "Score": score_non_rag,
        "Response": non_rag_responses[model_name]
    })
    results.append({
        "Model": model_name,
        "Type": "RAG",
        "Score": score_rag,
        "Response": rag_responses[model_name]
    })

    print(f"[{model_name}] Non-RAG: {score_non_rag:.4f} | RAG: {score_rag:.4f}")

# CSV 저장
df_scores = pd.DataFrame(results)
df_scores.to_csv(f"bert_scores_{subject}.csv", index=False, encoding="utf-8-sig")
print(f"\n✅ BERTScore 및 응답이 'bert_scores_{subject}.csv'로 저장되었습니다.")
