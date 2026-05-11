SELECT p.GENDER,
       p.ETHNICITY,
       p.RACE,
       SUM(CASE WHEN d.CANcER = 'M' THEN 1 ELSE 0 END) AS MELANOMA_instances,
       SUM(CASE WHEN d.CANcER = 'B' THEN 1 ELSE 0 END) AS BRCA_instances,
       SUM(CASE WHEN d.CANcER = 'O' THEN 1 ELSE 0 END) AS OVCA_instances,
       COUNT(p.PERSON_ID)                     AS total_instances,
         COUNT(DISTINCT p.PERSON_ID)            AS unique_patients
FROM CALCULATED_DX_DATA d,
     CALCULATED_PATIENT_DATA p
WHERE d.PERSON_ID = p.PERSON_ID
GROUP BY p.GENDER, p.GENDER, p.ETHNICITY, p.RACE