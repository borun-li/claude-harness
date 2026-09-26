"""Parsing of the phase documents. Everything keys on ids (REQ-/DES-/TC-/FND-), so the
parsers work whether the prose is English or Chinese."""
import pathlib
import re

HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", re.M)
RETIRED = re.compile(r"\bretired\b|已退役|已废弃", re.I)
CUT = re.compile(r"\bcut\b\W{0,6}(above|below)\b", re.I)
SIDE = re.compile(r"\bside\b\W{0,6}(backend|frontend)\b", re.I)
AUTOMATED = re.compile(r"\bautomated\b|自动化", re.I)
MANUAL = re.compile(r"\bmanual\b|手动|人工", re.I)
FIXTURES = re.compile(r"\bfixtures?\b[:*\s]{0,6}([^\n]*)", re.I)
NA = re.compile(r"^n/?a\b\W*(\S.{2,})", re.I)
GWT = [(re.compile(r"\bgiven\b", re.I), re.compile(r"\bwhen\b", re.I), re.compile(r"\bthen\b", re.I)),
       (re.compile(r"给定|假如|假设"), re.compile(r"当"), re.compile(r"那么|则"))]


def read(path):
    p = pathlib.Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else None


def nontrivial(text, min_lines):
    return text is not None and sum(1 for l in text.splitlines() if l.strip()) >= min_lines


FENCE = re.compile(r"^\s*(```|~~~)")
WORD = re.compile(r"[A-Za-z0-9_]+(?:['’.-][A-Za-z0-9_]+)*")
CJK = re.compile(r"[\u3400-\u9fff]")


def mask_code(text):
    """Blank out fenced code (same length, newlines kept) so offsets stay valid."""
    out, inside = [], False
    for line in text.splitlines(keepends=True):
        fence = bool(FENCE.match(line))
        body = line.rstrip("\n")
        out.append(" " * len(body) + line[len(body):] if inside or fence else line)
        if fence:
            inside = not inside
    return "".join(out)


def headings(text):
    return [(len(m.group(1)), m.group(2), m.start(), m.end()) for m in HEADING.finditer(mask_code(text))]


def words(text):
    """Word count outside code: Latin words plus CJK characters at two per word."""
    t = mask_code(text)
    return len(WORD.findall(t)) + (len(CJK.findall(t)) + 1) // 2


def prose_units(text):
    """(first line, word count) for every paragraph and list item outside code, tables and headings."""
    units, cur = [], []
    def flush():
        if cur:
            units.append((cur[0].strip()[:70], words(" ".join(cur))))
            cur.clear()
    for line in mask_code(text).splitlines():
        s = line.strip()
        if not s or s.startswith(("#", "|", ">")) or re.fullmatch(r"-{3,}", s):
            flush()
        elif re.match(r"([-*+]|\d+\.)\s", s):
            flush()
            cur.append(s)
        else:
            cur.append(s)
    flush()
    return units


def _block_end(hs, i, text):
    level = hs[i][0]
    for lvl, _, start, _ in hs[i + 1:]:
        if lvl <= level:
            return start
    return len(text)


def id_blocks(text, prefix):
    """{id: [block, ...]} for every heading whose title starts with PREFIX-nnn."""
    rx = re.compile(r"^\W*(%s-\d+)\b" % prefix)
    hs, out = headings(text), {}
    for i, (_, title, start, _) in enumerate(hs):
        m = rx.match(title)
        if m:
            out.setdefault(m.group(1), []).append(text[start:_block_end(hs, i, text)])
    return out


def ids_in(text, prefix):
    return set(re.findall(r"\b%s-\d+\b" % prefix, text or ""))


def table_rows(text):
    """Data rows of every markdown table in text (header and separator rows dropped)."""
    rows, in_table = [], False
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            in_table = False
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        if not in_table:
            in_table = True  # header row
            continue
        rows.append(cells)
    return rows


def field(block, name):
    """Value of a `**Name:**` line, or None if absent or still a template placeholder."""
    m = re.search(r"\*\*%s:?\*\*:?[ \t]*([^\n]*)" % re.escape(name), block or "", re.I)
    v = m.group(1).strip() if m else ""
    return None if not v or v.startswith(("{", "<")) else v


