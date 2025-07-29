import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from langchain.schema import Document
from vector_store import MultiSubjectVectorStoreManager

def web_search(query: str, max_results=3):
    """DuckDuckGo 검색"""
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=max_results)]
        return [{"title": r["title"], "link": r["href"], "snippet": r["body"]} for r in results]
    except Exception as e:
        return [{"title": "검색 오류", "link": "", "snippet": f"검색 중 오류 발생: {e}"}]

def save_web_results_to_vectorstore(vs_manager: MultiSubjectVectorStoreManager, subject_name: str, query: str):
    results = web_search(query)  # duckduckgo 기반 검색 결과
    docs = [Document(page_content=r["snippet"], metadata={"source": r["link"]}) for r in results]
    vs_manager.create_or_update_subject(subject_name, docs)
    return docs

def fetch_link_content(url: str) -> str:
    try:
        response = requests.get(url)
        response.encoding = response.apparent_encoding  # ✅ 한글 깨짐 해결
        soup = BeautifulSoup(response.text, "html.parser")
        paragraphs = [p.get_text().strip() for p in soup.select("p")]
        return "\n".join(paragraphs[:10])
    except Exception as e:
        return f"오류 발생: {e}"
