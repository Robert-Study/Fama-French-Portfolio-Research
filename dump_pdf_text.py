import re, zlib, sys

data = open(sys.argv[1], 'rb').read()
streams = []
for match in re.finditer(rb'stream[\r\n]+(.*?)[\r\n]+endstream', data, re.DOTALL):
    try:
        streams.append(zlib.decompress(match.group(1)))
    except:
        pass

s1 = streams[1]
print("Stream 1 raw text snippet:")
print(s1[:1000].decode('latin1', 'ignore'))
