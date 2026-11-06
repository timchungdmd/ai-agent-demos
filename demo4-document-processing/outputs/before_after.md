# Before / after — Demo 4

Raw extraction is never auto-corrected. Clean rows flow to the sheet
as extracted. Exception rows go to the human queue unchanged,
with the failing field and reason named.

| doc_id | total (as extracted) | status | failing_field | reason |
|--------|----------------------|--------|---------------|--------|
| DOC-01 | 583.20 | Clean | - | all_validations_pass |
| DOC-02 | 221.40 | Clean | - | all_validations_pass |
| DOC-03 | 594.00 | Clean | - | all_validations_pass |
| DOC-04 | 388.80 | Clean | - | all_validations_pass |
| DOC-05 | 432.00 | Clean | - | all_validations_pass |
| DOC-06 | 270.00 | Clean | - | all_validations_pass |
| DOC-07 | 1080.00 | Clean | - | all_validations_pass |
| DOC-08 | 210.60 | Clean | - | all_validations_pass |
| DOC-09 | 560.00 | Exception | total | total_mismatch:expected=540.00 stated=560.00 |
| DOC-10 | 324.00 | Exception | po_number | po_missing |

Exception queue: DOC-09 (total) and DOC-10 (po_number).
