#!/usr/bin/env python3
"""把 scan_schools.py 的結果併入 data/sources.json。

用法：python3 tools/merge_scan.py candidates.json
- 已在清單裡的學校（同學制＋同縣市＋同校名，或同網址）略過
- 每校只收一個：優先「頁面」，其次「需登入」，最後「單一檔案」
- 才藝班術科、體育班之類非學科考題不收
"""
import json, re, sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "sources.json"
NON_ACADEMIC = re.compile(r"術科|美術班|音樂班|舞蹈班|體育班|國樂|藝術才能|藝才")


def key(level, city, school):
    s = re.sub(r"[\s（）()]|國民|中小學|國中小|國中|國小|高級中學|高中|中學|小學|部$", "", school.replace("台", "臺"))
    return (level, city.replace("台", "臺"), s)


def norm(u):
    p = urlparse(u)
    return (p.hostname or "").replace("www.", "") + p.path.rstrip("/") + ("?" + p.query if p.query else "")


def kind_of(u):
    h = urlparse(u).hostname or ""
    return ("Google 雲端硬碟" if h == "drive.google.com" else "Google 協作平台" if h == "sites.google.com"
            else "OneDrive" if "sharepoint" in h else "學校網站")


def main():
    cur = json.loads(SRC.read_text(encoding="utf-8"))
    have_k = {key(x["level"], x["city"], x["school"]) for x in cur}
    have_u = {norm(x["url"]) for x in cur}
    scan = json.load(open(sys.argv[1], encoding="utf-8"))
    rank = {"page": 0, "login": 1, "file": 2}
    added = []
    for s in scan:
        if key(s["level"], s["city"], s["school"]) in have_k:
            continue
        cands = [c for c in s["candidates"] if not NON_ACADEMIC.search(c["text"] + c.get("title", ""))
                 and norm(c["url"]) not in have_u]
        if not cands:
            continue
        c = sorted(cands, key=lambda c: (rank[c["kind"]], -c.get("hits", 0)))[0]
        x = dict(level=s["level"], city=s["city"], school=s["school"], subject=None, kind=kind_of(c["url"]),
                 official_exam=False, url=c["url"], page_title=c.get("title") or c["text"],
                 status="login" if c["kind"] == "login" else "ok", checked="", via="逐校掃描",
                 homepage=False, single_file=c["kind"] == "file", private=s.get("private", False))
        cur.append(x); added.append(x)
        have_k.add(key(s["level"], s["city"], s["school"])); have_u.add(norm(c["url"]))
    SRC.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print("新增", len(added), dict(Counter(a["level"] for a in added)),
          "單一檔案", sum(a["single_file"] for a in added), "私立", sum(a["private"] for a in added))


if __name__ == "__main__":
    main()
