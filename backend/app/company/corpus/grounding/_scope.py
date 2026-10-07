"""
Scope parser for T00 grounding pack generation.
Parses IAC scope entries and resolves them against a set of DB rows.
"""

from __future__ import annotations
import re
from decimal import Decimal
from typing import List, Dict, Any, Tuple, Optional, Set


# ---------------------------------------------------------------------------
# Citation parsing
# ---------------------------------------------------------------------------

_IAC_CITE_RE = re.compile(
    r'^(?P<title>\d+)\s+IAC\s+(?P<article>\d+)-(?P<rule>[\d.]+)-(?P<section>[\d.]+)$'
)
_IAC_RULE_RE = re.compile(
    r'^(?P<title>\d+)\s+IAC\s+(?P<article>\d+)-(?P<rule>[\d.]+)$'
)


def parse_citation(cite: str) -> Optional[Tuple[str, str, str, str]]:
    """Parse a full IAC section citation into (title, article, rule, section)."""
    m = _IAC_CITE_RE.match(cite.strip())
    if m:
        return (m.group('title'), m.group('article'), m.group('rule'), m.group('section'))
    return None


def parse_rule(cite: str) -> Optional[Tuple[str, str, str]]:
    """Parse a rule-level citation into (title, article, rule)."""
    m = _IAC_RULE_RE.match(cite.strip())
    if m:
        return (m.group('title'), m.group('article'), m.group('rule'))
    return None


def row_sort_key(row: Dict[str, Any]) -> tuple:
    """Sort key for a section row by citation."""
    p = parse_citation(row.get('citation', ''))
    if p:
        title, article, rule, section = p
        try:
            return (int(title), int(article), Decimal(rule), Decimal(section))
        except Exception:
            pass
    return (0, 0, Decimal(0), Decimal(0))


# ---------------------------------------------------------------------------
# Scope definitions (canonical, matches T00 spec)
# ---------------------------------------------------------------------------

# Heading-match additions per pack
HEADING_MATCHES = {
    'T14': re.compile(r'disconnect|reconnect|deposit|payment arrangement|medical|bill', re.IGNORECASE),
    'T15': re.compile(r'meter|adjust|estimated', re.IGNORECASE),
    'T17': re.compile(r'complaint|dispute|information to customer', re.IGNORECASE),
}

# Scope entries for each pack (base scope, before heading matches & context)
# Format: list of (type, args) where type in ('rule', 'section', 'range', 'heading')
SCOPE_ENTRIES: Dict[str, List[tuple]] = {
    'T13': [
        ('rule', ('170', '4', '1')),
        ('rule', ('170', '16', '1')),
        ('heading', ('170', '1', re.compile(r'tariff|schedule|thirty|30-day|rate|time|computation|filing', re.IGNORECASE))),
    ],
    'T14': [
        ('section', ('170', '4', '1', '13')),
        ('section', ('170', '4', '1', '15')),
        ('section', ('170', '4', '1', '16')),
        ('rule', ('170', '16', '1')),
        # 16.5 and 16.6 are subsections of 16, not separate DB rows
    ],
    'T15': [
        ('range', ('170', '4', '1', Decimal('4'), Decimal('14'))),
    ],
    'T16': [
        ('rule', ('170', '4', '9')),
        ('rule', ('170', '16', '1')),
        ('section', ('170', '4', '1', '26')),
    ],
    'T17': [
        ('rule', ('170', '16', '1')),
        ('section', ('170', '4', '1', '13')),
        ('section', ('170', '4', '1', '16')),
    ],
    'T18': [
        ('range', ('170', '4', '1', Decimal('3'), Decimal('11'))),
    ],
    'T19': [
        ('section', ('170', '4', '1', '3')),
        ('section', ('170', '4', '1', '23')),
        ('section', ('170', '4', '1', '24')),
        ('section', ('170', '4', '9', '7')),
    ],
    'T20': [
        ('rule', ('327', '2', '6.1')),  # absent from DB
    ],
    'T21': [
        ('section', ('170', '4', '1', '3')),
        ('section', ('170', '4', '1', '24')),
    ],
}


