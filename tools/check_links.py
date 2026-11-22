#!/usr/bin/env python3
"""重新檢查 data/sources.json 裡每個連結，更新 status / page_title / checked，
並產生網頁讀取用的 data/sources.js。

用法：python3 tools/check_links.py
新增學校：直接在 data/sources.json 加一筆（level/city/school/url/kind…），再跑一次本程式。
"""
import json, re, ssl, html, datetime, urllib.request, concurrent.futures as cf
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "sources.json"
JS = ROOT / "data" / "sources.js"

ctx = ssl.create_default_context()
ctx.check_hostname = False          # 不少學校網站憑證設定有問題，只做存活檢查所以放寬
ctx.verify_mode = ssl.CERT_NONE
GONE = ["此資料夾不存在", "找不到網頁", "頁面不存在", "Page Not Found", "404 Not Found"]


def check(x):
    today = datetime.date.today().isoformat()
    try:
        req = urllib.request.Request(x["url"], headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "zh-TW"})
        r = urllib.request.urlopen(req, timeout=20, context=ctx)
        raw = r.read(300000)
        body = raw.decode("utf-8", "ignore")
        m = re.search(r"<title[^>]*>(.*?)</title>", body, re.S | re.I)
        if m:
            x["page_title"] = html.unescape(m.group(1)).strip()[:80]
        if "login" in r.geturl().lower() or "accounts.google" in r.geturl():
            x["status"] = "login"
        elif any(k in body for k in GONE):
            x["status"] = "broken"
        else:
            x["status"] = "ok"
    except urllib.error.HTTPError as e:
        x["status"] = "broken" if e.code in (404, 410) else "unstable"
    except Exception:
        x["status"] = "unstable"
    x["checked"] = today
    x.setdefault("homepage", False)
    return x


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    with cf.ThreadPoolExecutor(16) as ex:
        data = list(ex.map(check, data))
    SRC.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    JS.write_text("// 由 tools/check_links.py 自動產生，請改 sources.json\nwindow.SOURCES = "
                  + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")
    from collections import Counter
    print("共", len(data), "筆", dict(Counter(x["status"] for x in data)))
    for x in data:
        if x["status"] != "ok":
            print(f"  [{x['status']}] {x['city']} {x['school']}  {x['url']}")


if __name__ == "__main__":
    main()
