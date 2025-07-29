import os
from openai import OpenAI
import anthropic
import pandas as pd
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer, util
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
import itertools

# ===========================
# 0️⃣ .env 로드
# ===========================
load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

client = OpenAI(api_key=openai_api_key)
anthropic_client = anthropic.Anthropic(api_key=anthropic_api_key)

# ===========================
# 1️⃣ 임베딩 모델 로드
# ===========================
embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
bert_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# ===========================
# 2️⃣ 과목명 & 질문 설정
# ===========================
subject = "PLC"
question = "타이머 T와 카운터 C의 디폴트값과 사용 범위는?"

models = {
    "gpt-3.5-turbo": "openai",
    "gpt-4o": "openai",
    "claude-3-haiku-20240307": "anthropic",  # Claude 3.0
    "claude-3-5-sonnet-20241022": "anthropic"  # Claude 3.5
}

# ===========================
# 3️⃣ FAISS 문서 검색 (RAG 컨텍스트 생성)
# ===========================
faiss_path = f"./faiss_subjects/{subject}"
vs = FAISS.load_local(faiss_path, embedding_model, allow_dangerous_deserialization=True)
docs = vs.similarity_search(question, k=3)
rag_context = "\n\n".join([doc.page_content for doc in docs])
print("\n[🔍 RAG 검색 문서 미리보기]\n", rag_context[:500], "...\n")

# ===========================
# 4️⃣ API 호출 (RAG & Non-RAG)
# ===========================
rag_responses = {}
non_rag_responses = {}

for model_name, provider in models.items():
    # ---- Non-RAG ----
    print(f"[요청 중] {model_name} ({provider}) - Non-RAG")
    if provider == "openai":
        completion = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": question}],
            timeout=60
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

    # ---- RAG ----
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
# 5️⃣ BERTScore 계산
# ===========================
results = []

# ---- (A) RAG vs Non-RAG ----
for model_name in models.keys():
    emb_rag = bert_model.encode(rag_responses[model_name], convert_to_tensor=True)
    emb_non = bert_model.encode(non_rag_responses[model_name], convert_to_tensor=True)
    score = util.cos_sim(emb_rag, emb_non).item()
    results.append({
        "Comparison": "RAG vs Non-RAG (Same Model)",
        "Model": model_name,
        "Score": score,
        "RAG Response": rag_responses[model_name],
        "Non-RAG Response": non_rag_responses[model_name]
    })

# ---- (B) RAG끼리 유사도 ----
for m1, m2 in itertools.combinations(models.keys(), 2):
    emb1 = bert_model.encode(rag_responses[m1], convert_to_tensor=True)
    emb2 = bert_model.encode(rag_responses[m2], convert_to_tensor=True)
    score = util.cos_sim(emb1, emb2).item()
    results.append({
        "Comparison": "RAG vs RAG",
        "Model Pair": f"{m1} vs {m2}",
        "Score": score
    })

# ---- (C) Non-RAG끼리 유사도 ----
for m1, m2 in itertools.combinations(models.keys(), 2):
    emb1 = bert_model.encode(non_rag_responses[m1], convert_to_tensor=True)
    emb2 = bert_model.encode(non_rag_responses[m2], convert_to_tensor=True)
    score = util.cos_sim(emb1, emb2).item()
    results.append({
        "Comparison": "Non-RAG vs Non-RAG",
        "Model Pair": f"{m1} vs {m2}",
        "Score": score
    })

# ===========================
# 6️⃣ CSV 저장
# ===========================
df_scores = pd.DataFrame(results)
df_scores.to_csv(f"bert_scores_comparison_{subject}.csv", index=False, encoding="utf-8-sig")
print(f"\n✅ RAG/Non-RAG, RAG끼리, Non-RAG끼리 유사도 결과가 'bert_scores_comparison_{subject}.csv'로 저장되었습니다.")
