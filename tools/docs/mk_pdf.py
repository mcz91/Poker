"""Renderer docs/PRZEKAZANIE.md -> docs/PRZEKAZANIE.pdf.

Narzedzie dokumentacyjne POZA bramka repozytorium: wymaga `reportlab`,
ktory NIE jest zalezoscia produktu ani extras `dev`/`train`, i nie jest
objete `mypy` (poza `files` w pyproject). Uzycie:

    python -m venv /tmp/pdfvenv && /tmp/pdfvenv/bin/pip install reportlab
    /tmp/pdfvenv/bin/python tools/docs/mk_pdf.py docs/PRZEKAZANIE.md docs/PRZEKAZANIE.pdf

Zrodlem prawdy jest markdown; PDF jest jego zlozeniem na konkretny commit
i po kazdej zmianie dokumentu trzeba go wygenerowac ponownie. Fonty:
DejaVu (pelne polskie znaki); brak pliku kursywy -> mapowana na krój podstawowy.
"""

from __future__ import annotations

import html
import re
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

F = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("DJ", F + "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DJ-B", F + "DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("DJ-I", F + "DejaVuSans.ttf"))  # brak pliku kursywy w tym systemie
pdfmetrics.registerFont(TTFont("DJM", F + "DejaVuSansMono.ttf"))
pdfmetrics.registerFont(TTFont("DJM-B", F + "DejaVuSansMono-Bold.ttf"))
pdfmetrics.registerFontFamily("DJ", normal="DJ", bold="DJ-B", italic="DJ-I")

INK = colors.HexColor("#16191d")
MUTED = colors.HexColor("#5c6470")
RULE = colors.HexColor("#d4d8de")
CODEBG = colors.HexColor("#f4f5f7")
ACCENT = colors.HexColor("#1f4e79")
WARN = colors.HexColor("#8a3324")

ss = getSampleStyleSheet()


def st(name, **kw):
    base = dict(fontName="DJ", fontSize=9.2, leading=13.4, textColor=INK)
    base.update(kw)
    return ParagraphStyle(name, parent=ss["Normal"], **base)


S = {
    "body": st("body", alignment=TA_JUSTIFY, spaceAfter=5),
    "h1": st("h1", fontName="DJ-B", fontSize=17, leading=21, textColor=ACCENT,
             spaceBefore=2, spaceAfter=9),
    "h2": st("h2", fontName="DJ-B", fontSize=12.5, leading=16, textColor=ACCENT,
             spaceBefore=14, spaceAfter=6),
    "h3": st("h3", fontName="DJ-B", fontSize=10.2, leading=14, textColor=INK,
             spaceBefore=9, spaceAfter=4),
    "li": st("li", alignment=TA_JUSTIFY, leftIndent=11, bulletIndent=2, spaceAfter=3),
    "quote": st("quote", leftIndent=9, rightIndent=5, textColor=WARN,
                fontSize=8.9, leading=12.8, spaceBefore=3, spaceAfter=5),
    "code": st("code", fontName="DJM", fontSize=7.6, leading=10.4, textColor=INK),
    "th": st("th", fontName="DJ-B", fontSize=7.8, leading=10.4),
    "td": st("td", fontSize=7.8, leading=10.4),
    "tdr": st("tdr", fontSize=7.8, leading=10.4, alignment=2),
    "title": st("title", fontName="DJ-B", fontSize=25, leading=30, textColor=ACCENT),
    "sub": st("sub", fontSize=11.5, leading=16, textColor=MUTED),
    "meta": st("meta", fontSize=8.6, leading=12.6, textColor=MUTED),
}

INLINE = re.compile(
    r"\[(?P<lt>[^\]]+)\]\((?P<lu>[^)]+)\)|"      # link PRZED kodem: [`x`](y)
    r"\*\*(?P<b>.+?)\*\*|`(?P<c>[^`]+)`|~~(?P<s>.+?)~~|\*(?P<i>[^*]+)\*"
)


def inline(t: str) -> str:
    """Markdown inline -> znaczniki reportlab, z escapowaniem XML."""
    out, pos = [], 0
    for m in INLINE.finditer(t):
        out.append(html.escape(t[pos:m.start()]))
        if m.group("b"):
            out.append(f"<b>{inline(m.group('b'))}</b>")
        elif m.group("c"):
            out.append(
                '<font face="DJM" size="8" backColor="#f0f1f3">'
                f"{html.escape(m.group('c'))}</font>"
            )
        elif m.group("s"):
            out.append(f"<strike>{html.escape(m.group('s'))}</strike>")
        elif m.group("lt"):
            out.append(f"<u>{inline(m.group('lt'))}</u>")
        elif m.group("i"):
            out.append(f"<i>{html.escape(m.group('i'))}</i>")
        pos = m.end()
    out.append(html.escape(t[pos:]))
    txt = "".join(out).replace("‑", "-")
    return re.sub(r"~(?=[\d0-9])", "ok. ", txt)


def code_block(lines: list[str], width: float):
    body = "<br/>".join(html.escape(x).replace(" ", "&nbsp;") for x in lines)
    p = Paragraph(body, S["code"])
    t = Table([[p]], colWidths=[width])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODEBG),
        ("BOX", (0, 0), (-1, -1), 0.4, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def md_table(rows: list[list[str]], aligns: list[str], width: float):
    head, *body = rows
    ncol = len(head)
    # szerokosc kolumny proporcjonalna do zawartosci, z podloga i sufitem
    raw = []
    for i in range(ncol):
        cells = [head[i]] + [r[i] for r in body if i < len(r)]
        raw.append(max(6, max((len(re.sub(r"[*`\[\]]", "", c)) for c in cells), default=6)))
    total = sum(raw)
    widths = [max(width * 0.115, width * (v / total)) for v in raw]
    scale = width / sum(widths)
    widths = [w * scale for w in widths]

    data = [[Paragraph(inline(c), S["th"]) for c in head]]
    for r in body:
        row = []
        for i, c in enumerate(r):
            sty = S["tdr"] if i < len(aligns) and aligns[i] == "r" else S["td"]
            row.append(Paragraph(inline(c), sty))
        row += [Paragraph("", S["td"])] * (ncol - len(row))
        data.append(row)

    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "DJ"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef1f5")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, ACCENT),
        ("LINEBELOW", (0, 1), (-1, -2), 0.25, RULE),
        ("BOX", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafbfc")]),
    ]))
    return t


