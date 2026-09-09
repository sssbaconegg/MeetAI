import json
import time

import requests

BASE = "http://127.0.0.1:8000"

memo = "1. 서비스 출시 논의\n2. 담당자 업무 분담\n3. 다음 회의 일정"

with open("meeting_test.mp3", "rb") as f:
    resp = requests.post(
        f"{BASE}/upload-audio",
        files={"audio_file": ("meeting_test.mp3", f, "audio/mpeg")},
        data={"memo": memo, "language": "ko"},
    )
resp.raise_for_status()
job = resp.json()
print("submitted:", job)

job_id = job["job_id"]
while True:
    r = requests.get(f"{BASE}/jobs/{job_id}").json()
    if r["status"] != "processing":
        break
    time.sleep(4)

with open("memo_test_result2.json", "w", encoding="utf-8") as f:
    json.dump(r, f, ensure_ascii=False, indent=2)
print("done, status:", r["status"])
