"""
generate_ops_master.py
Deterministic generator for Rockridge Power & Light Company (RPL) shared
operational master data (T04 of the Strata v1 Synthetic Corpus).

Seed: 2024 — same seed always produces the same output.
"""

import os, json, math, hashlib, datetime
import numpy as np
import pandas as pd
import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, "..")
SEED = 2024

# ---------------------------------------------------------------------------
# §1.1 canonical constants
# ---------------------------------------------------------------------------
TOTAL_CUSTOMERS  = 407_491
RESIDENTIAL      = 361_480
NON_RESIDENTIAL  = 46_011
N_SUBSTATIONS    = 112
N_CIRCUITS       = 528
OH_MILES_TARGET  = 14_200.0
UG_MILES_TARGET  = 4_900.0

SERVICE_CENTERS  = ["LAF", "CRW", "THT", "FRK", "DAN"]

# 14 counties per §1.1
COUNTIES = [
    "Tippecanoe", "Vigo", "Hendricks", "Boone",
    "Putnam", "Fountain", "Warren", "Benton",
    "Carroll", "Clinton", "Montgomery", "Parke",
    "Vermillion", "White",
]

COUNTY_SC = {
    "Tippecanoe": "LAF", "Clinton": "FRK", "Carroll": "LAF",
    "Benton": "LAF",     "Warren": "LAF",  "Fountain": "CRW",
    "Montgomery": "CRW", "Boone": "DAN",   "Hendricks": "DAN",
    "Putnam": "CRW",     "Parke": "CRW",   "Vermillion": "THT",
    "White": "FRK",      "Vigo": "THT",
}

COUNTY_CUST_SHARE_RAW = {
    "Tippecanoe": 0.255, "Vigo": 0.150, "Hendricks": 0.120, "Boone": 0.100,
    "Montgomery": 0.060, "Clinton": 0.048, "Putnam": 0.045, "Carroll": 0.032,
    "Fountain": 0.030,   "Parke": 0.028,  "Warren": 0.025,  "Vermillion": 0.040,
    "Benton": 0.025,     "White": 0.010,
}
_cs = sum(COUNTY_CUST_SHARE_RAW.values())
COUNTY_CUST_SHARE = {k: v/_cs for k, v in COUNTY_CUST_SHARE_RAW.items()}

SUBSTATION_NAMES = [
    "Wea Creek","Wabash","Wildcat","Sugar Creek",
    "Lafayette East","Lafayette West","Lafayette North","Lafayette South",
    "Tippecanoe","Crawfordsville","Terre Haute","Frankfort","Danville",
    "Attica","Covington","Fountain County","Benton County","Warren County",
    "Clinton Falls","Greencastle","Fillmore","Roachdale","Walton","Flora",
    "Delphi","Monticello","Brookston","Shadeland","Romney","Wingate",
    "Darlington","New Market","Waynetown","Carroll County","Parke County",
    "Vermillion County","Boone County","Hendricks South","Plainfield","Avon",
    "Brownsburg","Pittsboro","Whitestown","Zionsville","Lebanon","Thorntown",
    "Jamestown","Rockville","Rosedale","Fontanet","Seelyville","West Terre Haute",
    "Brazil","Knightsville","Cory","Diamond","Staunton","Riley",
    "Pimento","Shepardsville","Lewis","Turkey Run","Alamo","Mecca",
    "Montezuma","Newport","Clinton County","Forest","Michigantown",
    "Kirklin","Mulberry","Frankfort East","Boyleston","Sedalia",
    "Stockwell","Colburn","Battle Ground","Dayton","Otterbein","Linden",
    "Bowers","Cementon","Big Creek","Indian Creek","Buck Creek","Pine Creek",
    "Coal Creek","Highland","Ingle","Yeddo","Newtown","Marshall",
    "Lodi","Cayuga","Dana","Perrysville","Fountain Park","Covington East",
    "Covington West","Fountain North","Mellott","Hillsboro","Wallace",
    "Veedersburg","Wingate North","New Richmond","Alamo East","Alamo West",
    "Monon","Reynolds","Chalmers","Brookfield","Idaville","Burnettsville",
    "Buffalo","Monticello East","White County","Wolcott","Chalmers West",
]


def _round_to_exact(floats, target):
    floored = np.floor(floats).astype(int)
    remainders = floats - floored
    deficit = target - floored.sum()
    idx = np.argsort(-remainders)[:deficit]
    floored[idx] += 1
    return floored


