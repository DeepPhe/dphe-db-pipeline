SELECT
    'Before Cancer' as period,
    AVG(record_count) as avg_icd9_codes_per_person
FROM (
    SELECT z.PERSON_ID, COUNT(*) as record_count
    FROM (
        SELECT epdx.FIRST_DX_DATE, b.PERSON_ID, b.CONDITION_START_DATE
        FROM omop.DIAGNOSIS_BRCAOVCA_HOSP_VW b
        JOIN (
            SELECT PERSON_ID, MIN(d.DATE) as FIRST_DX_DATE
            FROM lookup.CALCULATED_DX_DATA d
            WHERE d.CANCER = 'B'
            GROUP BY PERSON_ID
        ) as epdx ON epdx.PERSON_ID = b.PERSON_ID
        WHERE epdx.FIRST_DX_DATE < b.CONDITION_START_DATE
    ) as z
    GROUP BY z.PERSON_ID
) as p

UNION ALL

SELECT
    'After Cancer' as period,
    AVG(record_count) as avg_icd9_codes_per_person
FROM (
    SELECT z.PERSON_ID, COUNT(*) as record_count
    FROM (
        SELECT epdx.FIRST_DX_DATE, b.PERSON_ID, b.CONDITION_START_DATE
        FROM omop.DIAGNOSIS_BRCAOVCA_HOSP_VW b
        JOIN (
            SELECT PERSON_ID, MIN(d.DATE) as FIRST_DX_DATE
            FROM lookup.CALCULATED_DX_DATA d
            WHERE d.CANCER = 'B'
            GROUP BY PERSON_ID
        ) as epdx ON epdx.PERSON_ID = b.PERSON_ID
        WHERE epdx.FIRST_DX_DATE >= b.CONDITION_START_DATE
    ) as z
    GROUP BY z.PERSON_ID
) as p;