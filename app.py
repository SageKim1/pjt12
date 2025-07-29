import streamlit as st
import os
import base64
from config import Config
from pdf_processor import PDFProcessor
from vector_store import MultiSubjectVectorStoreManager
from chatbot import MultiSubjectChatbot
from quiz_generator import MultiSubjectQuizGen, Quiz, generate_quiz_from_link
from utils.web_tools import web_search, fetch_link_content, save_web_results_to_vectorstore

# =========================
# Streamlit 메인 학습 앱
# =========================
Config.validate()

# 세션 상태 초기화
if "vs_manager" not in st.session_state:
    st.session_state.vs_manager = MultiSubjectVectorStoreManager()
    st.session_state.pdf = PDFProcessor()
    st.session_state.bot = MultiSubjectChatbot(st.session_state.vs_manager)
    st.session_state.qg = MultiSubjectQuizGen(st.session_state.vs_manager)
    st.session_state.current_subject = ""
    st.session_state.wrong_answers = []
    st.session_state.chat_history = {}
    st.session_state.current_quizzes = []
    st.session_state.current_quiz_index = 0
    st.session_state.quiz_answers = {}
    st.session_state.quiz_completed = False

# 새로운 동영상 파일 경로
CHARACTER_VIDEO_PATH = Config.CHARACTER_VIDEO_PATH  # Config에서 불러오기
CHARACTER_VIDEO_WIDTH = 150

def play_character_video_html():
    if os.path.exists(CHARACTER_VIDEO_PATH):
        video_html = f"""
            <video src="{CHARACTER_VIDEO_PATH}" width="{CHARACTER_VIDEO_WIDTH}" autoplay muted loop style="border-radius:8px;margin-right:10px;vertical-align:top;display:inline-block;"></video>
        """
        st.markdown(video_html, unsafe_allow_html=True)
    else:
        st.write("캐릭터 영상(character.mp4)이 없습니다.")

def add_to_wrong_answers(quiz, user_answer):
    if isinstance(quiz, Quiz):
        wrong_item = {
            "subject": quiz.subject,
            "question": quiz.question,
            "options": quiz.options,
            "correct_answer": quiz.correct_answer,
            "user_answer": user_answer,
            "explanation": quiz.explanation,
            "type": getattr(quiz, "type", "multiple")
        }
    else:
        wrong_item = {
            "subject": quiz.get("subject", ""),
            "question": quiz.get("question", ""),
            "options": quiz.get("options", None),
            "correct_answer": quiz.get("correct_answer"),
            "user_answer": user_answer,
            "explanation": quiz.get("explanation", ""),
            "type": quiz.get("type", "multiple")
        }
    st.session_state.wrong_answers.append(wrong_item)

st.set_page_config(page_title=Config.APP_TITLE, page_icon="📚", layout="wide")

# 사이드바 과목 선택
st.sidebar.title("📚 학습 메뉴")
subjects = [s for s in st.session_state.vs_manager.get_subjects() if s.strip()]

if not subjects:
    st.warning("⚠ 현재 등록된 과목이 없습니다. PDF를 먼저 업로드하세요.")
else:
    selected_subject = st.sidebar.selectbox("📖 과목 선택", [""] + subjects, key="sidebar_subject")
    if selected_subject.strip():
        st.session_state.current_subject = selected_subject


# 페이지 상태
if "selected_page" not in st.session_state:
    st.session_state.selected_page = "📁 PDF 업로드"

page_list = ["📁 PDF 업로드", "💬 챗봇", "📝 퀴즈 생성", "🎯 퀴즈 풀기", "❌ 오답 노트", "🌐 웹 검색 & 링크 퀴즈", "📊 종합 리포트"]
page = st.sidebar.radio("페이지 이동", page_list, index=page_list.index(st.session_state.selected_page), key="page_radio")

# 캐릭터 영상 사이드바 표시
def get_video_base64(video_path):
    with open(video_path, "rb") as video_file:
        return base64.b64encode(video_file.read()).decode()