def _make_substations():
    rng = np.random.default_rng(SEED + 1)
    counties_sorted = sorted(COUNTY_CUST_SHARE.keys(),
                             key=lambda c: COUNTY_CUST_SHARE[c], reverse=True)
    raw = {c: max(1, int(round(COUNTY_CUST_SHARE[c] * N_SUBSTATIONS))) for c in COUNTIES}
    diff = N_SUBSTATIONS - sum(raw.values())
    raw[counties_sorted[0]] += diff

    rows = []
    used = set()
    sc_idx = {sc: 1 for sc in SERVICE_CENTERS}

    for county in COUNTIES:
        sc = COUNTY_SC[county]
        rural = COUNTY_CUST_SHARE[county] < 0.04
        for i in range(raw[county]):
            for attempt in range(300):
                name = SUBSTATION_NAMES[rng.integers(0, len(SUBSTATION_NAMES))]
                if attempt >= 3:
                    name = f"{name} {i+1}"
                if name not in used:
                    used.add(name)
                    break
            kv = 34.5 if rng.random() < (0.35 if rural else 0.15) else 12.47
            sid = f"{sc}-{sc_idx[sc]:03d}"
            sc_idx[sc] += 1
            rows.append({
                "substation_id": sid, "substation_name": name,
                "service_center": sc, "county": county,
                "primary_kv": kv,
                "supply_69kv_line_id": f"69KV-{sc}-{sc_idx[sc]-1:03d}",
                "transformer_count": int(rng.integers(1, 4)),
                "circuit_count": 0,
            })

    df = pd.DataFrame(rows)
    assert len(df) == N_SUBSTATIONS
    return df


def _make_circuits(subs_df):
    rng = np.random.default_rng(SEED + 2)
    n_subs = len(subs_df)
    ckt_counts = np.ones(n_subs, dtype=int) * 4
    extra = N_CIRCUITS - ckt_counts.sum()
    ckt_counts[rng.choice(n_subs, size=extra, replace=True)] += 1
    # Use a proper loop to distribute extras (may hit same index multiple times)
    ckt_counts = np.ones(n_subs, dtype=int) * 4
    idx_extra = rng.choice(n_subs, size=extra, replace=True)
    for i in idx_extra:
        ckt_counts[i] += 1
    assert ckt_counts.sum() == N_CIRCUITS

    VM_CATS = ["backbone", "lateral_dominant", "urban_ug_dominant"]
    VM_W    = [0.35, 0.50, 0.15]

    # --- miles draws ---
    rng2 = np.random.default_rng(SEED + 2)
    raw_oh, raw_ug, vm_list, volt_list, sub_list, county_list, sc_list = [], [], [], [], [], [], []
    for si, row in subs_df.iterrows():
        sid = row["substation_id"]
        for _ in range(ckt_counts[si]):
            vm = rng2.choice(VM_CATS, p=VM_W)
            if vm == "backbone":
                oh = rng2.lognormal(3.5, 0.5); ug = rng2.lognormal(1.5, 0.6)
            elif vm == "lateral_dominant":
                oh = rng2.lognormal(3.0, 0.5); ug = rng2.lognormal(0.8, 0.6)
            else:
                oh = rng2.lognormal(1.5, 0.5); ug = rng2.lognormal(2.8, 0.5)
            raw_oh.append(oh); raw_ug.append(ug)
            vm_list.append(vm); volt_list.append(row["primary_kv"])
            sub_list.append(sid); county_list.append(row["county"])
            sc_list.append(row["service_center"])

    raw_oh = np.array(raw_oh); raw_ug = np.array(raw_ug)
    scaled_oh = raw_oh * (OH_MILES_TARGET / raw_oh.sum())
    scaled_ug = raw_ug * (UG_MILES_TARGET / raw_ug.sum())

    # --- customer allocation ---
    urban_mult = np.array([0.85 if v == "urban_ug_dominant" else 1.0 for v in vm_list])
    county_sh  = np.array([COUNTY_CUST_SHARE[c] for c in county_list])
    size_proxy = 1.0 + np.log1p(scaled_oh + scaled_ug)
    res_w   = county_sh * size_proxy * urban_mult
    nonr_w  = county_sh * size_proxy * (1 - urban_mult * 0.5)
    res_int   = _round_to_exact(res_w / res_w.sum() * RESIDENTIAL, RESIDENTIAL)
    nonres_int = _round_to_exact(nonr_w / nonr_w.sum() * NON_RESIDENTIAL, NON_RESIDENTIAL)
    assert res_int.sum() == RESIDENTIAL
    assert nonres_int.sum() == NON_RESIDENTIAL
    assert (res_int + nonres_int).sum() == TOTAL_CUSTOMERS

    oh_r = np.round(scaled_oh, 1)
    ug_r = np.round(scaled_ug, 1)
    oh_r[-1] += round(OH_MILES_TARGET - oh_r.sum(), 1)
    ug_r[-1] += round(UG_MILES_TARGET - ug_r.sum(), 1)

    rows = []
    ckt_n = {}
    for idx in range(N_CIRCUITS):
        sid = sub_list[idx]
        ckt_n[sid] = ckt_n.get(sid, 0) + 1
        vm = vm_list[idx]
        phase = ("backbone_3ph_with_laterals"
                 if vm == "urban_ug_dominant" or rng2.random() > 0.35
                 else "1ph_dominant")
        crit = int(rng2.poisson(2 if vm == "urban_ug_dominant" else 0.3))
        # last_trim_year
        if vm == "backbone":
            lty = 2020 if rng2.random() < 0.05 else 2021
        else:
            lty = 2019 if rng2.random() < 0.08 else 2020
        rows.append({
            "circuit_id": f"{sid}-{ckt_n[sid]}",
            "substation_id": sid,
            "service_center": sc_list[idx],
            "county": county_list[idx],
            "voltage_kv": volt_list[idx],
            "phase_type": phase,
            "oh_miles": round(float(oh_r[idx]), 1),
            "ug_miles": round(float(ug_r[idx]), 1),
            "customers_on_circuit": int(res_int[idx] + nonres_int[idx]),
            "customers_residential": int(res_int[idx]),
            "customers_nonresidential": int(nonres_int[idx]),
            "critical_facilities": crit,
            "vm_category": vm,
            "last_trim_year": lty,
        })
    return pd.DataFrame(rows)


