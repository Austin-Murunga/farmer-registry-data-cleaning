"""Assemble the work sample PDF from the outputs of build_sample.py.
Run: python make_doc.py output work_sample.pdf
Builds a Word document; if Microsoft Word is installed (Windows), also saves it as PDF.
"""
import json
import sys
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

OUT, FINAL = Path(sys.argv[1]), Path(sys.argv[2])
f = json.loads((OUT / "facts.json").read_text(encoding="utf-8"))
code = json.loads((OUT / "snippets.json").read_text(encoding="utf-8"))
log = pd.read_csv(OUT / "issue_log.csv")
rows_removed = f["raw_rows"] - f["clean_rows"]
pct = lambda x: f"{x * 100:.0f}%"
FONT = "Times New Roman"

doc = Document()
for s in doc.sections:
    s.top_margin = s.bottom_margin = Inches(0.75)
    s.left_margin = s.right_margin = Inches(0.9)
st = doc.styles["Normal"]
st.font.name, st.font.size = FONT, Pt(11)
st.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), FONT)
st.paragraph_format.space_after = Pt(4)


def para(text="", bold=False, italic=False, size=11, align=None, after=4, color=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(after)
    if align:
        p.alignment = align
    parts = text.split("**")
    for i, part in enumerate(parts):
        if part:
            r = p.add_run(part)
            r.bold = bold or i % 2 == 1
            r.italic, r.font.size, r.font.name = italic, Pt(size), FONT
            if color:
                r.font.color.rgb = RGBColor.from_string(color)
    return p


def heading(text):
    p = para(text, bold=True, size=13, after=3)
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.keep_with_next = True


def bullet(text):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(2)
    for i, part in enumerate(text.split("**")):
        if part:
            r = p.add_run(part)
            r.bold, r.font.name, r.font.size = i % 2 == 1, FONT, Pt(11)


def shade(p, fill="F2F4F7"):
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), fill)
    pPr.append(shd)


def code_block(text, label):
    para(label, bold=True, size=10, after=1).paragraph_format.keep_with_next = True
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.left_indent = Inches(0.1)
    lines = text.rstrip().splitlines()
    for i, line in enumerate(lines):
        r = p.add_run(line)
        r.font.name, r.font.size = "Consolas", Pt(8.5)
        r._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "Consolas")
        if i < len(lines) - 1:
            r.add_break()
    shade(p)


