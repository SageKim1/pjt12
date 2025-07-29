import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from langchain.schema import Document
from vector_store import MultiSubjectVectorStoreManager

# 🔍 DuckDuckGo 검색
def web_search(query: str, max_results=3):
    """DuckDuckGo 검색"""
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=max_results)]
        return [
            {
                "title": r.get("title", ""),
                "link": r.get("href", ""),
                "snippet": r.get("body", "")
            } for r in results
        ]
    except Exception as e:
        return [{"title": "검색 오류", "link": "", "snippet": f"검색 중 오류 발생: {e}"}]

# 🔗 검색 결과를 벡터스토어에 저장
def save_web_results_to_vectorstore(vs_manager: MultiSubjectVectorStoreManager, subject_name: str, query: str):
    results = web_search(query)
    docs = [Document(page_content=r["snippet"], metadata={"source": r["link"]}) for r in results]
    vs_manager.create_or_update_subject(subject_name, docs)
    return docs

# 🌐 링크 본문 추출
def fetch_link_content(url: str) -> str:
    """
    주어진 URL에서 본문 텍스트 일부를 추출 (최대 10개 단락)
    """
    try:
        response = requests.get(url, timeout=7)  # ✅ 타임아웃 추가
        response.encoding = response.apparent_encoding  # ✅ 한글 깨짐 방지
        soup = BeautifulSoup(response.text, "html.parser")
        paragraphs = [p.get_text().strip() for p in soup.find_all("p")]
        main_text = "\n".join(filter(None, paragraphs[:10]))
        if not main_text:
            return "본문에서 추출 가능한 텍스트가 없습니다."
        return main_text
    except Exception as e:
        return f"오류 발생: {e}"

# 📝 링크 기반 더미 퀴즈 생성 (AI 연동 없이 예시)
def generate_quiz_from_link(url: str, n=3):
    """
    링크 본문에서 임시 객관식 퀴즈 리스트를 생성 (실제 AI 연동 시 대체 가능)
    """
    content_preview = fetch_link_content(url)
    if content_preview.startswith("오류 발생"):
        return [{
            "type": "multi",
            "question": "링크에서 본문을 불러올 수 없습니다.",
            "options": ["오류", "없음", "지원안함"],
            "correct_answer": 0,
            "explanation": content_preview,
            "subject": "웹 링크"
        }]
    quiz_list = []
    for i in range(n):
        quiz_list.append({
            "type": "multiple",
            "question": f"{i+1}. 아래 내용 일부를 참고해 만든 임시 문제입니다.\n\n{content_preview[:150]}...\n(실전 적용시 AI 연동 권장!)",
            "options": [f"선택지A_{i+1}", f"선택지B_{i+1}", f"선택지C_{i+1}"],
            "correct_answer": 0,
            "explanation": "정답: 선택지A (실제 문제와 정답은 AI를 통해 동적으로 생성할 수 있습니다.)",
            "subject": url
        })
    return quiz_list
