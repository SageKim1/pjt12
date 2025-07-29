# 📚 대학강의 PDF 챗봇 & 퀴즈 생성기

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.x-red)
![LangChain](https://img.shields.io/badge/LangChain-Framework-green)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT-yellow)
![Anthropic](https://img.shields.io/badge/Claude-AI-orange)

---

## 🔎 프로젝트 개요  
PDF 강의자료를 업로드하여 **AI 챗봇**과 **자동 퀴즈 생성기**를 활용한 학습 보조 웹앱입니다.  
강의자료를 기반으로 질문에 답변하고, 퀴즈를 생성해 학습 효과를 극대화할 수 있습니다.

---

## ✨ 주요 기능
- **📁 PDF 업로드 및 과목 관리**  
  강의 자료 PDF 업로드 및 과목별 문서 관리  
- **💬 강의자료 기반 챗봇**  
  AI가 PDF 자료를 기반으로 대화형 질의응답 제공  
- **📝 자동 퀴즈 생성**  
  객관식, 주관식, OX 혼합형 퀴즈 생성 및 풀이 기능  
- **❌ 오답 노트 PDF 다운로드**  
  틀린 문제 및 해설 기록 관리, PDF 다운로드 지원  
- **🌐 웹 검색 & 링크 퀴즈**  
  웹 검색 또는 URL 기반 퀴즈 생성 기능  
- **📊 학습 리포트**  
  과목별 오답 통계 및 취약 과목 분석 시각화  

---

## 🛠 기술 스택
- **Frontend/UI**: [Streamlit](https://streamlit.io)  
- **AI 모델**: OpenAI GPT, Anthropic Claude  
- **벡터 스토어**: FAISS  
- **프레임워크**: LangChain  
- **데이터 처리**: PyPDF2, BeautifulSoup, Requests  
- **시각화**: Matplotlib  

---

## 🚀 설치 및 실행 방법

### 1️⃣ 저장소 클론
```bash
git clone https://github.com/SageKim1/pjt12.git
cd pjt12
```

### 2️⃣ 가상환경 생성 및 활성화
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

### 3️⃣ 패키지 설치
```bash
pip install -r requirements.txt
```

### 4️⃣ 환경 변수 설정
`.env` 파일을 생성하고 아래 내용을 입력하세요:
```bash
MODEL_TYPE=openai  # 또는 claude
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_claude_api_key
```

### 5️⃣ 실행
```bash
streamlit run app.py
```

### 📂 폴더 구조
```bash
├── app.py               # 메인 Streamlit 앱
├── quiz_generator.py     # 퀴즈 생성 모듈
├── pdf_processor.py      # PDF 처리 및 텍스트 분리
├── vector_store.py       # 벡터 스토어 관리
├── chatbot.py            # 챗봇 로직
├── utils/                # 웹 검색 및 기타 유틸리티
├── config.py             # API 키 및 설정 관리
├── requirements.txt      # 의존성 패키지
└── README.md
```