st.sidebar.markdown("---")
st.sidebar.markdown("### 🎭 학습 도우미")
if os.path.exists(CHARACTER_VIDEO_PATH):
    video_base64 = get_video_base64(CHARACTER_VIDEO_PATH)
    video_html = f"""
        <video width="100%" autoplay muted loop playsinline>
            <source src="data:video/mp4;base64,{video_base64}" type="video/mp4">
        </video>
    """
    st.sidebar.markdown(video_html, unsafe_allow_html=True)
else:
    st.sidebar.info(f"{CHARACTER_VIDEO_PATH}(영상)이 없습니다.")

# 메인 제목
st.title(Config.APP_TITLE)
st.markdown(Config.APP_DESCRIPTION)

# ==============================
# 📁 PDF 업로드
# ==============================
if page == "📁 PDF 업로드":
    st.header("📁 PDF 업로드 및 과목 관리")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("과목 관리")
        new_subject = st.text_input("새 과목명 입력", placeholder="예: 데이터베이스", key="new_subject")
        if st.button("새 과목 추가"):
            new_subject = new_subject.strip()
            if new_subject:
                if new_subject not in subjects:
                    st.success(f"'{new_subject}' 과목이 추가되었습니다! PDF 업로드 시 활성화됩니다.")
                    st.rerun()
                else:
                    st.warning("이미 존재하는 과목입니다.")
            else:
                st.warning("과목명을 입력하세요.")
        if subjects:
            st.markdown("**기존 과목 목록:**")
            for subject in subjects:
                info = st.session_state.vs_manager.get_subject_info(subject)
                st.write(f"• {subject} ({info.get('문서 수', 0)}개 문서)")
    with col2:
        st.subheader("PDF 업로드")
        upload_subjects = subjects.copy()
        if new_subject and new_subject not in subjects:
            upload_subjects.append(new_subject)
        target_subject = st.selectbox("업로드할 과목 선택", upload_subjects, key="upload_subject")
        uploaded_files = st.file_uploader("PDF 파일 선택", type="pdf", accept_multiple_files=True)
        if uploaded_files and target_subject and st.button("업로드 및 처리"):
            upload_success = False
            for uploaded_file in uploaded_files:
                with st.spinner(f"'{target_subject}' 과목에 {uploaded_file.name} 처리 중..."):
                    chunks = st.session_state.pdf.process(uploaded_file)
                    if chunks:
                        st.session_state.vs_manager.create_or_update_subject(target_subject, chunks, file_name=uploaded_file.name)
                        st.success(f"'{uploaded_file.name}' 파일이 성공적으로 추가되었습니다!")
                        upload_success = True
                    else:
                        st.error(f"{uploaded_file.name} 처리에 실패했습니다.")
            if upload_success:
                st.rerun()

# ==============================
# 💬 챗봇
# ==============================
elif page == "💬 챗봇":
    st.header("💬 강의자료 챗봇")
    if not st.session_state.current_subject:
        st.warning("사이드바에서 과목을 선택하세요.")
    else:
        subject = st.session_state.current_subject
        st.info(f"현재 과목: **{subject}**")
        if subject not in st.session_state.chat_history:
            st.session_state.chat_history[subject] = []
        for chat in st.session_state.chat_history[subject]:
            with st.chat_message("user"): st.write(chat["question"])
            with st.chat_message("assistant"):
                col1, col2 = st.columns([0.2, 0.8], gap="small")
                with col1: play_character_video_html()
                with col2: st.write(chat["answer"])
        if question := st.chat_input("질문을 입력하세요"):
            with st.chat_message("user"): st.write(question)
            with st.chat_message("assistant"):
                col1, col2 = st.columns([0.2, 0.8], gap="small")
                with col1: play_character_video_html()
                with col2:
                    with st.spinner("AI 답변 생성 중..."):
                        answer, sources = st.session_state.bot.ask(subject, question)
                        st.write(answer)
                        if sources:
                            with st.expander("📚 참조 문서"):
                                for i, source in enumerate(sources):
                                    st.write(f"{i+1}. {source.metadata.get('source', '알 수 없음')}")
            st.session_state.chat_history[subject].append({"question": question, "answer": answer})