def _make_daily_saidi_history():
    rng = np.random.default_rng(SEED + 3)
    dates = pd.date_range("2019-01-01", "2023-12-31", freq="D")
    assert len(dates) == 1826

    def cserved(d):
        yrs = (datetime.date(2024, 12, 31) - d).days / 365.25
        return int(round(407_491 / (1.009 ** yrs)))

    n = len(dates)
    base = np.zeros(n)
    nz = rng.random(n) > 0.28
    base[nz] = rng.lognormal(1.5, 1.3, size=n)[nz]

    for yr in range(2019, 2024):
        ns = int(rng.integers(3, 8))
        yidx = np.where([d.year == yr for d in dates])[0]
        for si in rng.choice(yidx, size=ns, replace=False):
            base[si] += rng.uniform(60, 300)

    rows = []
    for i, d in enumerate(dates):
        cs = cserved(d.date())
        s = round(float(base[i]), 4)
        rows.append({"date": d.date().isoformat(), "customers_served": cs,
                     "cmi_all": int(s * cs), "saidi_all_min": s})
    return pd.DataFrame(rows)


def _compute_tmed(daily_df):
    nz = daily_df[daily_df["saidi_all_min"] > 0]["saidi_all_min"].values
    x = np.log(nz)
    mu = np.mean(x); sigma = np.std(x, ddof=1)
    return np.exp(mu + 2.5 * sigma), mu, sigma


def _make_med_days(tmed):
    rng = np.random.default_rng(SEED + 4)
    med_dates = [
        datetime.date(2024, 3, 15),
        datetime.date(2024, 5, 22),
        datetime.date(2024, 7, 4),
        datetime.date(2024, 8, 9),
        datetime.date(2024, 12, 23),
    ]
    rows = [{
        "year": d.year, "tmed_saidi_min": round(tmed, 4),
        "med_date": d.isoformat(),
        "daily_saidi_min": round(tmed * rng.uniform(3.0, 8.0), 2),
    } for d in med_dates]
    return pd.DataFrame(rows), med_dates


