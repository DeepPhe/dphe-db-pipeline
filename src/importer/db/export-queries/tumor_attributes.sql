
SELECT
    p.PATIENT_NAME  as patientid,
    c.CANCER_ID,
    t.TUMOR_ID,
    t.CLASS_URI AS tumor_type,
    ta.NAME AS attribute_name,
    tav.VALUE AS attribute_value,
    CASE
        WHEN tav.NEGATED = 1 THEN 'Excluded'
        WHEN tav.HISTORIC = 1 THEN 'Historical'
        WHEN tav.UNCERTAIN = 1 THEN 'Uncertain'
        ELSE 'Confirmed'
        END AS attribute_status,
    tav.CONFIDENCE AS confidence
FROM
    PATIENTS p
        JOIN
    CANCERS c ON p.PATIENT_ID = c.PATIENT_ID
        JOIN
    TUMORS t ON c.CANCER_ID = t.CANCER_ID
        LEFT JOIN
    TUMOR_ATTRIBUTES ta ON t.TUMOR_ID = ta.TUMOR_ID
        LEFT JOIN
    TUMOR_ATTRIBUTE_VALUES tav ON ta.ATTRIBUTE_ID = tav.ATTRIBUTE_ID
ORDER BY
    p.PATIENT_NAME, c.CANCER_ID, t.TUMOR_ID, ta.NAME;