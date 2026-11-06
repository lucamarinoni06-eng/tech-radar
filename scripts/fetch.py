#!/usr/bin/env python3
"""Scarica dati live (SEC, EPO, Federal Register, news) per le aziende in docs/data/companies.json.
Uso: python scripts/fetch.py [TICKER ...]
Variabili d'ambiente: SEC_USER_AGENT ("Nome Cognome email"), EPO_KEY, EPO_SECRET."""
import os, sys, json, time, base64, datetime as dt
import urllib.request, urllib.parse, urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
LIVE = DATA / "live"
SEC_UA = os.environ.get("SEC_USER_AGENT", "")
EPO_KEY = os.environ.get("EPO_KEY", "")
EPO_SECRET = os.environ.get("EPO_SECRET", "")


def http(url, headers=None, data=None, retries=3, timeout=30):
    h = {"User-Agent": SEC_UA or "tech-radar/1.0"}
    h.update(headers or {})
    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and i < retries - 1:
                time.sleep(2 * (i + 1)); continue
            raise
        except urllib.error.URLError:
            if i < retries - 1:
                time.sleep(2 * (i + 1)); continue
            raise


def jget(url, **kw):
    return json.loads(http(url, **kw))


# ---------- SEC EDGAR ----------
FORMS = ("10-K", "10-Q", "8-K", "DEF 14A")
TAGS = {
    "ricavi": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"],
    "utile_operativo": ["OperatingIncomeLoss"],
    "utile_netto": ["NetIncomeLoss"],
    "ricerca_sviluppo": ["ResearchAndDevelopmentExpense"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
}


def sec_filings(cik):
    r = jget(f"https://data.sec.gov/submissions/CIK{cik}.json")["filings"]["recent"]
    out = []
    for form, date, acc, doc in zip(r["form"], r["filingDate"], r["accessionNumber"], r["primaryDocument"]):
        if form in FORMS:
            out.append({"tipo": form, "data": date,
                        "link": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}"})
        if len(out) >= 12:
            break
    return out


def sec_financials(cik):
    facts = jget(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")["facts"].get("us-gaap", {})
    out = {}
    for key, tags in TAGS.items():
        rows = {}
        for t in tags:
            for e in facts.get(t, {}).get("units", {}).get("USD", []):
                if e.get("form") != "10-K" or "start" not in e:
                    continue
                days = (dt.date.fromisoformat(e["end"]) - dt.date.fromisoformat(e["start"])).days
                if 350 <= days <= 380 and e["end"] not in rows:
                    rows[e["end"]] = e["val"]
        if rows:
            out[key] = dict(sorted(rows.items())[-4:])
    return out


# ---------- EPO OPS (brevetti) ----------
def epo_token():
    cred = base64.b64encode(f"{EPO_KEY}:{EPO_SECRET}".encode()).decode()
    d = jget("https://ops.epo.org/3.2/auth/accesstoken",
             headers={"Authorization": "Basic " + cred, "Content-Type": "application/x-www-form-urlencoded"},
             data=b"grant_type=client_credentials")
    return d["access_token"]


def epo_count(tok, q):
    url = "https://ops.epo.org/3.2/rest-services/published-data/search?" + urllib.parse.urlencode({"q": q, "Range": "1-1"})
    try:
        d = jget(url, headers={"Authorization": "Bearer " + tok, "Accept": "application/json"})
        return int(d["ops:world-patent-data"]["ops:biblio-search"]["@total-result-count"])
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return 0
        raise


def patents(c):
    tok = epo_token()
    pa = "(" + " or ".join(f'pa="{n}"' for n in c["brevetti"]) + ")"
    y = dt.date.today().year
    per_anno = {str(a): epo_count(tok, f"{pa} and pd={a}") for a in range(y - 3, y + 1)}
    per_classe = {k: epo_count(tok, f"{pa} and cl={k} and pd={y - 1}") for k in c["cpc"]}
    link = "https://worldwide.espacenet.com/patent/search?q=" + urllib.parse.quote(f"pa={c['brevetti'][0]}")
    return {"per_anno": per_anno, "per_classe_anno_precedente": per_classe, "anno_classi": y - 1, "link": link}


# ---------- Federal Register (norme USA) ----------
def federal_register(term, n=8):
    q = urllib.parse.urlencode({"conditions[term]": term, "order": "newest", "per_page": n})
    d = jget("https://www.federalregister.gov/api/v1/documents.json?" + q)
    return [{"titolo": x.get("title"), "data": x.get("publication_date"), "tipo": x.get("type"),
             "agenzie": [a.get("name") for a in x.get("agencies", [])], "link": x.get("html_url")}
            for x in d.get("results", [])]


# ---------- News (Google News RSS) ----------
def news(q, n=10):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": "it", "gl": "IT", "ceid": "IT:it"})
    root = ET.fromstring(http(url))
    out = []
    for it in root.iter("item"):
        s = it.find("source")
        out.append({"titolo": it.findtext("title"), "link": it.findtext("link"),
                    "data": it.findtext("pubDate"), "fonte": s.text if s is not None else ""})
        if len(out) >= n:
            break
    return out


def step(res, name, fn):
    try:
        res[name] = fn()
    except Exception as e:  # una fonte che fallisce non blocca le altre
        res.setdefault("errori", {})[name] = f"{type(e).__name__}: {e}"


def run_company(c):
    res = {"aggiornato": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    if SEC_UA:
        step(res, "filing", lambda: sec_filings(c["cik"]))
        step(res, "bilancio", lambda: sec_financials(c["cik"]))
    else:
        res.setdefault("errori", {})["sec"] = "SEC_USER_AGENT non impostato"
    if EPO_KEY and EPO_SECRET:
        step(res, "brevetti", lambda: patents(c))
    else:
        res.setdefault("errori", {})["brevetti"] = "EPO_KEY/EPO_SECRET non impostati"
    step(res, "norme_usa", lambda: [d for t in c["fr_terms"] for d in federal_register(t, 6)])
    n = c["nome"]
    step(res, "news", lambda: news(f'"{n}" when:30d'))
    step(res, "news_legali", lambda: news(f'"{n}" (antitrust OR regulation OR lawsuit OR investigation OR fine) when:60d'))
    step(res, "news_brevetti", lambda: news(f'"{n}" (patent OR brevetto) when:90d', 6))
    return res


def main():
    cfg = json.load(open(DATA / "companies.json", encoding="utf-8"))
    LIVE.mkdir(parents=True, exist_ok=True)
    only = {a.upper() for a in sys.argv[1:]}
    for c in cfg["aziende"]:
        if only and c["ticker"] not in only:
            continue
        print("→", c["ticker"])
        (LIVE / f"{c['ticker']}.json").write_text(json.dumps(run_company(c), ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(1)
    if not only:
        s = cfg["settore"]
        res = {"aggiornato": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        step(res, "news", lambda: news(s["news_query"] + " when:14d", 12))
        step(res, "norme_usa", lambda: [d for t in s["fr_terms"] for d in federal_register(t, 6)])
        (LIVE / "_settore.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
