import os, shutil
import re
from typing import List, Dict
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.docstore.document import Document
from config import Config

class MultiSubjectVectorStoreManager:
    def __init__(self):
        # ✅ HuggingFace 임베딩 모델 사용 (예: all-MiniLM-L6-v2)
        self.embed = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        self.stores: Dict[str, FAISS] = {}
        self.load_all_subjects()

    def get_subject_path(self, subject_name: str) -> str:
        # 한글/특수문자 → 안전한 폴더명으로 변환
        # safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', subject_name)
        # return os.path.join(Config.FAISS_BASE_PATH, safe_name)
        
        return os.path.join(Config.FAISS_BASE_PATH, subject_name)


    def load_all_subjects(self):
        if not os.path.exists(Config.FAISS_BASE_PATH):
            return
        for subject_dir in os.listdir(Config.FAISS_BASE_PATH):
            subject_path = self.get_subject_path(subject_dir)
            if os.path.exists(subject_path):
                try:
                    self.stores[subject_dir] = FAISS.load_local(
                        subject_path, self.embed, allow_dangerous_deserialization=True
                    )
                except Exception as e:
                    print(f"과목 {subject_dir} 로드 실패: {e}")

    def create_or_update_subject(self, subject_name: str, docs: List[Document], file_name: str = None):
        subject_path = self.get_subject_path(subject_name)
        if subject_name in self.stores:
            new_store = FAISS.from_documents(docs, self.embed)
            self.stores[subject_name].merge_from(new_store)
        else:
            self.stores[subject_name] = FAISS.from_documents(docs, self.embed)

        os.makedirs(subject_path, exist_ok=True)
        self.stores[subject_name].save_local(subject_path)

        # ✅ PDF 파일명 기록 (중복 방지)
        if file_name:
            meta_file = os.path.join(subject_path, "pdf_files.txt")
            existing_files = []
            if os.path.exists(meta_file):
                with open(meta_file, "r", encoding="utf-8") as f:
                    existing_files = [line.strip() for line in f if line.strip()]
            if file_name not in existing_files:
                with open(meta_file, "a", encoding="utf-8") as f:
                    f.write(file_name + "\n")

    def get_subjects(self):
        if not os.path.exists(Config.FAISS_BASE_PATH):
            return []
        return [
            d for d in os.listdir(Config.FAISS_BASE_PATH)
            if d.strip() and os.path.isdir(os.path.join(Config.FAISS_BASE_PATH, d))
        ]

    def get_store(self, subject_name: str) -> FAISS:
        return self.stores.get(subject_name)

    def search(self, subject_name: str, query: str, k=4):
        store = self.stores.get(subject_name)
        return store.similarity_search(query, k=k) if store else []

    def get_retriever(self, subject_name: str, k=4):
        store = self.stores.get(subject_name)
        return store.as_retriever(search_kwargs={"k": k}) if store else None

    def delete_subject(self, subject_name: str):
        if subject_name in self.stores:
            del self.stores[subject_name]
            subject_path = self.get_subject_path(subject_name)
            if os.path.exists(subject_path):
                shutil.rmtree(subject_path)

    def get_subject_info(self, subject_name: str):
        store = self.stores.get(subject_name)
        meta_file = os.path.join(self.get_subject_path(subject_name), "pdf_files.txt")
        pdf_file_count = 0
        if os.path.exists(meta_file):
            with open(meta_file, "r", encoding="utf-8") as f:
                pdf_file_count = len([line.strip() for line in f if line.strip()])
        return {
            "status": "활성화됨" if store else "초기화되지 않음",
            "문서 수": pdf_file_count  # ✅ PDF 파일 수만 표시
        }
