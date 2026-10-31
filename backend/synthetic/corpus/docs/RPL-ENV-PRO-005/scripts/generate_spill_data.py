#!/usr/bin/env python3
"""
RPL-ENV-PRO-005 — Spill Events 2024 Dataset Generator
Seed: 2024 (deterministic)
Output: ../data/spill_events_2024.csv
"""

import csv
import hashlib
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Regulatory parameters
# ---------------------------------------------------------------------------
# The grounding pack for T20 (327 IAC 2-6.1) is EMPTY (out-of-scope reference).
# No regulatory thresholds are stated. All reportability logic is company practice.
params = {}  # empty – pack not ingested

# ---------------------------------------------------------------------------
# Company-practice parameters (§1.6 Table S; RPL-ENV-PRO-005 company practice)
# ---------------------------------------------------------------------------
company_params = {
    # Reportability triggers (company practice — no regulatory threshold)
    # A release is reportable if ANY of the following is true:
    #   CP-R1: receiving medium is surface_water or storm_drain
    #   CP-R2: soil_beyond_boundary (release crosses facility boundary)
    #   CP-R3: special_area_flag = Y
    #   CP-R4: pcb_status_code in ('UNK', 'PCB-C', 'PCB') regardless of medium
    #   CP-R5: catch-all – when classification uncertain, treat as reportable
    # A release is NOT reportable only when:
    #   CP-NR1: impervious surface, fully contained (volume_recovered >= volume_released),
    #            no drain threat, pcb_status not UNK/PCB-C/PCB, special_area_flag=N
    # Internal response window for notification (company target): 2 hours from determination
    "internal_notification_window_hours": 2,
    # Written follow-up (company practice): 30 days from release
    "written_followup_days": 30,
    # PCB status codes (§1.6 Table S — WAM codes)
    "pcb_status_codes": ["NP-T", "NP-M", "UNK", "PCB-C", "PCB"],
    # Target fraction of releases that are mineral oil
    "mineral_oil_fraction": 0.75,
    # IDEM numbers (§1.6 Table X)
    "idem_24hr_phone": "(888) 233-7745",
}

# ---------------------------------------------------------------------------
# Reference data from §1.1, §1.6
# ---------------------------------------------------------------------------
SEED = 2024
SERVICE_CENTERS = ["LAF", "CRW", "THT", "FRK", "DAN"]
COUNTIES = [
    "Tippecanoe", "Clinton", "Carroll", "White", "Benton",
    "Warren", "Fountain", "Montgomery", "Boone", "Hendricks",
    "Putnam", "Parke", "Vermillion", "Vigo",
]
SC_COUNTY_MAP = {
    "LAF": ["Tippecanoe", "Clinton", "Carroll", "White", "Benton"],
    "CRW": ["Montgomery", "Fountain", "Warren"],
    "THT": ["Vigo", "Vermillion", "Parke"],
    "FRK": ["Clinton", "Carroll", "Boone"],
    "DAN": ["Hendricks", "Boone", "Putnam"],
}

SOURCE_TYPES = [
    "pole_transformer",
    "padmount_transformer",
    "substation_equipment",
    "standby_generator",
    "fleet_vehicle",
    "bucket_truck_hydraulic",
    "fueling",
]

# Note: ~75% of releases must be mineral_oil (pole_transformer + padmount_transformer +
# substation_equipment together account for that share)

# RPL classification for each source type (7.1 table)
CLASSIFICATION_MAP = {
    "pole_transformer": "facility_equipment",
    "padmount_transformer": "facility_equipment",
    "substation_equipment": "facility_equipment_inside_boundary",
    "standby_generator": "facility_belly_tank",
    "fleet_vehicle": "transportation_in_transit",
    "bucket_truck_hydraulic": "transportation_at_worksite",
    "fueling": "facility_fuel_storage",
}

SUBSTANCE_MAP = {
    "pole_transformer": "mineral_oil",
    "padmount_transformer": "mineral_oil",
    "substation_equipment": "mineral_oil",
    "standby_generator": "diesel",
    "fleet_vehicle": "diesel",
    "bucket_truck_hydraulic": "hydraulic_fluid",
    "fueling": "diesel",
}

