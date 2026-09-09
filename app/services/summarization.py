import json
import re
from typing import List, Optional

import litellm

from app.config import OLLAMA_API_BASE, OLLAMA_MODEL, OLLAMA_NUM_CTX, SUMMARY_CHUNK_CHAR_LIMIT

_TASK_RULES = """담당업무는 스크립트에 구체적인 이름/직책/호칭이 확인될 때만 채우고,
없으면 빈 배열로 두세요. 여러 사람을 한 항목에 뭉뚱그리지 말고 담당자별로 항목을
나누세요. 이름을 지어내지 말고, 이름이 없다면 "우리 측", "상대측(회사명이 언급되면
회사명 포함)", 또는 스크립트에 나온 직책/호칭(예: "팀장님", "담당자님")을 사용하세요."""

_DATE_RULES = """일시나 다음회의는 스크립트(또는 이 구간)에 구체적인 날짜/요일/시간이
언급된 경우에만 채우고, 그런 언급이 없다면 반드시 null로 두세요. "회의 종료"처럼
날짜가 아닌 문구를 넣지 마세요."""

# 짧은 녹취록(청크 분할이 필요 없는 경우): 담당업무까지 한 번에 정확히 뽑아낸다.
SINGLE_PASS_SYSTEM_PROMPT = f"""당신은 회의록 작성 도우미입니다.
아래 메모는 사용자가 회의 중 작성한 간단한 기록이고, 스크립트는 회의 녹음을 전체 텍스트로 변환한 것입니다.
메모를 뼈대로 삼되, 스크립트에서 찾을 수 있는 세부 내용(정확한 결정사항, 담당자, 일정 등)으로
메모의 각 항목을 보완해서 완성된 회의록을 작성하세요.
스크립트에 없는 내용은 추측해서 만들지 말고, 메모 내용을 그대로 유지하세요.
메모가 없으면 스크립트 내용만으로 작성하세요.

{_TASK_RULES}

{_DATE_RULES}

최종 결과는 아래 JSON 형식으로만 응답하세요. 설명, 마크다운, 코드블록 없이 순수 JSON 객체 하나만 출력하세요.
찾을 수 없는 정보는 null 또는 빈 배열로 채우세요.

{{
  "회의 주제": "string",
  "일시": "string or null",
  "핵심내용": ["string", ...],
  "결정사항": ["string", ...],
  "담당업무": [{{"담당자": "string", "업무": "string"}}, ...],
  "다음회의": "string or null"
}}
"""

# 긴 녹취록을 청크로 나눠 통합하는 경로: 담당업무는 이미 청크별로 코드가 그대로
# 합쳐서 채우므로, 여기서는 전체 맥락이 필요한 항목만 LLM에게 맡긴다.
FINAL_SYSTEM_PROMPT = f"""당신은 회의록 작성 도우미입니다.
아래 메모는 사용자가 회의 중 작성한 간단한 기록이고, 스크립트는 회의 녹음을 전체 텍스트로 변환한 것입니다.
메모를 뼈대로 삼되, 스크립트에서 찾을 수 있는 세부 내용(정확한 결정사항, 일정 등)으로
메모의 각 항목을 보완해서 완성된 회의록을 작성하세요.
스크립트에 없는 내용은 추측해서 만들지 말고, 메모 내용을 그대로 유지하세요.
메모가 없으면 스크립트 내용만으로 작성하세요.

담당업무 항목은 이미 별도로 정확하게 추출되어 있으니 당신은 신경 쓰지 마세요.
아래 JSON에 "담당업무" 키는 포함하지 마세요.

{_DATE_RULES}

최종 결과는 아래 JSON 형식으로만 응답하세요. 설명, 마크다운, 코드블록 없이 순수 JSON 객체 하나만 출력하세요.
찾을 수 없는 정보는 null 또는 빈 배열로 채우세요.

{{
  "회의 주제": "string",
  "일시": "string or null",
  "핵심내용": ["string", ...],
  "결정사항": ["string", ...],
  "다음회의": "string or null"
}}
"""

