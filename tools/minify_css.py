#!/usr/bin/env python3
"""Write app/static/css/style.min.css from style.css.

Minifying is not the interesting part -- gzip already eats indentation. What
this buys is the ~15KB of comments and the repetition gzip still has to encode
references for: on this stylesheet the transferred bytes drop by about half.

The output is verified before it is written. Both files are flattened to an
ordered list of (context, selector, declaration) and compared. The comparison
normalises only what is unconditionally safe, so the two bugs a hand-written
CSS minifier actually ships -- a dropped space inside calc(), and `.a :hover`
collapsed into `.a:hover` -- fail the check instead of the page.
"""

import re
import sys
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "app" / "static" / "css"
SRC = CSS / "style.css"
OUT = CSS / "style.min.css"

# Strings, url() and comments are copied through untouched; the scanner below
# only ever rewrites what falls between them.
LITERAL = re.compile(
    r"""("(?:\\.|[^"\\])*")|('(?:\\.|[^'\\])*')|(url\([^)]*\))|(/\*.*?\*/)""",
    re.S | re.I,
)


def _chunks(css):
    pos = 0
    for m in LITERAL.finditer(css):
        if m.start() > pos:
            yield False, css[pos:m.start()]
        yield True, "" if m.group(4) else m.group(0)
        pos = m.end()
    if pos < len(css):
        yield False, css[pos:]


def minify(css):
    out = []
    brace = paren = 0
    pending_space = False
    for literal, chunk in _chunks(css):
        if literal:
            if pending_space and chunk:
                prev = out[-1][-1] if out and out[-1] else ""
                if not (prev in "{};,>~" or (prev == ":" and brace)):
                    out.append(" ")
            pending_space = False
            out.append(chunk)
            continue
        for ch in re.sub(r"\s+", " ", chunk):
            if ch == " ":
                pending_space = True
                continue
            # `:` separates a property from its value inside a block; outside
            # one it is a pseudo-class, where the leading space is a descendant
            # combinator and means something entirely different.
            drop_before = (
                ch in "{};,"
                or (ch == ":" and brace)
                or (ch in ">~" and not brace and not paren)
            )
            prev = out[-1][-1] if out and out[-1] else ""
            after = prev in "{};,>~" or (prev == ":" and brace)
            if pending_space and not drop_before and not after:
                out.append(" ")
            pending_space = False
            if ch == "{":
                brace += 1
            elif ch == "}":
                brace = max(0, brace - 1)
            elif ch == "(":
                paren += 1
            elif ch == ")":
                paren = max(0, paren - 1)
            out.append(ch)
    return re.sub(r";+\}", "}", "".join(out)).strip()


def flatten(css):
    """['@media …|selector|prop:value', …] in source order."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    rows, stack, buf = [], [], ""
    paren = 0
    i = 0
    while i < len(css):
        ch = css[i]
        if ch in "\"'":
            end = css.find(ch, i + 1)
            while end > 0 and css[end - 1] == "\\":
                end = css.find(ch, end + 1)
            end = len(css) - 1 if end < 0 else end
            buf += css[i:end + 1]
            i = end + 1
            continue
        if ch == "(":
            paren += 1
        elif ch == ")":
            paren = max(0, paren - 1)
        if paren:
            buf += ch
        elif ch == "{":
            stack.append(_sel(buf))
            buf = ""
        elif ch in ";}":
            if buf.strip():
                rows.append("|".join(stack) + "|" + _decl(buf))
            buf = ""
            if ch == "}" and stack:
                stack.pop()
        else:
            buf += ch
        i += 1
    return rows


def _sel(s):
    """A selector: `>` and `~` are always combinators here, `:` never is."""
    s = re.sub(r"\s+", " ", s).strip()
    return re.sub(r"\s*([>~,])\s*", r"\1", s)


def _decl(s):
    """A declaration: `:` splits it, but spaces inside a value stay put, which
    is what makes a mangled calc() visible."""
    s = re.sub(r"\s+", " ", s).strip()
    return re.sub(r"\s*([:,])\s*", r"\1", s, count=0)


def main():
    source = SRC.read_text()
    small = minify(source)

    a, b = flatten(source), flatten(small)
    if a != b:
        print(f"ABORT: {len(a)} source rules, {len(b)} minified", file=sys.stderr)
        for x, y in zip(a, b):
            if x != y:
                print(f"  src: {x}\n  min: {y}", file=sys.stderr)
                break
        return 1

    OUT.write_text(small)
    shrink = 100 - round(len(small) * 100 / len(source))
    print(f"{SRC.name} {len(source):,}B -> {OUT.name} {len(small):,}B "
          f"({shrink}% smaller; {len(a)} rules verified identical)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
