import time
import requests
import os

def test_integration_run():
    backend_url = "http://localhost:8000"
    ticker = "TESTBIAS"
    
    print(f"1. POST /api/analyze?ticker={ticker} 요청 전송...")
    res = requests.post(f"{backend_url}/api/analyze?ticker={ticker}")
    if res.status_code != 200:
        print(f"요청 실패: {res.text}")
        return
        
    task_id = res.json()["task_id"]
    print(f"수신된 Task ID: {task_id}")
    
    print("\n2. 백엔드 폴링 시작 (상태 추적)...")
    while True:
        status_res = requests.get(f"{backend_url}/api/tasks/{task_id}")
        if status_res.status_code != 200:
            print("상태 조회 실패")
            break
            
        task_data = status_res.json()
        status_str = task_data.get("status")
        stage_str = task_data.get("stage")
        print(f" - [Status: {status_str}] [Stage: {stage_str}]")
        
        if status_str in ["COMPLETED", "FAILED"]:
            break
            
        time.sleep(1.5)
        
    print("\n3. 최종 결과 분석...")
    if status_str == "COMPLETED":
        data = task_data.get("data", {})
        print("✅ 파이프라인 수행 완료!")
        
        print("\n[기업 한글 프로필]")
        print(data.get("company_profile"))
        
        print("\n[재무 데이터 (상위 5개 분기)]")
        financials = data.get("financials", {})
        dates = financials.get("dates", [])
        revenue = financials.get("revenue", [])
        net_income = financials.get("net_income", [])
        for i in range(min(5, len(dates))):
            rev_val = f"${revenue[i]/1e9:,.2f}B" if revenue[i] is not None else "N/A"
            ni_val = f"${net_income[i]/1e9:,.2f}B" if net_income[i] is not None else "N/A"
            print(f" - {dates[i]} | 매출: {rev_val} | 순이익: {ni_val}")
            
        print("\n[AI 검증 재무 요약]")
        fin_summary = data.get("financial_summary", {})
        if fin_summary:
            print(f"Summary: {fin_summary.get('summary')}")
        else:
            print("배제됨 (None)")
            
        print("\n[차트 어노테이션 뉴스 이벤트 (최대 3개)]")
        chart_events = data.get("chart_events", [])
        for ev in chart_events:
            print(f" - [{ev.get('date')}] ({ev.get('sentiment')}) {ev.get('title')}")
            
        print("\n[동향 분석 뉴스 카드 (상위 3개)]")
        trends = data.get("trends", [])
        for i, trend in enumerate(trends[:3]):
            print(f" [{i+1}] ({trend.get('sentiment')}) [{trend.get('quarter')}] {trend.get('title')}")
            print(f"     Summary: {trend.get('summary')}")
            print(f"     Source: {trend.get('source')} | URL: {trend.get('url')}")
    else:
        print(f"❌ 파이프라인 수행 실패: {task_data.get('error_message')}")

if __name__ == "__main__":
    test_integration_run()
