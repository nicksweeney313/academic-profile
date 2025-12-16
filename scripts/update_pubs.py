import json, re
from pathlib import Path
import requests
import bibtexparser

ORCID = Path("data/orcid.txt").read_text().strip()
OPENALEX = "https://api.openalex.org/works"

OUT_AUTO_PUBS = Path("bib/auto_publications.bib")
OUT_AUTO_WPS  = Path("bib/auto_working_papers.bib")
OUT_JSON      = Path("site/publications.json")

MANUAL_BIBS = [Path("bib/manual_publications.bib"), Path("bib/manual_working_papers.bib")]

def normalise_title(t: str) -> str:
    t = (t or "").lower()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[^a-z0-9 ]", "", t)
    return t.strip()

def read_manual_keys():
    """Return sets of DOIs and normalised titles from manual bib files (manual wins)."""
    import bibtexparser
    from bibtexparser.bparser import BibTexParser

    dois, titles = set(), set()
    parser = BibTexParser(common_strings=True)
    parser.expect_multiple_parse = True

    for p in MANUAL_BIBS:
        if not p.exists():
            continue

        text = p.read_text(encoding="utf-8")
        bib_db = bibtexparser.loads(text, parser=parser)

        for e in (bib_db.entries or []):
            doi = (e.get("doi") or "").strip().lower()
            if doi:
                doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
                dois.add(doi)
            titles.add(normalise_title(e.get("title", "")))

    return dois, titles



def fetch(orcid: str):
    r = requests.get(
        OPENALEX,
        params={"filter": f"author.orcid:{orcid}", "per-page": 200, "sort": "publication_date:desc"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("results", [])

def authors_to_bib(authorships):
    names = []
    for a in authorships or []:
        n = a.get("author", {}).get("display_name")
        if n:
            names.append(n)
    return " and ".join(names)

def work_to_entry(w):
    doi = (w.get("doi") or "").strip()
    doi_clean = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").lower() if doi else ""
    title = w.get("title") or ""
    year = w.get("publication_year") or ""
    date = w.get("publication_date") or ""
    cited_by = w.get("cited_by_count")
    wtype = (w.get("type") or "").lower()
    journal = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or ""

    if wtype == "journal-article":
        keywords, entrytype = ["publication"], "article"
    else:
        keywords, entrytype = ["workingpaper"], "unpublished"

    first_author = (w.get("authorships") or [{}])[0].get("author", {}).get("display_name", "author")
    surname = (first_author.split() or ["author"])[-1].lower()
    key = f"{surname}{year}{re.sub(r'[^a-z0-9]+','', normalise_title(title)[:24])}"

    entry = {"ENTRYTYPE": entrytype, "ID": key, "title": title, "author": authors_to_bib(w.get("authorships"))}
    if year: entry["year"] = str(year)
    if journal and entrytype == "article": entry["journal"] = journal
    if doi_clean: entry["doi"] = doi_clean
    if date: entry["date"] = date
    if cited_by is not None: entry["note"] = f"Cited by {cited_by}"
    entry["keywords"] = ",".join(keywords)

    web = {
        "id": key, "title": title, "year": year, "date": date, "venue": journal,
        "doi": doi_clean, "doi_url": f"https://doi.org/{doi_clean}" if doi_clean else None,
        "cited_by_count": cited_by, "keywords": keywords,
        "authors": [a.get("author", {}).get("display_name") for a in (w.get("authorships") or []) if a.get("author", {}).get("display_name")],
        "type": wtype,
    }
    return entry, web

def write_bib(entries, path: Path):
    import bibtexparser
    from bibtexparser.bwriter import BibTexWriter
    from bibtexparser.bibdatabase import BibDatabase

    db = BibDatabase()
    db.entries = entries

    writer = BibTexWriter()
    writer.indent = "  "
    writer.order_entries_by = ("year", "ID")  # optional; you can remove if you like

    path.write_text(bibtexparser.dumps(db, writer=writer), encoding="utf-8")

def main():
    if not ORCID:
        raise SystemExit("Put your ORCID in data/orcid.txt")
    manual_dois, manual_titles = read_manual_keys()
    works = fetch(ORCID)

    pubs, wps, web_items = [], [], []
    for w in works:
        entry, web = work_to_entry(w)
        if web["doi"] and web["doi"] in manual_dois:
            continue
        if normalise_title(web["title"]) in manual_titles:
            continue
        (pubs if "publication" in web["keywords"] else wps).append(entry)
        web_items.append(web)

    write_bib(pubs, OUT_AUTO_PUBS)
    write_bib(wps, OUT_AUTO_WPS)
    OUT_JSON.write_text(json.dumps(web_items, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_AUTO_PUBS} ({len(pubs)})")
    print(f"Wrote {OUT_AUTO_WPS} ({len(wps)})")
    print(f"Wrote {OUT_JSON} ({len(web_items)})")

if __name__ == "__main__":
    main()
