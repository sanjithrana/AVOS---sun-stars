# Drugs@FDA — data dictionary

Source: [Drugs@FDA Data Files](https://www.fda.gov/drugs/drug-approvals-and-databases/drugsfda-data-files), refreshed by FDA every weekday.
Descriptions are summarised from FDA's *Data Definitions* section; types are the types this pipeline writes to Parquet/SQLite.
`ApplNo` (6 digits) and `ProductNo` (3 digits) are kept as zero-padded **strings** — never cast them to numbers or joins will break.

## Relationships

```
Applications (ApplNo)
 ├── Products (ApplNo, ProductNo)
 │     ├── MarketingStatus (ApplNo, ProductNo) ── MarketingStatus_Lookup (MarketingStatusID)
 │     └── TE (ApplNo, ProductNo, MarketingStatusID, TECode)
 └── Submissions (ApplNo, SubmissionType, SubmissionNo) ── SubmissionClass_Lookup (SubmissionClassCodeID)
       ├── SubmissionPropertyType  (… , SubmissionPropertyTypeID)
       ├── ApplicationDocs (ApplicationDocsID) ── ApplicationsDocsType_Lookup (ApplicationDocsTypeID)
       └── Join_Submission_ActionTypes_Lookup (j_submissionActionTypeID) ── ActionTypes_Lookup (ActionTypes_LookupID)
```
FDA's data contains some child rows whose parent is missing (see `data_quality_report.md`), so use LEFT JOINs.

## Tables

### Applications — one row per application
| Column | Type | Description |
|---|---|---|
| ApplNo | str (PK) | FDA application number (6 digits, zero-padded) |
| ApplType | str | `NDA` new drug, `ANDA` generic, `BLA` biologic |
| ApplPublicNotes | str | Public notes about the application |
| SponsorName | str | Company holding the application |

### Products — one row per product (strength/form) in an application
| Column | Type | Description |
|---|---|---|
| ApplNo | str (PK) | Application number |
| ProductNo | str (PK) | Product number within the application (3 digits) |
| Form | str | Dosage form;route, e.g. `TABLET;ORAL` |
| Strength | str | Strength as published, e.g. `EQ 10MG BASE` |
| ReferenceDrug | int | Reference Listed Drug flag (0 = no, 1 = yes, 2 = TBD) |
| DrugName | str | Brand/proprietary name |
| ActiveIngredient | str | Active ingredient(s) |
| ReferenceStandard | int | Reference Standard flag (0/1; NULL when not provided) |

### MarketingStatus — current marketing status per product
| Column | Type | Description |
|---|---|---|
| MarketingStatusID | int | → MarketingStatus_Lookup |
| ApplNo | str (PK) | Application number |
| ProductNo | str (PK) | Product number |

### MarketingStatus_Lookup
| Column | Type | Description |
|---|---|---|
| MarketingStatusID | int (PK) | 1 Prescription, 2 Over-the-counter, 3 Discontinued, 4 None (Tentative Approval), 5 For Further Manufacturing Use |
| MarketingStatusDescription | str | Description |

### TE — therapeutic equivalence codes (Orange Book)
| Column | Type | Description |
|---|---|---|
| ApplNo | str (PK) | Application number |
| ProductNo | str (PK) | Product number |
| MarketingStatusID | int (PK) | Marketing status |
| TECode | str (PK) | TE code, e.g. `AB`, `AB1`, `AP`. A product can have several codes, so TECode is part of the key |

### Submissions — every original application and supplement
| Column | Type | Description |
|---|---|---|
| ApplNo | str (PK) | Application number |
| SubmissionClassCodeID | int | → SubmissionClass_Lookup (NULL for ~12k older rows) |
| SubmissionType | str (PK) | `ORIG` original or `SUPPL` supplement |
| SubmissionNo | int (PK) | Submission sequence number |
| SubmissionStatus | str | `AP` approved, `TA` tentative approval, `CR` complete response, … |
| SubmissionStatusDate | date | Date of the status (for `ORIG`+`AP` = approval date) |
| SubmissionsPublicNotes | str | Public notes (may contain HTML) |
| ReviewPriority | str | `STANDARD`, `PRIORITY`, `UNKNOWN`, … |

### SubmissionClass_Lookup
| Column | Type | Description |
|---|---|---|
| SubmissionClassCodeID | int (PK) | ID |
| SubmissionClassCode | str | Short code, e.g. `EFFICACY`, `LABELING`, `TYPE 1` |
| SubmissionClassCodeDescription | str | Description |

### SubmissionPropertyType — properties attached to submissions (e.g. orphan designation)
| Column | Type | Description |
|---|---|---|
| ApplNo | str (PK) | Application number |
| SubmissionType | str (PK) | `ORIG` / `SUPPL` |
| SubmissionNo | int (PK) | Submission number |
| SubmissionPropertyTypeCode | str | `Orphan`, or NULL (source literal `Null`) |
| SubmissionPropertyTypeID | int (PK) | Property ID (0 = none) |

### ApplicationDocs — letters, labels, reviews linked to submissions
| Column | Type | Description |
|---|---|---|
| ApplicationDocsID | int (PK) | Document ID |
| ApplicationDocsTypeID | int | → ApplicationsDocsType_Lookup |
| ApplNo | str | Application number |
| SubmissionType | str | `ORIG` / `SUPPL` / `APPL` |
| SubmissionNo | int | Submission number |
| ApplicationDocsTitle | str | Title (`0` when FDA did not give one) |
| ApplicationDocsURL | str | Link to the PDF/page on accessdata.fda.gov |
| ApplicationDocsDate | date | Document date |

### ApplicationsDocsType_Lookup
| Column | Type | Description |
|---|---|---|
| ApplicationDocsType_Lookup_ID | int (PK) | ID |
| ApplicationDocsType_Lookup_Description | str | e.g. Letter, Label, Review |

### Join_Submission_ActionTypes_Lookup — action types per submission
| Column | Type | Description |
|---|---|---|
| SubmissionType | str | `ORIG` / `SUPPL` (one row blank in source) |
| j_submissionActionTypeID | int (PK) | Row ID |
| ApplNo | str | Application number |
| SubmissionNo | int | Submission number |
| ActionTypes_LookupID | int | → ActionTypes_Lookup (NULL in ~300 rows) |

### ActionTypes_Lookup
| Column | Type | Description |
|---|---|---|
| ActionTypes_LookupID | int (PK) | ID |
| ActionTypes_LookupDescription | str | e.g. Efficacy, Labeling |
| SupplCategoryLevel1Code | str | Supplement category level 1 |
| SupplCategoryLevel2Code | str | Supplement category level 2 |

## Convenience views (SQLite only)
| View | What it gives you |
|---|---|
| `v_products` | Product + sponsor + application type + marketing status text + TE codes (comma-joined) |
| `v_submissions` | Submission + sponsor + class code/description + `IsOrphan` flag |
| `v_original_approvals` | `ORIG` + `AP` submissions → original approval date per application |
| `v_application_docs` | Documents with their type description |
