#!/usr/bin/env python3
"""Builds the aws-book.com short-link site (GitHub Pages, repo 0feklevy/aws-book).

  aws-book.com/              -> the book page
  aws-book.com/<n>           -> simulation n (the number on its card / QR code), also /01, /sim1, /simulation-1 ...
  aws-book.com/<words>       -> resolved like the book page's search box:
      * the exact name or folder of one sim (/temperature-knob, /gradient-descent) -> that sim
      * the search finds exactly one sim (/theory-of-mind, /white-gold)            -> that sim
      * the search finds several (/ising, /bacteria, /annealing)                  -> the book page
        with the search filled in (book/index.html?q=ising), showing all of them
      * otherwise an extra alias below (/isingknob, /knob) or a near spelling     -> that sim
      * nothing                                                                   -> the book page
  Case, dashes, underscores, spaces, camelCase and Hebrew all work.

The list of sims and their search keywords are read from ../../index.html (SIMS and KEYWORDS),
so the numbers and search stay in step with the book page. Rebuild and push after changing them:
    python3 build.py <out-dir>
"""
import json, re, sys, shutil, unicodedata
from pathlib import Path
from urllib.parse import quote

BOOK = "https://science-of-awe.com/book/"
INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"

# Extra spellings that go straight to one sim when the search alone would not find it
# (glued words, abbreviations, old folder names). Keyed by href as in index.html.
EXTRA = {
    "guidance/knob-ising/": ["knob ising", "ising knob", "temperature", "temperature ising", "ising temperature",
                             "temp knob", "temperature dial", "ising dial", "knob"],
    "guidance/murmuration-knob/": ["murmuration knob", "knob murmuration", "flock knob", "boids knob", "flock dial"],
    "guidance/pluck-ising/": ["pluck ising", "ising pluck", "twins"],
    "guidance/pluck-boids/": ["pluck boids", "boids pluck", "pluck boids v2", "pluck flock", "pluck"],
    "guidance/ising-disagree/": ["ising disagree", "ising kid disagree", "disagree"],
    "guidance/flagellar/": ["flagellar motor", "flagella"],
    "guidance/boids-3d/": ["boids 3d", "3d boids", "starling pov", "murmuration pov"],
    "guidance/annealing/": ["atom annealing", "metal annealing"],
    "guidance/compare/": ["compare ising", "ising compare"],
    "guidance/dress/": ["dress demo"],
    "guidance/gradient/": ["ee3d", "gradient descent"],
    "guidance/scaling/": ["ising scaling", "ising scalling"],
    "guidance/kinesin/": ["kinesin dynein", "motor ratchet"],
    "guidance/vae/": ["vae digits", "vae digit"],
    "guidance/gossip-network/": ["gossip"],
    "guidance/central-dogma/": ["dogma"],
    "guidance/horizontal-transfer/": ["hgt", "gene transfer"],
    "guidance/nn-pdc/": ["nnpdc", "pdc", "predictive coding"],
    "guidance/mouse-lab/": ["tmaze", "t maze", "mouse lab"],
    "guidance/neurons/": ["neuron"],
    "guidance/chignolin/": ["protein journey", "proteins journey", "3d protein process", "protein"],
    "guidance/tom-game/": ["tom", "tomgame", "theory of mind"],
    "guidance/chemotaxis/": ["chemo"],
    "https://enrichtube.com/unlocking-the-secrets-of-starling-behavior": ["starling behaviour"],
    "https://enrichtube.com/effective-communication": ["edge of chaos"],
    "guidance/brian-park/": ["brian", "brian park"],
}
NUM_PREFIXES = ["", "sim", "simulation", "s", "qr", "no", "num", "number", "chapter", "ch", "page", "p", "n"]
HOME_WORDS = ["", "book", "index", "home", "all", "simulations", "sims", "list", "awe", "science of awe"]


