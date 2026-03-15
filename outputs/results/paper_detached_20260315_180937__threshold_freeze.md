# Threshold Freeze Report

- Generated at: `2026-03-15T10:10:12.115154`
- E1 summary: `/opt/pangu/pangu/outputs/summaries/e1_detached_20260315_103207.json`
- E1 aggregate recommendation: `hold`
- Operational decision: `freeze`

## Current Threshold Snapshot

- Family thresholds: `{'reasoning': 0.45, 'assessment': 0.35, 'planning': 0.4}`
- Task-key thresholds: `{'Q&A': 0.05, 'EC': 0.05}`

## Decision Notes

- The live E1 rerun artifacts remain the formal basis for calibration review.
- The current code snapshot includes task-key thresholds for Q&A and EC that were applied after the saved E1 rerun completed.
- Thresholds are frozen operationally for the paper run so E2-E6 artifacts can be captured without more calibration churn.
- Do not change thresholds again until the full paper-stage artifact bundle is saved.

## E1 Review Reasons

- en: cascade quality drops 0.0270 vs 7b_only, beyond the 0.02 tolerance.