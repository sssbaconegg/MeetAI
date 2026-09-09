import time

import requests
import streamlit as st

st.set_page_config(page_title="회의록 자동 생성", page_icon="📝", layout="centered")

DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
LANGUAGE_OPTIONS = {"자동 감지": None, "한국어": "ko", "영어": "en"}

st.title("📝 회의록 자동 생성")
st.caption("녹음 파일과 메모를 올리면 전사 후 구조화된 회의록을 만들어줍니다.")

with st.sidebar:
    api_base_url = st.text_input("API 서버 주소", value=DEFAULT_API_BASE_URL)

memo = st.text_area(
    "회의 메모 (선택)",
    height=150,
    placeholder="회의 중 적은 간단한 메모를 입력하세요. 비워두면 녹음만으로 회의록을 작성합니다.",
)
audio_file = st.file_uploader("녹음 파일 업로드 (mp3 / wav)", type=["mp3", "wav"])
language_label = st.selectbox("녹음 언어", list(LANGUAGE_OPTIONS.keys()))

generate_clicked = st.button(
    "회의록 생성", type="primary", disabled=audio_file is None
)


def _submit_job() -> dict:
    files = {
        "audio_file": (
            audio_file.name,
            audio_file.getvalue(),
            audio_file.type or "application/octet-stream",
        )
    }
    data = {}
    if memo.strip():
        data["memo"] = memo
    language = LANGUAGE_OPTIONS[language_label]
    if language:
        data["language"] = language

    resp = requests.post(f"{api_base_url}/upload-audio", files=files, data=data, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _poll_job(job_id: str, status_placeholder) -> dict:
    start = time.time()
    while True:
        elapsed = int(time.time() - start)
        status_placeholder.info(f"⏳ 회의록을 생성하고 있습니다... ({elapsed}초 경과)")
        result = requests.get(f"{api_base_url}/jobs/{job_id}", timeout=10).json()
        if result["status"] != "processing":
            return result
        time.sleep(3)


def _render_list(title: str, items) -> None:
    st.subheader(title)
    if items:
        for item in items:
            st.markdown(f"- {item}")
    else:
        st.markdown("_없음_")


def _render_result(result: dict) -> None:
    summary = result["summary"]

    st.success("회의록 생성 완료")
    st.header(summary.get("회의 주제") or "(회의 주제 없음)")
    if summary.get("일시"):
        st.caption(f"🗓️ {summary['일시']}")

    _render_list("핵심 내용", summary.get("핵심내용"))
    _render_list("결정사항", summary.get("결정사항"))

    st.subheader("담당 업무")
    tasks = summary.get("담당업무") or []
    if tasks:
        st.table(tasks)
    else:
        st.markdown("_없음_")

    st.subheader("다음 회의")
    st.markdown(summary.get("다음회의") or "_미정_")

    if result.get("memo"):
        with st.expander("입력한 메모"):
            st.write(result["memo"])

    with st.expander("전체 전사 텍스트 보기"):
        st.write(result.get("transcript") or "_전사 결과 없음_")


if generate_clicked:
    try:
        job = _submit_job()
    except requests.RequestException as exc:
        st.error(f"요청 전송에 실패했습니다: {exc}")
        st.stop()

    status_placeholder = st.empty()
    try:
        result = _poll_job(job["job_id"], status_placeholder)
    except requests.RequestException as exc:
        st.error(f"상태 조회에 실패했습니다: {exc}")
        st.stop()
    status_placeholder.empty()

    if result["status"] == "failed":
        st.error(f"회의록 생성에 실패했습니다: {result.get('error')}")
    else:
        _render_result(result)
