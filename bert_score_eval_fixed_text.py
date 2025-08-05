import pandas as pd
from sentence_transformers import SentenceTransformer, util

# ===========================
# 1️⃣ 임베딩 모델 로드
# ===========================
bert_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# ===========================
# 2️⃣ 기준 텍스트 설정 (reference_text)
# ===========================
reference_text = """
{
  "공통": "파라미터 설정 범위 합계 28.8K 워드 이내에서 변경 가능",
  "워드 디바이스": [
    {"디바이스명": "타이머", "디폴트값": "2048점", "사용범위": "T0~T2047"},
    {"디바이스명": "적산 타이머", "디폴트값": "0점", "사용범위": "ST0~ST2047"},
    {"디바이스명": "카운터", "디폴트값": "1024점", "사용범위": "C0~C1023"},
    {"디바이스명": "데이터 레지스터", "디폴트값": "12288점", "사용범위": "D0~D12287"},
    {"디바이스명": "링크 레지스터", "디폴트값": "8192점", "사용범위": "W0~W8191"},
    {"디바이스명": "특수 링크 레지스터", "디폴트값": "2048점", "사용범위": "SW0~SW2147"}
  ]
}
"""

# ===========================
# 3️⃣ CSV 로드
# ===========================
df = pd.read_csv("total_responses.csv")

# ===========================
# 4️⃣ reference_text 임베딩
# ===========================
emb_ref = bert_model.encode(reference_text, convert_to_tensor=True)

# ===========================
# 5️⃣ 각 모델 응답과 BERTScore 계산
# ===========================
results = []
for idx, row in df.iterrows():
    model_name = row["Model"]
    response = row["Response"]

    emb_res = bert_model.encode(response, convert_to_tensor=True)
    score = util.cos_sim(emb_ref, emb_res).item()

    results.append({
        "Model": model_name,
        "BERTScore (cosine similarity)": round(score, 4),
        "Response": response
    })

# ===========================
# 6️⃣ 결과 저장
# ===========================
df_scores = pd.DataFrame(results)
df_scores.to_csv("bert_scores_vs_reference.csv", index=False, encoding="utf-8-sig")

print("\n✅ BERTScore 계산 완료: 'bert_scores_vs_reference.csv'로 저장됨")
print(df_scores[["Model", "BERTScore (cosine similarity)"]])
