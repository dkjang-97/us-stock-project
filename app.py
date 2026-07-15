import streamlit as st
import requests
import time
import os
from dotenv import load_dotenv
from visualizer import render_dashboard

# Load environment variables
load_dotenv()

st.set_page_config(
    page_title="AI 기업 재무 및 동향 분석 시스템",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📈 AI 기반 기업 재무 및 동향 분석 시스템")

# Backend API configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Sidebar for Admin Log Viewer & Configuration
with st.sidebar:
    st.header("🛠️ 관리자 설정 및 로그")
    
    # API key check indicator
    api_key_check = os.getenv("GEMINI_API_KEY", "")
    if api_key_check and api_key_check != "YOUR_GEMINI_API_KEY_HERE":
        st.success("✅ Gemini API Key 로드 완료")
    else:
        st.warning("⚠️ Gemini API Key 미설정 (로컬 시뮬레이션)")
        
    st.write("---")
    
    # Real-time Log Viewer (displays last 50 lines of app.log)
    st.subheader("📋 시스템 실시간 로그 (최신 50줄)")
    if st.button("🔄 로그 새로고침") or "log_refresh" not in st.session_state:
        st.session_state["log_refresh"] = True
        
    log_file_path = "app.log"
    if os.path.exists(log_file_path):
        try:
            with open(log_file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                last_50_lines = lines[-50:]
                log_text = "".join(last_50_lines)
                st.code(log_text, language="log")
        except Exception as e:
            st.error(f"로그 파일을 읽는 도중 오류가 발생했습니다: {str(e)}")
    else:
        st.caption("로그 파일이 아직 생성되지 않았습니다 (app.log)")

# Main UI layout
ticker = st.text_input("기업 티커(Ticker) 입력 (예: AAPL, TSLA, TESTBIAS)", placeholder="AAPL")

if st.button("📊 분석 시작"):
    if not ticker.strip():
        st.error("티커를 입력해 주세요.")
    else:
        ticker_clean = ticker.strip().upper()
        # 1. Trigger API Request
        try:
            res = requests.post(f"{BACKEND_URL}/api/analyze?ticker={ticker_clean}", timeout=10)
            if res.status_code == 200:
                task_id = res.json()["task_id"]
                
                # Create a placeholder container for dynamic loading animations
                loading_placeholder = st.empty()
                
                status_str = "PENDING"
                task_data = {}
                
                # Put the status loader inside the empty placeholder
                with loading_placeholder.status("데이터 분석 작업을 준비하는 중...", expanded=True) as status_box:
                    while True:
                        try:
                            status_res = requests.get(f"{BACKEND_URL}/api/tasks/{task_id}", timeout=5)
                            if status_res.status_code == 200:
                                task_data = status_res.json()
                                stage = task_data.get("stage")
                                status_str = task_data.get("status")
                                
                                if status_str == "PENDING":
                                    status_box.update(label="⏳ 대기 중...", state="running")
                                elif status_str == "MATCHING":
                                    status_box.update(label="🔍 SEC CIK 정보를 매칭하는 중입니다...", state="running")
                                    st.write("SEC CIK 룩업을 수행하고 있습니다...")
                                elif status_str == "LOADING_SEC":
                                    status_box.update(label="📊 SEC 재무 데이터를 수집 및 가공 중입니다...", state="running")
                                    st.write("분기별 XBRL 재무 팩트 데이터를 불러오고 있습니다...")
                                elif status_str == "TREND_ANALYSIS":
                                    status_box.update(label="📰 최근 동향 정보 및 기사를 수집하는 중입니다...", state="running")
                                    st.write("Yahoo Finance RSS 영어 기사 번역 및 동향 리포트를 조합 중..." )
                                elif status_str == "VERIFYING":
                                    status_box.update(label="🛡️ 실시간 수치 검증 및 AI 어조 필터링을 수행하는 중입니다...", state="running")
                                    st.write("재무 데이터 대조 및 AI 환각/투자 유도 표현 필터링 실행 중...")
                                    
                                if status_str in ["COMPLETED", "FAILED"]:
                                    break
                            else:
                                status_box.update(label="⚠️ 백엔드 상태를 조회할 수 없습니다.", state="error")
                                break
                        except Exception as e:
                            st.warning(f"폴링 중 연결 시도 실패: {str(e)}")
                            
                        time.sleep(1.5)  # Poll every 1.5 seconds
                        
                    # Polling finished, update status label
                    if status_str == "COMPLETED":
                        status_box.update(label="✅ 분석 완료!", state="complete")
                        
                # If completed successfully, completely clear the loading status box
                if status_str == "COMPLETED":
                    loading_placeholder.empty()
                    # Render the final dashboard
                    render_dashboard(task_data.get("data"))
                else:
                    st.error(f"분석 도중 에러가 발생했습니다: {task_data.get('error_message')}")
                    st.info("사이드바의 상세 로그 창을 열어 시스템의 구체적인 Traceback을 확인할 수 있습니다.")
                        
            else:
                st.error(f"분석 요청 실패: {res.text}")
        except Exception as e:
            st.error(f"백엔드 연결에 실패했습니다. FastAPI 서버가 8000 포트에서 실행 중인지 확인하세요: {str(e)}")
