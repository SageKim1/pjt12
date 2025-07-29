from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    MODEL_TYPE = os.getenv("MODEL_TYPE", "openai")  # "openai" 또는 "claude"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    
    # 모델명 (Claude 또는 OpenAI에 따라 분기)
    CLAUDE_MODEL = "claude-3-7-sonnet-20250219"
    OPENAI_MODEL = "gpt-3.5-turbo"
    TEMPERATURE = 0.3
    
    # LLM_MODEL 자동 선택 속성 추가
    @classmethod
    def LLM_MODEL(cls):
        return cls.CLAUDE_MODEL if cls.MODEL_TYPE == "claude" else cls.OPENAI_MODEL

    @classmethod
    def validate(cls):
        if cls.MODEL_TYPE == "openai" and not cls.OPENAI_API_KEY.startswith("sk"):
            raise ValueError("OPENAI_API_KEY가 올바르게 설정되지 않았습니다.")
        elif cls.MODEL_TYPE == "claude" and not cls.ANTHROPIC_API_KEY.startswith("sk"):
            raise ValueError("ANTHROPIC_API_KEY가 올바르게 설정되지 않았습니다.")


    # PDF 설정
    MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

    # FAISS 저장 경로
    FAISS_BASE_PATH = os.getenv("FAISS_BASE_PATH", "./faiss_subjects")

    # UI 설정
    APP_TITLE = "대학강의 PDF 챗봇 & 퀴즈 생성기"
    APP_DESCRIPTION = "PDF 강의자료를 업로드하여 맞춤형 학습 도우미를 만드세요!"
    CHARACTER_VIDEO_PATH = os.getenv("CHARACTER_VIDEO_PATH", "video_02.mp4")