def get_scope_citations(
    pack: str,
    all_s1: List[Dict[str, Any]],
) -> Tuple[List[str], List[str]]:
    """
    Return (scope_citations, context_citations) for a pack.
    scope_citations: citations with role='scope'
    context_citations: citations with role='context'

    all_s1: list of row dicts from the database (S1 snapshot).
    """
    scope_cites: Set[str] = set()
    context_cites: Set[str] = set()

    entries = list(SCOPE_ENTRIES.get(pack, []))
    # Add heading-match additions for T10, T11, T12 (union packs) - handled in get_union_scope

    def row_matches_entry(row: Dict[str, Any], entry: tuple) -> bool:
        t, rule, art = row.get('title_number'), row.get('subpart'), row.get('part')
        sec = row.get('section_number')
        etype = entry[0]
        args = entry[1]

        if etype == 'rule':
            title, article, rule_id = args
            return (t == title and art == article and rule == rule_id)

        elif etype == 'section':
            title, article, rule_id, section_id = args
            return (t == title and art == article and rule == rule_id and sec == str(section_id))

        elif etype == 'range':
            title, article, rule_id, sec_from, sec_to = args
            if t != title or art != article or rule != rule_id:
                return False
            try:
                sec_d = Decimal(sec)
                return sec_from <= sec_d <= sec_to
            except Exception:
                return False

        elif etype == 'heading':
            title, article, heading_re = args
            if t != title or art != article:
                return False
            return bool(heading_re.search(row.get('heading', '')))

        return False

    # Apply base scope entries
    for entry in entries:
        for row in all_s1:
            if row_matches_entry(row, entry):
                scope_cites.add(row['citation'])

    # Apply heading-match additions for this pack
    hm = HEADING_MATCHES.get(pack)
    if hm:
        for row in all_s1:
            t, art, rule = row.get('title_number'), row.get('part'), row.get('subpart')
            if t == '170' and art == '4' and rule == '1':
                if hm.search(row.get('heading', '')):
                    scope_cites.add(row['citation'])

    # Context sections: 170 IAC 4-1-0.5, 4-1-1, 4-1-2 for any pack with 170 IAC 4-1 sections
    has_4_1 = any(
        row['citation'] for row in all_s1
        if row['citation'] in scope_cites and
        row.get('title_number') == '170' and row.get('part') == '4' and row.get('subpart') == '1'
    )
    if has_4_1:
        ctx_sections = ['170 IAC 4-1-1', '170 IAC 4-1-2']
        # 4-1-0.5 does not exist in DB, skip
        for row in all_s1:
            if row['citation'] in ctx_sections and row['citation'] not in scope_cites:
                context_cites.add(row['citation'])

    # Context sections: definitions/applicability sections of every rule in scope
    # Find distinct rules in scope
    rules_in_scope: Set[Tuple[str, str, str]] = set()
    for cite in scope_cites:
        p = parse_citation(cite)
        if p:
            rules_in_scope.add((p[0], p[1], p[2]))

    # For each rule in scope, add its section 1 and section 2 (definitions/applicability) as context
    for (title, article, rule_id) in rules_in_scope:
        for row in all_s1:
            if (row.get('title_number') == title and
                row.get('part') == article and
                row.get('subpart') == rule_id):
                sec = row.get('section_number', '')
                try:
                    sec_d = Decimal(sec)
                    # Include sections 1 and 2 as definitions/applicability context
                    if sec_d <= Decimal('2') and row['citation'] not in scope_cites:
                        context_cites.add(row['citation'])
                except Exception:
                    pass

    return sorted(scope_cites), sorted(context_cites)


def get_union_scope_citations(
    base_packs: List[str],
    all_s1: List[Dict[str, Any]],
) -> Tuple[Set[str], Set[str]]:
    """Return union of scope and context citations from multiple packs."""
    all_scope: Set[str] = set()
    all_context: Set[str] = set()
    for pack in base_packs:
        s, c = get_scope_citations(pack, all_s1)
        all_scope.update(s)
        all_context.update(c)
    # Context: union minus scope
    all_context -= all_scope
    return all_scope, all_context
