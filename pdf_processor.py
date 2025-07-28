import os, tempfile
from typing import List, Optional
from PyPDF2 import PdfReader
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from config import Config

class PDFProcessor:
    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=Config.CHUNK_SIZE,
            chunk_overlap=Config.CHUNK_OVERLAP,
            separators=["\n\n", "\n", " ", ""],
        )

    def _valid(self, file) -> bool:
        if file.size > Config.MAX_FILE_SIZE_MB * 1024 * 1024:
            return False
        if not file.name.lower().endswith(".pdf"):
            return False
        return True

    def _extract_text(self, file) -> Optional[str]:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(file.getvalue())
            path = tmp.name
        try:
            reader = PdfReader(path)
            text = ""
            for i, page in enumerate(reader.pages, 1):
                if (t := page.extract_text()):
                    text += f"\n\n=== 페이지 {i} ===\n\n{t}"
            return text if text.strip() else None
        finally:
            os.unlink(path)

    def process(self, file) -> Optional[List[Document]]:
        if not self._valid(file):
            return None
        if not (text := self._extract_text(file)):
            return None
        doc = Document(page_content=text, metadata={"source": file.name})
        chunks = self.splitter.split_documents([doc])
        for idx, c in enumerate(chunks):
            c.metadata.update(chunk_id=idx)
        return chunks
