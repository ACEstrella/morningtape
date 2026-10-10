#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""모닝테이프 정적 사이트 생성기 (파이썬 표준 라이브러리만 사용)

data/editions/*.json 을 읽어 아래 파일을 만든다.
  index.html, e/<id>.html, archive.html, latest.json, feed.xml, sitemap.xml,
  robots.txt, 404.html, sw.js
사용법: python3 build.py      (데이터에 오류가 있으면 아무것도 쓰지 않고 종료 코드 1)
"""
import datetime as dt
import hashlib
import html
import json
import re
import sys
from email.utils import format_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "editions"

SITE = {
    "name": "모닝테이프",
    "tagline": "해외증시·경제 브리핑",
    "url": "https://acestrella.github.io/morningtape/",
    "telegram": "",    # 예: https://t.me/morningtape_kr  (비워 두면 표시 안 함)
    "naver_blog": "",  # 예: https://blog.naver.com/아이디
}
CATS = [("us", "미국증시"), ("biz", "기업"), ("rates", "금리·연준"),
        ("oil", "유가·중동"), ("kr", "국내"), ("global", "글로벌")]
CAT_LABEL = dict(CATS)
DIRS = {"up", "dn", ""}
WD = "월화수목금토일"
ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-(am|pm)$")
REQUIRED = ["id", "summary", "published_at", "ticker", "lead", "stories",
            "indicators", "movers", "schedule", "sources"]


# ------------------------------------------------------------------ helpers
def e(s):
    return html.escape("" if s is None else str(s), quote=True)


def dcls(d):
    return d if d in ("up", "dn") else ""


def label(eid):
    return "아침판" if eid.endswith("-am") else "저녁판"


def when(ed):
    return dt.datetime.fromisoformat(ed["published_at"])


def stamp(t):
    return f"{t:%Y.%m.%d} ({WD[t.weekday()]}) {t:%H:%M}"


def md(t):
    return f"{t.month}월 {t.day}일"


def short_md(t):
    return f"{t.month}/{t.day}"


def jsonld(obj):
    return ('<script type="application/ld+json">'
            + json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")
            + "</script>")


# ------------------------------------------------------------------ validation
def validate(ed, fname):
    errs = [f"'{k}' 항목이 없음" for k in REQUIRED if k not in ed]
    if errs:
        return errs
    if ed["id"] + ".json" != fname:
        errs.append(f"id({ed['id']})와 파일명({fname})이 다름")
    if not ID_RE.match(ed["id"]):
        errs.append("id 형식은 YYYY-MM-DD-am 또는 YYYY-MM-DD-pm")
    try:
        t = when(ed)
        if t.tzinfo is None:
            errs.append("published_at 끝에 +09:00 필요")
        elif not ed["id"].startswith(f"{t:%Y-%m-%d}"):
            errs.append("published_at 날짜와 id 날짜가 다름")
    except Exception:
        errs.append("published_at 형식 오류 (예: 2026-10-08T18:00:00+09:00)")
    lead = ed["lead"] if isinstance(ed["lead"], dict) else {}
    for k in ("cat", "time", "title", "dek", "body", "source", "url"):
        if not lead.get(k):
            errs.append(f"lead.{k} 없음")
    if lead.get("cat") and lead["cat"] not in CAT_LABEL:
        errs.append(f"lead.cat '{lead['cat']}' 은 {list(CAT_LABEL)} 중 하나여야 함")
    if lead.get("body") and not isinstance(lead["body"], list):
        errs.append("lead.body 는 문단 문자열 배열")
    if not isinstance(ed["stories"], list) or len(ed["stories"]) < 6:
        errs.append("stories 는 6개 이상")
    for i, st in enumerate(ed["stories"] or []):
        for k in ("cat", "title", "summary", "source", "url"):
            if not st.get(k):
                errs.append(f"stories[{i}].{k} 없음")
        if st.get("cat") and st["cat"] not in CAT_LABEL:
            errs.append(f"stories[{i}].cat '{st['cat']}' 잘못됨")
    for name, lst in (("ticker", ed["ticker"]), ("stories", ed["stories"]),
                      ("indicators", ed["indicators"]), ("movers", ed["movers"]),
                      ("lead.chips", lead.get("chips", []))):
        for i, x in enumerate(lst or []):
            if x.get("dir", "") not in DIRS:
                errs.append(f"{name}[{i}].dir 은 \"up\", \"dn\", \"\" 중 하나")
    urls = [lead.get("url")] + [s.get("url") for s in ed["stories"] or []] \
        + [s.get("url") for s in ed["sources"] or []]
    for u in urls:
        if u and not str(u).startswith(("http://", "https://")):
            errs.append(f"링크 형식 오류: {u}")
    for i, x in enumerate(ed["ticker"] or []):
        if not x.get("k"):
            errs.append(f"ticker[{i}].k 없음")
    return errs


def warnings(ed):
    cats = {ed["lead"]["cat"]} | {s["cat"] for s in ed["stories"]}
    miss = [lab for c, lab in CATS if c not in cats]
    return [f"기사가 없는 탭: {', '.join(miss)}"] if miss else []


# ------------------------------------------------------------------ page parts
def head(title, desc, canonical, root, av, eid="", og_type="website", extra=""):
    return f"""<!doctype html>
<html lang="ko" data-root="{e(root)}" data-edition="{e(eid)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(canonical)}">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="{e(SITE['name'])}">
<meta property="og:locale" content="ko_KR">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(canonical)}">
<meta property="og:image" content="{SITE['url']}icons/og.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#0A6B66">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="{e(SITE['name'])}">
<link rel="manifest" href="{root}manifest.webmanifest">
<link rel="icon" href="{root}icons/favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="{root}icons/apple-touch-icon.png">
<link rel="alternate" type="application/rss+xml" title="{e(SITE['name'])}" href="{root}feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Gothic+A1:wght@700;800&family=IBM+Plex+Mono:wght@500;600&family=IBM+Plex+Sans+KR:wght@400;500;700&display=swap">
<link rel="stylesheet" href="{root}assets/style.css?v={av}">
{extra}
</head>
<body>"""


def logo():
    return ('<svg class="logo" width="36" height="36" viewBox="0 0 36 36" aria-hidden="true">'
            '<rect width="36" height="36" rx="7" fill="var(--accent)"/>'
            '<polyline points="6,25 13,19 18,22 24,12 30,15" fill="none" stroke="var(--on-accent)" '
            'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def banner(root):
    home = root or "./"
    return f"""<div class="newer" id="newer" hidden>
  <div class="wrap newer-in"><span><b>새 브리핑</b> <span class="bt"></span></span><a href="{home}">지금 보기 →</a></div>
</div>"""


def masthead(root, t=None, eid=""):
    home = root or "./"
    links = [f'<a href="{home}">최신</a>', f'<a href="{root}archive.html">지난 브리핑</a>']
    if SITE["telegram"]:
        links.append(f'<a href="{e(SITE["telegram"])}" rel="noopener">텔레그램</a>')
    if SITE["naver_blog"]:
        links.append(f'<a href="{e(SITE["naver_blog"])}" rel="noopener">블로그</a>')
    st = ""
    if t is not None:
        st = (f'<div class="stamp"><time datetime="{t.isoformat()}">{stamp(t)}</time>'
              f'KST · {label(eid)}</div>')
    return f"""<header class="mast wrap">
  <a class="brand" href="{home}">{logo()}<span><strong>{e(SITE['name'])}</strong><span>{e(SITE['tagline'])} · 매일 06:30 / 18:00</span></span></a>
  <div class="mast-r">
    {st}
    <nav class="topnav" aria-label="사이트">{''.join(links)}<button type="button" class="install" id="install" hidden>앱 설치</button></nav>
  </div>
</header>
<p class="ioshint wrap" id="ioshint" hidden>사파리 아래쪽 <b>공유 버튼</b> → <b>홈 화면에 추가</b>를 누르면 앱처럼 쓸 수 있어요.</p>"""


def ticker(items):
    def li(x):
        v = f'<span class="v">{e(x["v"])}</span>' if x.get("v") else ""
        c = ""
        if x.get("chg"):
            cls = {"up": "tu", "dn": "td"}.get(x.get("dir", ""), "tn")
            c = f'<span class="{cls}">{e(x["chg"])}</span>'
        return f'<li><span class="k">{e(x["k"])}</span>{v}{c}</li>'
    body = "".join(li(x) for x in items)
    return f"""<div class="tape" aria-label="주요 지표">
  <div class="tape-track">
    <ul class="tape-list">{body}</ul>
    <ul class="tape-list" aria-hidden="true">{body}</ul>
  </div>
</div>"""


def tabs():
    btns = ['<button type="button" class="tab" id="tab-all" data-filter="all" aria-pressed="true">전체</button>']
    btns += [f'<button type="button" class="tab" id="tab-{c}" data-filter="{c}" aria-pressed="false">{lab}</button>'
             for c, lab in CATS]
    return f'<div class="tabbar"><nav class="tabs wrap" aria-label="섹션">{"".join(btns)}</nav></div>'


def lead_html(L):
    chips = "".join(f'<span class="chip">{e(c["k"])} <span class="num {dcls(c.get("dir"))}">{e(c["v"])}</span></span>'
                    for c in L.get("chips", []))
    body = "".join(f"<p>{e(p)}</p>" for p in L["body"])
    return f"""<article class="lead" data-cat="{e(L['cat'])}">
  <div class="kicker">{e(CAT_LABEL[L['cat']])}<span class="time">{e(L['time'])}</span></div>
  <h1>{e(L['title'])}</h1>
  <p class="dek">{e(L['dek'])}</p>
  {f'<div class="chips">{chips}</div>' if chips else ''}
  <div class="body">{body}</div>
  <div class="byline"><span>출처: {e(L['source'])}</span><a href="{e(L['url'])}" target="_blank" rel="noopener">원문 보기 ↗</a></div>
</article>"""


def story_html(s):
    badge = f'<span class="chg {dcls(s.get("dir"))}">{e(s["badge"])}</span>' if s.get("badge") else ""
    return f"""<article class="story" data-cat="{e(s['cat'])}">
  <div class="story-top"><span class="kicker">{e(CAT_LABEL[s['cat']])}</span>{badge}</div>
  <h2>{e(s['title'])}</h2>
  <p>{e(s['summary'])}</p>
  <footer><span>{e(s['source'])}</span><a href="{e(s['url'])}" target="_blank" rel="noopener">원문 ↗</a></footer>
</article>"""


def rail(ed, t, root, recent):
    def small(x):
        return "<small>" + e(x.get("sub")) + "</small>" if x.get("sub") else ""

    def note(s):
        return "<p>" + e(s.get("note")) + "</p>" if s.get("note") else ""

    rows = "".join(
        f'<tr><td>{e(x["name"])}{small(x)}</td>'
        f'<td class="{dcls(x.get("dir"))}">{e(x.get("chg") or "—")}</td></tr>'
        for x in ed["indicators"])
    movers = "".join(
        f'<li><span><span class="tk">{e(m["tk"])}</span><span class="nm">{e(m.get("nm"))}</span></span>'
        f'<span class="num {dcls(m.get("dir"))}">{e(m["chg"])}</span></li>'
        for m in ed["movers"])
    sched = "".join(
        f'<li><div class="d">{e(s["d"])}<span>{e(s.get("t"))}</span></div>'
        f'<div><b>{e(s["title"])}</b>{note(s)}</div></li>'
        for s in ed["schedule"])
    rec = "".join(
        f'<li><a href="{root}e/{r["id"]}.html"><span class="rl">{short_md(when(r))} {label(r["id"])}</span>'
        f'<span class="rt">{e(r["lead"]["title"])}</span></a></li>'
        for r in recent)
    rec_sec = (f'<section><h2>지난 브리핑</h2><ul class="recent">{rec}</ul>'
               f'<a class="more" href="{root}archive.html">전체 보기 →</a></section>') if rec else ""
    return f"""<aside class="rail">
  <section>
    <h2>시장 지표 · {short_md(t)} {t:%H:%M}</h2>
    <table class="ind"><tbody>{rows}</tbody></table>
    <p class="legend">국내 표기 관례: 빨강 ▲ 상승 · 파랑 ▼ 하락</p>
  </section>
  {f'<section><h2>특징주</h2><ul class="movers">{movers}</ul></section>' if movers else ''}
  {f'<section><h2>주요 일정 · 한국시간</h2><ul class="sched">{sched}</ul></section>' if sched else ''}
  {rec_sec}
</aside>"""


def footer(root, sources=()):
    src = ""
    if sources:
        items = "".join(f'<li><a href="{e(s["url"])}" target="_blank" rel="noopener">{e(s["name"])}</a></li>'
                        for s in sources)
        src = f"<h2>출처</h2><ul>{items}</ul>"
    return f"""<footer class="wrap foot">
  {src}
  <p>모닝테이프는 공개된 기사를 직접 요약해 하루 두 번(06:30·18:00 KST) 정리합니다. 투자 권유가 아니며, 판단 전에 원문과 실시간 시세를 확인하세요.</p>
  <p class="foot-links"><a href="{root or './'}">최신 브리핑</a><a href="{root}archive.html">지난 브리핑</a><a href="{root}feed.xml">RSS</a></p>
</footer>"""


def scripts(root, av):
    return f'<script src="{root}assets/app.js?v={av}" defer></script>\n</body>\n</html>\n'


# ------------------------------------------------------------------ pages
def edition_page(ed, root, canonical, av, prev_ed, next_ed, recent, is_index=False):
    t = when(ed)
    lab = label(ed["id"])
    L = ed["lead"]
    permalink = SITE["url"] + f"e/{ed['id']}.html"
    if is_index:
        title = f"{SITE['name']} · {SITE['tagline']} ({md(t)} {lab})"
    else:
        title = f"{md(t)} {lab} 증시 브리핑: {L['title']} | {SITE['name']}"
    ld = jsonld({
        "@context": "https://schema.org", "@type": "NewsArticle",
        "headline": L["title"][:110], "description": ed["summary"],
        "datePublished": t.isoformat(), "dateModified": t.isoformat(), "inLanguage": "ko",
        "mainEntityOfPage": permalink, "image": [SITE["url"] + "icons/og.png"],
        "author": {"@type": "Organization", "name": SITE["name"], "url": SITE["url"]},
        "publisher": {"@type": "Organization", "name": SITE["name"],
                      "logo": {"@type": "ImageObject", "url": SITE["url"] + "icons/icon-512.png"}},
    })
    nav = ""
    parts = []
    if prev_ed:
        pt = when(prev_ed)
        parts.append(f'<a href="{root}e/{prev_ed["id"]}.html">← 이전 · {short_md(pt)} {label(prev_ed["id"])}</a>')
    else:
        parts.append("<span></span>")
    if is_index:
        parts.append(f'<a href="{root}e/{ed["id"]}.html">이 판 고정 주소</a>')
    elif next_ed:
        nt = when(next_ed)
        parts.append(f'<a href="{root}e/{next_ed["id"]}.html">다음 · {short_md(nt)} {label(next_ed["id"])} →</a>')
    nav = f'<nav class="ednav" aria-label="판 이동">{"".join(parts)}</nav>'
    stories = "".join(story_html(s) for s in ed["stories"])
    return (head(title, ed["summary"], canonical, root, av, ed["id"], "article", ld)
            + banner(root) + ticker(ed["ticker"]) + masthead(root, t, ed["id"]) + tabs()
            + f"""
<main class="wrap grid">
  <div class="col-main">
    {lead_html(L)}
    <div class="stories" id="stories">{stories}</div>
    <p class="empty" id="empty" hidden>이 섹션에 표시할 기사가 없어요.</p>
    {nav}
  </div>
  {rail(ed, t, root, recent)}
</main>
""" + footer(root, ed["sources"]) + scripts(root, av))


def archive_page(eds, av):
    days = {}
    for ed in reversed(eds):
        days.setdefault(ed["id"][:10], []).append(ed)
    blocks = []
    for day, items in days.items():
        t0 = when(items[0])
        lis = "".join(
            f'<li><a href="e/{x["id"]}.html"><span class="al">{label(x["id"])} <span>{when(x):%H:%M}</span></span>'
            f'<span class="at"><b>{e(x["lead"]["title"])}</b><span>{e(x["summary"])}</span></span></a></li>'
            for x in items)
        blocks.append(f'<section class="aday"><h2>{t0:%Y.%m.%d} ({WD[t0.weekday()]})</h2><ul>{lis}</ul></section>')
    return (head(f"지난 브리핑 | {SITE['name']}", "모닝테이프가 정리한 해외증시·경제 브리핑 전체 목록",
                 SITE["url"] + "archive.html", "", av)
            + banner("") + masthead("") + f"""
<main class="wrap arch">
  <h1>지난 브리핑</h1>
  <p class="arch-dek">하루 두 번 정리한 브리핑을 모두 모았어요. 총 {len(eds)}개.</p>
  {''.join(blocks)}
</main>
""" + footer("") + scripts("", av))


def notfound_page(av):
    root = SITE["url"]
    return (head(f"페이지를 찾을 수 없어요 | {SITE['name']}", "요청한 페이지가 없습니다.", SITE["url"], root, av)
            + masthead(root) + f"""
<main class="wrap arch">
  <h1>페이지를 찾을 수 없어요</h1>
  <p class="arch-dek">주소가 바뀌었거나 지워진 페이지예요. <a href="{root}">최신 브리핑</a>이나 <a href="{root}archive.html">지난 브리핑</a>에서 찾아보세요.</p>
</main>
""" + footer(root) + scripts(root, av))


def feed_xml(eds):
    items = []
    for ed in list(reversed(eds))[:40]:
        t = when(ed)
        link = SITE["url"] + f"e/{ed['id']}.html"
        items.append(f"""<item><title>{e(md(t) + ' ' + label(ed['id']) + ' · ' + ed['lead']['title'])}</title>
<link>{link}</link><guid isPermaLink="true">{link}</guid>
<pubDate>{format_datetime(t)}</pubDate><description>{e(ed['summary'])}</description></item>""")
    last = format_datetime(when(eds[-1]))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>{e(SITE['name'])}</title><link>{SITE['url']}</link>
<description>{e(SITE['tagline'])} · 매일 06:30 / 18:00 KST</description>
<language>ko</language><lastBuildDate>{last}</lastBuildDate>
{''.join(items)}
</channel></rss>
"""


def sitemap_xml(eds):
    urls = [(SITE["url"], when(eds[-1])), (SITE["url"] + "archive.html", when(eds[-1]))]
    urls += [(SITE["url"] + f"e/{x['id']}.html", when(x)) for x in reversed(eds)]
    body = "".join(f"<url><loc>{u}</loc><lastmod>{t.isoformat()}</lastmod></url>" for u, t in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>\n'


def sw_js(av):
    tpl = (ROOT / "assets" / "sw.template.js").read_text(encoding="utf-8")
    return tpl.replace("__VERSION__", av)


# ------------------------------------------------------------------ main
def main():
    eds, errors = [], []
    files = sorted(DATA.glob("*.json"))
    if not files:
        print("data/editions 에 JSON이 없습니다.")
        return 1
    for f in files:
        try:
            ed = json.loads(f.read_text(encoding="utf-8"))
        except Exception as ex:
            errors.append(f"{f.name}: JSON 문법 오류 → {ex}")
            continue
        errs = validate(ed, f.name)
        if errs:
            errors += [f"{f.name}: {x}" for x in errs]
        else:
            eds.append(ed)
    if errors:
        print("오류가 있어 사이트를 만들지 않았습니다:")
        print("\n".join("  - " + x for x in errors))
        return 1
    eds.sort(key=lambda x: x["id"])
    for w in warnings(eds[-1]):
        print("경고:", w)

    h = hashlib.sha1()
    for p in ("assets/style.css", "assets/app.js", "assets/sw.template.js", "manifest.webmanifest"):
        h.update((ROOT / p).read_bytes())
    av = h.hexdigest()[:8]

    out = {}
    (ROOT / "e").mkdir(exist_ok=True)
    for i, ed in enumerate(eds):
        prev_ed = eds[i - 1] if i > 0 else None
        next_ed = eds[i + 1] if i + 1 < len(eds) else None
        recent = [x for x in reversed(eds) if x["id"] != ed["id"]][:6]
        out[f"e/{ed['id']}.html"] = edition_page(
            ed, "../", SITE["url"] + f"e/{ed['id']}.html", av, prev_ed, next_ed, recent)
    latest = eds[-1]
    recent = [x for x in reversed(eds) if x["id"] != latest["id"]][:6]
    out["index.html"] = edition_page(latest, "", SITE["url"], av,
                                     eds[-2] if len(eds) > 1 else None, None, recent, is_index=True)
    out["archive.html"] = archive_page(eds, av)
    out["404.html"] = notfound_page(av)
    lt = when(latest)
    out["latest.json"] = json.dumps({
        "id": latest["id"], "label": f"{short_md(lt)} {label(latest['id'])}",
        "title": latest["lead"]["title"], "stamp": stamp(lt),
        "url": SITE["url"] + f"e/{latest['id']}.html"}, ensure_ascii=False) + "\n"
    out["feed.xml"] = feed_xml(eds)
    out["sitemap.xml"] = sitemap_xml(eds)
    out["robots.txt"] = f"User-agent: *\nAllow: /\nSitemap: {SITE['url']}sitemap.xml\n"
    out["sw.js"] = sw_js(av)

    for rel, text in out.items():
        (ROOT / rel).write_text(text, encoding="utf-8")
    print(f"완료: 판 {len(eds)}개, 최신 {latest['id']} ({label(latest['id'])}), 파일 {len(out)}개 생성")
    return 0


if __name__ == "__main__":
    sys.exit(main())
