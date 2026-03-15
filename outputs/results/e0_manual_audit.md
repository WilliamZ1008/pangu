# E0 Manual Audit Note

Date: 2026-03-14
Scope: shared-8 EduBench tasks only
Method: prompt text, task family fit, and gold-field shape were manually checked on 5 samples per task family.

## Overall conclusions

- Shared-8 counts and deterministic dev/test splits match the experiment specs.
- Canonical prompts are task-specific and readable across both English and Chinese samples.
- No stale cross-task prompt leakage was found in the reviewed set.
- Chinese QG prompts no longer show unrelated stale "成语" drift. When a QG sample contains 成语 content, it is because the underlying knowledge point is actually 成语.

## Answering

- `en_Q&A_00001_3b11275c0efa`: multiple-choice festival question is cleanly preserved; gold answer format matches the prompt.
- `en_Q&A_00002_b37bfaa70d1f`: lunar-calendar festival question is coherent and not contaminated by other task templates.
- `en_Q&A_00003_328934d0d7a0`: short MCQ prompt is concise; gold option format is still recoverable even though it is only `C`.
- `zh_Q&A_00001_35a940ca34a7`: Chinese pronunciation question is preserved as a direct single-turn prompt with no extra instruction noise.
- `zh_Q&A_00002_05c26f863e8d`: Chinese multi-select radical question remains a plain benchmark item and gold options are structurally sensible.

## Correction

- `en_EC_00001_9f42478a8879`: question and original answer are clearly separated; corrected answer and explanation align with EC schema.
- `en_EC_00002_d267a29ab32c`: arithmetic correction prompt is minimal and unambiguous.
- `en_EC_00003_bf2434af22ff`: multiplication correction sample has the expected two-part gold structure.
- `zh_EC_00001_be73c14250f8`: Chinese multi-select vocabulary correction prompt is canonical and the gold list is coherent.
- `zh_EC_00002_8acaba4448e1`: Chinese literature correction sample preserves both authorship and theme correction without schema drift.

## Generation

- `en_QG_00001_a5ff40f97f57`: literature knowledge-point prompt is correctly framed as QG and the gold bundle has question, guidance, and answer.
- `en_QG_00002_487f31b58033`: elementary arithmetic generation sample is simple and schema-consistent.
- `en_QG_00003_09381fb02368`: another arithmetic generation example confirms stable canonical section formatting.
- `zh_QG_00001_2fb9aeb7b1a0`: Chinese poetry generation sample is correctly tied to the stated knowledge point, with no unrelated idiom drift.
- `zh_QG_00002_04b8229d9e9d`: this sample mentions 成语 because the knowledge point is actually 成语的意思和运用; this is valid task content, not stale prompt contamination.

## Grading

- `en_AG_00001_81c7c938789f`: True/False grading sample cleanly separates the question from the student answer.
- `en_AG_00002_abd8335fb111`: short objective grading sample has aligned score, detail, and feedback fields.
- `en_AG_00003_8f78cf192c42`: duplicate topical coverage does not indicate loader corruption; sample structure remains valid.
- `zh_AG_00001_a1ab0b59a9a5`: Chinese AG prompt correctly includes options and student answer in canonical sections.
- `zh_AG_00002_2377d72be6ea`: Chinese literature grading sample has sensible partial-credit gold feedback.

## Guidance

- `en_IP_00001_43e618a93007`: Great Wall guidance prompt stays as a pure hinting task and does not collapse into direct answering.
- `en_IP_00002_5043649abb14`: arithmetic hint sample is short and appropriately scaffolded.
- `en_IP_00003_d3e902f8b769`: addition guidance sample preserves the IP task style rather than a final-answer template.
- `zh_IP_00001_34b7cde700b0`: Chinese vocabulary hint prompt is coherent and the gold guidance is non-trivial.
- `zh_IP_00002_79a8a8299477`: Chinese reading-comprehension hint sample remains task-appropriate and context-aware.

## Personalized Content

- `en_PLS_00001_2b0969903e79`: student profile is preserved in structured sections and the gold content is clearly personalized.
- `en_PLS_00002_1d6af47c457c`: language-proficiency subfields survive prompt normalization correctly.
- `en_PLS_00003_46eea04e6566`: profile richness is retained without collapsing into unreadable JSON.
- `zh_PLS_00001_548e82eef7c2`: Chinese high-school language profile yields a coherent personalized content target.
- `zh_PLS_00002_4b37542d70be`: Chinese elementary math support sample retains learner traits and intervention details.

## Planning

- `en_PCC_00001_d16434ca9e1b`: beginner Chinese learning-plan prompt is well-formed and gold planning fields are rich.
- `en_PCC_00002_e2fa2c8c038f`: intermediate learner profile remains intact with realistic course sequencing.
- `en_PCC_00003_f5c6f2e1da0a`: planning prompt keeps study habits and goals visible, which is important for PCC.
- `zh_PCC_00001_2711848cce40`: Chinese elementary-language planning sample preserves weak points and learning habits correctly.
- `zh_PCC_00002_83699b29589f`: Chinese learner profile with nested ability fields remains canonical and readable.

## Follow-up

- E0 count report: `outputs/results/e0_shared8_count_report.json`
- E0 split report: `outputs/results/e0_shared8_split_report.json`
- This manual note is sufficient to justify that the corrected loader is trustworthy enough to begin calibration and main experiment runs once `1B` and `7B` services are restarted.