# Typical nameplate volumes by source (gallons, §1.6 Table S)
VOLUME_RANGES = {
    "pole_transformer": (8, 55),       # pole-mount 10-167 kVA
    "padmount_transformer": (20, 650),  # padmount
    "substation_equipment": (60, 12000), # substation transformers + regulators
    "standby_generator": (10, 660),    # belly tanks (partial fills; full: 1500/660/660 gal)
    "fleet_vehicle": (5, 60),          # diesel tank partial spills
    "bucket_truck_hydraulic": (1, 15), # hydraulic hose failures
    "fueling": (1, 30),               # fueling overfill
}

# Release fraction (percentage of nameplate that actually escapes)
RELEASE_FRACTION = {
    "pole_transformer": (0.2, 1.0),
    "padmount_transformer": (0.1, 0.8),
    "substation_equipment": (0.05, 0.4),
    "standby_generator": (0.1, 0.9),
    "fleet_vehicle": (0.3, 1.0),
    "bucket_truck_hydraulic": (0.5, 1.0),
    "fueling": (0.6, 1.0),
}

CAUSES = {
    "pole_transformer": ["storm_wind", "lightning", "equipment_failure", "vehicle_strike", "vandalism_theft"],
    "padmount_transformer": ["vehicle_strike", "equipment_failure", "vandalism_theft", "storm_wind"],
    "substation_equipment": ["equipment_failure", "lightning", "storm_wind"],
    "standby_generator": ["equipment_failure", "overfill", "hose_failure"],
    "fleet_vehicle": ["vehicle_strike", "hose_failure", "equipment_failure"],
    "bucket_truck_hydraulic": ["hose_failure", "equipment_failure"],
    "fueling": ["overfill", "hose_failure"],
}

RECEIVING_MEDIA = [
    "impervious",
    "soil_inside_boundary",
    "soil_beyond_boundary",
    "surface_water",
    "storm_drain",
    "sewer",
]

PCB_STATUS_WEIGHTS = {
    "NP-T": 0.35,   # confirmed non-PCB tested
    "NP-M": 0.40,   # manufacturer certified non-PCB
    "UNK": 0.18,    # unknown – treat as PCB
    "PCB-C": 0.04,  # PCB-contaminated
    "PCB": 0.03,    # confirmed PCB equipment
}

# App-E forced events (must appear in the dataset)
APP_E_EVENTS = [
    {
        "event_id": "SPL-2024-0033",
        "discovered_ts": "2024-04-17T14:22",
        "service_center": "LAF",
        "county": "Tippecanoe",
        "source_type": "padmount_transformer",
        "substance": "mineral_oil",
        "pcb_status_code": "NP-M",
        "volume_released_gal": 42.0,
        "volume_recovered_gal": 8.0,
        "receiving_medium": "storm_drain",
        "special_area_flag": "N",
        "cause": "vehicle_strike",
        "decision_row": "T7-3",
        "reportable": "Y",
    },
    {
        "event_id": "SPL-2024-0071",
        "discovered_ts": "2024-07-09T08:55",
        "service_center": "CRW",
        "county": "Montgomery",
        "source_type": "pole_transformer",
        "substance": "mineral_oil",
        "pcb_status_code": "UNK",
        "volume_released_gal": 18.0,
        "volume_recovered_gal": 10.0,
        "receiving_medium": "soil_inside_boundary",
        "special_area_flag": "N",
        "cause": "lightning",
        "decision_row": "T7-5",
        "reportable": "Y",
    },
    {
        "event_id": "SPL-2024-0088",
        "discovered_ts": "2024-09-03T11:40",
        "service_center": "THT",
        "county": "Vigo",
        "source_type": "bucket_truck_hydraulic",
        "substance": "hydraulic_fluid",
        "pcb_status_code": "NP-T",
        "volume_released_gal": 3.5,
        "volume_recovered_gal": 3.5,
        "receiving_medium": "impervious",
        "special_area_flag": "N",
        "cause": "hose_failure",
        "decision_row": "T7-1",
        "reportable": "N",
    },
]


