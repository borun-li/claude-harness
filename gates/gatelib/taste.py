"""Taste measures: what the captured pages measure against the configured taste values.

`gate.py capture` writes a `page.json` beside every web capture (capture_web.mjs: fonts, text sizes,
corner radii, gradients, open dialogs, read from the rendered page). `notes` compares them with
`taste` in the harness configuration and returns one line per difference. The lines are reported
by `fe-verify` and fail nothing: they are leads for the reviewer and the user, not findings.

Measured only for a product whose class is `tool` (`product_class` in `state.json`, else in the
harness configuration): the configured values are a tool's. A key set to null is not measured.
"""
from .common import harness_cfg, read_json

CLASS = "tool"
KEYS = ("font_families_max", "radius_px", "body_px", "gradients_max", "dialogs_open_max")


def product_class(ctx):
    state = read_json(ctx.run / "state.json") or {}
    return state.get("product_class") or harness_cfg(ctx.project).get("product_class")


def settings(ctx):
    """The measures to take, or None with the reason none is taken."""
    cfg = harness_cfg(ctx.project).get("taste") or {}
    cfg = {k: cfg[k] for k in KEYS if cfg.get(k) is not None}
    if not cfg:
        return None, "no `taste` values configured"
    cls = product_class(ctx)
    if cls != CLASS:
        return None, f"product_class is {cls!r}; the values are a {CLASS}'s"
    return cfg, None


def _px(v):
    return f"{v:g} px"


def page_notes(facts, cfg):
    """The differences one captured page shows, as text without the capture's name."""
    out = []
    fonts = facts.get("fonts") or {}
    limit = cfg.get("font_families_max")
    if limit is not None and len(fonts) > limit:
        by_use = sorted(fonts, key=lambda f: -fonts[f]["count"])
        out.append(f"{len(fonts)} font families outside code ({', '.join(by_use)}); at most {limit}. "
                   f"`{by_use[-1]}` is on `{fonts[by_use[-1]]['example']}`")
    allowed = cfg.get("radius_px")
    if allowed is not None:
        ok = {f"{float(a):g}px" for a in allowed} | {"round"}
        odd = {r: v for r, v in (facts.get("radii") or {}).items() if r not in ok}
        if odd:
            shown = ", ".join(f"{r} on `{v['example']}`" for r, v in sorted(odd.items()))
            out.append(f"corner radius {shown}; the values are {', '.join(_px(a) for a in allowed if a)} or fully round")
    body = cfg.get("body_px")
    sizes = facts.get("text_px") or {}
    if body is not None and sizes:
        total = sum(v["count"] for v in sizes.values())
        most = max(sizes, key=lambda s: sizes[s]["count"])
        if most != f"{float(body):g}px":
            out.append(f"most text is {most} ({round(100 * sizes[most]['count'] / total)}% of the characters, "
                       f"e.g. `{sizes[most]['example']}`); body text is {_px(body)}")
    limit = cfg.get("gradients_max")
    grads = facts.get("gradients") or []
    if limit is not None and len(grads) > limit:
        out.append(f"{len(grads)} gradient backgrounds ({', '.join(f'`{g}`' for g in grads[:3])}); at most {limit}")
    limit = cfg.get("dialogs_open_max")
    dialogs = facts.get("dialogs_open") or []
    if limit is not None and len(dialogs) > limit:
        out.append(f"{len(dialogs)} dialogs open at once ({', '.join(f'`{d}`' for d in dialogs[:3])}); at most {limit}")
    return out


def notes(ctx, round_dir):
    """(lines, pages measured, why not) for one evidence round. Each line names the captures that
    show it, so one difference seen at every size and state is one line."""
    cfg, why = settings(ctx)
    if cfg is None:
        return [], 0, why
    manifest = read_json(round_dir / "manifest.json") or {}
    seen, pages = {}, 0
    for e in manifest.get("entries", []):
        name = (e.get("files") or {}).get("page.json")
        facts = read_json(round_dir / name) if name else None
        if not isinstance(facts, dict):
            continue
        pages += 1
        for n in page_notes(facts, cfg):
            seen.setdefault(n, []).append(f"{e['id']}@{e.get('size')}")
    if not pages:
        return [], 0, "no web capture in this round carries page measures"
    lines = []
    for n, where in seen.items():
        more = f" and {len(where) - 3} more" if len(where) > 3 else ""
        lines.append(f"{n} — {', '.join(where[:3])}{more}")
    return lines, pages, None
