SELECT
    p.PATIENT_NAME as patientid,
    ca.CANCER_ID,
    c.PREFERRED_TEXT AS concept_description,
    c.DPHE_GROUP AS concept_category,
    CASE
        WHEN c.NEGATED = 1 THEN 'Excluded'
        WHEN c.HISTORIC = 1 THEN 'Historical'
        WHEN c.UNCERTAIN = 1 THEN 'Uncertain'
        ELSE 'Confirmed'
        END AS concept_status,
    cav.VALUE AS attribute_value,
    ca_attr.NAME AS attribute_name
FROM
    PATIENTS p
        JOIN
    CANCERS ca ON p.PATIENT_ID = ca.PATIENT_ID
        JOIN
    CANCER_CONCEPTS cc ON ca.CANCER_ID = cc.CANCER_ID
        JOIN
    CONCEPTS c ON cc.CONCEPT_ID = c.CONCEPT_ID
        LEFT JOIN
    CANCER_ATTRIBUTES ca_attr ON ca.CANCER_ID = ca_attr.CANCER_ID
        LEFT JOIN
    CANCER_ATTRIBUTE_VALUES cav ON ca_attr.ATTRIBUTE_ID = cav.ATTRIBUTE_ID
ORDER BY
    ca.CANCER_ID, c.DPHE_GROUP, c.PREFERRED_TEXT;