# ==============================
# 📝 퀴즈 생성 (퀴즈 유형 포함)
# ==============================
elif page == "📝 퀴즈 생성":
    st.header("📝 퀴즈 자동 생성")
    if not st.session_state.current_subject:
        st.warning("사이드바에서 과목을 선택하세요.")
    else:
        subject = st.session_state.current_subject
        st.info(f"현재 과목: **{subject}**")
        col1, col2, col3, col4 = st.columns(4)
        with col1: num_questions = st.number_input("문항 수", 1, 20, 5, key="q_num")
        with col2: difficulty = st.selectbox("난이도", ["쉬움", "보통", "어려움"], key="q_dif")
        with col3: topic = st.text_input("특정 주제 (선택사항)", key="q_topic")
        with col4: quiz_type = st.selectbox("퀴즈 유형", ["객관식", "주관식", "OX", "혼합"], key="q_type")
        if st.button("🎲 퀴즈 생성"):
            with st.spinner("퀴즈 생성 중..."):
                quizzes = st.session_state.qg.generate(subject, num_questions, difficulty, topic, quiz_type)
                if quizzes:
                    st.session_state.current_quizzes = quizzes
                    st.session_state.quiz_subject = subject
                    st.session_state.current_quiz_index = 0
                    st.session_state.quiz_answers = {}
                    st.session_state.quiz_completed = False
                    st.success(f"{len(quizzes)}개의 퀴즈가 생성되었습니다!")
                    st.session_state.selected_page = "🎯 퀴즈 풀기"
                    st.rerun()
                else:
                    st.error("퀴즈 생성 실패! PDF 업로드 및 API 키를 확인하세요.")