def split_row(line: str) -> list[str]:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    # identyfikatory kontraktow nie moga sie lamac w poprzek kolumny
    return [re.sub(r"\bPOKER-(\d)", "POKER\u2011\\1", c) for c in cells]


def parse(md: str, width: float):
    flow: list = []
    lines = md.split("\n")
    i = 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()

        if s.startswith("```"):
            j, buf = i + 1, []
            while j < len(lines) and not lines[j].strip().startswith("```"):
                buf.append(lines[j])
                j += 1
            flow += [Spacer(1, 3), code_block(buf, width), Spacer(1, 6)]
            i = j + 1
            continue

        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if s.startswith("|") and re.match(r"^\|[\s:|-]+\|$", nxt):
            aligns = ["r" if c.strip().endswith(":") else "l" for c in split_row(lines[i + 1])]
            rows, j = [split_row(s)], i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                rows.append(split_row(lines[j]))
                j += 1
            flow += [Spacer(1, 3), md_table(rows, aligns, width), Spacer(1, 7)]
            i = j
            continue

        if s.startswith("### "):
            flow.append(Paragraph(inline(s[4:]), S["h3"]))
        elif s.startswith("## "):
            flow.append(Paragraph(inline(s[3:]), S["h2"]))
        elif s.startswith("# "):
            flow.append(Paragraph(inline(s[2:]), S["h1"]))
        elif s.startswith("> "):
            j, buf = i, []
            while j < len(lines) and lines[j].strip().startswith(">"):
                buf.append(lines[j].strip().lstrip(">").strip())
                j += 1
            flow.append(Paragraph(inline(" ".join(buf)), S["quote"]))
            i = j
            continue
        elif s == "---":
            flow.append(Spacer(1, 5))
        elif re.match(r"^[-*] ", s) or re.match(r"^\d+\. ", s):
            j, buf = i, []
            indent = len(ln) - len(ln.lstrip())
            while j < len(lines):
                nxt = lines[j]
                t = nxt.strip()
                if j > i and (not t or re.match(r"^[-*] ", t) or re.match(r"^\d+\. ", t)
                              or t.startswith("|") or t.startswith("#") or t.startswith("```")):
                    break
                if j > i and (len(nxt) - len(nxt.lstrip())) <= indent and t:
                    break
                buf.append(t)
                j += 1
            text = " ".join(buf)
            m = re.match(r"^(\d+)\.\s+(.*)$", text)
            if m:
                flow.append(Paragraph(inline(m.group(2)), S["li"], bulletText=m.group(1) + "."))
            else:
                flow.append(Paragraph(inline(text[2:]), S["li"], bulletText="•"))
            i = j
            continue
        elif s:
            j, buf = i, []
            while j < len(lines) and lines[j].strip() and not re.match(
                r"^(#|\||```|> |[-*] |\d+\. |---)", lines[j].strip()
            ):
                buf.append(lines[j].strip())
                j += 1
            flow.append(Paragraph(inline(" ".join(buf)), S["body"]))
            i = j
            continue
        i += 1
    return flow