def norm(s):
    """Same as norm() in index.html: lowercase, no accents / niqqud, letters and digits only."""
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(s))      # camelCase -> camel case (path segments)
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c) and not "֑" <= c <= "ׇ")
    return " ".join(re.split(r"[\W_]+", s)).strip()


def key(s):
    return norm(s).replace(" ", "")


def read_sims():
    html = INDEX_HTML.read_text()
    block = html.split("const SIMS = [", 1)[1].split("];", 1)[0]
    sims = []
    for obj in re.findall(r"\{(.*?)\}", block, re.S):
        get = lambda f: re.search(f + r':\s*"((?:[^"\\]|\\.)*)"', obj, re.S).group(1)
        sims.append({"href": get("href"), "name": get("name"), "blurb": get("blurb")})
    kw_block = html.split("const KEYWORDS = {", 1)[1].split("};", 1)[0]
    kws = dict(re.findall(r'"([^"]+)":\s*"([^"]*)"', kw_block))
    for s in sims:
        path_words = re.sub(r"^.*?//[^/]+|guidance|[-/]", " ", s["href"])
        s["words"] = sorted(set(norm(" ".join([s["name"], s["blurb"], kws.get(s["href"], ""), path_words])).split()))
        s["url"] = s["href"] if s["href"].startswith("http") else BOOK + s["href"]
    return sims


def find_sims(sims, q):
    """Same as findSims() in index.html: every query word starts some word (or sits inside one, from 3 letters)."""
    terms = norm(q).split()
    if not terms:
        return []
    return [i for i, s in enumerate(sims)
            if all(any(w.startswith(t) or (len(t) >= 3 and t in w) for w in s["words"]) for t in terms)]


def main(out):
    sims = read_sims()
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    direct, extra = {}, {}            # key -> sim index
    for i, s in enumerate(sims):
        for n in (str(i + 1), f"{i + 1:02d}"):
            for p in NUM_PREFIXES:
                direct[key(p + n)] = i
        direct[key(s["name"])] = i
        direct.setdefault(key(s["href"].rstrip("/").split("/")[-1]), i)
        for a in EXTRA.get(s["href"], []):
            if key(a) in extra and extra[key(a)] != i:
                sys.exit(f"alias clash: {a!r}")
            extra[key(a)] = i
    if set(EXTRA) - {s["href"] for s in sims}:
        sys.exit(f"EXTRA has hrefs not in index.html: {set(EXTRA) - {s['href'] for s in sims}}")

    def resolve(path_words):
        k = path_words.replace(" ", "")
        if k in (key(h) for h in HOME_WORDS):
            return BOOK
        if k in direct:
            return sims[direct[k]]["url"]
        hits = find_sims(sims, path_words)
        if len(hits) == 1:
            return sims[hits[0]]["url"]
        if hits:
            return BOOK + "index.html?q=" + quote(path_words)
        if k in extra:
            return sims[extra[k]]["url"]
        return None                    # 404.html tries near spellings, then the book page

    # Pre-built folders (answer 200) for every known spelling, glued and dashed.
    phrases = set()
    for s in sims:
        phrases.update([s["name"], s["href"].rstrip("/").split("/")[-1]] + EXTRA.get(s["href"], []))
        phrases.update(s["words"])
    built = {}
    for ph in phrases:
        w = norm(ph)
        if not w or not w.isascii():
            continue
        url = resolve(w)
        if url:
            for folder in {w.replace(" ", ""), w.replace(" ", "-")}:
                built[folder] = url
    for k in direct:
        built[k] = resolve(k)
    for folder, url in built.items():
        (out / folder).mkdir(exist_ok=True)
        (out / folder / "index.html").write_text(page(url))
    (out / "index.html").write_text(page(BOOK))

    data = {"book": BOOK, "home": [key(h) for h in HOME_WORDS],
            "sims": [{"u": s["url"], "w": s["words"]} for s in sims],
            "direct": direct, "extra": extra}
    (out / "404.html").write_text(NOT_FOUND.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":"))))
    (out / "CNAME").write_text("aws-book.com\n")
    (out / ".nojekyll").write_text("")
    (out / "links.txt").write_text("".join(f"/{f}  ->  {u}\n" for f, u in sorted(built.items(), key=lambda x: (x[1], x[0]))))
    shutil.copy(__file__, out / "build.py")
    print(f"{len(sims)} sims, {len(built)} pre-built links -> {out}")


