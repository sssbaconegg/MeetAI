from app.services.summarization import _split_into_chunks, summarize_meeting

with open("meeting_script.txt", encoding="utf-8") as f:
    base_text = f.read().replace("\n", " ").strip()

long_transcript = " ".join([base_text] * 5)
print(f"transcript length: {len(long_transcript)} chars")

chunks = _split_into_chunks(long_transcript, 1500)
print(f"chunk count: {len(chunks)}")
for i, c in enumerate(chunks):
    print(f"  chunk {i+1}: {len(c)} chars")

result = summarize_meeting(long_transcript)
import json
with open("chunking_result.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print("saved to chunking_result.json")