CHUNK_NOTE_SYSTEM_PROMPT = f"""당신은 회의록 요약 도우미입니다.
아래는 긴 회의 녹취록의 일부 구간입니다. 이 구간에서 언급된 내용만 근거로 정리하세요.
이 구간에 없는 내용은 지어내지 마세요.

{_TASK_RULES}

{_DATE_RULES}

아래 JSON 형식으로만 응답하세요. 설명, 마크다운, 코드블록 없이 순수 JSON 객체 하나만 출력하세요.

{{
  "회의 주제 단서": "string or null",
  "일시": "string or null",
  "핵심내용": ["string", ...],
  "결정사항": ["string", ...],
  "담당업무": [{{"담당자": "string", "업무": "string"}}, ...],
  "다음회의": "string or null"
}}
"""

_DEFAULTS = {
    "회의 주제": None,
    "일시": None,
    "핵심내용": [],
    "결정사항": [],
    "담당업무": [],
    "다음회의": None,
}

# "일시"/"다음회의"가 실제 날짜·요일·시간 언급인지 판별 (아니면 null 처리).
_DATE_LIKE_RE = re.compile(
    r"\d{4}\s*[.\-/년]\s*\d{1,2}\s*[.\-/월]\s*\d{1,2}"  # 2027.9.16 / 2027년 9월 16일
    r"|\d{1,2}\s*월\s*\d{1,2}\s*일"  # 9월 16일
    r"|[월화수목금토일]\s*요일"  # 화요일
    r"|\d{1,2}\s*시(\s*\d{1,2}\s*분)?"  # 오전 10시, 10시 30분
)


def _looks_like_date(value: Optional[str]) -> bool:
    if not value or not isinstance(value, str):
        return False
    return bool(_DATE_LIKE_RE.search(value))


def _extract_json(text: str) -> dict:
    cleaned = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(cleaned[start : end + 1])


def _chat(system_prompt: str, user_content: str) -> str:
    response = litellm.completion(
        # ollama_chat/ 를 써야 keep_alive가 top-level로 제대로 전달됨
        # (ollama/ 는 /api/generate로 가면서 keep_alive를 options 안에 잘못 중첩시킴)
        model=f"ollama_chat/{OLLAMA_MODEL}",
        api_base=OLLAMA_API_BASE,
        num_ctx=OLLAMA_NUM_CTX,
        temperature=0.2,
        timeout=1200,
        keep_alive="30m",  # 매 호출마다 모델이 언로드/재로드되지 않도록 유지
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )
    return response["choices"][0]["message"]["content"]


def _split_into_chunks(transcript: str, limit: int) -> List[str]:
    sentences = re.split(r"(?<=[.!?다요])\s+", transcript)
    chunks: List[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > limit:
            chunks.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _normalize_tasks(raw_tasks) -> List[dict]:
    """청크(또는 단일 패스) 응답의 담당업무 리스트를 {"담당자","업무"} 형태로 정리."""
    tasks: List[dict] = []
    if not isinstance(raw_tasks, list):
        return tasks
    for item in raw_tasks:
        if not isinstance(item, dict):
            continue
        owner = str(item.get("담당자") or "").strip()
        work = str(item.get("업무") or "").strip()
        if not owner or not work:
            continue
        tasks.append({"담당자": owner, "업무": work})
    return tasks


def _dedup_tasks(tasks: List[dict]) -> List[dict]:
    """(담당자, 업무)가 완전히 동일한 항목만 중복 제거한다 (재해석/재구성 없이)."""
    seen = set()
    result = []
    for task in tasks:
        key = (task["담당자"], task["업무"])
        if key in seen:
            continue
        seen.add(key)
        result.append(task)
    return result


def _apply_defaults_and_validate(result: dict) -> dict:
    merged = dict(_DEFAULTS)
    merged.update(result)

    for key, default in _DEFAULTS.items():
        value = merged.get(key)
        if isinstance(default, list) and not isinstance(value, list):
            merged[key] = default
        elif isinstance(value, str) and value.strip().lower() in ("null", "none", ""):
            merged[key] = None

    for key in ("일시", "다음회의"):
        if merged.get(key) is not None and not _looks_like_date(merged[key]):
            merged[key] = None

    return merged


def _extract_final_json(content: str) -> dict:
    try:
        return _extract_json(content)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM 응답을 JSON으로 파싱하지 못했습니다: {exc}\n원본 응답: {content}"
        ) from exc


