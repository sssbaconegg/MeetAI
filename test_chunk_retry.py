"""청크 JSON 파싱 실패 -> 재시도 -> 그래도 실패 시 경고 표시 로직을 mock으로 검증."""
import json
from unittest.mock import patch

import app.services.summarization as summ

# 청크 3개짜리 transcript를 강제로 만들기 위해 chunk 분리 함수는 그대로 쓰고,
# _chat만 mock해서 청크별 응답을 통제한다.
transcript = "가나다. " * 50 + "라마바. " * 50 + "사아자. " * 50  # 대략 3청크 분량

call_log = []


def fake_chat(system_prompt, user_content):
    call_log.append(user_content[:20])
    if "구간 1/" in user_content:
        return json.dumps({
            "회의 주제 단서": "주제A",
            "핵심내용": ["내용1"],
            "결정사항": [],
            "담당업무": [{"담당자": "홍길동", "업무": "업무1"}],
            "일시": None,
            "다음회의": None,
        }, ensure_ascii=False)
    if "구간 2/" in user_content:
        # 항상 깨진 JSON을 리턴 -> 재시도해도 계속 실패해야 함
        return "이것은 JSON이 아닙니다 { 깨진 상태"
    if "구간 3/" in user_content:
        return json.dumps({
            "회의 주제 단서": "주제C",
            "핵심내용": ["내용3"],
            "결정사항": ["결정3"],
            "담당업무": [{"담당자": "김철수", "업무": "업무3"}],
            "일시": None,
            "다음회의": None,
        }, ensure_ascii=False)
    # 최종 통합(_finalize) 호출
    return json.dumps({
        "회의 주제": "통합주제",
        "일시": None,
        "핵심내용": ["통합1"],
        "결정사항": ["통합결정"],
        "다음회의": None,
    }, ensure_ascii=False)


with patch.object(summ, "_chat", side_effect=fake_chat), \
     patch.object(summ, "SUMMARY_CHUNK_CHAR_LIMIT", 100):
    result = summ.summarize_meeting(transcript, memo="테스트메모")

print("call_count:", len(call_log))
print("담당업무:", result.get("담당업무"))
print("처리_경고:", result.get("처리_경고"))
assert result.get("처리_경고"), "실패 경고가 최종 결과에 포함되어야 함"
assert any(t["담당자"] == "홍길동" for t in result["담당업무"]), "성공한 청크(1) 데이터는 살아있어야 함"
assert any(t["담당자"] == "김철수" for t in result["담당업무"]), "성공한 청크(3) 데이터는 살아있어야 함"
print("OK: 재시도 로직 및 경고 표시 정상 동작")
