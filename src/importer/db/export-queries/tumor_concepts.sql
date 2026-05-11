SELECT
    p.PATIENT_NAME  as patientid,
    c.CANCER_ID,
    t.TUMOR_ID,
    con.PREFERRED_TEXT AS concept_description,
    con.DPHE_GROUP AS concept_category,
    CASE
        WHEN con.NEGATED = 1 THEN 'Excluded'
        WHEN con.HISTORIC = 1 THEN 'Historical'
        WHEN con.UNCERTAIN = 1 THEN 'Uncertain'
        ELSE 'Confirmed'
    END AS concept_status,
    tav.VALUE AS attribute_value,
    ta.NAME AS attribute_name
FROM
    PATIENTS p
    JOIN CANCERS c ON p.PATIENT_ID = c.PATIENT_ID
    JOIN TUMORS t ON c.CANCER_ID = t.CANCER_ID
    JOIN TUMOR_CONCEPTS tc ON t.TUMOR_ID = tc.TUMOR_ID
    JOIN CONCEPTS con ON tc.CONCEPT_ID = con.CONCEPT_ID
    LEFT JOIN TUMOR_ATTRIBUTES ta ON t.TUMOR_ID = ta.TUMOR_ID
    LEFT JOIN TUMOR_ATTRIBUTE_VALUES tav ON ta.ATTRIBUTE_ID = tav.ATTRIBUTE_ID
ORDER BY
    p.PATIENT_NAME, c.CANCER_ID, t.TUMOR_ID, con.DPHE_GROUP, con.PREFERRED_TEXT;