def has_gwt(block):
    return any(all(rx.search(block) for rx in trio) for trio in GWT)


def requirements(text):
    """Parsed REQs: {id: {"blocks": n, "retired": bool, "cut": above|below|None, "gwt": bool,
    "interface": bool}}."""
    out = {}
    for rid, blocks in id_blocks(text, "REQ").items():
        b = blocks[0]
        m = CUT.search(b)
        out[rid] = {"blocks": len(blocks), "retired": bool(RETIRED.search(b.splitlines()[0]) or
                                                          re.search(r"\*\*status\W{0,6}retired", b, re.I)),
                    "cut": m.group(1).lower() if m else None, "gwt": has_gwt(b),
                    "interface": "[interface]" in b, "source": _source(b), "words": words(b),
                    **_fixtures(b)}
    return out


def _source(block):
    """The Source value if it quotes the user or cites an artifact, else None."""
    m = re.search(r"\bsource\b[:*\s]{0,6}([^\n]*)", block, re.I)
    v = m.group(1).strip() if m else ""
    quoted = re.search(r"[\"“”「」『』'‘’]", v)
    cited = re.search(r"[\w-]+\.(md|txt|pdf|docx?)\b|§|/", v)
    return v if v and not v.startswith(("<", "{")) and (quoted or cited) else None


def _fixtures(block):
    """Fixtures field: {"fixtures": [FX ids] | None if the field is absent, "fixtures_na": reason}."""
    m = FIXTURES.search(block)
    if not m:
        return {"fixtures": None, "fixtures_na": None}
    value = m.group(1).strip()
    na = NA.match(value)
    return {"fixtures": sorted(ids_in(value, "FX")), "fixtures_na": na.group(1).strip() if na else None}


def active_reqs(reqs):
    """REQs this round must deliver: not retired, above the cut line."""
    return {r for r, v in reqs.items() if not v["retired"] and v["cut"] == "above"}


def designs(text):
    out = {}
    for did, blocks in id_blocks(text, "DES").items():
        b = blocks[0]
        m = SIDE.search(b)
        out[did] = {"blocks": len(blocks), "serves": ids_in(mask_code(b), "REQ"),
                    "side": m.group(1).lower() if m else None, "words": words(b)}
    return out


def testcases(text):
    out = {}
    for tid, blocks in id_blocks(text, "TC").items():
        b = blocks[0]
        mode = "automated" if AUTOMATED.search(b) else ("manual" if MANUAL.search(b) else None)
        out[tid] = {"blocks": len(blocks), "verifies": ids_in(b, "REQ"), "mode": mode}
    return out


def report_results(text):
    """{TC: pass|fail|blocked} from the results table of 05-test-report.md."""
    out = {}
    for cells in table_rows(text or ""):
        tcs = [c for c in cells if re.fullmatch(r"TC-\d+", c)]
        verdict = next((c.lower() for c in cells if c.lower() in ("pass", "fail", "blocked")), None)
        if tcs and verdict:
            out[tcs[0]] = verdict
    return out


def findings(text):
    """{FND: {"severity", "where", "req", "status", "scenario"}} from 06-review-report.md."""
    out = {}
    for cells in table_rows(text or ""):
        if cells and re.fullmatch(r"FND-\d+", cells[0]) and len(cells) >= 5:
            out[cells[0]] = {"severity": cells[1].lower(), "where": cells[3], "req": cells[4],
                             "status": None, "scenario": False}
    for fid, blocks in id_blocks(text or "", "FND").items():
        b = blocks[0]
        st = re.search(r"\bstatus\b\W{0,6}([^\n]*)", b, re.I)
        sc = re.search(r"\bscenario\b\W{0,6}(\S[^\n]*)", b, re.I)
        entry = out.setdefault(fid, {"severity": None, "where": None, "req": None})
        entry["status"] = st.group(1).strip().lower() if st else None
        entry["scenario"] = bool(sc and not sc.group(1).startswith(("<", "{")))
    return out
