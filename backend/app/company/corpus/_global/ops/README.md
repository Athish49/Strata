# RPL Operational Master Data — Data Dictionary

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
