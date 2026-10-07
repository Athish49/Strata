"""
T00 leak test for grounding packs.
Verifies that no S2-only content has leaked into the S1 packs.

Tests:
(a) No pack contains any S2-only 6-word shingle
(b) No pack contains any citation that exists only in S2
(c) No pack field other than the specified schema fields
(d) Per-pack high counts >= 2 where possible

Run:
    python _leaktest.py

Writes _leaktest_report.json to the grounding directory.
"""

from __future__ import annotations
import json
import os
import re
import sys
from typing import Any, Dict, List, Set

import psycopg2

DB_URL = (
    'postgresql://neondb_owner:npg_ADz3ZjdW4YFr@'
    'ep-fancy-river-ar47ie12-pooler.c-4.us-west-2.aws.neon.tech/'
    'neondb?sslmode=require&channel_binding=require'
)

GROUNDING_DIR = os.path.dirname(os.path.abspath(__file__))
PACKS = [f'T{n}' for n in list(range(10, 22))]
S1_DATE = '2024-12-31'
S2_DATE = '2025-12-31'

ALLOWED_SECTION_FIELDS = {
    'citation', 'heading', 'role', 'status_s1', 'effective_date_s1',
    'body_text_s1', 'body_text_s1_normalized', 'subsections',
    'iac_cross_refs_s1', 'external_refs_s1', 'coverage_priority',
}
ALLOWED_TOP_FIELDS = {'task', 'law_as_of', 'sections', 'must_cover'}


def shingles_6gram(text: str) -> Set[tuple]:
    """Generate 6-word shingles from text."""
    words = text.lower().split()
    if len(words) < 6:
        return set()
    return {tuple(words[i:i+6]) for i in range(len(words)-5)}


def get_conn():
    return psycopg2.connect(DB_URL)


def fetch_all_iac_bodies(conn, snapshot_date: str) -> Dict[str, str]:
    """Fetch {citation: body_text} for all IAC rows at a snapshot."""
    cur = conn.cursor()
    cur.execute(
        "SELECT citation, body_text FROM code_sections WHERE source_system = 'iac' AND snapshot_date = %s",
        (snapshot_date,)
    )
    return {row[0]: (row[1] or '') for row in cur.fetchall()}


def load_pack(pack_name: str) -> Dict[str, Any]:
    path = os.path.join(GROUNDING_DIR, f'{pack_name}.json')
    with open(path) as f:
        return json.load(f)