def page(url):
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>AWEscience</title><meta name="robots" content="noindex">
<meta http-equiv="refresh" content="0; url={url}"><link rel="canonical" href="{url}">
<script>location.replace({json.dumps(url)})</script>
</head><body><a href="{url}">{url}</a></body></html>
"""


NOT_FOUND = r"""<!doctype html><html><head><meta charset="utf-8"><title>AWEscience</title>
<meta name="robots" content="noindex">
<script>
(function () {
  var D = __DATA__;
  function norm(s) {
    return String(s).replace(/([a-z])([A-Z])/g, "$1 $2").toLowerCase().normalize("NFKD")
      .replace(/[̀-֑ͯ-ׇ]/g, "").replace(/[^\p{L}\p{N}]+/gu, " ").trim();
  }
  function find(q) {
    var terms = norm(q).split(" ").filter(Boolean), hits = [];
    if (!terms.length) return hits;
    D.sims.forEach(function (s, i) {
      if (terms.every(function (t) {
        return s.w.some(function (w) { return w.indexOf(t) === 0 || (t.length >= 3 && w.indexOf(t) >= 0); });
      })) hits.push(i);
    });
    return hits;
  }
  function lev(a, b) {
    var d = [], i, j;
    for (i = 0; i <= a.length; i++) d[i] = [i];
    for (j = 0; j <= b.length; j++) d[0][j] = j;
    for (i = 1; i <= a.length; i++)
      for (j = 1; j <= b.length; j++)
        d[i][j] = Math.min(d[i-1][j] + 1, d[i][j-1] + 1, d[i-1][j-1] + (a[i-1] === b[j-1] ? 0 : 1));
    return d[a.length][b.length];
  }
  function resolve(words) {
    var k = words.replace(/ /g, "");
    if (D.home.indexOf(k) >= 0) return D.book;
    if (k in D.direct) return D.sims[D.direct[k]].u;
    var m = /^\D*0*(\d+)$/.exec(k);
    if (m && m[1] in D.direct) return D.sims[D.direct[m[1]]].u;
    var hits = find(words);
    if (hits.length === 1) return D.sims[hits[0]].u;
    if (hits.length) return D.book + "index.html?q=" + encodeURIComponent(words);
    if (k in D.extra) return D.sims[D.extra[k]].u;
    return null;
  }
  function near(words) {             // small typo: the closest name / alias, if close enough
    var k = words.replace(/ /g, ""), best = null, bd = 99, a, d;
    if (k.length < 4) return null;
    var all = Object.assign({}, D.extra, D.direct);
    for (a in all) { if (a.length < 3) continue; d = lev(k, a); if (d < bd) { bd = d; best = a; } }
    return best && bd <= Math.max(1, Math.floor(k.length / 5)) ? D.sims[all[best]].u : null;
  }
  var raw = location.pathname;
  try { raw = decodeURIComponent(raw); } catch (e) {}
  var segs = raw.split("/").filter(Boolean).map(norm).filter(Boolean);
  // The whole path first, then each segment from the end (/book/1, /sim/ising-knob).
  var tries = [segs.join(" ")].concat(segs.slice().reverse()), url = null, t;
  for (t = 0; t < tries.length && !url; t++) url = resolve(tries[t]);
  for (t = 0; t < tries.length && !url; t++) url = near(tries[t]);
  location.replace(url || D.book);
})();
</script></head><body></body></html>
"""

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "site")
