import av

input_path = "meeting_test.wav"
output_path = "meeting_test.mp3"

in_container = av.open(input_path)
out_container = av.open(output_path, mode="w")

in_stream = in_container.streams.audio[0]
out_stream = out_container.add_stream("mp3", rate=in_stream.rate)

for frame in in_container.decode(in_stream):
    for packet in out_stream.encode(frame):
        out_container.mux(packet)

for packet in out_stream.encode(None):
    out_container.mux(packet)

out_container.close()
in_container.close()
print("converted to", output_path)