def table(header, rows, widths):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Light Grid Accent 1"
    for c, h in enumerate(header):
        cell = t.rows[0].cells[c]
        cell.text = ""
        r = cell.paragraphs[0].add_run(h); r.bold = True; r.font.size = Pt(10); r.font.name = FONT
    for row in rows:
        cells = t.add_row().cells
        for c, v in enumerate(row):
            cells[c].text = ""
            r = cells[c].paragraphs[0].add_run(str(v)); r.font.size = Pt(10); r.font.name = FONT
    for row in t.rows:
        for c, w in enumerate(widths):
            row.cells[c].width = Inches(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def image(name, width=6.4):
    doc.add_picture(str(OUT / name), width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER


# ---------------------------------------------------------------- content
para("Analytical Work Sample", bold=True, size=18, align=WD_ALIGN_PARAGRAPH.CENTER, after=0)
para("Cleaning and reconciling a farmer registry with sales data", size=13, align=WD_ALIGN_PARAGRAPH.CENTER, after=0)
para("Austin Alutsachi Murunga  |  Data analysis work sample  |  November 2026",
     size=10, align=WD_ALIGN_PARAGRAPH.CENTER, after=8)
note = para("All data in this sample is synthetic. I generated it with a fixed random seed to reproduce problems "
            "common in field-collected registries. It contains no real farmer, customer or employer data. "
            "Tools: Python (pandas), SQL (SQLite) and matplotlib.", italic=True, size=10, after=8)
shade(note, "EAF4EC")

heading("1. The task")
para(f"A programme team has a farmer registry of **{f['raw_rows']} rows** collected by field staff and a sales file of "
     f"**{f['sales']:,} transactions**. Management wants a trusted count of registered and active farmers by county. "
     "Before any indicator can be reported, the registry has to be cleaned and every sale linked to one farmer.")

heading("2. Summary for management")
bullet(f"The registry holds **{f['clean_rows']} real farmers**, not {f['raw_rows']}. {rows_removed} rows "
       f"({rows_removed / f['raw_rows'] * 100:.0f}%) were double uploads, conflicting versions of the same farmer, "
       "or farmers registered twice.")
bullet(f"County was written {f['county_before']} different ways; it now uses {f['county_after']} agreed names. "
       f"Valid phone numbers rose from {pct(f['before']['Valid phone'])} to {pct(f['after']['Valid phone'])}.")
bullet(f"Sales that link to exactly one farmer rose from {pct(f['linked_before'])} to {pct(f['linked_after'])}. "
       f"The remaining {f['orphans']} sales use farmer IDs that do not exist and are listed for the Sales team to correct.")
bullet(f"{f['active_total']} farmers ({f['active_total'] / f['clean_rows'] * 100:.0f}%) made a purchase in the last 90 days. "
       f"Activity ranges from {pct(f['low']['rate'])} in {f['low']['county']} to {pct(f['top']['rate'])} in {f['top']['county']}.")
bullet("Nothing was guessed. Missing values and impossible dates are flagged and returned to field teams, "
       "not filled in.")

heading("3. What I found, and what I did")
image("chart_issues.png", 6.2)
table(["Issue", "Rows", "Action"], log.values.tolist(), [3.1, 0.6, 2.6])

heading("4. Cleaning rules and trade-offs")
bullet("**One farmer, one ID.** The farmer ID is the key every other dataset joins to, so duplicates were resolved before anything else.")
bullet("**Conflicting versions:** when the same ID appears with different details, the most recent update wins. "
       "This assumes field edits correct earlier entries. Where that is not true, a review list is safer.")
bullet("**Re-registrations** are merged only when **both** the phone number and the name match. Matching on phone alone "
       "would wrongly merge household members who share a phone, which is common in rural areas. The earliest ID is kept, "
       "and sales recorded under the duplicate ID are re-pointed to it.")
bullet("**Dates** in three formats were parsed to one. Dates in the future, before the programme started, or that do not "
       "exist (e.g. 30 February) were blanked and returned to the field team rather than corrected by guesswork.")
bullet("**Missing values were not imputed.** Filling in a county or gender would make the data look complete but "
       "could be wrong. Instead, gaps are counted and reported with each indicator.")

heading("5. Result")
image("chart_quality.png", 6.2)
para("Every check and every number above is produced by one script that can be rerun each week on new data, "
     "so the cleaning does not depend on one person repeating manual steps.")

heading("6. Code excerpts")
para("The SQL version of the de-duplication rule was run against the same data and returned exactly the same farmers "
     "as the Python version. The script checks this automatically.", size=10.5)
code_block(code["standardise_phone"], "Standardising phone numbers (Python)")
code_block(code["parse_date"], "Parsing dates and rejecting impossible ones (Python)")
code_block(code["resolve_conflicts"] + "\n" + code["merge_reregistrations"], "Resolving conflicts and merging re-registrations (Python)")
code_block(code["SQL_LATEST"], "Latest version of each farmer (SQL, window function)")
code_block(code["SQL_LINK"], "Sales that do not link to a registered farmer (SQL)")

heading("7. Indicator on the clean data")
image("chart_indicator.png", 6.2)
table(["Indicator", "Definition", "Calculation"], [
    ["Registered farmer", "A unique farmer ID after de-duplication and merging", "Count of farmer IDs in the clean registry"],
    ["Active farmer", "A registered farmer with at least one sale in the last 90 days", "Active farmers ÷ registered farmers"],
    ["Sales linkage rate", "Sales that match exactly one registered farmer", "Linked sales ÷ all sales"],
    ["Duplicate rate", "Rows that were not unique farmers", "Rows removed ÷ raw rows"],
    ["Field completeness", "Records with a valid value in a required field", "Valid values ÷ records, per field"],
], [1.3, 2.6, 2.4])
para(f"**Reading it with care:** county groups are small (67–102 farmers), so a few percentage points of difference may "
     f"not be meaningful. {f['missing']['county']} farmers have no county and are shown separately rather than dropped, "
     "so the total still adds up.", size=10.5)

heading("8. Preventing these errors at source")
bullet("**Form validation** in the collection tool (e.g. KoboToolbox): a phone number pattern, a county pick-list, and "
       "registration dates limited to the programme period.")
bullet("**Check for an existing farmer** by phone and name before a new ID is created, which stops most re-registrations.")
bullet("**Weekly automated checks** with an issue log shared with field supervisors, so recurring errors are fixed in "
       "the field, not repeatedly in the office.")
bullet("**Written indicator definitions** (as in section 7), so every report counts farmers the same way.")

tmp = (OUT / "work_sample.docx").resolve()
doc.save(tmp)
print("saved", tmp)


def to_pdf(src, dst):
    """Save a PDF with Microsoft Word (Windows only)."""
    import subprocess
    src, dst = str(src).replace("'", "''"), str(Path(dst).resolve()).replace("'", "''")
    ps = ("$w = New-Object -ComObject Word.Application; $w.Visible = $false; try { "
          f"$d = $w.Documents.Open('{src}', $false, $true); $d.SaveAs2('{dst}', 17); $d.Close($false) "
          "} finally { $w.Quit() }")
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], check=True)


try:
    to_pdf(tmp, FINAL)
    print("saved", FINAL)
except Exception as e:  # no Word: open the .docx and export it yourself
    print("PDF step skipped:", e)
