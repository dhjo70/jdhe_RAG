import streamlit as st
import requests
import pandas as pd
import json
import streamlit.components.v1 as components

import socket

def get_local_ip():
    try:
        # Create a dummy socket connection to resolve the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# Dynamically set the API base URL to the machine's local IP address
# This ensures that other users on the local network connect to the hosting machine, not their own localhost.
API_BASE_URL = f"http://{get_local_ip()}:8000"
st.set_page_config(page_title="JDHE Analytics", layout="wide", initial_sidebar_state="expanded")

# --- Custom Built-in CSS ---
st.markdown("""
<style>
    .stApp, .stMarkdown, .stText {
        font-family: 'Google Sans', 'Helvetica Neue', sans-serif;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {
        background-color: transparent !important;
    }
    
    /* Overall Background */
    .stApp {
        background-color: #FFFFFF;
    }
    
    /* Sidebar Styling (Gemini style) */
    [data-testid="stSidebar"] {
        background-color: #F8F9FA !important;
        border-right: none !important;
    }
    [data-testid="stSidebar"] .stButton>button {
        text-align: left !important;
        white-space: pre-wrap !important;
        height: auto !important;
        padding: 12px 16px !important;
        line-height: 1.4 !important;
        border: none !important;
        background-color: transparent !important;
        border-radius: 20px !important; /* Pill shape */
        color: #444746 !important;
        font-weight: 500 !important;
        box-shadow: none !important;
    }
    [data-testid="stSidebar"] .stButton>button:hover {
        background-color: #E8EAED !important;
        color: #1F1F1F !important;
    }
    
    /* Input Box Styling */
    .stTextInput>div>div>input {
        border-radius: 8px;
        border: 1px solid #DADCE0;
        padding: 12px 16px;
    }
    .stTextInput>div>div>input:focus {
        border-color: #1A73E8;
        box-shadow: none;
    }
    
    /* Chat Area Styling (Remove borders/backgrounds) */
    .stChatMessage {
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 1rem 0 !important;
    }
    [data-testid="chatAvatarIcon-user"] {
        background-color: #E8EAED;
        color: #1F1F1F;
    }
    [data-testid="chatAvatarIcon-assistant"] {
        background-color: transparent;
        color: #1A73E8;
        font-size: 1.2rem;
    }
    

    /* Data Expander / Status */
    .streamlit-expanderHeader {
        color: #444746 !important;
        font-weight: 500 !important;
        border: none !important;
        background-color: transparent !important;
    }
        border: none !important;
        background-color: transparent !important;
        box-shadow: none !important;
    }
    
    /* Example Question Custom Buttons */
    div.stButton.example-btn > button {
        height: 120px !important;
        width: 100% !important;
        text-align: left !important;
        white-space: pre-wrap !important;
        padding: 1rem !important;
        border-radius: 12px !important;
        border: 1px solid #E0E0E0 !important;
        background-color: #FFFFFF !important;
        color: #1F1F1F !important;
        transition: all 0.2s ease-in-out !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
    }
    div.stButton.example-btn > button:hover {
        border-color: #1A73E8 !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
        transform: translateY(-2px) !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Session State Management ---
if "token" not in st.session_state:
    # Try to recover from query params on refresh
    if "token" in st.query_params:
        st.session_state.token = st.query_params["token"]
    else:
        st.session_state.token = None
        
if "current_conversation_id" not in st.session_state:
    if "chat_id" in st.query_params:
        try:
            st.session_state.current_conversation_id = int(st.query_params["chat_id"])
        except ValueError:
            st.session_state.current_conversation_id = None
    else:
        st.session_state.current_conversation_id = None
        
if "messages" not in st.session_state:
    st.session_state.messages = []

def get_headers():
    if st.session_state.token:
        return {"Authorization": f"Bearer {st.session_state.token}"}
    return {}

@st.dialog("Delete Conversation")
def delete_confirm_dialog(conv_id: int):
    st.warning("이 대화 기록을 정말로 삭제하시겠습니까? (이 작업은 되돌릴 수 없습니다.)")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancel", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("Delete", type="primary", use_container_width=True, icon=":material/delete:"):
            res = requests.delete(f"{API_BASE_URL}/conversations/{conv_id}", headers=get_headers())
            if res.status_code == 200:
                    if st.session_state.current_conversation_id == conv_id:
                        st.session_state.current_conversation_id = None
                        st.session_state.messages = []
                        if "chat_id" in st.query_params:
                            del st.query_params["chat_id"]
                    st.rerun()
            else:
                st.error("Failed to delete.")

# --- Auth UI ---
if not st.session_state.token:
    st.title("JDHE Research Portal")
    st.markdown("Please log in to access your personalized analysis workspace and chat history.")
    
    tab1, tab2 = st.tabs(["Sign In", "Create Account"])
    
    with tab1:
        st.subheader("Login to Workspace")
        with st.form("login_form"):
            login_user = st.text_input("Username", autocomplete="username")
            login_pass = st.text_input("Password", type="password", autocomplete="current-password")
            submit_login = st.form_submit_button("로그인", type="primary")
            
            if submit_login:
                try:
                    res = requests.post(f"{API_BASE_URL}/token", data={"username": login_user, "password": login_pass})
                    res.raise_for_status()
                    st.session_state.token = res.json()["access_token"]
                    st.query_params["token"] = st.session_state.token
                    st.session_state.messages = []
                    st.session_state.current_conversation_id = None
                    if "chat_id" in st.query_params:
                        del st.query_params["chat_id"]
                    st.rerun()
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 401:
                        st.error("아이디 또는 비밀번호가 일치하지 않습니다.")
                    else:
                        st.error("로그인 중 오류가 발생했습니다.")
                except requests.exceptions.RequestException:
                    st.error("서버에 연결할 수 없습니다. 백엔드가 켜져있는지 확인하세요.")

    with tab2:
        st.subheader("Register New Account")
        with st.form("register_form"):
            reg_user = st.text_input("Username", autocomplete="username")
            reg_pass = st.text_input("Password", type="password", autocomplete="new-password")
            reg_pass_confirm = st.text_input("Confirm Password", type="password", autocomplete="new-password")
            submit_reg = st.form_submit_button("Register")
            
            if submit_reg:
                if not reg_user or not reg_pass:
                    st.warning("아이디와 비밀번호를 모두 입력해주세요.")
                elif reg_pass != reg_pass_confirm:
                    st.error("입력하신 두 비밀번호가 서로 일치하지 않습니다. 다시 확인해주세요.")
                else:
                    try:
                        res = requests.post(f"{API_BASE_URL}/register", json={"username": reg_user, "password": reg_pass})
                        res.raise_for_status()
                        st.success("🎉 회원가입이 완료되었습니다! 왼쪽 탭을 눌러 로그인해주세요.")
                    except requests.exceptions.HTTPError as e:
                        if e.response.status_code == 400:
                            st.error("이미 존재하는 아이디입니다. 다른 아이디를 사용해주세요.")
                        else:
                            st.error(f"회원가입 실패: {e.response.text}")
                    except requests.exceptions.RequestException:
                        st.error("서버에 연결할 수 없습니다.")
                    
    st.stop()  # Halt rendering rest of the app until logged in

# --- Sidebar: Conversation History ---
with st.sidebar:
    top_c1, top_c2 = st.columns([1, 4], vertical_alignment="center")
    with top_c1:
        if st.button("", icon=":material/home:", help="홈 (초기 화면)"):
            st.session_state.current_conversation_id = None
            st.session_state.messages = []
            if "chat_id" in st.query_params:
                del st.query_params["chat_id"]
            st.rerun()
    with top_c2:
        if st.button("새 채팅", icon=":material/add:", type="secondary", use_container_width=True):
            try:
                res = requests.post(f"{API_BASE_URL}/conversations", json={"title": "New Conversation"}, headers=get_headers())
                res.raise_for_status()
                new_conv = res.json()
                st.session_state.current_conversation_id = new_conv["id"]
                st.query_params["chat_id"] = str(new_conv["id"])
                st.session_state.messages = []
                st.rerun()
            except requests.exceptions.RequestException as e:
                st.error("새 대화를 생성하지 못했습니다.")
            
    st.divider()

    st.markdown("<h3 style='margin-bottom: 0px;'>분석 모드</h3>", unsafe_allow_html=True)
    search_mode_display = st.radio(
        "검색 모드",
        ["📊 통계 분석 (메타데이터 기반)", "🧠 심층 분석 (논문 내용 기반)"],
        index=0,
        label_visibility="collapsed"
    )
    st.session_state.search_mode_val = "meta_analysis" if "통계" in search_mode_display else "deep_insight"
    st.divider()
    
    # Load conversations list
    st.markdown("<p style='font-size: 12px; color: #5F6368; font-weight: 600; margin-top: 10px; margin-bottom: 5px;'>채팅</p>", unsafe_allow_html=True)
    try:
        convs_res = requests.get(f"{API_BASE_URL}/conversations", headers=get_headers())
        convs_res.raise_for_status()
        conversations = convs_res.json()
        
        for conv in conversations:
            col1, col2 = st.columns([5, 1], vertical_alignment="center")
            is_active = (conv["id"] == st.session_state.current_conversation_id)
            
            dt_str = ""
            if "created_at" in conv and conv["created_at"]:
                try:
                    # SQLite CURRENT_TIMESTAMP is in UTC. Let's convert it to KST.
                    # e.g. '2026-03-13 11:32:24'
                    from datetime import datetime
                    import pytz
                    
                    utc_dt = datetime.strptime(conv["created_at"], "%Y-%m-%d %H:%M:%S")
                    utc_dt = utc_dt.replace(tzinfo=pytz.UTC)
                    
                    # Convert to Local Time (KST for South Korea)
                    kst_tz = pytz.timezone('Asia/Seoul')
                    kst_dt = utc_dt.astimezone(kst_tz)
                    
                    dt_str = kst_dt.strftime("%m/%d %H:%M")
                except Exception:
                    pass
            
            title_text = conv['title']
            icon_name = ":material/chat_bubble_outline:"
            if is_active:
                title_text = f"**{conv['title']}**"
                icon_name = ":material/chat:"
                
            btn_label = f"{title_text}\n🕒 {dt_str}"
                
            with col1:
                if st.button(btn_label, key=f"conv_{conv['id']}", use_container_width=True, icon=icon_name):
                    st.session_state.current_conversation_id = conv["id"]
                    st.query_params["chat_id"] = str(conv["id"])
                    # Fetch history
                    hist_res = requests.get(f"{API_BASE_URL}/conversations/{conv['id']}/messages", headers=get_headers())
                    if hist_res.status_code == 200:
                        st.session_state.messages = []
                        for msg in hist_res.json():
                            sql_data = json.loads(msg["sql_data"]) if msg["sql_data"] else None
                            thought_process = json.loads(msg["thought_process"]) if msg.get("thought_process") else []
                            st.session_state.messages.append({
                                "role": msg["role"],
                                "content": msg["content"],
                                "intent": msg["intent_type"],
                                "sql_data": sql_data,
                                "thought_process": thought_process
                            })
                    st.rerun()
            with col2:
                if st.button("", key=f"del_{conv['id']}", help="Delete Conversation", icon=":material/delete:"):
                    delete_confirm_dialog(conv['id'])
    except Exception as e:
        st.error("Failed to load conversation list.")

    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("설정 및 도움말", icon=":material/settings:"):
        st.toast("설정 메뉴는 준비 중입니다.", icon="⚙️")
        
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("로그아웃", icon=":material/logout:"):
        st.session_state.token = None
        if "token" in st.query_params:
            del st.query_params["token"]
        st.session_state.current_conversation_id = None
        if "chat_id" in st.query_params:
            del st.query_params["chat_id"]
        st.session_state.messages = []
        st.rerun()

# --- Main Chat App ---
st.markdown("<h2 style='color: #1F1F1F; font-weight: 500; font-size: 22px; margin-top: -20px;'>JDHE <span style='font-size: 16px; color: #5F6368; font-weight: 400;'>Journal Research AI</span></h2>", unsafe_allow_html=True)



prompt = st.chat_input("Journal Research AI에게 물어보기...")

# 1. Create a new conversation if sending a message from the initial state
if prompt and st.session_state.current_conversation_id is None:
    try:
        res = requests.post(f"{API_BASE_URL}/conversations", json={"title": "New Conversation"}, headers=get_headers())
        res.raise_for_status()
        new_conv = res.json()
        st.session_state.current_conversation_id = new_conv["id"]
        st.query_params["chat_id"] = str(new_conv["id"])
        st.session_state.messages = []
    except Exception as e:
        st.error("새 대화를 생성하지 못했습니다.")

# 2. Render Empty State if no conversation is active
# Wrap in a placeholder to explicitly clear it from the frontend immediately upon creating a new conversation
empty_state_container = st.empty()

if st.session_state.current_conversation_id is None:
    with empty_state_container.container():
        st.markdown("<br><br><br><h1 style='text-align: center; color: #1F1F1F; font-size: 40px; font-weight: 400; background: -webkit-linear-gradient(45deg, #4285F4, #D96570); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>안녕하세요.</h1>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center; color: #444746; font-size: 32px; font-weight: 400;'>어떤 논문 데이터가 필요하신가요?</h2>", unsafe_allow_html=True)
        
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #5F6368; font-size: 16px;'>아래 질문 카드 중 하나를 클릭하면 대화창에 자동으로 예시가 입력됩니다:</p>", unsafe_allow_html=True)
        
        # We use columns and custom buttons to act as cards
        col1, col2, col3 = st.columns(3)
    
    def prefill_example(query: str):
        st.session_state.trigger_query = query
        st.rerun()
            
    with col1:
        st.markdown("<div class='example-btn'>", unsafe_allow_html=True)
        if st.session_state.search_mode_val == "meta_analysis":
            if st.button("📊 정량적 통계 질문\n\n\"Vol 13 Issue 4에서 출판된 논문의 총 개수는 몇 개인가요?\"", key="ex1_m", use_container_width=True):
                prefill_example("Vol 13 Issue 4에서 출판된 논문의 총 개수는 몇 개인가요?")
        else:
            if st.button("🧠 정성적 의미 검색\n\n\"다문화 교육이나 다양성(Diversity)을 다룬 논문들의 핵심 결론들을 요약해줘.\"", key="ex1_d", use_container_width=True):
                prefill_example("다문화 교육이나 다양성(Diversity)을 다룬 논문들의 핵심 결론들을 요약해줘.")
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col2:
        st.markdown("<div class='example-btn'>", unsafe_allow_html=True)
        if st.session_state.search_mode_val == "meta_analysis":
            if st.button("👥 특정 논문 추출\n\n\"소수인종에 관한 논문을 찾아줘.\"", key="ex2_m", use_container_width=True):
                prefill_example("소수인종에 관한 논문을 찾아줘.")
        else:
            if st.button("🧐 심층 분석 질문\n\n\"교수진의 태도가 유학생들의 학업 성취도에 미치는 영향은 무엇인가요?\"", key="ex2_d", use_container_width=True):
                prefill_example("교수진의 태도가 유학생들의 학업 성취도에 미치는 영향은 무엇인가요?")
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col3:
        st.markdown("<div class='example-btn'>", unsafe_allow_html=True)
        if st.session_state.search_mode_val == "meta_analysis":
            if st.button("📋 전체 목록 조회\n\n\"JDHE 저널에 등록된 모든 양적 연구 논문 리스트를 보여줘.\"", key="ex3_m", use_container_width=True):
                prefill_example("JDHE 저널에 등록된 모든 양적 연구 논문 리스트를 보여줘.")
        else:
            if st.button("🎯 복합 분석 (통계+의미)\n\n\"2018년부터 2020년 사이에 '질적 연구'를 진행한 논문들의 주요 연구 대상은 누구인가요?\"", key="ex3_d", use_container_width=True):
                prefill_example("2018년부터 2020년 사이에 '질적 연구'를 진행한 논문들의 주요 연구 대상은 누구인가요?")
        st.markdown("</div>", unsafe_allow_html=True)
        
    # Inject JS to fill the chat_input if a card was clicked
    if "trigger_query" in st.session_state and st.session_state.trigger_query:
        query_text = st.session_state.trigger_query.replace('"', '\\"').replace('\n', '\\n')
        js_code = f"""
        <script>
        const setChatInput = () => {{
            const chatInput = window.parent.document.querySelector('[data-testid="stChatInput"] textarea');
            if (chatInput) {{
                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
                nativeInputValueSetter.call(chatInput, "{query_text}");
                
                const event = new Event('input', {{ bubbles: true }});
                chatInput.dispatchEvent(event);
                
                for (let key in chatInput) {{
                    if (key.startsWith("__reactProps$")) {{
                        if (chatInput[key].onChange) {{
                            chatInput[key].onChange({{ target: chatInput }});
                        }}
                        break;
                    }}
                }}
                
                chatInput.focus();
                chatInput.setSelectionRange(chatInput.value.length, chatInput.value.length);
            }}
        }};
        setTimeout(setChatInput, 100);
        setTimeout(setChatInput, 500);
        </script>
        """
        components.html(js_code, height=0, width=0)
        del st.session_state.trigger_query
        
    st.stop()
else:
    empty_state_container.empty()


for msg in st.session_state.messages:
    avatar = "👤" if msg["role"] == "user" else "✨"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])
        
        if msg.get("thought_process"):
            with st.expander("생각하는 과정 표시", expanded=False):
                # Clean up emojis for professional UI
                for idx, thought in enumerate(msg["thought_process"]):
                    cleaned_thought = thought.replace("🤖", "").replace("🔍", "").replace("📊", "").replace("✅", "").replace("🎯", "").replace("🧠", "").replace("💡", "").strip()
                    st.write(f"- {cleaned_thought}")
                    
        if msg.get("sql_data"):
            with st.expander("Data Table"):
                df = pd.DataFrame(msg["sql_data"])
                st.dataframe(df)
                numeric_cols = df.select_dtypes(include=['number']).columns
                if len(numeric_cols) > 0 and len(df.columns) >= 2:
                    try:
                        idx_col = [c for c in df.columns if c not in numeric_cols][0]
                        chart_df = df.set_index(idx_col)
                        st.bar_chart(chart_df[numeric_cols])
                    except Exception:
                        pass
        if msg.get("intent"):
            pass

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="✨"):
        final_answer = ""
        sql_result = None
        intent_type = "Unknown"
        
        try:
            with st.status("생각하는 과정 표시...", expanded=True) as status:
                payload = {
                    "query": prompt,
                    "conversation_id": st.session_state.current_conversation_id,
                    "search_mode": st.session_state.search_mode_val
                }
                response = requests.post(
                    f"{API_BASE_URL}/query", 
                    json=payload, 
                    headers=get_headers(),
                    stream=True
                )
                
                if response.status_code == 401:
                    st.error("Session expired. Please log in again.")
                    st.session_state.token = None
                    st.stop()
                    
                response.raise_for_status()
                
                thought_process_list = []
                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        if chunk["type"] == "status":
                            # Hide emojified status messages coming from backend by stripping them or just printing
                            # Let's clean the backend message slightly by removing common emojis
                            raw_msg = chunk["message"]
                            msg_cleaned = raw_msg.replace("🤖", "").replace("🔍", "").replace("📊", "").replace("✅", "").replace("🎯", "").replace("🧠", "").replace("💡", "").strip()
                            st.write(msg_cleaned)
                            thought_process_list.append(raw_msg)
                        elif chunk["type"] == "result":
                            data = chunk["data"]
                            final_answer = data.get("final_answer", "")
                            intent_data = data.get("intent", {})
                            intent_type = intent_data.get("intent_type", "Unknown")
                            sql_result = data.get("sql_result", None)
                
                status.update(label="생각하는 과정 완료", state="complete", expanded=False)
            
            st.markdown(final_answer)
            
            if sql_result and isinstance(sql_result, list) and len(sql_result) > 0:
                with st.expander("데이터 표 및 통계 확인"):
                    df = pd.DataFrame(sql_result)
                    st.dataframe(df)
                    numeric_cols = df.select_dtypes(include=['number']).columns
                    if len(numeric_cols) > 0 and len(df.columns) >= 2:
                        try:
                            idx_col = [c for c in df.columns if c not in numeric_cols][0]
                            chart_df = df.set_index(idx_col)
                            st.bar_chart(chart_df[numeric_cols])
                        except Exception:
                            pass


            st.session_state.messages.append({
                "role": "assistant", 
                "content": final_answer,
                "sql_data": sql_result,
                "intent": intent_type,
                "thought_process": thought_process_list
            })
            st.rerun()  # Trigger refresh to update sidebar title
            
        except Exception as e:
            st.error(f"Failed to query API: {e}")
