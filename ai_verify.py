import os
import google.generativeai as genai
from logger import logger

# Initialize Gemini Client if API key is provided
def get_gemini_model():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
        logger.warning("GEMINI_API_KEY가 구성되지 않았거나 템플릿 값입니다. AI 검증은 로컬 시뮬레이션 모드로 실행됩니다.")
        return None
    try:
        genai.configure(api_key=api_key)
        # Using gemini-3.5-flash as specified by user
        model = genai.GenerativeModel("gemini-3.5-flash")
        return model
    except Exception as e:
        logger.error(f"Gemini 모델 초기화 실패. error={str(e)}")
        return None

def check_local_bias(text: str) -> tuple[bool, str]:
    """
    Local fallback keyword check for biased and investment promoting terms.
    """
    bias_keywords = [
        "must buy", "strong buy", "skyrocket", "to the moon", "crash to zero", 
        "definitely buy", "강력 매수", "폭등", "무조건 상승", "추천 종목"
    ]
    text_lower = text.lower()
    for kw in bias_keywords:
        if kw in text_lower:
            return False, f"투자 유도 또는 편향적인 표현('{kw}')이 발견되었습니다. (로컬 검증)"
    return True, ""

def run_verification(data_block: dict, block_type: str) -> tuple[bool, str]:
    """
    Runs both Rule-based and AI-based verification on the data block.
    Returns (is_valid, reason_message)
    """
    # 1. Rule-based verification (우선 처리)
    if block_type == 'financial_summary':
        years = data_block.get("years", [])
        if len(years) != 3:
            return False, "수치 데이터가 최근 3개년 구조가 아닙니다."
            
        revenue = data_block.get("revenue", [])
        net_income = data_block.get("net_income", [])
        if len(revenue) != 3 or len(net_income) != 3:
            return False, "매출액 또는 순이익 수치 데이터의 개수가 3개가 아닙니다."
            
        summary_text = data_block.get("summary", "")
        if not summary_text:
            return False, "재무 요약문 텍스트가 비어 있습니다."
            
    elif block_type == 'trend_item':
        summary_text = data_block.get("summary", "")
        if not summary_text:
            return False, "동향 기사 요약 텍스트가 비어 있습니다."
            
        sentiment = data_block.get("sentiment", "")
        if sentiment not in ["Good", "Neutral", "Bad"]:
            return False, f"감성 분류 값('{sentiment}')이 올바르지 않습니다. (Good, Neutral, Bad 중 하나여야 함)"

    # 2. AI-based verification
    model = get_gemini_model()
    if not model:
        return check_local_bias(data_block.get("summary", ""))
        
    try:
        system_prompt = (
            "당신은 금융 리포트 검증 AI입니다. 주어진 데이터 블록이 다음 조건들을 충족하는지 검증하십시오:\n"
            "1. 투자 유도 표현(예: '강력 매수', '꼭 사야 한다', '폭등할 것')이 전혀 없어야 합니다. 극도로 중립적인 보고서 어조여야 합니다.\n"
            "2. 환각(Hallucination)이 없어야 하며, 주어진 수치나 팩트 이외의 허구 사실을 언급하지 않아야 합니다.\n"
            "3. 어조가 지나치게 주관적이거나 편향되지 않아야 합니다.\n\n"
            "아래 데이터 블록의 요약문(summary)을 분석하고, 위 조건을 위반했다면 그 구체적인 이유(reason)를 적어주시고, 안전하다면 오직 'VALID'라고만 응답하세요.\n"
            "응답 포맷:\n"
            "- 적합한 경우: VALID\n"
            "- 부적합한 경우: INVALID: [구체적인 사유]"
        )
        
        prompt = f"검증 대상 타입: {block_type}\n데이터 내용: {data_block}\n요약문: {data_block.get('summary')}"
        
        response = model.generate_content(
            contents=[
                {"role": "user", "parts": [system_prompt + "\n\n" + prompt]}
            ]
        )
        result_text = response.text.strip()
        
        if result_text.startswith("VALID"):
            return True, ""
        elif result_text.startswith("INVALID"):
            reason = result_text.replace("INVALID:", "").strip()
            return False, reason if reason else "AI 검증 정책 위배 (편향성 또는 환각 의심)"
        else:
            if "invalid" in result_text.lower():
                return False, result_text
            # If AI response format is loose, run fallback local check
            return check_local_bias(data_block.get("summary", ""))
            
    except Exception as e:
        logger.warning(f"Gemini API verification call failed. error={str(e)}. Falling back to local keyword verification.")
        return check_local_bias(data_block.get("summary", ""))

