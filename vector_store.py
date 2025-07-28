import os, shutil
from typing import List, Dict
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.docstore.document import Document
from config import Config

class MultiSubjectVectorStoreManager:
    def __init__(self):
        self.embed = OpenAIEmbeddings(
            openai_api_key=Config.OPENAI_API_KEY,
            model="text-embedding-ada-002",
        )
        self.stores: Dict[str, FAISS] = {}
        self.load_all_subjects()

    def get_subject_path(self, subject_name: str) -> str:
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

    def create_or_update_subject(self, subject_name: str, docs: List[Document]):
        subject_path = self.get_subject_path(subject_name)
        if subject_name in self.stores:
            new_store = FAISS.from_documents(docs, self.embed)
            self.stores[subject_name].merge_from(new_store)
        else:
            self.stores[subject_name] = FAISS.from_documents(docs, self.embed)
        os.makedirs(subject_path, exist_ok=True)
        self.stores[subject_name].save_local(subject_path)

    def get_subjects(self) -> List[str]:
        return list(self.stores.keys())

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
        return (
            {"status": "활성화됨", "문서 수": store.index.ntotal}
            if store
            else {"status": "초기화되지 않음"}
        )