def _finalize(memo: Optional[str], script_content: str) -> dict:
    """전체 맥락이 필요한 항목(주제/일시/핵심내용/결정사항/다음회의)만 LLM에게 맡긴다.
    담당업무는 호출부(summarize_meeting의 청크 경로)에서 별도로 채워 넣는다."""
    memo_section = memo.strip() if memo and memo.strip() else "(작성된 메모 없음)"
    user_content = f"[사용자 메모]\n{memo_section}\n\n[회의 스크립트]\n{script_content}"
    content = _chat(FINAL_SYSTEM_PROMPT, user_content)
    return _apply_defaults_and_validate(_extract_final_json(content))


def _single_pass(memo: Optional[str], transcript: str) -> dict:
    """청크 분할이 필요 없는 짧은 녹취록: 담당업무까지 한 번에 정확하게 뽑아낸다."""
    memo_section = memo.strip() if memo and memo.strip() else "(작성된 메모 없음)"
    user_content = f"[사용자 메모]\n{memo_section}\n\n[회의 스크립트]\n{transcript}"
    content = _chat(SINGLE_PASS_SYSTEM_PROMPT, user_content)
    data = _extract_final_json(content)
    data["담당업무"] = _dedup_tasks(_normalize_tasks(data.get("담당업무")))
    return _apply_defaults_and_validate(data)


def _chat_chunk_note_with_retry(chunk_index: int, total: int, chunk: str) -> Optional[dict]:
    """청크 요약 호출 + JSON 파싱. 실패하면 1회 재시도하고, 그래도 실패하면
    어떤 청크에서 실패했는지 로그로 남기고 None을 반환한다(조용히 넘어가지 않는다)."""
    user_content = f"녹취록 구간 {chunk_index + 1}/{total}:\n{chunk}"
    last_error: Optional[Exception] = None
    last_raw = ""
    for attempt in (1, 2):
        raw = _chat(CHUNK_NOTE_SYSTEM_PROMPT, user_content)
        last_raw = raw
        try:
            return _extract_json(raw)
        except json.JSONDecodeError as exc:
            last_error = exc
            if attempt == 1:
                print(
                    f"[WARN] 청크 {chunk_index + 1}/{total} JSON 파싱 실패, 재시도합니다: {exc}",
                    flush=True,
                )

    print(
        f"[ERROR] 청크 {chunk_index + 1}/{total} JSON 파싱 재시도까지 실패, 이 구간은 건너뜁니다."
        f" error={last_error}\nraw_response={last_raw}",
        flush=True,
    )
    return None


def summarize_meeting(transcript: str, memo: Optional[str] = None) -> dict:
    if len(transcript) <= SUMMARY_CHUNK_CHAR_LIMIT:
        return _single_pass(memo, transcript)

    chunks = _split_into_chunks(transcript, SUMMARY_CHUNK_CHAR_LIMIT)
    chunk_notes = []
    all_tasks: List[dict] = []
    failed_chunks: List[int] = []
    for i, chunk in enumerate(chunks):
        data = _chat_chunk_note_with_retry(i, len(chunks), chunk)
        if data is None:
            failed_chunks.append(i + 1)
            data = {}

        all_tasks.extend(_normalize_tasks(data.get("담당업무")))

        note_lines = [f"[구간 {i + 1} 메모]"]
        if data.get("회의 주제 단서"):
            note_lines.append(f"주제 단서: {data['회의 주제 단서']}")
        if data.get("일시"):
            note_lines.append(f"일시 언급: {data['일시']}")
        for line in data.get("핵심내용") or []:
            note_lines.append(f"- {line}")
        for line in data.get("결정사항") or []:
            note_lines.append(f"- (결정) {line}")
        if data.get("다음회의"):
            note_lines.append(f"다음회의 언급: {data['다음회의']}")
        chunk_notes.append("\n".join(note_lines))

    combined_notes = "\n\n".join(chunk_notes)
    result = _finalize(memo, combined_notes)
    # 담당업무는 LLM이 재해석/재구성하지 않고, 청크별로 추출된 리스트를 그대로 합쳐서
    # 중복(담당자+업무 완전 일치)만 제거한다.
    result["담당업무"] = _dedup_tasks(all_tasks)

    if failed_chunks:
        total = len(chunks)
        result["처리_경고"] = (
            f"일부 구간 처리 실패: {total}개 구간 중 {', '.join(str(n) for n in failed_chunks)}번째"
            " 구간을 요약하지 못했습니다. 해당 구간의 내용은 이 회의록에 반영되지 않았을 수 있습니다."
        )

    return result