def _make_outage_events(circuits_df, subs_df, med_dates):
    """
    Generate events calibrated to:
      ex-MED SAIFI 1.05-1.15, SAIDI 130-150, CAIDI 115-140
      with-MED SAIDI 220-350
    Strategy:
      • Use level distribution biased toward service/transformer
      • Feeder 7%, sub 0.08%, supply 0.02% to keep mean CI/event ~50
      • Post-generate scaling step to normalise SAIFI into target band
    """
    rng = np.random.default_rng(SEED + 5)

    CAUSE_MAP = {
        "vegetation": ["tree_inside_row_growth","tree_inside_row_failure",
                       "tree_outside_row_fallin","tree_unknown_location"],
        "weather":    ["wind","lightning","ice_snow","flood","heat"],
        "equipment":  ["oh_conductor","ug_cable","transformer","cutout_fuse",
                       "arrester","insulator","pole","connector",
                       "recloser_breaker","substation_equipment"],
        "animal":     ["squirrel","bird","snake_raccoon_other"],
        "public":     ["vehicle","dig_in","vandalism_theft","fire",
                       "customer_equipment","third_party_contact"],
        "power_supply":["69kv_line","transmission_supply_miso","substation_supply"],
        "operational":["overload","switching_error","protection_miscoordination"],
        "planned":    ["maintenance","construction","emergency_switching_for_safety"],
        "unknown":    ["unknown_patrolled_no_cause"],
    }

    # ex-MED cause shares (targets: veg 20-27%, equip 25-33%, animal 12-18%,
    #   weather 8-14%, public 5-9%, power_supply 1-3%, operational 1-3%,
    #   planned 5-10%, unknown 6-12%)
    CSH = {"vegetation":0.215,"equipment":0.285,"animal":0.130,"weather":0.110,
           "public":0.070,"power_supply":0.020,"operational":0.020,
           "planned":0.070,"unknown":0.065}
    _t = sum(CSH.values()); CSH = {k:v/_t for k,v in CSH.items()}

    # MED day cause shares
    CSH_MED = {"vegetation":0.45,"weather":0.35,"equipment":0.10,"animal":0.02,
               "public":0.02,"power_supply":0.03,"operational":0.01,
               "planned":0.01,"unknown":0.01}

    # Level distribution (calibrated for SAIFI target)
    LEVEL_W = {"service":0.37,"transformer":0.30,"lateral":0.25,
               "feeder":0.070,"substation":0.0080,"supply":0.002}
    _lw = sum(LEVEL_W.values())
    LEVEL_W = {k:v/_lw for k,v in LEVEL_W.items()}

    # Customer size: lognormal(mu, sigma) — mu = ln(median)
    # Medians: service=2, transformer=5, lateral=35, feeder=300, sub=2300, supply=6250
    CUST_PARAMS = {
        "service":     (math.log(2),    0.50),
        "transformer": (math.log(5),    0.60),
        "lateral":     (math.log(35),   0.80),
        "feeder":      (math.log(300),  0.90),
        "substation":  (math.log(2300), 0.70),
        "supply":      (math.log(6250), 0.70),
    }
    # Duration (minutes): lognormal(mu, sigma)
    # With ci_scale ~0.669 applied to customers, SAIDI = SAIFI × CAIDI.
    # Actual CMI uses restoration step fractions (~0.68×customers×duration).
    # These medians produce CAIDI ~127 min → SAIDI ~140 min.
    DUR_PARAMS = {
        "service":     (math.log(65),  0.80),
        "transformer": (math.log(80),  0.80),
        "lateral":     (math.log(88),  0.80),
        "feeder":      (math.log(100), 0.70),
        "substation":  (math.log(130), 0.70),
        "supply":      (math.log(160), 0.70),
    }

    DEVICE_BY_LEVEL = {
        "service":     ["service"],
        "transformer": ["transformer"],
        "lateral":     ["fuse","sectionalizer"],
        "feeder":      ["feeder_breaker","recloser"],
        "substation":  ["substation_breaker"],
        "supply":      ["69kv_line"],
    }
    DETECT_BY_LEVEL = {
        "service":     ["ami_last_gasp","customer_call"],
        "transformer": ["ami_last_gasp","customer_call","scada"],
        "lateral":     ["ami_last_gasp","customer_call","scada"],
        "feeder":      ["scada","ami_last_gasp"],
        "substation":  ["scada"],
        "supply":      ["scada"],
    }

    MONTH_RATE = {1:0.7,2:0.7,3:1.0,4:1.5,5:1.8,6:1.8,
                  7:1.9,8:1.8,9:1.2,10:1.0,11:0.9,12:0.9}
    MONTH_RATE_2025 = {1:0.9}

    circuit_ids = circuits_df["circuit_id"].tolist()
    ckt_sub  = dict(zip(circuits_df["circuit_id"], circuits_df["substation_id"]))
    ckt_cust = dict(zip(circuits_df["circuit_id"], circuits_df["customers_on_circuit"]))
    ckt_co   = dict(zip(circuits_df["circuit_id"], circuits_df["county"]))
    ckt_sc   = dict(zip(circuits_df["circuit_id"], circuits_df["service_center"]))

    med_set = {str(d) for d in med_dates}

    levels_list = list(LEVEL_W.keys())
    levels_prob = [LEVEL_W[k] for k in levels_list]

    TARGET_EVENTS = 10_800
    N_MED_FRAC = 0.12   # ~12% of events on MED days

    n_nonmed = int(TARGET_EVENTS * (1 - N_MED_FRAC))
    n_med    = TARGET_EVENTS - n_nonmed

    # --- allocate non-MED events by month ---
    all_months = [(2024,m) for m in range(1,13)] + [(2025,1)]
    rates = {(2024,m): MONTH_RATE[m] for m in range(1,13)}
    rates[(2025,1)] = MONTH_RATE_2025[1]
    total_rate = sum(rates.values())
    month_n = {k: int(n_nonmed * v/total_rate) for k,v in rates.items()}
    deficit = n_nonmed - sum(month_n.values())
    month_n[(2024,6)] += deficit

    import calendar

    def rand_ts(year, month):
        _, ld = calendar.monthrange(year, month)
        return datetime.datetime(year, month,
                                 int(rng.integers(1,ld+1)),
                                 int(rng.integers(0,24)),
                                 int(rng.integers(0,60)), 0)

    def tree_loc(cat, code):
        if cat != "vegetation": return "n/a"
        if "inside" in code:  return "inside_row"
        if "outside" in code: return "outside_row"
        return "unknown"

    raw_events = []
    inc_counter = 1
    evt_counter = 1
    med_inc = {str(d): f"INC-2024-{inc_counter+i:05d}" for i,d in enumerate(med_dates)}
    inc_counter += len(med_dates)

    def make_event(year, month, day=None, is_med=False, med_date_str="", inc_id=None):
        nonlocal inc_counter, evt_counter
        level = rng.choice(levels_list, p=levels_prob)
        mu_c, sig_c = CUST_PARAMS[level]
        mu_d, sig_d = DUR_PARAMS[level]

        ci = max(1, int(round(rng.lognormal(mu_c, sig_c))))
        # MED events: somewhat more customers (kept moderate to control with-MED SAIDI)
        if is_med:
            ci = int(round(ci * rng.uniform(1.2, 2.5)))
        ckt_idx = int(rng.integers(0, len(circuit_ids)))
        ckt_id  = circuit_ids[ckt_idx]
        max_cust = ckt_cust[ckt_id]
        if level in ("service","transformer","lateral","feeder"):
            ci = min(ci, max_cust)
        ci = max(1, ci)

        dur = max(1, int(round(rng.lognormal(mu_d, sig_d))))
        if is_med:
            dur = int(round(dur * rng.uniform(2.0, 4.0)))

        if day is not None:
            ts = datetime.datetime(year, month, day,
                                   int(rng.integers(0,24)), int(rng.integers(0,60)), 0)
        else:
            ts = rand_ts(year, month)

        cause_cat = rng.choice(list(CSH_MED.keys()),
                               p=list(CSH_MED.values())) if is_med \
               else rng.choice(list(CSH.keys()), p=list(CSH.values()))
        cause_code = rng.choice(CAUSE_MAP[cause_cat])

        w_code = cause_code if cause_cat == "weather" else ""
        intentional = "Y" if cause_cat == "planned" else "N"
        detect = rng.choice(DETECT_BY_LEVEL[level])
        device_type = rng.choice(DEVICE_BY_LEVEL[level])
        end_ts = ts + datetime.timedelta(minutes=dur)

        if inc_id is None:
            inc_id = f"INC-{year}-{inc_counter:05d}"
            inc_counter += 1

        evt_id = f"EVT-{year}-{evt_counter:07d}"
        evt_counter += 1
        return {
            "event_id": evt_id, "incident_id": inc_id,
            "start_ts": ts.strftime("%Y-%m-%dT%H:%M:%S"),
            "end_ts":   end_ts.strftime("%Y-%m-%dT%H:%M:%S"),
            "utc_offset": "-05:00", "duration_min": dur,
            "customers_affected": ci, "customer_minutes": 0, "restoration_steps": 0,
            "circuit_id": ckt_id, "substation_id": ckt_sub[ckt_id],
            "service_center": ckt_sc[ckt_id], "county": ckt_co[ckt_id],
            "municipality": "unincorporated",
            "device_type": device_type,
            "device_id": f"{device_type.upper()}-{ckt_id}-{int(rng.integers(1,99)):02d}",
            "outage_level": level, "cause_category": cause_cat, "cause_code": cause_code,
            "tree_location": tree_loc(cause_cat, cause_code),
            "weather_code": w_code, "intentional": intentional,
            "critical_facilities_affected": 0, "detection_source": detect,
            "med_flag": "Y" if is_med else "N",
            "med_date": med_date_str if is_med else "",
            "notes": "major event day storm event" if is_med else "",
        }

    # Non-MED events
    for (yr, mo), n in month_n.items():
        for _ in range(n):
            raw_events.append(make_event(yr, mo))

    # MED events
    n_per_med = n_med // len(med_dates)
    for d in med_dates:
        n_this = int(n_per_med * (1.5 if d.month == 3 else 1.0))
        inc_id = med_inc[str(d)]
        for _ in range(n_this):
            raw_events.append(make_event(d.year, d.month, d.day,
                                         is_med=True, med_date_str=str(d), inc_id=inc_id))

    raw_events.sort(key=lambda e: e["start_ts"])
    print(f"  Raw events generated: {len(raw_events)}")

    # -----------------------------------------------------------------------
    # Scaling step: normalise SAIFI to 1.05–1.15 range
    # -----------------------------------------------------------------------
    ANNUAL_CUST = int(round(407_491 / (1.009 ** 0.5)))  # mid-2024 ~405,667

    exmed_events = [e for e in raw_events
                    if e["med_flag"] == "N" and e["start_ts"].startswith("2024")]
    raw_ci = sum(e["customers_affected"] for e in exmed_events)
    raw_saifi = raw_ci / ANNUAL_CUST
    target_saifi = 1.10
    ci_scale = target_saifi / raw_saifi if raw_saifi > 0 else 1.0
    print(f"  Raw ex-MED SAIFI={raw_saifi:.4f}  scale factor={ci_scale:.4f}")

    # Clamp ci_scale; do NOT scale duration (medians already calibrated)
    ci_scale = max(0.5, min(2.0, ci_scale))
    print(f"  ci_scale applied={ci_scale:.4f}")

    for e in raw_events:
        if e["med_flag"] == "N":
            new_ci = max(1, round(e["customers_affected"] * ci_scale))
            max_c = ckt_cust[e["circuit_id"]]
            if e["outage_level"] in ("service","transformer","lateral","feeder"):
                new_ci = min(new_ci, max_c)
            e["customers_affected"] = max(1, new_ci)

    # -----------------------------------------------------------------------
    # Restoration steps
    # -----------------------------------------------------------------------
    steps = []
    for e in raw_events:
        n_cust = e["customers_affected"]
        dur    = e["duration_min"]
        ts0    = datetime.datetime.fromisoformat(e["start_ts"])
        n_steps = 1 if n_cust <= 2 else int(rng.integers(1, min(5, n_cust+1)))

        if n_steps == 1:
            restored = [n_cust]
            times    = [ts0 + datetime.timedelta(minutes=dur)]
        else:
            fracs = rng.dirichlet(np.ones(n_steps) * 2.0)
            r_raw = _round_to_exact(fracs * n_cust, n_cust)
            restored = r_raw.tolist()
            tf = np.sort(np.concatenate([rng.uniform(0.3, 1.0, n_steps-1), [1.0]]))
            times = [ts0 + datetime.timedelta(minutes=max(1, int(dur * f))) for f in tf]

        total_cm = 0; remaining = n_cust
        for si, (st, cr) in enumerate(zip(times, restored)):
            mo = max(1, int((st - ts0).total_seconds() / 60))
            total_cm += cr * mo
            remaining -= cr
            steps.append({"event_id": e["event_id"], "step_no": si+1,
                           "step_ts": st.strftime("%Y-%m-%dT%H:%M:%S"),
                           "customers_restored": int(cr),
                           "customers_remaining": max(0, remaining)})
        e["customer_minutes"]  = total_cm
        e["restoration_steps"] = n_steps

    events_df = pd.DataFrame(raw_events)
    steps_df  = pd.DataFrame(steps)

    # -----------------------------------------------------------------------
    # Incidents
    # -----------------------------------------------------------------------
    inc_rows = []
    for inc_id, grp in events_df.groupby("incident_id"):
        is_med  = (grp["med_flag"] == "Y").any()
        is_plan = (grp["cause_category"] == "planned").all()
        inc_type = "storm" if is_med else ("planned" if is_plan else "single_event")
        inc_rows.append({
            "incident_id": inc_id,
            "incident_type": inc_type,
            "first_start_ts": grp["start_ts"].min(),
            "utc_offset": "-05:00",
            "utility_aware_ts": grp["start_ts"].min(),
            "peak_customers_out": int(grp["customers_affected"].max()),
            "peak_ts": grp["start_ts"].min(),
            "total_customers_affected": int(grp["customers_affected"].sum()),
            "counties_affected": "|".join(sorted(grp["county"].unique())),
            "municipalities_affected": "",
            "critical_facilities_affected": 0,
            "restored_ts": grp["end_ts"].max(),
            "etr_first_ts": grp["start_ts"].min(),
            "primary_cause_category": grp["cause_category"].mode()[0],
        })
    inc_df = pd.DataFrame(inc_rows)
    print(f"  Final: {len(events_df)} events, {len(steps_df)} steps, {len(inc_df)} incidents")
    return inc_df, events_df, steps_df