def local_fix(block: dict) -> dict:
    """
    Removes key biased keywords locally.
    """
    summary = block.get("summary", "")
    bias_words = ["must buy", "strong buy", "skyrocket", "to the moon", "crash to zero", "definitely buy"]
    for bw in bias_words:
        summary = summary.replace(bw, "stable outlook")
        summary = summary.replace(bw.upper(), "stable outlook")
        summary = summary.replace(bw.title(), "stable outlook")
        
    ko_biases = ["강력 매수", "폭등", "무조건 상승", "떡상", "추천 종목"]
    for kb in ko_biases:
        summary = summary.replace(kb, "중립적 추이 관찰")
        
    block["summary"] = summary + " (로컬 자동 보정 완료)"
    return block

def regenerate_block(data_block: dict, reason: str, block_type: str) -> dict:
    """
    Requests Gemini (or local fallback) to regenerate the summary statement.
    """
    model = get_gemini_model()
    
    if not model:
        return local_fix(data_block)
        
    try:
        if block_type == 'financial_summary':
            prompt = (
                f"다음 재무 데이터 요약문은 다음 사유로 검증에 실패했습니다:\n"
                f"에러 사유: {reason}\n\n"
                f"원본 재무 정보:\n"
                f"- 연도: {data_block.get('years')}\n"
                f"- 매출액: {data_block.get('revenue')}\n"
                f"- 순이익: {data_block.get('net_income')}\n"
                f"- 기존 요약문: {data_block.get('summary')}\n\n"
                f"**지시사항**:\n"
                f"위 에러 사유를 해결하여, 극도로 중립적인 보고서 어조로 재무 요약문을 재생성하세요. "
                f"투자 유도 표현은 절대 배제하고, 원천 데이터 수치와 정확히 일치하며 팩트에만 기반해야 합니다.\n"
                f"오직 재생성된 요약문 텍스트만 출력하세요. 다른 안내 문구는 넣지 마세요."
            )
        else: # trend_item
            prompt = (
                f"다음 기업 동향 뉴스는 다음 사유로 검증에 실패했습니다:\n"
                f"에러 사유: {reason}\n\n"
                f"기사 정보:\n"
                f"- 제목: {data_block.get('title')}\n"
                f"- 기존 요약문: {data_block.get('summary')}\n"
                f"- 감성 분류: {data_block.get('sentiment')}\n\n"
                f"**지시사항**:\n"
                f"위 에러 사유를 해결하여, 극도로 중립적이고 사실에 입각한 기사 요약문을 다시 작성하세요. "
                f"어조에 편향이 없어야 하며, 투자 추천 표현은 배제해야 합니다.\n"
                f"오직 재생성된 요약문 텍스트만 출력하세요. 다른 안내 문구는 넣지 마세요."
            )
            
        response = model.generate_content(prompt)
        new_summary = response.text.strip()
        
        data_block["summary"] = new_summary
        logger.info(f"[{block_type}] Successfully regenerated block.")
        return data_block
        
    except Exception as e:
        logger.warning(f"Failed to regenerate block via Gemini. error={str(e)}. Running local fallback fix.")
        return local_fix(data_block)

def verify_and_retry_block(data_block: dict, block_type: str, max_retries: int = 2) -> tuple[dict | None, str]:
    """
    Verifies a data block and retries up to max_retries on failure.
    If it fails all retries, returns (None, "EXCLUDED").
    """
    for attempt in range(1, max_retries + 1):
        is_valid, reason = run_verification(data_block, block_type)
        if is_valid:
            logger.info(f"[{block_type}] 검증 통과 (시도 {attempt}/{max_retries})")
            return data_block, "SUCCESS"
        
        logger.warning(f"[{block_type}] 검증 실패 (시도 {attempt}/{max_retries}): {reason}")
        data_block = regenerate_block(data_block, reason, block_type)
        
    logger.error(f"[{block_type}] 최종 검증 실패. 결과에서 제외 처리합니다.")
    return None, "EXCLUDED"
