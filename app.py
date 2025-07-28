import streamlit as st
import os
from config import Config
from pdf_processor import PDFProcessor
from vector_store import MultiSubjectVectorStoreManager
from chatbot import MultiSubjectChatbot
from quiz_generator import MultiSubjectQuizGen, Quiz

Config.validate()

if "vs_manager" not in st.session_state:
    st.session_state.vs_manager = MultiSubjectVectorStoreManager()
    st.session_state.pdf = PDFProcessor()
    st.session_state.bot = MultiSubjectChatbot(st.session_state.vs_manager)
    st.session_state.qg = MultiSubjectQuizGen(st.session_state.vs_manager)
    st.session_state.current_subject = ""
    st.session_state.wrong_answers = []
    st.session_state.chat_history = {}

CHARACTER_VIDEO_PATH = Config.CHARACTER_VIDEO_PATH
CHARACTER_VIDEO_WIDTH = 120  # 원하는 크기로 조정

def play_character_video_html():
    if os.path.exists(CHARACTER_VIDEO_PATH):
        video_html = f"""
            <video src="{CHARACTER_VIDEO_PATH}" width="{CHARACTER_VIDEO_WIDTH}" autoplay muted loop style="border-radius:8px;margin-right:10px;vertical-align:top;display:inline-block;"></video>
        """
        st.markdown(video_html, unsafe_allow_html=True)
    else:
        st.write("캐릭터 영상(character.mp4)이 없습니다.")

def add_to_wrong_answers(quiz: Quiz, user_answer: int):
    wrong_item = {
        "subject": quiz.subject,
        "question": quiz.question,
        "options": quiz.options,
        "correct_answer": quiz.correct_answer,
        "user_answer": user_answer,
        "explanation": quiz.explanation
    }
    st.session_state.wrong_answers.append(wrong_item)

st.set_page_config(page_title=Config.APP_TITLE, page_icon="📚", layout="wide")
st.sidebar.title("📚 학습 메뉴")

subjects = st.session_state.vs_manager.get_subjects()
if subjects:
    selected_subject = st.sidebar.selectbox("📖 과목 선택", [""] + subjects, key="sidebar_subject")
    if selected_subject:
        st.session_state.current_subject = selected_subject

page = st.sidebar.radio("페이지 이동", [
    "📁 PDF 업로드", 
    "💬 챗봇", 
    "📝 퀴즈 생성", 
    "🎯 퀴즈 풀기", 
    "❌ 오답 노트"
])

st.sidebar.markdown("---")
st.sidebar.markdown("### 🎭 학습 도우미 수정")
if os.path.exists(CHARACTER_VIDEO_PATH):
    st.sidebar.video(CHARACTER_VIDEO_PATH, start_time=0)
else:
    st.sidebar.info("character.mp4(영상)가 없습니다.")

st.title(Config.APP_TITLE)
st.markdown(Config.APP_DESCRIPTION)

# ---------- PDF 업로드 ----------
if page == "📁 PDF 업로드":
    st.header("📁 PDF 업로드 및 과목 관리")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("과목 관리")
        new_subject = st.text_input("새 과목명 입력", placeholder="예: 데이터베이스", key="new_subject")
        if st.button("새 과목 추가") and new_subject:
            if new_subject not in subjects:
                st.success(f"'{new_subject}' 과목이 추가되었습니다! PDF 업로드 시 활성화됩니다.")
                st.rerun()
            else:
                st.warning("이미 존재하는 과목입니다.")
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
        uploaded_file = st.file_uploader("PDF 파일 선택", type="pdf")
        if uploaded_file and target_subject and st.button("업로드 및 처리"):
            with st.spinner(f"'{target_subject}' 과목에 PDF 처리 중..."):
                chunks = st.session_state.pdf.process(uploaded_file)
                if chunks:
                    st.session_state.vs_manager.create_or_update_subject(target_subject, chunks)
                    st.success(f"'{target_subject}' 과목에 PDF가 성공적으로 추가되었습니다!")
                    st.rerun()
                else:
                    st.error("PDF 처리에 실패했습니다.")

# ---------- 챗봇 ----------
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
            with st.chat_message("user"):
                st.write(chat["question"])
            with st.chat_message("assistant"):
                col1, col2 = st.columns([0.2, 0.8], gap="small")
                with col1:
                    play_character_video_html()
                with col2:
                    st.write(chat["answer"])
        if question := st.chat_input("질문을 입력하세요"):
            with st.chat_message("user"):
                st.write(question)
            with st.chat_message("assistant"):
                col1, col2 = st.columns([0.2, 0.8], gap="small")
                with col1:
                    play_character_video_html()
                with col2:
                    with st.spinner("AI 답변 생성 중..."):
                        answer, sources = st.session_state.bot.ask(subject, question)
                        st.write(answer)
                        if sources:
                            with st.expander("📚 참조 문서"):
                                for i, source in enumerate(sources):
                                    st.write(f"{i+1}. {source.metadata.get('source', '알 수 없음')}")
            st.session_state.chat_history[subject].append({
                "question": question, "answer": answer
            })