def determine_reportability(row):
    """
    Apply company-practice reportability rules (no regulatory thresholds).
    Returns (reportable, decision_row, exclusion_applied)
    """
    pcb = row["pcb_status_code"]
    medium = row["receiving_medium"]
    special = row["special_area_flag"]
    recovered = row["volume_recovered_gal"]
    released = row["volume_released_gal"]
    fully_contained = recovered >= released

    # CP-NR1 exclusion: impervious, fully contained, no PCB risk, no special area
    if (medium == "impervious" and fully_contained
            and pcb not in ("UNK", "PCB-C", "PCB")
            and special == "N"):
        return "N", "T7-1", "RPL-ENV-PRO-005:7.3.1"

    # CP-R4: PCB/UNK status regardless of medium
    if pcb in ("UNK", "PCB-C", "PCB"):
        return "Y", "T7-5", ""

    # CP-R3: special area flag
    if special == "Y":
        return "Y", "T7-4", ""

    # CP-R1: surface water or storm drain
    if medium in ("surface_water", "storm_drain"):
        return "Y", "T7-3", ""

    # CP-R2: beyond boundary
    if medium == "soil_beyond_boundary":
        return "Y", "T7-2", ""

    # Soil inside boundary, not PCB, not special area, not contained
    if medium == "soil_inside_boundary":
        if not fully_contained:
            return "Y", "T7-2", ""
        else:
            return "N", "T7-1", "RPL-ENV-PRO-005:7.3.2"

    # Sewer: reportable (conservative company practice)
    if medium == "sewer":
        return "Y", "T7-3", ""

    # Catch-all: reportable
    return "Y", "T7-6", ""