def run_leak_tests() -> Dict[str, Any]:
    """Run all leak tests and return report."""
    report = {
        'status': 'PASS',
        'tests': {},
        'pack_results': {},
    }

    print("Connecting to database for leak test...")
    conn = get_conn()
    s1_bodies = fetch_all_iac_bodies(conn, S1_DATE)
    s2_bodies = fetch_all_iac_bodies(conn, S2_DATE)
    conn.close()

    # Build S1 citation set
    s1_citations = set(s1_bodies.keys())
    s2_citations = set(s2_bodies.keys())

    # S2-only citations (exist in S2 but not S1)
    s2_only_citations = s2_citations - s1_citations

    # Build S2-only shingles: shingles present in S2 bodies but absent from ALL S1 bodies
    # "S2-only" = a shingle that does not appear anywhere in S1, only in S2
    all_s1_shingles: Set[tuple] = set()
    for body in s1_bodies.values():
        all_s1_shingles.update(shingles_6gram(body))

    all_s2_shingles: Set[tuple] = set()
    for body in s2_bodies.values():
        all_s2_shingles.update(shingles_6gram(body))

    s2_only_shingles = all_s2_shingles - all_s1_shingles

    print(f"S2-only citations: {len(s2_only_citations)}")
    print(f"S2-only 6-gram shingles: {len(s2_only_shingles)}")

    # Run tests per pack
    test_a_issues = []  # S2-only shingles found in pack
    test_b_issues = []  # S2-only citations in pack
    test_c_issues = []  # Extra fields in pack
    test_d_issues = []  # High count < 2

    for pack_name in PACKS:
        pack = load_pack(pack_name)
        pack_issues = {
            'test_a': [],
            'test_b': [],
            'test_c': [],
            'test_d': None,
        }

        # Test (a): No S2-only 6-word shingle in any pack text field
        for section in pack.get('sections', []):
            for field in ('body_text_s1', 'body_text_s1_normalized', 'heading'):
                text = section.get(field, '') or ''
                section_sh = shingles_6gram(text)
                overlap = section_sh & s2_only_shingles
                if overlap:
                    sample = list(overlap)[:3]
                    pack_issues['test_a'].append({
                        'citation': section.get('citation'),
                        'field': field,
                        'sample_shingles': [' '.join(s) for s in sample],
                    })

        # Test (b): No S2-only citation in pack
        for section in pack.get('sections', []):
            cite = section.get('citation', '')
            if cite in s2_only_citations:
                pack_issues['test_b'].append(cite)

        # Test (c): No extra fields in pack schema
        # Check top-level fields
        extra_top = set(pack.keys()) - ALLOWED_TOP_FIELDS
        if extra_top:
            pack_issues['test_c'].append({'location': 'top_level', 'extra_fields': sorted(extra_top)})
        # Check section fields
        for section in pack.get('sections', []):
            extra_sec = set(section.keys()) - ALLOWED_SECTION_FIELDS
            if extra_sec:
                pack_issues['test_c'].append({
                    'location': f'section[{section.get("citation")}]',
                    'extra_fields': sorted(extra_sec),
                })

        # Test (d): Per-pack high counts >= 2 where >= 2 eligible citations exist
        high_count = sum(1 for s in pack.get('sections', []) if s.get('coverage_priority') == 'high')
        eligible_count = sum(
            1 for s in pack.get('sections', [])
            if s.get('status_s1') == 'active'
        )
        if eligible_count >= 2 and high_count < 2:
            pack_issues['test_d'] = {
                'high_count': high_count,
                'eligible_count': eligible_count,
                'message': f'Pack {pack_name} has {high_count} high citations but {eligible_count} eligible; need >= 2',
            }

        report['pack_results'][pack_name] = {
            'sections_total': len(pack.get('sections', [])),
            'active_sections': sum(1 for s in pack.get('sections', []) if s.get('status_s1') == 'active'),
            'high_sections': high_count,
            'test_a_issues': pack_issues['test_a'],
            'test_b_issues': pack_issues['test_b'],
            'test_c_issues': pack_issues['test_c'],
            'test_d_issue': pack_issues['test_d'],
        }

        if pack_issues['test_a']:
            test_a_issues.extend(pack_issues['test_a'])
        if pack_issues['test_b']:
            test_b_issues.extend(pack_issues['test_b'])
        if pack_issues['test_c']:
            test_c_issues.extend(pack_issues['test_c'])
        if pack_issues['test_d']:
            test_d_issues.append(pack_issues['test_d'])

    # Overall test results
    report['tests'] = {
        'a_no_s2_shingles': {
            'result': 'PASS' if not test_a_issues else 'FAIL',
            'description': 'No pack contains any S2-only 6-word shingle',
            'issue_count': len(test_a_issues),
            'issues': test_a_issues[:10],  # first 10
        },
        'b_no_s2_only_citations': {
            'result': 'PASS' if not test_b_issues else 'FAIL',
            'description': 'No pack contains any citation that exists only in S2',
            'issue_count': len(test_b_issues),
            'issues': test_b_issues[:20],
        },
        'c_no_extra_fields': {
            'result': 'PASS' if not test_c_issues else 'FAIL',
            'description': 'No pack field other than the specified schema fields',
            'issue_count': len(test_c_issues),
            'issues': test_c_issues[:10],
        },
        'd_high_counts': {
            'result': 'PASS' if not test_d_issues else 'FAIL',
            'description': 'Per-pack high counts >= 2 where possible',
            'issue_count': len(test_d_issues),
            'issues': test_d_issues,
        },
    }

    # Overall status
    any_fail = any(v['result'] == 'FAIL' for v in report['tests'].values())
    report['status'] = 'FAIL' if any_fail else 'PASS'

    return report


def main():
    report = run_leak_tests()

    out_path = os.path.join(GROUNDING_DIR, '_leaktest_report.json')
    with open(out_path, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\nLeak test result: {report['status']}")
    for test_name, test_result in report['tests'].items():
        print(f"  {test_name}: {test_result['result']} ({test_result['issue_count']} issues)")

    print(f"\nPer-pack summary:")
    for pack_name, pr in report['pack_results'].items():
        print(f"  {pack_name}: total={pr['sections_total']} active={pr['active_sections']} high={pr['high_sections']}")

    print(f"\nReport written to {out_path}")
    return report


if __name__ == '__main__':
    main()
