import os
import requests
import streamlit as st
from datetime import datetime
from logger import logger

def fetch_company_facts(cik: str) -> dict:
    """
    Fetches raw company facts JSON from SEC EDGAR.
    """
    user_agent = os.getenv("SEC_USER_AGENT", "MyStockAnalyzerApp admin@mystockanalyzerapp.com")
    headers = {"User-Agent": user_agent}
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    
    logger.info(f"Fetching Company Facts from SEC for CIK {cik}: {url}")
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch company facts for CIK {cik}. error={str(e)}")
        raise RuntimeError(f"SEC 재무 데이터 수집에 실패했습니다 (CIK: {cik}). API 요청 제한이나 User-Agent 설정을 확인해 주세요: {str(e)}")

def extract_quarterly_metric(facts: dict, metric_candidates: list[str]) -> dict:
    """
    Extracts financial statement metric values from SEC facts JSON, mapping them by period 'end' date.
    Supports both 10-Q (Quarterly) and 10-K (Annual) reports.
    """
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    metric_data = {}
    
    for candidate in metric_candidates:
        if candidate in us_gaap:
            units = us_gaap[candidate].get("units", {})
            usd_units = units.get("USD", [])
            
            # Sort entries by 'filed' date so that later restatements/amendments overwrite older values
            sorted_entries = sorted(
                [e for e in usd_units if e.get("form") in ["10-K", "10-Q"]],
                key=lambda x: x.get("filed", "")
            )
            
            for entry in sorted_entries:
                end_date = entry.get("end")
                val = entry.get("val")
                if end_date and val is not None:
                    metric_data[end_date] = float(val)
            
            # If we successfully parsed any data under this XBRL tag, stop seeking
            if metric_data:
                break
                
    return metric_data

@st.cache_data(ttl=3600, show_spinner=False)
def get_financial_data_3years(ticker: str, cik: str) -> dict:
    """
    Retrieves revenue and net income time series for the last 12 quarters (3 years of data points).
    Returns a dictionary structure:
    {
      "ticker": "AAPL",
      "cik": "0000320193",
      "dates": ["2023-03-31", "2023-06-30", ...],
      "revenue": [94840000000.0, 81797000000.0, ...],
      "net_income": [24160000000.0, 19881000000.0, ...]
    }
    """
    if cik == "0000000000":
        logger.info("Dummy CIK detected. Returning mock quarterly financials for test.")
        # 12 quarters of mock data
        dates = [
            "2023-03-31", "2023-06-30", "2023-09-30", "2023-12-31",
            "2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31",
            "2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"
        ]
        revenue = [
            94800000000.0, 81800000000.0, 89500000000.0, 119600000000.0,
            90800000000.0, 85800000000.0, 94900000000.0, 124000000000.0,
            96000000000.0, 91000000000.0, 99000000000.0, None # Mock N/A gap
        ]
        net_income = [
            24100000000.0, 19900000000.0, 23000000000.0, 33900000000.0,
            23600000000.0, 21400000000.0, 25000000000.0, 34600000000.0,
            25500000000.0, 22000000000.0, 27000000000.0, None # Mock N/A gap
        ]
        return {
            "ticker": ticker,
            "cik": cik,
            "dates": dates,
            "revenue": revenue,
            "net_income": net_income
        }
        
    facts = fetch_company_facts(cik)
    
    revenue_candidates = [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet"
    ]
    
    net_income_candidates = [
        "NetIncomeLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic"
    ]
    
    rev_map = extract_quarterly_metric(facts, revenue_candidates)
    ni_map = extract_quarterly_metric(facts, net_income_candidates)
    
    # Get sorted union of all dates available
    all_dates = sorted(list(set(rev_map.keys()) | set(ni_map.keys())))
    
    if not all_dates:
        logger.warning(f"No financial data found for {ticker}.")
        current_year = datetime.now().year
        all_dates = [f"{current_year-2}-12-31", f"{current_year-1}-12-31", f"{current_year}-12-31"]
        return {
            "ticker": ticker,
            "cik": cik,
            "dates": all_dates,
            "revenue": [None, None, None],
            "net_income": [None, None, None]
        }
        
    # Slice the last 12 points (roughly 3 years of quarterly/annual filings)
    target_dates = all_dates[-12:]
    
    # Ensure at least 4 points exist for plotting
    while len(target_dates) < 4:
        try:
            prev_date = datetime.strptime(target_dates[0], "%Y-%m-%d")
            from datetime import timedelta
            new_date = (prev_date - timedelta(days=90)).strftime("%Y-%m-%d")
            target_dates.insert(0, new_date)
        except Exception:
            target_dates.insert(0, "2023-01-01")
            
    revenue_list = [rev_map.get(d) for d in target_dates]
    net_income_list = [ni_map.get(d) for d in target_dates]
    
    result = {
        "ticker": ticker,
        "cik": cik,
        "dates": target_dates,
        "revenue": revenue_list,
        "net_income": net_income_list
    }
    
    logger.info(f"Processed financial data for {ticker}. Total periods: {len(target_dates)}")
    return result
