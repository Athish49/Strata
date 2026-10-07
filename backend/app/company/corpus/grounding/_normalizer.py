"""
Normalizer for IAC body text.
Strips administrative boilerplate so that readoption-only changes compare equal,
while genuine substantive edits still show up as different.

Unit tests at the bottom; run: python _normalizer.py
"""

from __future__ import annotations
import re
import unicodedata


# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

# Authority/Affected block at the very beginning of body_text, before "Sec. N."
# Format: "Authority: IC ... Affected: IC ... Sec. N."
# Strategy: strip everything before and including the "Sec. N." label
# Pattern: optional Auth block + optional Affected block + "Sec. <number>."
_ADMIN_PREFIX_RE = re.compile(
    r'^(?:Authority:[^S]*?)?(?:Affected:[^S]*?)?\s*Sec\.\s+[\d.]+\.\s*',
    re.IGNORECASE
)

# DIN strings: 8 digits - IR - 9+ digits (like 20240215-IR-170230456RFA)
_DIN_RE = re.compile(r'\b\d{8}-IR-\d{9,}\b')

# Indiana Register citation: "Indiana Register, Volume X, Issue N, Page N" or abbreviated
_IND_REG_RE = re.compile(r'\bIndiana Register[^;.]{0,80}', re.IGNORECASE)

# "Filed" or "Readopted" stamps: match from (Filed or (Readopted to end of text
# These appear inside or after the history paren
_FILED_RE = re.compile(r'\s*[\(\s](?:Filed|Readopted)\s+[^)]*\)?\s*$', re.IGNORECASE | re.DOTALL)


def _strip_history_paren(text: str) -> str:
    """
    Remove the trailing history parenthetical.
    Format: "...text. (Agency; DIN; filed/readopted ...)"
    The parenthetical is the last balanced-paren group at the end that contains
    'filed' or 'readopted'.
    """
    s = text.rstrip()
    if not s or s[-1] != ')':
        return text

    # Walk backwards to find matching '('
    depth = 0
    i = len(s) - 1
    while i >= 0:
        if s[i] == ')':
            depth += 1
        elif s[i] == '(':
            depth -= 1
            if depth == 0:
                break
        i -= 1

    if i < 0 or depth != 0:
        return text  # unmatched parens

    inner = s[i+1:len(s)-1]
    # Check if this looks like a history parenthetical
    if re.search(r'\b(filed|readopted|transferred|amended|adopted)\b', inner, re.IGNORECASE):
        return s[:i].rstrip()

    return text


