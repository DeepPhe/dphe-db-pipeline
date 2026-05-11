    SELECT
        p.PATIENT_NAME as patientid,
        c.CANCER_ID as cancerid,
        c.CLASS_URI AS cancer_type,
        ca.NAME AS attribid,
        cav.VALUE AS attribval,
        cav.CONFIDENCE
    FROM
        PATIENTS p
            JOIN
        CANCERS c ON p.PATIENT_ID = c.PATIENT_ID
            LEFT JOIN
        CANCER_ATTRIBUTES ca ON c.CANCER_ID = ca.CANCER_ID
            LEFT JOIN
        CANCER_ATTRIBUTE_VALUES cav ON ca.ATTRIBUTE_ID = cav.ATTRIBUTE_ID
    ORDER BY
        p.PATIENT_NAME, c.CANCER_ID, ca.NAME;