# ==============================
# 🎯 퀴즈 풀기
# ==============================
elif page == "🎯 퀴즈 풀기":
    st.header("🎯 퀴즈 풀기")
    if not st.session_state.current_quizzes:
        st.info("먼저 '📝 퀴즈 생성' 또는 '링크 기반 퀴즈'에서 퀴즈를 만들어주세요.")
    else:
        quizzes = st.session_state.current_quizzes
        if "current_quiz_index" not in st.session_state:
            st.session_state.current_quiz_index = 0
            st.session_state.quiz_answers = {}
            st.session_state.quiz_completed = False
        current_index = st.session_state.current_quiz_index

        if not st.session_state.quiz_completed and current_index < len(quizzes):
            quiz = quizzes[current_index]
            st.subheader(f"Q{current_index + 1}. {quiz.question} [{quiz.type.upper()}]")

            if quiz.type == "multiple":
                user_answer = st.radio("답을 선택하세요:", options=range(len(quiz.options)),
                                       format_func=lambda x: f"{chr(65+x)}. {quiz.options[x]}",
                                       key=f"quiz_{current_index}")
            elif quiz.type == "ox":
                user_answer = st.radio("답을 선택하세요:", options=range(2),
                                       format_func=lambda x: ["O", "X"][x], key=f"quiz_{current_index}")
            elif quiz.type == "short":
                user_answer = st.text_input("답을 입력하세요 (단어 또는 짧은 문장):", key=f"quiz_{current_index}")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("➡ 다음"):
                    is_correct = False
                    if quiz.type == "short":
                        cleaned_user = user_answer.strip().lower() if user_answer else ""
                        cleaned_correct = str(quiz.correct_answer).strip().lower()
                        is_correct = cleaned_user == cleaned_correct
                    else:
                        is_correct = user_answer == quiz.correct_answer

                    st.session_state.quiz_answers[current_index] = user_answer
                    if not is_correct: add_to_wrong_answers(quiz, user_answer)
                    if current_index + 1 < len(quizzes):
                        st.session_state.current_quiz_index += 1
                        st.rerun()
                    else:
                        st.session_state.quiz_completed = True
                        st.rerun()

            with col2:
                if current_index > 0 and st.button("⬅ 이전"):
                    st.session_state.current_quiz_index -= 1
                    st.rerun()

        elif st.session_state.quiz_completed:
            st.success("🎉 퀴즈 완료!")
            correct_count = sum(
                1 for i, q in enumerate(quizzes)
                if (q.type != "short" and st.session_state.quiz_answers.get(i) == q.correct_answer) or
                   (q.type == "short" and st.session_state.quiz_answers.get(i, "").strip().lower() ==
                    str(q.correct_answer).strip().lower())
            )
            st.write(f"정답: {correct_count}/{len(quizzes)}")
            for i, quiz in enumerate(quizzes):
                user_answer = st.session_state.quiz_answers.get(i, "" if quiz.type == "short" else -1)
                if quiz.type == "short":
                    is_correct = user_answer.strip().lower() == str(quiz.correct_answer).strip().lower()
                    st.write(f"{'✅' if is_correct else '❌'} Q{i+1}: {quiz.question} [SHORT]")
                    st.write(f"정답: {quiz.correct_answer}")
                    st.write(f"내 답: {user_answer}")
                else:
                    is_correct = user_answer == quiz.correct_answer
                    st.write(f"{'✅' if is_correct else '❌'} Q{i+1}: {quiz.question} [{quiz.type.upper()}]")
                    if quiz.type == "multiple":
                        st.write(f"정답: {chr(65+quiz.correct_answer)}. {quiz.options[quiz.correct_answer]}")
                        if user_answer >= 0: st.write(f"내 답: {chr(65+user_answer)}. {quiz.options[user_answer]}")
                    elif quiz.type == "ox":
                        st.write(f"정답: {'O' if quiz.correct_answer == 0 else 'X'}")
                        if user_answer >= 0: st.write(f"내 답: {'O' if user_answer == 0 else 'X'}")
                st.write(f"해설: {quiz.explanation}")
                st.markdown("---")

            if st.button("🔄 다시 풀기"):
                st.session_state.current_quiz_index = 0
                st.session_state.quiz_answers = {}
                st.session_state.quiz_completed = False
                st.rerun()



