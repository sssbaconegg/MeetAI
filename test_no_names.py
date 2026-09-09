import json

from app.services.summarization import summarize_meeting

transcript = (
    "안녕하세요, 오늘 회의는 다음 분기 협력 방안에 대한 논의입니다. "
    "저희 팀장님이 이번 제안서 초안을 준비해서 다음 주까지 공유하기로 했습니다. "
    "가나전자 측에서는 담당자님이 견적서를 검토해서 이번 주 안에 회신 주시기로 했습니다. "
    "논의 끝에 계약 조건은 다음 회의에서 최종 확정하기로 결정했습니다. "
    "다음 회의는 9월 19일 오전 10시에 진행하기로 했습니다."
)

result = summarize_meeting(transcript, memo=None)
with open("no_names_result.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print("done")
