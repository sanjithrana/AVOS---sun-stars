# Drugs@FDA data quality report — snapshot 2026-11-05

- Source zip: `drugsatfda_20261105.zip` (sha256 `20e9801ff7aab406…`)
- Processed at: 2026-11-06 05:04:02 UTC

## Tables

| Table | Rows | Primary key | PK dups | Repaired lines | Rejected lines | Non-ASCII rows |
|---|---:|---|---:|---|---|---:|
| Applications | 29,444 | ApplNo | 0 | — | — | 0 |
| Products | 51,975 | ApplNo, ProductNo | 0 | — | — | 0 |
| Submissions | 194,421 | ApplNo, SubmissionType, SubmissionNo | 0 | — | — | 19 |
| SubmissionPropertyType | 321,980 | ApplNo, SubmissionType, SubmissionNo, SubmissionPropertyTypeID | 0 | — | — | 0 |
| ApplicationDocs | 81,479 | ApplicationDocsID | 0 | 78679 | — | 0 |
| Join_Submission_ActionTypes_Lookup | 210,286 | j_submissionActionTypeID | 0 | — | — | 0 |
| MarketingStatus | 52,586 | ApplNo, ProductNo | 0 | — | — | 0 |
| TE | 26,841 | ApplNo, ProductNo, MarketingStatusID, TECode | 0 | — | — | 0 |
| ActionTypes_Lookup | 59 | ActionTypes_LookupID | 0 | — | — | 0 |
| ApplicationsDocsType_Lookup | 62 | ApplicationDocsType_Lookup_ID | 0 | — | — | 0 |
| MarketingStatus_Lookup | 5 | MarketingStatusID | 0 | — | — | 0 |
| SubmissionClass_Lookup | 28 | SubmissionClassCodeID | 0 | — | — | 0 |

Repaired lines had a stray empty tab-separated field which was removed. Non-ASCII rows are Windows-1252 characters (e.g. curly apostrophes) now stored as UTF-8.

## Referential integrity (reported, not enforced)

These gaps exist in FDA's published data (e.g. submissions for applications that are no longer listed). Rows are kept; use LEFT JOINs.

| Child | Columns | Parent | Rows checked | Orphans |
|---|---|---|---:|---:|
| Products | ApplNo | Applications | 51,975 | 11 |
| Submissions | ApplNo | Applications | 194,421 | 5,377 |
| MarketingStatus | ApplNo, ProductNo | Products | 52,586 | 611 |
| TE | ApplNo, ProductNo | Products | 26,841 | 12 |
| ApplicationDocs | ApplNo, SubmissionType, SubmissionNo | Submissions | 81,479 | 152 |
| SubmissionPropertyType | ApplNo, SubmissionType, SubmissionNo | Submissions | 321,980 | 256 |
| Join_Submission_ActionTypes_Lookup | ApplNo, SubmissionType, SubmissionNo | Submissions | 210,285 | 493 |
| Join_Submission_ActionTypes_Lookup | ActionTypes_LookupID | ActionTypes_Lookup | 209,985 | 0 |
| Submissions | SubmissionClassCodeID | SubmissionClass_Lookup | 182,533 | 0 |
| ApplicationDocs | ApplicationDocsTypeID | ApplicationsDocsType_Lookup | 81,479 | 0 |
| MarketingStatus | MarketingStatusID | MarketingStatus_Lookup | 52,586 | 0 |
| TE | MarketingStatusID | MarketingStatus_Lookup | 26,841 | 0 |