def generate_events(rng, n=95):
    """Generate n random spill events."""
    TZ = ZoneInfo("America/Indiana/Indianapolis")
    start = datetime(2024, 1, 1, tzinfo=TZ)
    end = datetime(2024, 12, 31, 23, 59, tzinfo=TZ)

    # Substance frequency: ~75% mineral oil
    # pole_transformer(mineral_oil) + padmount_transformer(mineral_oil) +
    # substation_equipment(mineral_oil) = 0.75 total weight
    source_weights = {
        "pole_transformer": 0.38,
        "padmount_transformer": 0.28,
        "substation_equipment": 0.09,
        "standby_generator": 0.05,
        "fleet_vehicle": 0.09,
        "bucket_truck_hydraulic": 0.07,
        "fueling": 0.04,
    }
    source_list = list(source_weights.keys())
    source_probs = list(source_weights.values())

    records = []
    seq = 1
    event_ids_used = {e["event_id"] for e in APP_E_EVENTS}

    for _ in range(n):
        # Generate event_id
        while True:
            candidate = f"SPL-2024-{seq:04d}"
            seq += 1
            if candidate not in event_ids_used:
                # reserve App-E IDs
                if candidate in {"SPL-2024-0033", "SPL-2024-0071", "SPL-2024-0088"}:
                    continue
                event_ids_used.add(candidate)
                break

        sc = rng.choice(SERVICE_CENTERS)
        county = rng.choice(SC_COUNTY_MAP[sc])
        source_type = rng.choices(source_list, weights=source_probs)[0]
        substance = SUBSTANCE_MAP[source_type]

        # Volume
        vol_min, vol_max = VOLUME_RANGES[source_type]
        vol_released = round(rng.triangular(vol_min, vol_max, vol_min * 2.5), 1)
        # Higher recovery for contained scenarios (more realistic)
        frac_recovered = rng.triangular(0.3, 1.0, 0.75)
        vol_recovered = round(min(vol_released * frac_recovered, vol_released), 1)

        # PCB status
        pcb_codes = list(PCB_STATUS_WEIGHTS.keys())
        pcb_wts = list(PCB_STATUS_WEIGHTS.values())
        # Substation equipment more likely to be tracked
        if source_type == "substation_equipment":
            pcb_wts = [0.25, 0.30, 0.25, 0.12, 0.08]
        pcb_status = rng.choices(pcb_codes, weights=pcb_wts)[0]

        # Receiving medium probabilities (impervious|soil_inside|soil_beyond|surface_water|storm_drain|sewer)
        medium_weights = {
            "pole_transformer": [0.04, 0.48, 0.22, 0.10, 0.12, 0.04],
            "padmount_transformer": [0.15, 0.25, 0.18, 0.08, 0.28, 0.06],
            "substation_equipment": [0.25, 0.50, 0.15, 0.04, 0.04, 0.02],
            "standby_generator": [0.40, 0.35, 0.10, 0.04, 0.08, 0.03],
            "fleet_vehicle": [0.25, 0.18, 0.28, 0.12, 0.12, 0.05],
            "bucket_truck_hydraulic": [0.45, 0.22, 0.18, 0.08, 0.05, 0.02],
            "fueling": [0.45, 0.30, 0.08, 0.04, 0.10, 0.03],
        }
        mwts = medium_weights.get(source_type, [1/6]*6)
        medium = rng.choices(RECEIVING_MEDIA, weights=mwts)[0]

        # Special area flag (10% chance, slightly higher for beyond-boundary)
        if medium in ("soil_beyond_boundary", "surface_water"):
            special = rng.choice(["Y", "Y", "N", "N", "N"])
        else:
            special = rng.choice(["Y"] + ["N"] * 9)

        cause_list = CAUSES.get(source_type, ["equipment_failure"])
        cause = rng.choice(cause_list)

        # Timestamps
        delta_seconds = int((end - start).total_seconds())
        disc_dt = start + timedelta(seconds=rng.randint(0, delta_seconds))
        # Duration to stop spill: 0.25–4 hours after discovery
        stop_dt = disc_dt + timedelta(hours=rng.uniform(0.25, 4.0))
        if stop_dt > end:
            stop_dt = end

        utc_offset = "-05:00" if disc_dt.month in (11, 12, 1, 2, 3) else "-04:00"

        reportable, decision_row, exclusion = determine_reportability({
            "pcb_status_code": pcb_status,
            "receiving_medium": medium,
            "special_area_flag": special,
            "volume_released_gal": vol_released,
            "volume_recovered_gal": vol_recovered,
        })

        # IDEM report timestamp (for reportable events)
        idem_report_ts = ""
        idem_incident_no = ""
        update_count = 0
        third_party_notice_req = "N"
        third_party_notice_ts = ""
        if reportable == "Y":
            # Company practice: report within 2 hours of determination
            # 80% within 1 hour, 20% within 2 hours (satisfying margin rule: no past limit)
            report_delay = rng.uniform(0.2, 1.8)  # all within 2-hr window
            idem_dt = disc_dt + timedelta(hours=rng.uniform(0.3, 0.8) + report_delay * 0.5)
            if idem_dt > end + timedelta(days=1):
                idem_dt = disc_dt + timedelta(hours=1.0)
            idem_report_ts = idem_dt.strftime("%Y-%m-%dT%H:%M")
            idem_incident_no = f"IDEM-ER-2024-{rng.randint(10000, 99999)}"
            update_count = rng.choices([0, 1, 2], weights=[0.60, 0.30, 0.10])[0]
            # Third-party notice: if surface water, beyond boundary, or special area
            if medium in ("surface_water",) or special == "Y":
                third_party_notice_req = "Y"
                tpn_dt = disc_dt + timedelta(hours=rng.uniform(1.0, 8.0))
                third_party_notice_ts = tpn_dt.strftime("%Y-%m-%dT%H:%M")

        # Closed date
        close_days = rng.randint(5, 45)
        closed_date = (disc_dt + timedelta(days=close_days)).strftime("%Y-%m-%d")

        compliance_conf_req = "Y" if reportable == "Y" and medium in ("surface_water", "storm_drain") else "N"

        records.append({
            "event_id": candidate,
            "discovered_ts": disc_dt.strftime("%Y-%m-%dT%H:%M"),
            "stopped_ts": stop_dt.strftime("%Y-%m-%dT%H:%M"),
            "utc_offset": utc_offset,
            "service_center": sc,
            "county": county,
            "source_type": source_type,
            "rpl_classification": CLASSIFICATION_MAP[source_type],
            "substance": substance,
            "pcb_status_code": pcb_status,
            "volume_released_gal": vol_released,
            "volume_recovered_gal": vol_recovered,
            "receiving_medium": medium,
            "special_area_flag": special,
            "cause": cause,
            "reportable": reportable,
            "decision_row": decision_row,
            "exclusion_applied": exclusion,
            "idem_report_ts": idem_report_ts,
            "idem_incident_no": idem_incident_no,
            "update_count": update_count,
            "third_party_notice_required": third_party_notice_req,
            "third_party_notice_ts": third_party_notice_ts,
            "closed_date": closed_date,
            "compliance_confirmation_requested": compliance_conf_req,
        })

    return records


