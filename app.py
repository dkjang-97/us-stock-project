import streamlit as st
import time
import os
from datetime import datetime
from dotenv import load_dotenv

# Import custom processing modules
from data_match import get_cik_by_ticker
from data_load import get_financial_data_3years
from explainer_trend import get_trend_analysis
from tasks import (
    generate_company_profile_korean,
    generate_financial_summary_ai,
    verify_and_retry_block_cached
)
from ai_verify import check_local_bias, local_fix
from visualizer import render_dashboard

# Load environment variables
load_dotenv()

st.set_page_config(
    page_title="AI 기업 재무 및 동향 분석 시스템",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject Binance Dark Design System global CSS
st.markdown("""
<style>
    /* Global Background and Fonts */
    .stApp {
        background-color: #0b0e11 !important;
        color: #eaecef !important;
    }
    
    /* Text Color Resets */
    h1, h2, h3, h4, h5, h6, p, span, label, li, div, small, select, button {
        color: #eaecef !important;
        font-family: "BinanceNova", "BinancePlex", -apple-system, BlinkMacSystemFont, sans-serif !important;
    }
    
    /* Subtitles and headers coloring (Gold accent for main elements) */
    h1, h2 {
        color: #fcd535 !important;
    }
    
    /* Input Fields (Binance Surface Dark) */
    div[data-baseweb="input"] {
        background-color: #1e2329 !important;
        border: 1px solid #2b3139 !important;
        border-radius: 8px !important;
    }
    input {
        color: #eaecef !important;
        background-color: #1e2329 !important;
    }
    
    /* Sidebar Overrides */
    section[data-testid="stSidebar"] {
        background-color: #0b0e11 !important;
        border-right: 1px solid #2b3139 !important;
    }
    section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {
        color: #fcd535 !important;
    }
    
    /* Button Custom styling (Pill / Primary Yellow CTA) */
    button[kind="secondary"] {
        background-color: #fcd535 !important;
        color: #181a20 !important;
        border: none !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        padding: 8px 16px !important;
        transition: background 0.2s ease-in-out !important;
    }
    button[kind="secondary"]:hover {
        background-color: #f0b90b !important;
        color: #181a20 !important;
    }
    button[kind="secondary"]:active {
        background-color: #d8a308 !important;
    }
    
    /* Links and Tabs Styling */
    div[data-baseweb="tab-list"] {
        background-color: #0b0e11 !important;
        border-bottom: 1px solid #2b3139 !important;
    }
    button[data-baseweb="tab"] {
        background-color: #0b0e11 !important;
        color: #707a8a !important;
        font-weight: 500 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #fcd535 !important;
        border-bottom: 2px solid #fcd535 !important;
    }
    
    /* Metrics panel decoration */
    div[data-testid="stMetricValue"] {
        color: #fcd535 !important;
        font-weight: 700 !important;
    }
    
    /* Block container margins */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("📈 AI 기반 기업 재무 및 동향 분석 시스템")

# API key validation helper
api_key = None
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

if not api_key:
    api_key = os.getenv("GEMINI_API_KEY")

# Sidebar for Admin Log Viewer & Configuration
with st.sidebar:
    st.header("🛠️ 관리자 설정 및 로그")
    
    if api_key and api_key != "YOUR_GEMINI_API_KEY_HERE":
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
        
        try:
            # Create a placeholder container for dynamic loading animations
            loading_placeholder = st.empty()
            
            with loading_placeholder.status(f"🔍 {ticker_clean} 데이터 분석 파이프라인 가동 중...", expanded=True) as status_box:
                
                # 1. Matching Stage
                status_box.update(label="🔍 1단계: SEC CIK 정보 매칭 및 한글 프로필 생성 중...", state="running")
                st.write("티커 데이터베이스에서 CIK 식별코드를 검색하고 있습니다...")
                cik = get_cik_by_ticker(ticker_clean)
                
                st.write("Gemini AI를 통해 기업의 한글 소개 프로필 정보를 작성하고 있습니다...")
                company_profile = generate_company_profile_korean(ticker_clean)
                
                # 2. Loading SEC Financials Stage
                status_box.update(label="📊 2단계: SEC XBRL 분기 재무 데이터 수집 중...", state="running")
                st.write("최근 3개년(12분기) 분기 공시 정보를 파싱하여 재무제표 데이터를 가공하는 중입니다...")
                financials = get_financial_data_3years(ticker_clean, cik)
                
                # 3. Trend News Translations (1.2s cooldown applied sequentially)
                status_box.update(label="📰 3단계: 최근 동향 뉴스 수집 및 개별 순차 번역 중...", state="running")
                st.write("Yahoo Finance RSS 실시간 기사를 긁어와 1.2초 대기 간격으로 개별 번역을 진행 중입니다...")
                years = sorted(list(set([datetime.strptime(d, "%Y-%m-%d").year for d in financials["dates"]])))
                trends = get_trend_analysis(ticker_clean, years)
                
                # 4. Verification and Bias correction (Double Pass)
                status_box.update(label="🛡️ 4단계: 실시간 데이터 이중 검증 및 AI 보정 수행 중...", state="running")
                st.write("연도별 실적 요약문을 마크다운 표(Table)로 가공하고 편향 수치 자동 대조를 진행합니다...")
                raw_summary = generate_financial_summary_ai(financials)
                
                # Demonstration trigger: inject biased keywords to showcase verification retry & edit
                if ticker_clean == "TESTBIAS":
                    raw_summary += " 이 주식은 반드시 매수해야 하는 대박 추천 종목입니다. 무조건 폭등합니다."
                    
                financial_summary_block = {
                    "years": years[:3],
                    "revenue": financials["revenue"][:3],
                    "net_income": financials["net_income"][:3],
                    "summary": raw_summary
                }
                
                verified_fin_block, _ = verify_and_retry_block_cached(financial_summary_block, "financial_summary")
                
                # Verify trends using super-fast local rules (No Gemini API call to save time)
                verified_trends_list = []
                for idx, trend in enumerate(trends):
                    if ticker_clean == "TESTBIAS" and idx == 0:
                        trend["summary"] += " This stock is a must buy, to the moon!"
                    
                    st.write(f"기사 실시간 검증 진행률 ({idx+1}/{len(trends)}): {trend['title'][:30]}...")
                    is_valid, reason = check_local_bias(trend.get("summary", ""))
                    if not is_valid:
                        trend = local_fix(trend)
                    verified_trends_list.append(trend)
                
                # 4.1 Apply strict capping (Max 3 Good, 3 Bad per year)
                st.write("각 연도별로 가장 중대한 호재 3개, 악재 3개 뉴스를 압축 선별하고 있습니다...")
                capped_trends_list = []
                for year in [2023, 2024, 2025]:
                    year_goods = [t for t in verified_trends_list if t.get("year") == year and t.get("sentiment") == "Good"][:3]
                    year_bads = [t for t in verified_trends_list if t.get("year") == year and t.get("sentiment") == "Bad"][:3]
                    capped_trends_list.extend(year_goods)
                    capped_trends_list.extend(year_bads)
                other_years = [t for t in verified_trends_list if t.get("year") not in [2023, 2024, 2025]]
                capped_trends_list.extend(other_years)
                capped_trends_list.sort(key=lambda x: x.get("date", "2000-01-01"), reverse=True)
                
                # Chart events selection
                chart_events = []
                seen_dates = set()
                all_trends_sorted = sorted(capped_trends_list, key=lambda x: 0 if x.get("sentiment") in ["Good", "Bad"] else 1)
                for t in all_trends_sorted:
                    ev_date = t.get("date")
                    if ev_date and ev_date not in seen_dates:
                        if len(chart_events) >= 3:
                            break
                        seen_dates.add(ev_date)
                        chart_events.append({
                            "date": ev_date,
                            "title": t.get("title"),
                            "summary": t.get("summary"),
                            "sentiment": t.get("sentiment")
                        })
                
                # Complete data payload
                final_data = {
                    "company_profile": company_profile,
                    "financials": financials,
                    "financial_summary": verified_fin_block,
                    "trends": capped_trends_list,
                    "chart_events": chart_events
                }
                
                status_box.update(label="✅ 분석 파이프라인 완료!", state="complete")
                
            # Clear status loading box and render the dashboard layout
            loading_placeholder.empty()
            render_dashboard(final_data)
            
        except Exception as e:
            st.error(f"분석 수행 도중 오류가 발생했습니다: {str(e)}")
            st.info("상세 스택트레이스는 로컬 터미널이나 app.log를 점검하세요.")