# ==============================
# ❌ 오답 노트 (PDF 다운로드 포함)
# ==============================
elif page == "❌ 오답 노트":
    st.header("❌ 오답 노트")
    if not st.session_state.wrong_answers:
        st.info("아직 오답이 없습니다.")
    else:
        st.write(f"총 {len(st.session_state.wrong_answers)}개의 오답이 있습니다.")
        subjects_in_wrong = list({w["subject"] for w in st.session_state.wrong_answers})
        selected_subject = st.selectbox("과목별 오답 보기", ["전체"] + subjects_in_wrong)
        filtered_wrongs = st.session_state.wrong_answers if selected_subject == "전체" else [w for w in st.session_state.wrong_answers if w["subject"] == selected_subject]

        for idx, wrong in enumerate(filtered_wrongs, start=1):
            st.markdown(f"### ❌ Q{idx}. [{wrong['subject']}] {wrong['question']} [{wrong['type'].upper()}]")
            if wrong["type"] == "multiple":
                for opt_idx, option in enumerate(wrong["options"]):
                    is_correct = (opt_idx == wrong["correct_answer"])
                    prefix = "✅" if is_correct else ("👉" if opt_idx == wrong["user_answer"] else "•")
                    st.write(f"{prefix} {chr(65+opt_idx)}. {option}")
            elif wrong["type"] == "ox":
                st.write(f"정답: {'O' if wrong['correct_answer'] == 0 else 'X'}")
                st.write(f"내 답: {'O' if wrong['user_answer'] == 0 else 'X'}")
            elif wrong["type"] == "short":
                st.write(f"정답: {wrong['correct_answer']}")
                st.write(f"내 답: {wrong['user_answer']}")
            st.info(f"💡 해설: {wrong['explanation']}")
            st.divider()

        if st.button("📄 오답 노트 PDF 다운로드"):
            # ✅ 폰트 파일 존재 여부 체크
            if not os.path.exists("NotoSansKR-Regular.ttf") or not os.path.exists("NotoSansKR-Bold.ttf"):
                st.warning("⚠ NotoSansKR 폰트 파일이 없습니다. PDF 다운로드가 정상 작동하지 않을 수 있습니다.")
            else:
                from fpdf import FPDF
                import re

                def sanitize(text):
                    if not isinstance(text, str): 
                        text = str(text)
                    text = re.sub(r"[\u200b-\u200d\uFEFF]", "", text)
                    return text.strip()

                pdf = FPDF()
                pdf.add_font('NotoSansKR', '', 'NotoSansKR-Regular.ttf', uni=True)
                pdf.add_font('NotoSansKR', 'B', 'NotoSansKR-Bold.ttf', uni=True)
                pdf.set_auto_page_break(auto=True, margin=15)
                pdf.add_page()
                pdf.set_font('NotoSansKR', 'B', 16)
                pdf.cell(0, 10, sanitize("오답 노트"), ln=True, align='C')
                pdf.ln(10)

                for idx, w in enumerate(st.session_state.wrong_answers, 1):
                    pdf.set_font('NotoSansKR', 'B', 12)
                    pdf.multi_cell(0, 10, sanitize(f"{idx}. [{w['subject']}] {w['question']}"))
                    pdf.set_font('NotoSansKR', '', 11)
                    if w["type"] == "multiple":
                        for i, opt in enumerate(w["options"]):
                            mark = "[정답]" if i == w["correct_answer"] else ("[내 답]" if i == w["user_answer"] else "")
                            pdf.multi_cell(0, 8, sanitize(f"{chr(65+i)}. {opt} {mark}"))
                    elif w["type"] == "ox":
                        pdf.multi_cell(0, 8, sanitize(f"정답: {'O' if w['correct_answer']==0 else 'X'} / 내 답: {'O' if w['user_answer']==0 else 'X'}"))
                    elif w["type"] == "short":
                        pdf.multi_cell(0, 8, sanitize(f"정답: {w['correct_answer']} / 내 답: {w['user_answer']}"))
                    pdf.set_font('NotoSansKR', '', 10)
                    pdf.multi_cell(0, 8, sanitize(f"해설: {w['explanation']}"))
                    pdf.ln(5)

                pdf_bytes = pdf.output(dest="S").encode("latin1")
                b64 = base64.b64encode(pdf_bytes).decode()
                href = f'<a href="data:application/octet-stream;base64,{b64}" download="오답노트.pdf">📥 오답 노트 다운로드</a>'
                st.markdown(href, unsafe_allow_html=True)


