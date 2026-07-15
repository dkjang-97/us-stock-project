import os
from dotenv import load_dotenv

# Load env variables
load_dotenv()

from logger import logger
from data_match import get_cik_by_ticker
from data_load import get_financial_data_3years
from explainer_trend import get_trend_analysis

def test_pipeline():
    ticker = "AAPL"
    # Set a custom task id to test logger format
    logger.set_task_id("TEST-TASK-001")
    logger.info(f"--- [Step 2 테스트 시작] Ticker: {ticker} ---")
    
    try:
        # 1. Ticker -> CIK Lookup
        logger.info("1단계: Ticker to CIK 매핑 수행 중...")
        cik = get_cik_by_ticker(ticker)
        logger.info(f"1단계 성공: Ticker '{ticker}' -> CIK '{cik}'")
        
        # 2. Load SEC 3-Year financials
        logger.info("2단계: SEC 3개년 재무 데이터 수집 중...")
        financial_data = get_financial_data_3years(ticker, cik)
        logger.info("2단계 성공: 재무 데이터 로드 완료")
        logger.info(f" - 대상 연도 (Years): {financial_data['years']}")
        logger.info(f" - 매출액 (Revenue): {financial_data['revenue']}")
        logger.info(f" - 순이익 (Net Income): {financial_data['net_income']}")
        
        # 3. Fetch Trend/News items
        logger.info("3단계: 3개년 동향 및 뉴스 수집 중...")
        trends = get_trend_analysis(ticker, financial_data['years'])
        logger.info(f"3단계 성공: 동향 분석 데이터 로드 완료 (총 {len(trends)}개)")
        
        # Print top 5 items for verification
        logger.info("수집된 동향 데이터 중 상위 5개 출력:")
        for i, trend in enumerate(trends[:5]):
            logger.info(f" [{i+1}] 연도: {trend['year']} | 감성: {trend['sentiment']} | 제목: {trend['title']} | 출처: {trend['source']}")
            
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    test_pipeline()