def inject_app_e(records):
    """Add App-E forced events with full computed columns."""
    TZ = ZoneInfo("America/Indiana/Indianapolis")
    result = []
    app_e_ids = {e["event_id"] for e in APP_E_EVENTS}

    # Remove any accidental collision from generated records
    records = [r for r in records if r["event_id"] not in app_e_ids]

    for forced in APP_E_EVENTS:
        disc_dt = datetime.fromisoformat(forced["discovered_ts"]).replace(tzinfo=TZ)
        # stop 1–2 hours later
        stop_dt = disc_dt + timedelta(hours=1.5)
        utc_offset = "-05:00" if disc_dt.month in (11, 12, 1, 2, 3) else "-04:00"

        idem_report_ts = ""
        idem_incident_no = ""
        update_count = 0
        tpn_req = "N"
        tpn_ts = ""
        compliance_conf_req = "N"

        if forced["reportable"] == "Y":
            report_dt = disc_dt + timedelta(hours=0.75)
            idem_report_ts = report_dt.strftime("%Y-%m-%dT%H:%M")
            idem_incident_no = f"IDEM-ER-2024-{int(forced['event_id'].split('-')[-1]) + 50000}"
            update_count = 1
            if forced["receiving_medium"] in ("surface_water", "storm_drain"):
                tpn_req = "Y"
                tpn_dt = disc_dt + timedelta(hours=2.0)
                tpn_ts = tpn_dt.strftime("%Y-%m-%dT%H:%M")
                compliance_conf_req = "Y"

        close_dt = disc_dt + timedelta(days=21)

        result.append({
            "event_id": forced["event_id"],
            "discovered_ts": forced["discovered_ts"],
            "stopped_ts": stop_dt.strftime("%Y-%m-%dT%H:%M"),
            "utc_offset": utc_offset,
            "service_center": forced["service_center"],
            "county": forced["county"],
            "source_type": forced["source_type"],
            "rpl_classification": CLASSIFICATION_MAP[forced["source_type"]],
            "substance": forced["substance"],
            "pcb_status_code": forced["pcb_status_code"],
            "volume_released_gal": forced["volume_released_gal"],
            "volume_recovered_gal": forced["volume_recovered_gal"],
            "receiving_medium": forced["receiving_medium"],
            "special_area_flag": forced["special_area_flag"],
            "cause": forced["cause"],
            "reportable": forced["reportable"],
            "decision_row": forced["decision_row"],
            "exclusion_applied": forced.get("exclusion_applied", ""),
            "idem_report_ts": idem_report_ts,
            "idem_incident_no": idem_incident_no,
            "update_count": update_count,
            "third_party_notice_required": tpn_req,
            "third_party_notice_ts": tpn_ts,
            "closed_date": close_dt.strftime("%Y-%m-%d"),
            "compliance_confirmation_requested": compliance_conf_req,
        })

    # Combine and sort by event_id
    all_records = records + result
    all_records.sort(key=lambda r: r["event_id"])
    return all_records


def main():
    rng = random.Random(SEED)

    # Generate base records (target ~92 to get 95 total with 3 forced)
    records = generate_events(rng, n=92)
    records = inject_app_e(records)

    assert 80 <= len(records) <= 110, f"Row count out of range: {len(records)}"

    out_dir = Path(__file__).parent.parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "spill_events_2024.csv"

    columns = [
        "event_id", "discovered_ts", "stopped_ts", "utc_offset",
        "service_center", "county",
        "source_type", "rpl_classification",
        "substance", "pcb_status_code",
        "volume_released_gal", "volume_recovered_gal",
        "receiving_medium", "special_area_flag", "cause",
        "reportable", "decision_row", "exclusion_applied",
        "idem_report_ts", "idem_incident_no", "update_count",
        "third_party_notice_required", "third_party_notice_ts",
        "closed_date", "compliance_confirmation_requested",
    ]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)

    # Compute sha256
    sha256 = hashlib.sha256(out_path.read_bytes()).hexdigest()

    # Write manifest
    manifest = {
        "files": [
            {
                "file": "spill_events_2024.csv",
                "rows": len(records),
                "columns": columns,
                "sha256": sha256,
                "generator_script": "scripts/generate_spill_data.py",
                "seed": SEED,
            }
        ]
    }
    manifest_path = out_dir / "_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Generated {len(records)} rows → {out_path}")
    print(f"SHA-256: {sha256}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
