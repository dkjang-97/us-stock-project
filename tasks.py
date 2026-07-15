import uuid
import threading
from datetime import datetime
from logger import logger
from data_match import get_cik_by_ticker
from data_load import get_financial_data_3years
from explainer_trend import get_trend_analysis
from ai_verify import verify_and_retry_block, get_gemini_model

# In-memory database to store task statuses and results
TASKS_DB = {}

# Mutex lock for thread safety in task database updates
_db_lock = threading.Lock()

def create_task(ticker: str) -> str:
    """
    Creates a new analysis task in PENDING state and returns its unique ID.
    """
    task_id = str(uuid.uuid4())
    with _db_lock:
        TASKS_DB[task_id] = {
            "task_id": task_id,
            "ticker": ticker.upper(),
            "status": "PENDING",
            "stage": "PENDING",
            "data": None,
            "error_message": None
        }
    logger.info(f"Task created: {task_id} for Ticker {ticker}")
    return task_id

def get_task_status(task_id: str) -> dict:
    """
    Retrieves the status of a specific task.
    """
    with _db_lock:
        return TASKS_DB.get(task_id)

def update_task_state(task_id: str, status: str, stage: str, data: dict = None, error_message: str = None):
    """
    Updates status, stage, data, and error message of a task.
    """
    with _db_lock:
        if task_id in TASKS_DB:
            if status:
                TASKS_DB[task_id]["status"] = status
            if stage:
                TASKS_DB[task_id]["stage"] = stage
            if data is not None:
                TASKS_DB[task_id]["data"] = data
            if error_message is not None:
                TASKS_DB[task_id]["error_message"] = error_message
    logger.debug(f"Task {task_id} state updated: status={status}, stage={stage}")

def generate_company_profile_korean(ticker: str) -> str:
    """
    Generates a concise 1-sentence Korean profile of the company.
    Format: 'Company Name (Ticker) | Industry Sector | Business summary'
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

def generate_financial_summary_ai(financials: dict) -> str:
    """
    Generates an annual financial summary table in Markdown format.
    Aggregates quarterly/annual values by year and renders it as a structured table.
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
        # Ask Gemini to enrich this table with a growth analysis column
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

def run_analysis_pipeline(task_id: str, ticker: str):
    """
    The background task runner that executes the entire analytical pipeline.
    """
    logger.set_task_id(task_id)
    logger.info(f"Starting background task pipeline for ticker '{ticker}'")
    
    try:
        # 1. Matching Stage
        update_task_state(task_id, status="MATCHING", stage="MATCHING")
        cik = get_cik_by_ticker(ticker)
        
        # Generate company profile in Korean
        company_profile = generate_company_profile_korean(ticker)
        
        # 2. Loading SEC Stage
        update_task_state(task_id, status="LOADING_SEC", stage="LOADING_SEC")
        financials = get_financial_data_3years(ticker, cik)
        
        # 3. Trend Analysis Stage
        update_task_state(task_id, status="TREND_ANALYSIS", stage="TREND_ANALYSIS")
        # Extract years from dates for mock database compatibility
        years = sorted(list(set([datetime.strptime(d, "%Y-%m-%d").year for d in financials["dates"]])))
        trends = get_trend_analysis(ticker, years)
        
        # 4. Verifying Stage
        update_task_state(task_id, status="VERIFYING", stage="VERIFYING")
        
        # 4.1 Generate and verify financial summary
        raw_summary = generate_financial_summary_ai(financials)
        
        # Demonstration trigger: inject biased keywords to showcase verification retry & edit
        if ticker.upper() == "TESTBIAS":
            raw_summary += " 이 주식은 반드시 매수해야 하는 대박 추천 종목입니다. 무조건 폭등합니다."
            
        financial_summary_block = {
            "years": years[:3], # Needs 3 elements to pass rule verification
            "revenue": financials["revenue"][:3],
            "net_income": financials["net_income"][:3],
            "summary": raw_summary
        }
        
        logger.info("Verifying financial summary block...")
        verified_fin_block, status_fin = verify_and_retry_block(financial_summary_block, "financial_summary")
        
        # 4.2 Verify trend news items
        verified_trends_list = []
        for idx, trend in enumerate(trends):
            if ticker.upper() == "TESTBIAS" and idx == 0:
                trend["summary"] += " This stock is a must buy, to the moon!"
                
            logger.info(f"Verifying trend item {idx+1}/{len(trends)}: {trend['title']}")
            verified_item, status_item = verify_and_retry_block(trend, "trend_item")
            
            if verified_item is not None:
                verified_trends_list.append(verified_item)
            else:
                logger.warning(f"Trend item '{trend['title']}' was excluded due to verification failures.")
                
        # Apply strict capping: Max 3 Good and 3 Bad events per calendar year (2023, 2024, 2025)
        capped_trends_list = []
        for year in [2023, 2024, 2025]:
            year_goods = [t for t in verified_trends_list if t.get("year") == year and t.get("sentiment") == "Good"][:3]
            year_bads = [t for t in verified_trends_list if t.get("year") == year and t.get("sentiment") == "Bad"][:3]
            capped_trends_list.extend(year_goods)
            capped_trends_list.extend(year_bads)
        # Add other years if any
        other_years = [t for t in verified_trends_list if t.get("year") not in [2023, 2024, 2025]]
        capped_trends_list.extend(other_years)
        # Sort again by date descending
        capped_trends_list.sort(key=lambda x: x.get("date", "2000-01-01"), reverse=True)
                
        # 4.3 Filter 2-3 major events to display on the Plotly chart
        # We select events with 'Good' or 'Bad' sentiment and different dates
        chart_events = []
        seen_dates = set()
        
        # Sort news so that major events (Good/Bad) are parsed first
        all_trends_sorted = sorted(
            capped_trends_list,
            key=lambda x: 0 if x.get("sentiment") in ["Good", "Bad"] else 1
        )
        
        for t in all_trends_sorted:
            ev_date = t.get("date")
            if ev_date and ev_date not in seen_dates:
                if len(chart_events) >= 3: # Limit to max 3 dots to prevent overlap cluttering
                    break
                seen_dates.add(ev_date)
                chart_events.append({
                    "date": ev_date,
                    "title": t.get("title"),
                    "summary": t.get("summary"),
                    "sentiment": t.get("sentiment")
                })
                
        # 5. Completed
        final_data = {
            "company_profile": company_profile,
            "financials": financials,
            "financial_summary": verified_fin_block,
            "trends": capped_trends_list,
            "chart_events": chart_events
        }
        
        update_task_state(task_id, status="COMPLETED", stage="COMPLETED", data=final_data)
        logger.info(f"Background task pipeline for '{ticker}' completed successfully.")
        
    except Exception as e:
        logger.error(f"Error in task pipeline for '{ticker}': {str(e)}")
        update_task_state(task_id, status="FAILED", stage="FAILED", error_message=str(e))
