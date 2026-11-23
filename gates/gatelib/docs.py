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


# One word each: an inline code span, a URL, a path (`docs/x/evidence/Q-3-1440.png` is not five words).
ATOM = re.compile(r"`[^`\n]+`|https?://[!-~]+|[\w.@~%+-]*(?:/[A-Za-z0-9_.@~%+-]+)+/?", re.A)


def words(text):
    """Word count outside fenced code: Latin words plus CJK characters at two per word. An inline
    code span, a URL and a path each count as one word."""
    t, atoms = ATOM.subn(" ", mask_code(text))
    return atoms + len(WORD.findall(t)) + (len(CJK.findall(t)) + 1) // 2


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


def line_field(block, name):
    """Value of a field written at the start of a line, bold or not (`- **Status:** x`, `Status: x`),
    or None if absent or a template placeholder."""
    m = re.search(r"^[ \t]*(?:[-*+][ \t]+)?\**%s\**[ \t]*[:：]\**[ \t]*([^\n]*)" % re.escape(name),
                  block or "", re.I | re.M)
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


def claimed(block, name):
    """REQ ids a block claims: those on its `**<name>:**` line, so a REQ mentioned in passing ("keeps
    REQ-004 from the last round working") is not a claim. No such line: the whole block, outside code."""
    line = field(block, name)
    return ids_in(line, "REQ") if line else ids_in(mask_code(block), "REQ")


def designs(text):
    out = {}
    for did, blocks in id_blocks(text, "DES").items():
        b = blocks[0]
        m = SIDE.search(b)
        out[did] = {"blocks": len(blocks), "serves": claimed(b, "Serves"),
                    "side": m.group(1).lower() if m else None, "words": words(b)}
    return out


def testcases(text):
    out = {}
    for tid, blocks in id_blocks(text, "TC").items():
        b = blocks[0]
        out[tid] = {"blocks": len(blocks), "verifies": claimed(b, "Verifies"), "mode": _mode(b)}
    return out


def _mode(block):
    """automated | manual | None, read from the `**Mode:**` field alone when there is one (the word it
    names first), so "automated" in the body does not turn a manual case automated. No such field:
    the whole block, as `claimed` does."""
    value = field(block, "Mode") or line_field(block, "Mode")
    if value is None:
        return "automated" if AUTOMATED.search(block) else ("manual" if MANUAL.search(block) else None)
    hits = sorted((m.start(), mode) for mode, rx in (("automated", AUTOMATED), ("manual", MANUAL))
                  for m in [rx.search(value)] if m)
    return hits[0][1] if hits else None


# A verdict cell: the word alone, in any case, bold or in backticks, after a status mark or not.
VERDICTS = {"pass": "pass", "passed": "pass", "fail": "fail", "failed": "fail", "blocked": "blocked"}
VERDICT = re.compile(r"[\s*`\u2705\u274c\u26a0\ufe0f\u2713\u2714\u2717\u2718]*(%s)[\s*`]*" % "|".join(VERDICTS),
                     re.I)


def _verdict(cell):
    """pass | fail | blocked for a cell that holds exactly one verdict (`passed`, `**PASS**`,
    `✅ pass`), else None: `pass / fail` is two verdicts, so none."""
    m = VERDICT.fullmatch(cell)
    return VERDICTS[m.group(1).lower()] if m else None


def report_results(text):
    """{TC: pass|fail|blocked} from the tables of 05-test-report.md. A TC whose rows disagree (an old
    round's table left beside the current one) is `conflict: <verdicts>`, never silently the last row."""
    seen = {}
    for cells in table_rows(text or ""):
        tcs = [c for c in cells if re.fullmatch(r"TC-\d+", c)]
        verdict = next((v for v in map(_verdict, cells) if v), None)
        if tcs and verdict:
            seen.setdefault(tcs[0], []).append(verdict)
    return {t: v[0] if len(set(v)) == 1 else "conflict: " + ", ".join(dict.fromkeys(v)) for t, v in seen.items()}


def findings(text):
    """{FND: {"severity", "where", "req", "status", "scenario"}} from 06-review-report.md."""
    out = {}
    for cells in table_rows(text or ""):
        if cells and re.fullmatch(r"FND-\d+", cells[0]) and len(cells) >= 5:
            out[cells[0]] = {"severity": cells[1].lower(), "where": cells[3], "req": cells[4],
                             "status": None, "scenario": False}
    for fid, blocks in id_blocks(text or "", "FND").items():
        b = blocks[0]
        # Only a `Status:` / `Scenario:` field line: "returns status 500" in a scenario is not a status.
        st, sc = line_field(b, "Status"), line_field(b, "Scenario")
        entry = out.setdefault(fid, {"severity": None, "where": None, "req": None})
        entry["status"] = st.lower() if st else None
        entry["scenario"] = bool(sc)
    return out