def build(src: str, dst: str) -> None:
    md = open(src, encoding="utf-8").read()
    # tytul i lead z naglowka pliku
    body_md = md.split("\n", 1)[1]
    lead_end = body_md.index("---")
    lead = body_md[:lead_end].strip()
    rest = body_md[lead_end + 3:]

    doc = BaseDocTemplate(
        dst, pagesize=A4,
        leftMargin=20 * mm, rightMargin=17 * mm,
        topMargin=17 * mm, bottomMargin=16 * mm,
        title="Poker — wytyczne dla zespołu przejmującego",
        author="Architekt produktu Poker", subject="Przekazanie linii blueprintu GTO",
    )
    fw = doc.width

    def deco(canv, d):
        canv.saveState()
        canv.setFont("DJ", 7.2)
        canv.setFillColor(MUTED)
        canv.drawString(d.leftMargin, A4[1] - 11 * mm,
                        "Poker — wytyczne dla zespołu przejmującego")
        canv.drawRightString(A4[0] - d.rightMargin, A4[1] - 11 * mm, "mcz91/Poker · 2026-09-07")
        canv.setStrokeColor(RULE)
        canv.setLineWidth(0.4)
        canv.line(d.leftMargin, A4[1] - 13 * mm, A4[0] - d.rightMargin, A4[1] - 13 * mm)
        canv.line(d.leftMargin, 13 * mm, A4[0] - d.rightMargin, 13 * mm)
        canv.drawCentredString(A4[0] / 2, 9 * mm, str(canv.getPageNumber()))
        canv.restoreState()

    def cover(canv, d):
        canv.saveState()
        canv.setStrokeColor(ACCENT)
        canv.setLineWidth(2.2)
        canv.line(d.leftMargin, A4[1] - 45 * mm, d.leftMargin + 46 * mm, A4[1] - 45 * mm)
        canv.setFont("DJ", 7.2)
        canv.setFillColor(MUTED)
        canv.drawCentredString(A4[0] / 2, 9 * mm, "1")
        canv.restoreState()

    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height - 6 * mm, id="n")
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame], onPage=cover),
        PageTemplate(id="main", frames=[frame], onPage=deco),
    ])

    flow = [
        Spacer(1, 52 * mm),
        Paragraph("Wytyczne dla zespołu przejmującego", S["title"]),
        Spacer(1, 4 * mm),
        Paragraph("Produkt <b>Poker</b> — linia blueprintu GTO dla Spin &amp; Go", S["sub"]),
        Spacer(1, 12 * mm),
        Paragraph(inline(lead.replace("\n", " ")), S["meta"]),
        Spacer(1, 10 * mm),
    ]
    facts = [
        ["repozytorium",
         "mcz91/Poker (publiczne) · gałąź claude/poker-project-architecture-jw6ukd"],
        ["stan bramki", "ruff + mypy + pytest — 483 testy, ~5 min 50 s"],
        ["ostatni kontrakt", "POKER-57 (format .bpk v2) — zamknięty 2026-09-07"],
        ["następny krok", "POKER-58, potem POKER-59 przed każdym długim przebiegiem"],
        ["kierunek", "decyzja 29 (rodzina blueprintów per tier) + decyzja 30"],
    ]
    rows = [[Paragraph(f"<b>{a}</b>", S["td"]), Paragraph(inline(b), S["td"])]
            for a, b in facts]
    t = Table(rows, colWidths=[fw * 0.24, fw * 0.76])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
    ]))
    flow += [t, NextPageTemplate('main'), PageBreak()]
    flow += parse(rest, fw)
    doc.build(flow)


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
