"""PyAV로 test1111.mp3의 특정 구간만 잘라 짧은 테스트 파일을 만든다 (ffmpeg 미설치 환경 대응).
회의 실제 시작은 11:07부터라고 확인됨 -> 11:07 ~ 16:07 (5분) 구간을 자른다.
"""
import av

SRC = "test1111.mp3"
DST = "test1111_5min.mp3"
START_SEC = 11 * 60 + 7  # 11:07
DURATION_SEC = 5 * 60
END_SEC = START_SEC + DURATION_SEC

in_container = av.open(SRC)
in_stream = in_container.streams.audio[0]

out_container = av.open(DST, mode="w")
out_stream = out_container.add_stream("mp3", rate=in_stream.rate)

resampler = av.AudioResampler(
    format=out_stream.format,
    layout=out_stream.layout,
    rate=out_stream.rate,
)

for frame in in_container.decode(in_stream):
    ft = frame.time or 0
    if ft < START_SEC:
        continue
    if ft > END_SEC:
        break
    for rframe in resampler.resample(frame):
        for packet in out_stream.encode(rframe):
            out_container.mux(packet)

for packet in out_stream.encode(None):
    out_container.mux(packet)

out_container.close()
in_container.close()

# 검증: duration + 실제 신호 있는지 확인
import numpy as np

check = av.open(DST)
d = check.duration / 1_000_000
print(f"created {DST}: duration={d:.1f}s ({d/60:.2f} min)")

check2 = av.open(DST)
s2 = check2.streams.audio[0]
maxabs = 0.0
for i, frame in enumerate(check2.decode(s2)):
    arr = frame.to_ndarray()
    maxabs = max(maxabs, float(np.abs(arr).max()))
    if i >= 100:
        break
print(f"signal check (first ~100 frames): maxabs={maxabs}")
