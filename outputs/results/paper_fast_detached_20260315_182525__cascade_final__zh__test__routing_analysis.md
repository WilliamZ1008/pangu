# E5 Routing Analysis

- Run name: `cascade_final__zh__test__paper_fast_detached_20260315_182525__20260315_110751`
- System: `cascade_final`
- Lang/split: `zh / test`
- Total items: `354`
- accepted_by_1b_rate: `0.2288135593220339`
- 7b_invocation_rate: `0.7711864406779662`
- accepted_by_1b_accuracy: `0.8024691358024691`
- escalated_sample_accuracy: `0.5074074074074074`

## Per-task Invocation Rate

| task_key | total_items | 7b_invocation_rate | accepted_by_1b_rate | quality_score |
| --- | ---: | ---: | ---: | ---: |
| AG | 42 | 1.0000 | 0.0000 | 0.1 |
| EC | 28 | 1.0000 | 0.0000 | 0.25 |
| IP | 61 | 0.0820 | 0.9180 | 1.0 |
| PCC | 26 | 0.9615 | 0.0385 | 0.6923076923076923 |
| PLS | 16 | 0.5000 | 0.5000 | 1.0 |
| Q&A | 59 | 0.7288 | 0.2712 | 0.10344827586206896 |
| QG | 61 | 1.0000 | 0.0000 | 0.8032786885245902 |
| TMG | 61 | 1.0000 | 0.0000 | 0.6721311475409836 |

## Average Latency By Task Family

| task_family | total_items | latency_avg |
| --- | ---: | ---: |
| answering | 59 | 23.3974 |
| correction | 28 | 27.0292 |
| generation | 122 | 37.7065 |
| grading | 42 | 27.9907 |
| guidance | 61 | 9.9877 |
| personalized_content | 16 | 24.5201 |
| planning | 26 | 41.1121 |