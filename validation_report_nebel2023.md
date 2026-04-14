# World3-03 NEBEL 2023 Validation Report

- Window: 1970–2020
- Variables evaluated: 6
- Variables passed: 3
- Total NRMSD: 0.4957
- Total NRMSD bound: 0.2719
- Overall passed: False

## Per-variable results

| variable | nrmsd | bound | function | passed |
|---|---|---|---|---|
| population | 0.3393 | 0.0190 | direct | False |
| industrial_output | 0.3595 | 0.4740 | change_rate | True |
| food_per_capita | 0.8202 | 1.1080 | change_rate | True |
| pollution | 0.5994 | 0.3370 | change_rate | False |
| nonrenewable_resources | -0.9296 | 0.7570 | change_rate | True |
| service_per_capita | 1.7854 | 0.6190 | change_rate | False |

## Notes

- Skipping human_welfare_hdi: missing data
- Skipping ecological_footprint: missing data
