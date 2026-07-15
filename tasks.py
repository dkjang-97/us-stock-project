import os
import re
import streamlit as st
from logger import logger
from ai_verify import verify_and_retry_block, get_gemini_model

@st.cache_data(ttl=3600, show_spinner=False)
def generate_company_profile_korean(ticker: str) -> str:
    """
    Generates a concise 1-sentence Korean profile of the company.
    Cached for 1 hour to prevent redundant Gemini API calls.
    """
    ticker_upper = ticker.strip().upper()
    mock_profiles = {
        "AAPL": "애플 (AAPL) | IT 소비자 가전 | 글로벌 스마트폰(아이폰), 가상현실 헤드셋(비전 프로) 및 자체 모바일 소프트웨어 생태계를 선도하는 글로벌 테크 기업",
        "TSLA": "테슬라 (TSLA) | 친환경 완성차 및 미래 에너지 | 전기 자동차(EV) 대량 양산 및 완전자율주행 FSD 시스템, 메가팩 저장 장치를 제조하는 글로벌 혁신 에너지 기업"
    }
    
    model = get_gemini_model()
    if not model:
        return mock_profiles.get(ticker_upper, f"{ticker_upper} | 글로벌 성장 기업 | 최근 시장 지배력을 공고히 다지고 있는 미국 증시의 대표적인 기업입니다.")
        
    try:
        prompt = (
            f"주식 티커 {ticker_upper} 에 대해 한글로 한 문장 형태의 기업 요약 프로필을 생성해 주세요. "
            f"형식: '[기업한글이름] ([티커]) | [주요섹터/산업분야] | [기업에 대한 구체적인 비즈니스 설명(1문장)]'\n"
            f"예시: 애플 (AAPL) | IT 소비자 가전 | 글로벌 아이폰 제조 및 자체 모바일 소프트웨어 생태계를 선도하는 IT 업계 1위 기업.\n\n"
            f"생성 결과:"
        )
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.warning(f"Failed to generate company profile via Gemini. error={str(e)}")
        return mock_profiles.get(ticker_upper, f"{ticker_upper} | 글로벌 성장 상장 기업 | 시장 점유율을 확장하고 있는 대표 상장 테크 기업입니다.")

@st.cache_data(ttl=3600, show_spinner=False)
def generate_financial_summary_ai(financials: dict) -> str:
    """
    Generates an annual financial summary table in Markdown format.
    Cached to prevent duplicate prompts.
    """
    dates = financials.get("dates", [])
    revenue = financials.get("revenue", [])
    net_income = financials.get("net_income", [])
    ticker = financials.get("ticker", "")
    
    # 1. Group by year
    yearly_data = {}
    for d, rev, ni in zip(dates, revenue, net_income):
        year = d[:4]
        if year not in yearly_data:
            yearly_data[year] = {"revenue": 0.0, "net_income": 0.0, "has_rev": False, "has_ni": False}
        if rev is not None:
            yearly_data[year]["revenue"] += rev
            yearly_data[year]["has_rev"] = True
        if ni is not None:
            yearly_data[year]["net_income"] += ni
            yearly_data[year]["has_ni"] = True
            
    # Build local markdown table
    table_header = "| 회계 연도 | 누적 매출액 (Revenue) | 누적 순이익 (Net Income) | 순이익률 (Margin) |\n| :---: | :---: | :---: | :---: |\n"
    table_rows = []
    for y in sorted(yearly_data.keys()):
        y_info = yearly_data[y]
        rev_val = y_info["revenue"]
        ni_val = y_info["net_income"]
        
        rev_str = f"${rev_val/1e9:,.2f} B" if y_info["has_rev"] else "N/A"
        ni_str = f"${ni_val/1e9:,.2f} B" if y_info["has_ni"] else "N/A"
        
        if y_info["has_rev"] and y_info["has_ni"] and rev_val > 0:
            margin = f"{(ni_val / rev_val) * 100:.2f}%"
        else:
            margin = "N/A"
        table_rows.append(f"| {y}년 | {rev_str} | {ni_str} | {margin} |")
        
    local_table = table_header + "\n".join(table_rows)
    
    model = get_gemini_model()
    if not model:
        return f"### 📊 {ticker} 연도별 재무 실적 추이 요약\n\n" + local_table
        
    try:
        prompt = (
            f"다음 {ticker}의 재무 실적 마크다운 표 데이터에 '성장성 및 경영 분석' 열을 추가하여 "
            f"각 연도별 실적 성격과 평가를 한국어 한 문장씩 포함한 새로운 완성형 마크다운 표를 작성해 주세요. "
            f"절대 투자 추천 단어(강력 매수, 폭등 등)나 편향적 단어를 쓰지 마십시오. 오직 완성된 마크다운 표만 출력하세요.\n\n"
            f"원본 표:\n{local_table}\n\n"
            f"완성된 마크다운 표:"
        )
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini를 통한 마크다운 표 요약 생성 실패. error={str(e)}")
        return f"### 📊 {ticker} 연도별 재무 실적 추이 요약\n\n" + local_table

@st.cache_data(ttl=3600, show_spinner=False)
def verify_and_retry_block_cached(block: dict, block_type: str):
    """
    Statically cached wrapper for the double pass bias verification engine.
    """
    return verify_and_retry_block(block, block_type)