# ---------- 🌐 웹 검색 & 링크 퀴즈 ----------
elif page == "🌐 웹 검색 & 링크 퀴즈":
    st.header("🌐 웹 검색 & 링크 퀴즈")

    tab1, tab2 = st.tabs(["🔍 웹 검색", "🔗 링크 기반 퀴즈"])

    # 🔍 웹 검색 탭
    with tab1:
        query = st.text_input("검색어 입력", placeholder="예: 위키독스 파이썬")
        if st.button("검색"):
            if query.strip():
                results = web_search(query)
                if results:
                    for r in results:
                        st.markdown(f"### [{r['title']}]({r['link']})")
                        st.write(r["snippet"])
                        st.divider()
                    # ✅ 검색 결과 벡터스토어 저장 버튼
                    if st.button("이 검색 결과를 벡터스토어에 저장"):
                        save_web_results_to_vectorstore(
                            st.session_state.vs_manager,
                            st.session_state.current_subject or "웹 검색 자료",
                            query
                        )
                        st.success("검색 결과가 벡터스토어에 저장되었습니다!")
                else:
                    st.warning("검색 결과가 없습니다.")
            else:
                st.warning("검색어를 입력하세요.")

    # 🔗 링크 기반 퀴즈 탭
    with tab2:
        url = st.text_input("퀴즈를 생성할 링크를 입력하세요", placeholder="예: https://wikidocs.net/book/1")
        num_q = st.number_input("문항 수", min_value=1, max_value=10, value=3, step=1)

        if st.button("퀴즈 생성"):
            if url.strip():
                with st.spinner("링크에서 내용 불러오는 중..."):
                    content = fetch_link_content(url)
                    st.subheader("📄 본문 내용 (요약)")
                    st.text_area("본문", content, height=200)

                    quizzes = generate_quiz_from_link(url, n=num_q)
                    if quizzes:
                        st.session_state.current_quizzes = quizzes
                        st.session_state.quiz_subject = "웹 링크 퀴즈"
                        st.session_state.current_quiz_index = 0
                        st.session_state.quiz_answers = {}
                        st.session_state.quiz_completed = False
                        st.success(f"✅ {len(quizzes)}개의 퀴즈가 생성되어 '🎯 퀴즈 풀기'에 추가되었습니다.")
                        st.session_state.selected_page = "🎯 퀴즈 풀기"
                        st.rerun()
                    else:
                        st.error("퀴즈를 생성하지 못했습니다.")
            else:
                st.warning("링크를 입력하세요.")

# ---------- 📊 종합 리포트 ----------
elif page == "📊 종합 리포트":
    st.header("📊 종합 리포트 및 오답 통계")
    if not st.session_state.wrong_answers:
        st.info("아직 오답 기록이 없습니다.")
    else:
        from collections import Counter, defaultdict
        import matplotlib.pyplot as plt, platform

        # ✅ 폰트 설정
        if platform.system() == 'Windows':
            plt.rc('font', family='Malgun Gothic')
        elif platform.system() == 'Darwin':
            plt.rc('font', family='AppleGothic')
        else:
            plt.rc('font', family='NanumGothic')
        plt.rcParams['axes.unicode_minus'] = False

        subject_count = Counter([w["subject"] for w in st.session_state.wrong_answers])
        subjects, counts = zip(*subject_count.items())
        fig, ax = plt.subplots(figsize=(6, 4))
        bars = ax.bar(subjects, counts, color='#FF7F7F', width=0.5)
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height()+0.1, int(bar.get_height()), ha='center')
        ax.set_ylabel("오답 수"); ax.set_title("과목별 오답 통계")
        st.pyplot(fig)

        # 취약 과목 분석
        st.subheader("📌 취약 과목 분석 및 복습 추천")
        for subject, count in sorted(subject_count.items(), key=lambda x: x[1], reverse=True):
            st.write(f"• **{subject}**: {count}개 오답 → 🔁 복습 권장")
            if st.button(f"👉 {subject} 복습하기", key=f"go_{subject}"):
                st.session_state.current_subject = subject
                st.session_state.selected_page = "🎯 퀴즈 풀기"
                st.rerun()

        # 키워드 분석
        topic_counter = defaultdict(int)
        for w in st.session_state.wrong_answers:
            for word in w["explanation"].split():
                if len(word) > 3: topic_counter[word] += 1
        st.subheader("📌 오답 해설 주요 키워드")
        for kw, freq in sorted(topic_counter.items(), key=lambda x: x[1], reverse=True)[:5]:
            st.write(f"• **{kw}**: {freq}회 등장")



# Sidebar 현황
st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 학습 현황")
if st.session_state.current_subject:
    info = st.session_state.vs_manager.get_subject_info(st.session_state.current_subject)
    st.sidebar.write(f"현재 과목: {st.session_state.current_subject}")
    st.sidebar.write(f"문서 수: {info.get('문서 수', 0)}")
wrong_count = len(st.session_state.wrong_answers)
st.sidebar.write(f"오답 문제: {wrong_count}개")