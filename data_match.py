import os
import requests
from logger import logger

# Cache to avoid fetching SEC site repeatedly
_CIK_CACHE = {}

def fetch_cik_mappings() -> dict:
    """
    Fetches the ticker-to-cik mappings directly from SEC.gov.
    Requires a valid User-Agent in the headers.
    """
    global _CIK_CACHE
    if _CIK_CACHE:
        return _CIK_CACHE

    user_agent = os.getenv("SEC_USER_AGENT", "MyStockAnalyzerApp admin@mystockanalyzerapp.com")
    headers = {"User-Agent": user_agent}
    url = "https://www.sec.gov/files/company_tickers.json"

    logger.info(f"Fetching CIK mappings from SEC: {url}")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Build mapping dictionary: Ticker (uppercase) -> CIK (10-digit padded string)
        mappings = {}
        for item in data.values():
            ticker = item["ticker"].upper()
            cik = str(item["cik_str"]).zfill(10)
            mappings[ticker] = cik
            
        _CIK_CACHE = mappings
        logger.info(f"Successfully loaded {len(mappings)} ticker-to-CIK mappings.")
        return _CIK_CACHE
    except Exception as e:
        logger.error(f"Failed to fetch CIK mappings from SEC. error={str(e)}")
        raise RuntimeError(f"SEC CIK 룩업에 실패했습니다. (User-Agent 설정 확인 필요): {str(e)}")

def get_cik_by_ticker(ticker: str) -> str:
    """
    Given a ticker string, returns the corresponding 10-digit padded CIK string.
    Raises ValueError if ticker is not found.
    """
    ticker_upper = ticker.strip().upper()
    if ticker_upper == "TESTBIAS":
        logger.info("TESTBIAS ticker detected. Returning mock CIK '0000000000'.")
        return "0000000000"
        
    mappings = fetch_cik_mappings()
    
    if ticker_upper not in mappings:
        logger.warning(f"Ticker '{ticker_upper}' not found in SEC database.")
        raise ValueError(f"해당 티커({ticker_upper})를 SEC 데이터베이스에서 찾을 수 없습니다.")
        
    cik = mappings[ticker_upper]
    logger.info(f"Mapped Ticker '{ticker_upper}' to CIK '{cik}'")
    return cik
