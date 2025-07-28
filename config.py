import os
from dotenv import load_dotenv

load_dotenv()  # .env 환경변수 읽기

class Config:
    # OpenAI API Key
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    # PDF 업로드/처리 기본값
    MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

    # FAISS 저장 루트
    FAISS_BASE_PATH = os.getenv("FAISS_BASE_PATH", "./faiss_subjects")

    # LLM
    LLM_MODEL = "gpt-3.5-turbo"
    TEMPERATURE = 0.7

    # 앱 타이틀/설명
    APP_TITLE = "📚 대학강의 PDF 챗봇 & 퀴즈 생성기"
    APP_DESCRIPTION = "PDF 강의자료를 업로드하여 맞춤형 학습 도우미를 만드세요!"

    CHARACTER_VIDEO_PATH = os.getenv("CHARACTER_VIDEO_PATH", "character.mp4")

    @classmethod
    def validate(cls):
        if not cls.OPENAI_API_KEY or not cls.OPENAI_API_KEY.startswith("sk"):
            raise ValueError("OPENAI_API_KEY가 올바르게 설정되지 않았습니다.")