def _make_reliability_facts(events_df, tmed, med_dates):
    def cs_mid(m):
        d = datetime.date(2024, m, 15)
        return int(round(407_491 / (1.009 ** ((datetime.date(2024,12,31)-d).days/365.25))))

    monthly_cs = {m: cs_mid(m) for m in range(1, 13)}
    annual_cs  = cs_mid(7)

    med_set = {str(d) for d in med_dates}
    ev24 = events_df[events_df["start_ts"].str.startswith("2024")].copy()
    ev24["month"]   = ev24["start_ts"].str[5:7].astype(int)
    ev24["is_med"]  = ev24["med_flag"] == "Y"
    ev24["is_plan"] = ev24["cause_category"] == "planned"

    def idx(df, cs, xm=False, xp=False):
        d = df.copy()
        if xm: d = d[~d["is_med"]]
        if xp: d = d[~d["is_plan"]]
        ci  = int(d["customers_affected"].sum())
        cmi = int(d["customer_minutes"].sum())
        saifi = round(ci / cs, 4)
        saidi = round(cmi / cs, 4)
        caidi = round(saidi / saifi, 4) if saifi > 0 else 0.0
        return {"ci": ci, "cmi": cmi, "saifi": saifi, "saidi": saidi, "caidi": caidi}

    ann_wm = idx(ev24, annual_cs)
    ann_xm = idx(ev24, annual_cs, xm=True)

    monthly = {}
    for m in range(1, 13):
        me = ev24[ev24["month"] == m]
        monthly[m] = {"with_med": idx(me, monthly_cs[m]),
                      "ex_med":   idx(me, monthly_cs[m], xm=True),
                      "customers_served": monthly_cs[m]}

    veg = ev24[ev24["cause_category"] == "vegetation"]
    veg_in  = ev24[ev24["tree_location"] == "inside_row"]
    veg_out = ev24[ev24["tree_location"] == "outside_row"]

    def _native(obj):
        """Recursively convert numpy scalars to native Python types."""
        if isinstance(obj, dict):
            return {k: _native(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_native(v) for v in obj]
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        return obj

    raw = {
        "generated_by": "generate_ops_master.py",
        "seed": int(SEED),
        "customers_served_annual_2024": int(annual_cs),
        "customers_served_monthly_2024": {int(k): int(v) for k, v in monthly_cs.items()},
        "tmed_saidi_min": float(round(tmed, 4)),
        "med_dates_2024": [str(d) for d in med_dates],
        "annual_2024": {"with_med": ann_wm, "ex_med": ann_xm},
        "monthly_2024": {str(m): v for m, v in monthly.items()},
        "vegetation_2024": {
            "ci":  int(veg["customers_affected"].sum()),
            "cmi": int(veg["customer_minutes"].sum()),
            "saifi": float(round(float(veg["customers_affected"].sum()) / annual_cs, 4)),
            "saidi": float(round(float(veg["customer_minutes"].sum()) / annual_cs, 4)),
            "inside_row_ci":  int(veg_in["customers_affected"].sum()),
            "outside_row_ci": int(veg_out["customers_affected"].sum()),
        },
        "vegetation_2022_summary": {"saifi":0.28,"saidi":38.5,
                                    "inside_row_pct":62,"outside_row_pct":38},
        "vegetation_2023_summary": {"saifi":0.31,"saidi":41.2,
                                    "inside_row_pct":59,"outside_row_pct":41},
    }
    return _native(raw)


def _write_readme(out_dir):
    txt = """# RPL Operational Master Data — Data Dictionary

**Package:** `corpus/_global/ops/`  **Generator:** `scripts/generate_ops_master.py` (seed 2024)
**Company:** Rockridge Power & Light Company (RPL)

Canonical operational master data shared by T16 (vegetation), T18 (meters), T19 (interruption reporting).
Do not alter; read-only inputs for downstream tasks.

## File Index
| File | Rows | Description |
|---|---|---|
| `substations_master.csv` | 112 | Distribution substation registry |
| `circuits_master.csv` | 528 | Distribution circuit registry |
| `daily_saidi_history_2019_2023.csv` | 1,826 | Daily SAIDI 2019-2023 for TMED computation |
| `med_days.csv` | 5 | Major Event Day identifications 2024 |
| `outage_incidents_base.csv` | varies | Incident-level records |
| `outage_events_base.csv` | ~10,800 | Sustained outage records 2024-01-01 to 2025-01-31 |
| `outage_restoration_steps_base.csv` | varies | Restoration steps per event |
| `reliability_facts.yaml` | — | Computed reliability indices |

## circuits_master.csv canonical sums
- Σ oh_miles = 14,200.0 ± 0.1
- Σ ug_miles = 4,900.0 ± 0.1
- Σ customers_on_circuit = 407,491 (exact)
- Σ customers_residential = 361,480 (exact)
- Σ customers_nonresidential = 46,011 (exact)

## Cause Code Taxonomy
| Category | Codes |
|---|---|
| vegetation | tree_inside_row_growth, tree_inside_row_failure, tree_outside_row_fallin, tree_unknown_location |
| weather | wind, lightning, ice_snow, flood, heat |
| equipment | oh_conductor, ug_cable, transformer, cutout_fuse, arrester, insulator, pole, connector, recloser_breaker, substation_equipment |
| animal | squirrel, bird, snake_raccoon_other |
| public | vehicle, dig_in, vandalism_theft, fire, customer_equipment, third_party_contact |
| power_supply | 69kv_line, transmission_supply_miso, substation_supply |
| operational | overload, switching_error, protection_miscoordination |
| planned | maintenance, construction, emergency_switching_for_safety |
| unknown | unknown_patrolled_no_cause |

## Key field notes
- `customer_minutes` in `outage_events_base.csv` = Σ(customers_restored × minutes_out) over restoration steps (not customers × duration).
- `med_flag` = Y when the event began on a Major Event Day; N otherwise.
- `tree_location`: inside_row / outside_row / unknown / n/a
- `intentional`: Y for planned outages only.

*Auto-generated — do not edit manually.*
"""
    with open(os.path.join(out_dir, "README.md"), "w") as f:
        f.write(txt)


def _write_manifest(out_dir, subs_df, ckts_df, events_df, facts, med_dates, tmed):
    exm = facts["annual_2024"]["ex_med"]
    wm  = facts["annual_2024"]["with_med"]
    manifest = {
        "package": "corpus/_global/ops", "task": "T04", "seed": SEED,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "summary": {
            "substations": int(len(subs_df)),
            "circuits": int(len(ckts_df)),
            "oh_miles": float(round(ckts_df["oh_miles"].sum(), 1)),
            "ug_miles": float(round(ckts_df["ug_miles"].sum(), 1)),
            "customers_total": int(ckts_df["customers_on_circuit"].sum()),
            "customers_residential": int(ckts_df["customers_residential"].sum()),
            "customers_nonresidential": int(ckts_df["customers_nonresidential"].sum()),
            "events_total": int(len(events_df)),
            "med_days_2024": len(med_dates),
            "tmed_min": round(float(tmed), 4),
            "annual_2024_ex_med": {k: float(exm[k]) for k in ("saifi","saidi","caidi")},
            "annual_2024_with_med_saidi": float(wm["saidi"]),
        },
    }
    with open(os.path.join(out_dir, "_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)


def main():
    print("="*60)
    print("RPL Ops Master Data Generator — seed", SEED)
    print("="*60)
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(os.path.join(OUT_DIR, "scripts"), exist_ok=True)

    print("\n[1] substations_master.csv ...")
    subs_df = _make_substations()

    print("[2] circuits_master.csv ...")
    ckts_df = _make_circuits(subs_df)
    cc = ckts_df.groupby("substation_id").size().reset_index(name="circuit_count")
    subs_df = subs_df.drop(columns=["circuit_count"]).merge(cc, on="substation_id", how="left")
    subs_df["circuit_count"] = subs_df["circuit_count"].fillna(0).astype(int)

    print(f"  OH {ckts_df['oh_miles'].sum():.1f}  UG {ckts_df['ug_miles'].sum():.1f}"
          f"  Cust {ckts_df['customers_on_circuit'].sum()}"
          f"  Res {ckts_df['customers_residential'].sum()}"
          f"  NonRes {ckts_df['customers_nonresidential'].sum()}")

    print("[3] daily_saidi_history_2019_2023.csv ...")
    daily_df = _make_daily_saidi_history()

    print("[4] TMED ...")
    tmed, mu_log, sig_log = _compute_tmed(daily_df)
    print(f"  M_nonzero={( daily_df['saidi_all_min']>0).sum()}  μ={mu_log:.4f}  σ={sig_log:.4f}  TMED={tmed:.4f} min")

    print("[5] med_days.csv ...")
    med_df, med_dates = _make_med_days(tmed)
    for _, r in med_df.iterrows():
        print(f"  {r['med_date']}  SAIDI={r['daily_saidi_min']:.1f} > TMED={tmed:.1f}")

    print("[6] outage events ...")
    inc_df, evt_df, stp_df = _make_outage_events(ckts_df, subs_df, med_dates)

    print("[7] reliability_facts.yaml ...")
    facts = _make_reliability_facts(evt_df, tmed, med_dates)
    exm = facts["annual_2024"]["ex_med"]
    wm  = facts["annual_2024"]["with_med"]
    print(f"  ex-MED  SAIFI={exm['saifi']:.4f}  SAIDI={exm['saidi']:.1f}  CAIDI={exm['caidi']:.1f}")
    print(f"  w-MED   SAIDI={wm['saidi']:.1f}")

    def chk(v, lo, hi, name):
        ok = lo <= v <= hi
        print(f"    {name}: {v:.3f} [{lo}-{hi}] {'PASS' if ok else 'FAIL'}")
        return ok

    ok  = chk(exm["saifi"],  1.05, 1.15, "SAIFI ex-MED")
    ok &= chk(exm["saidi"],  130,  150,  "SAIDI ex-MED")
    ok &= chk(exm["caidi"],  115,  140,  "CAIDI ex-MED")
    ok &= chk(wm["saidi"],   220,  350,  "SAIDI w-MED")
    if not ok:
        print("  WARNING: one or more reliability targets missed — see acceptance_tests.py")

    print("[8] Writing files ...")
    subs_df.to_csv(os.path.join(OUT_DIR, "substations_master.csv"), index=False)
    ckts_df.to_csv(os.path.join(OUT_DIR, "circuits_master.csv"), index=False)
    daily_df.to_csv(os.path.join(OUT_DIR, "daily_saidi_history_2019_2023.csv"), index=False)
    med_df.to_csv(os.path.join(OUT_DIR, "med_days.csv"), index=False)
    inc_df.to_csv(os.path.join(OUT_DIR, "outage_incidents_base.csv"), index=False)
    evt_df.to_csv(os.path.join(OUT_DIR, "outage_events_base.csv"), index=False)
    stp_df.to_csv(os.path.join(OUT_DIR, "outage_restoration_steps_base.csv"), index=False)
    with open(os.path.join(OUT_DIR, "reliability_facts.yaml"), "w") as f:
        yaml.dump(facts, f, default_flow_style=False, sort_keys=False)
    _write_readme(OUT_DIR)
    _write_manifest(OUT_DIR, subs_df, ckts_df, evt_df, facts, med_dates, tmed)
    print("Done.")
    return facts, tmed, med_dates


if __name__ == "__main__":
    main()