def normalize(body_text: str) -> str:
    """
    Full normalizer pipeline. Returns normalized body text suitable for
    change detection (readoption-only changes will compare equal).
    """
    if not body_text:
        return ''
    t = body_text

    # Remove the admin prefix (Authority/Affected block + Sec. label)
    # This handles the common IAC format: "Authority: ... Affected: ... Sec. N. <body>"
    t = _ADMIN_PREFIX_RE.sub('', t)

    # If admin prefix wasn't found, try to remove just the leading Sec. label
    if t == body_text:
        t = re.sub(r'^\s*Sec\.\s+[\d.]+\.\s*', '', t)

    # Remove DIN strings
    t = _DIN_RE.sub('', t)

    # Remove Indiana Register citations
    t = _IND_REG_RE.sub('', t)

    # Remove trailing history parenthetical
    t = _strip_history_paren(t.strip())

    # Normalize typography
    t = t.replace('‘', "'").replace('’', "'")  # curly quotes
    t = t.replace('“', '"').replace('”', '"')  # curly double quotes
    t = t.replace('—', '--').replace('–', '-')  # em/en dash
    t = t.replace(' ', ' ')  # non-breaking space
    t = t.replace('§', 'section')  # section symbol
    t = unicodedata.normalize('NFKC', t)

    # Collapse whitespace and lowercase
    t = re.sub(r'\s+', ' ', t).strip().lower()
    return t


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def _run_unit_tests():
    """
    Run unit tests:
    - >=10 readoption-only pairs must normalize equal
    - >=5 pairs with one-word substantive edits must differ
    """
    # Template body text fragments (no admin boilerplate)
    BODY_3 = "A utility shall retain records for at least three (3) years."
    BODY_5_2YR = "A meter shall be tested within two (2) years."
    BODY_5_4YR = "A meter shall be tested within four (4) years."
    BODY_1 = "Customer means any person eligible for service."
    BODY_16 = "(a) A utility may disconnect service only upon providing notice."
    BODY_7 = "Standards shall conform to applicable requirements."
    BODY_8_2 = "Average accuracy shall be within plus or minus two percent (2%)."
    BODY_8_1 = "Average accuracy shall be within plus or minus one percent (1%)."
    BODY_9 = "Test equipment accuracy shall be verified annually."
    BODY_11_30 = "A customer may file a complaint within thirty (30) days."
    BODY_11_60 = "A customer may file a complaint within sixty (60) days."
    BODY_13 = "Bills shall be rendered monthly."
    BODY_24_60 = "An accident report shall be filed within sixty (60) days."
    BODY_24_30 = "A written report shall be filed within thirty (30) days."
    BODY_4 = "Records of meter purchases shall include the date and serial number."
    BODY_16B = "The utility shall provide fourteen (14) days notice before disconnection."
    BODY_16B10 = "The utility shall provide ten (10) days notice before disconnection."

    def _with_prefix(body, sec_num=3):
        return f"Authority: IC 8-1-1-3 ; IC 8-1-2-4 Affected: IC 8-1-2-12 Sec. {sec_num}. {body}"

    def _with_old_history(body, sec_num=3):
        return _with_prefix(body, sec_num) + " (Indiana Utility Regulatory Commission; filed Jan 1, 2005, 10:00 a.m.: 28 IR 1234)"

    def _with_new_history(body, sec_num=3):
        return _with_prefix(body, sec_num) + " (Indiana Utility Regulatory Commission; readopted filed Feb 15, 2024, 9:00 a.m.: 20240215-IR-170230456RFA)"

    def _with_old_filed(body, sec_num=3):
        return _with_prefix(body, sec_num) + " (Filed 05/01/2010)"

    def _with_new_readopt(body, sec_num=3):
        return _with_prefix(body, sec_num) + " (Readopted filed 03/20/2024)"

    def _with_din_old(body, sec_num=3):
        return _with_prefix(body, sec_num) + " 20100401-IR-170090123FRA"

    def _with_din_new(body, sec_num=3):
        return _with_prefix(body, sec_num) + " 20240301-IR-170230456RFA"

    def _with_ir_old(body, sec_num=3):
        return _with_prefix(body, sec_num) + " (Indiana Register, Volume 28, Issue 4, Page 100)"

    def _with_ir_new(body, sec_num=3):
        return _with_prefix(body, sec_num) + " (Indiana Register, Volume 47, Issue 3, Page 200)"

    # Readoption-only pairs (should normalize equal)
    READOPT_PAIRS = [
        (_with_old_history(BODY_3, 3),    _with_new_history(BODY_3, 3)),
        (_with_old_filed(BODY_5_2YR, 5),  _with_new_readopt(BODY_5_2YR, 5)),
        (_with_old_history(BODY_1, 1),    _with_new_history(BODY_1, 1)),
        (_with_old_filed(BODY_16, 16),    _with_new_readopt(BODY_16, 16)),
        (_with_old_history(BODY_7, 7),    _with_new_history(BODY_7, 7)),
        (_with_ir_old(BODY_8_2, 8),       _with_ir_new(BODY_8_2, 8)),
        (_with_old_history(BODY_9, 9),    _with_new_readopt(BODY_9, 9)),
        (_with_din_old(BODY_11_30, 11),   _with_din_new(BODY_11_30, 11)),
        (_with_old_filed(BODY_13, 13),    _with_new_readopt(BODY_13, 13)),
        (_with_old_filed(BODY_24_60, 24), _with_new_history(BODY_24_60, 24)),
        (_with_old_history(BODY_4, 4),    _with_new_readopt(BODY_4, 4)),
    ]

    # Substantive edit pairs (should normalize different)
    SUBST_PAIRS = [
        (_with_prefix(BODY_3, 3),         _with_prefix("A utility shall retain records for at least five (5) years.", 3)),
        (_with_prefix(BODY_16B, 16),      _with_prefix(BODY_16B10, 16)),
        (_with_prefix(BODY_8_2, 8),       _with_prefix(BODY_8_1, 8)),
        (_with_prefix(BODY_11_30, 11),    _with_prefix(BODY_11_60, 11)),
        (_with_prefix(BODY_24_60, 24),    _with_prefix(BODY_24_30, 24)),
        (_with_prefix(BODY_5_2YR, 5),     _with_prefix(BODY_5_4YR, 5)),
    ]

    passed_r = 0
    print("=== Readoption-only pairs (should normalize EQUAL) ===")
    for i, (a, b) in enumerate(READOPT_PAIRS):
        na, nb = normalize(a), normalize(b)
        ok = (na == nb)
        passed_r += int(ok)
        print(f"  Pair {i+1}: {'PASS' if ok else 'FAIL'}")
        if not ok:
            print(f"    A: {na[:120]}")
            print(f"    B: {nb[:120]}")
    print(f"\nReadoption pairs: {passed_r}/{len(READOPT_PAIRS)} passed")

    passed_s = 0
    print("\n=== Substantive edit pairs (should normalize DIFFERENT) ===")
    for i, (a, b) in enumerate(SUBST_PAIRS):
        na, nb = normalize(a), normalize(b)
        ok = (na != nb)
        passed_s += int(ok)
        print(f"  Pair {i+1}: {'PASS' if ok else 'FAIL'}")
        if not ok:
            print(f"    Both: {na[:120]}")
    print(f"\nSubstantive pairs: {passed_s}/{len(SUBST_PAIRS)} passed")

    assert passed_r >= 10, f"Need >=10 readoption pairs equal, got {passed_r}"
    assert passed_s >= 5, f"Need >=5 substantive pairs different, got {passed_s}"
    print("\nAll unit tests PASSED")
    return True


if __name__ == '__main__':
    _run_unit_tests()
