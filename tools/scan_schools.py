#!/usr/bin/env python3
"""逐校掃描：從教育部學校名錄的官網網址出發，找「考古題／段考試題／題庫」頁面。

用法：
  python3 tools/scan_schools.py 名錄.csv [名錄2.csv ...] --out candidates.json [--level 國中] [--only 雲林縣,金門縣] [--limit 50]

做法（每校最多抓約 8 頁，對學校網站負擔很小）：
  1. 抓首頁，找連結文字/網址符合「考題關鍵字」的連結 → 直接當候選
  2. 首頁上「教務處／教學組／下載專區」之類的連結再往下抓一層，同樣找考題連結
  3. 候選頁再打開確認：標題或內文要出現考題關鍵字才算
"""
import argparse, csv, json, re, ssl, html, sys, time, urllib.request, concurrent.futures as cf
from urllib.parse import urljoin, urlparse

EXAM = re.compile(r"考古題|段考試題|段考題|歷屆試題|歷屆考題|段考考題|試題下載|試題分享|試題庫|題庫|定期評量試題|評量試題|定期考查試題|月考試題|期中考試題|期末考試題")
EXAM_BAD = re.compile(r"會考簡章|命題規範|命題注意|審題|作業規定|實施要點|補考名單|成績查詢|線上測驗系統|因材網|均一")
HUB = re.compile(r"教務處|教學組|註冊組|試務|下載專區|檔案下載|資料下載|文件下載|檔案櫃|網路硬碟|資源分享|學習資源")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh) quiz-bank-directory-scan", "Accept-Language": "zh-TW"}
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
A_RE = re.compile(r"<a\b[^>]*?href\s*=\s*[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", re.S | re.I)
TAG = re.compile(r"<[^>]+>")
SKIP_EXT = re.compile(r"\.(jpg|jpeg|png|gif|zip|rar|mp4|mp3)$", re.I)


def fetch(url, n=400_000):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15, context=ctx)
        ct = r.headers.get("Content-Type", "")
        if "html" not in ct and "text" not in ct:
            return r.geturl(), "", ct
        raw = r.read(n)
        m = re.search(r"charset=([\w-]+)", ct) or re.search(r"charset=[\"']?([\w-]+)", raw[:3000].decode("ascii", "ignore"))
        enc = m.group(1).lower() if m else "utf-8"
        enc = "big5" if enc in ("big5", "big-5", "x-big5") else enc
        try:
            return r.geturl(), raw.decode(enc, "ignore"), ct
        except LookupError:
            return r.geturl(), raw.decode("utf-8", "ignore"), ct
    except Exception:
        return None, "", ""


def links(base, body):
    out = []
    for href, text in A_RE.findall(body):
        href = html.unescape(href.strip())
        if href.startswith(("javascript:", "mailto:", "tel:")):
            continue
        t = re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", text))).strip()
        title = re.search(r"title\s*=\s*[\"']([^\"']+)", text)
        try:
            out.append((urljoin(base, href), (t or "")[:60]))
        except ValueError:
            continue
    return out


def title_of(body):
    m = re.search(r"<title[^>]*>(.*?)</title>", body, re.S | re.I)
    return html.unescape(re.sub(r"\s+", " ", m.group(1))).strip()[:80] if m else ""


def same_site(u, home):
    h = urlparse(u).hostname or ""
    hh = (urlparse(home).hostname or "").replace("www.", "")
    return hh and (hh in h or h in ("drive.google.com", "sites.google.com", "affairs.kh.edu.tw", "class.kh.edu.tw"))


def scan(school):
    try:
        return _scan(school)
    except Exception as e:
        return dict(school, reachable=False, candidates=[], error=str(e)[:80])


def _scan(school):
    home = school["url"]
    if not home.startswith("http"):
        home = "http://" + home
    final, body, _ = fetch(home)
    res = dict(school, reachable=bool(final), candidates=[])
    if not final:
        return res
    seen, cands, hubs = {final}, {}, []
    for u, t in links(final, body):
        if u in seen or SKIP_EXT.search(u):
            continue
        seen.add(u)
        if EXAM.search(t) and not EXAM_BAD.search(t):
            cands[u] = t
        elif HUB.search(t) and same_site(u, final) and len(hubs) < 4:
            hubs.append(u)
    for h in hubs:
        f2, b2, _ = fetch(h)
        if not f2:
            continue
        for u, t in links(f2, b2):
            if u in seen or SKIP_EXT.search(u):
                continue
            seen.add(u)
            if EXAM.search(t) and not EXAM_BAD.search(t):
                cands[u] = t
    # 確認候選（最多 4 個）
    for u, t in list(cands.items())[:4]:
        if u.lower().endswith((".pdf", ".doc", ".docx", ".odt")):
            res["candidates"].append(dict(url=u, text=t, title="", kind="file"))
            continue
        f3, b3, _ = fetch(u)
        if not f3:
            continue
        if "accounts.google" in f3 or "login" in f3.lower():
            res["candidates"].append(dict(url=u, text=t, title="", kind="login"))
            continue
        ti = title_of(b3)
        hits = len(EXAM.findall(b3))
        if EXAM.search(ti + t) or hits >= 3:
            res["candidates"].append(dict(url=u, text=t, title=ti, hits=hits, kind="page"))
    return res


def load(paths, level, only):
    rows = []
    for p in paths:
        lv = "國小" if "e1" in p else "國中"
        if level and lv != level:
            continue
        for r in csv.DictReader(open(p, encoding="utf-8-sig")):
            city = re.sub(r"^\[\d+\]", "", r["縣市名稱"]).replace("台", "臺")
            if only and city not in only:
                continue
            url = (r.get("網址") or "").strip()
            if not url:
                continue
            name = re.sub(r"^(市立|縣立|國立|私立|國立.*?附設)", "", r["學校名稱"])
            rows.append(dict(level=lv, city=city, school=name, private=r["公/私立"] == "私立", url=url, code=r["代碼"]))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--level")
    ap.add_argument("--only")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=24)
    a = ap.parse_args()
    rows = load(a.csv, a.level, set(a.only.split(",")) if a.only else None)
    if a.limit:
        rows = rows[: a.limit]
    print("學校數", len(rows), file=sys.stderr)
    out, t0 = [], time.time()
    with cf.ThreadPoolExecutor(a.workers) as ex:
        for i, r in enumerate(ex.map(scan, rows), 1):
            out.append(r)
            if i % 100 == 0:
                print(f"{i}/{len(rows)}  {time.time()-t0:.0f}s  有候選 {sum(1 for x in out if x['candidates'])}", file=sys.stderr, flush=True)
    json.dump(out, open(a.out, "w"), ensure_ascii=False, indent=1)
    print("完成", len(out), "可連線", sum(x["reachable"] for x in out), "有候選", sum(1 for x in out if x["candidates"]), file=sys.stderr)


if __name__ == "__main__":
    main()
