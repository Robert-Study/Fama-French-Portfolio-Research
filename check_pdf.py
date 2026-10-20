import re, zlib, sys

def analyze_pdf(pdf_path):
    data = open(pdf_path, 'rb').read()
    print("Raw size:", len(data))
    decompressed = []
    # Find all Flate streams
    for match in re.finditer(rb'stream[\r\n]+(.*?)[\r\n]+endstream', data, re.DOTALL):
        chunk = match.group(1)
        try:
            decomp = zlib.decompress(chunk)
            decompressed.append(decomp)
        except Exception:
            pass
    full_text = data + b"\n".join(decompressed)
    pages = re.findall(rb'/Type\s*/Page\b', full_text)
    counts = re.findall(rb'/Count\s+(\d+)', full_text)
    print(f"Direct /Type /Page count: {len(pages)}")
    print(f"Direct /Count values: {[int(c) for c in counts]}")
    # Also look for trailer / Root / Pages
    for m in re.finditer(rb'/Count\s+(\d+)', full_text):
        print(f"Found /Count: {m.group(0)}")

if __name__ == '__main__':
    analyze_pdf(sys.argv[1])