# ---------- 퀴즈 생성 ----------
elif page == "📝 퀴즈 생성":
    st.header("📝 퀴즈 자동 생성")
    if not st.session_state.current_subject:
        st.warning("사이드바에서 과목을 선택하세요.")
    else:
        subject = st.session_state.current_subject
        st.info(f"현재 과목: **{subject}**")
        col1, col2, col3 = st.columns(3)
        with col1:
            num_questions = st.number_input("문항 수", 1, 20, 5, key="q_num")
        with col2:
            difficulty = st.selectbox("난이도", ["쉬움", "보통", "어려움"], key="q_dif")
        with col3:
            topic = st.text_input("특정 주제 (선택사항)", key="q_topic")
        if st.button("🎲 퀴즈 생성"):
            with st.spinner("퀴즈 생성 중..."):
                quizzes = st.session_state.qg.generate(subject, num_questions, difficulty, topic)
                if quizzes:
                    st.session_state.current_quizzes = quizzes
                    st.session_state.quiz_subject = subject
                    st.success(f"{len(quizzes)}개의 퀴즈가 생성되었습니다!")

# ---------- 퀴즈 풀기 ----------
elif page == "🎯 퀴즈 풀기":
    st.header("🎯 퀴즈 풀기")
    if "current_quizzes" not in st.session_state or not st.session_state.current_quizzes:
        st.info("먼저 '📝 퀴즈 생성'에서 퀴즈를 만들어주세요.")
    else:
        quizzes = st.session_state.current_quizzes
        quiz_subject = st.session_state.get("quiz_subject", "")
        if "current_quiz_index" not in st.session_state:
            st.session_state.current_quiz_index = 0
            st.session_state.quiz_answers = {}
            st.session_state.quiz_completed = False
        current_index = st.session_state.current_quiz_index
        if not st.session_state.quiz_completed and current_index < len(quizzes):
            quiz = quizzes[current_index]
            progress = (current_index + 1) / len(quizzes)
            col1, col2 = st.columns([0.18,0.82], gap="small")
            with col1:
                play_character_video_html()
            with col2:
                st.subheader(f"Q{current_index + 1}. {quiz.question}")
                user_answer = st.radio(
                    "답을 선택하세요:",
                    options=range(len(quiz.options)),
                    format_func=lambda x: f"{chr(65+x)}. {quiz.options[x]}",
                    key=f"quiz_{current_index}"
                )
            colA, colB = st.columns(2)
            with colA:
                if st.button("다음 문제"):
                    st.session_state.quiz_answers[current_index] = user_answer
                    if user_answer != quiz.correct_answer:
                        add_to_wrong_answers(quiz, user_answer)
                    if current_index + 1 < len(quizzes):
                        st.session_state.current_quiz_index += 1
                        st.rerun()
                    else:
                        st.session_state.quiz_completed = True
                        st.rerun()
            with colB:
                if current_index > 0 and st.button("이전 문제"):
                    st.session_state.current_quiz_index -= 1
                    st.rerun()
        elif st.session_state.quiz_completed:
            st.success("🎉 퀴즈 완료!")
            correct_count = 0
            total_questions = len(quizzes)
            for i, quiz in enumerate(quizzes):
                user_answer = st.session_state.quiz_answers.get(i, -1)
                is_correct = user_answer == quiz.correct_answer
                if is_correct:
                    correct_count += 1
                status_icon = "✅" if is_correct else "❌"
                st.write(f"{status_icon} **Q{i+1}**: {quiz.question}")
                st.write(f"정답: {chr(65+quiz.correct_answer)}. {quiz.options[quiz.correct_answer]}")
                if user_answer >= 0:
                    st.write(f"내 답: {chr(65+user_answer)}. {quiz.options[user_answer]}")
                st.write(f"해설: {quiz.explanation}")
                st.markdown("---")
            score = (correct_count / total_questions) * 100
            st.metric("최종 점수", f"{correct_count}/{total_questions} ({score:.1f}%)")
            if st.button("🔄 다시 풀기"):
                st.session_state.current_quiz_index = 0
                st.session_state.quiz_answers = {}
                st.session_state.quiz_completed = False
                st.rerun()

# ---------- 오답 노트 ----------
elif page == "❌ 오답 노트":
    st.header("❌ 오답 노트")
    if not st.session_state.wrong_answers:
        st.info("아직 틀린 문제가 없습니다.")
    else:
        st.write(f"총 {len(st.session_state.wrong_answers)}개의 틀린 문제가 있습니다.")
        subjects_in_wrong = list(set([item["subject"] for item in st.session_state.wrong_answers]))
        selected_filter = st.selectbox("과목별 필터", ["전체"] + subjects_in_wrong)
        for i, wrong_item in enumerate(st.session_state.wrong_answers):
            if selected_filter != "전체" and wrong_item["subject"] != selected_filter:
                continue
            with st.expander(f"[{wrong_item['subject']}] {wrong_item['question'][:50]}..."):
                st.write(f"**문제**: {wrong_item['question']}")
                for j, option in enumerate(wrong_item['options']):
                    icon = ""
                    if j == wrong_item['correct_answer']:
                        icon = "✅ (정답)"
                    elif j == wrong_item['user_answer']:
                        icon = "❌ (내 답)"
                    st.write(f"{chr(65+j)}. {option} {icon}")
                st.write(f"**해설**: {wrong_item['explanation']}")
        if st.button("🗑️ 오답 노트 초기화"):
            st.session_state.wrong_answers = []
            st.success("오답 노트가 초기화되었습니다.")
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 학습 현황")
if st.session_state.current_subject:
    info = st.session_state.vs_manager.get_subject_info(st.session_state.current_subject)
    st.sidebar.write(f"현재 과목: {st.session_state.current_subject}")
    st.sidebar.write(f"문서 수: {info.get('문서 수', 0)}")
wrong_count = len(st.session_state.wrong_answers)
st.sidebar.write(f"오답 문제: {wrong_count}개")
