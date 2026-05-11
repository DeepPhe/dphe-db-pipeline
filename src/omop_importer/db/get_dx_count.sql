SELECT p.GENDER,
       SUM(CASE WHEN d.CANcER = 'M' THEN 1 ELSE 0 END) AS MELANOMA_count,
       SUM(CASE WHEN d.CANcER = 'B' THEN 1 ELSE 0 END) AS BRCA_count,
       SUM(CASE WHEN d.CANcER = 'O' THEN 1 ELSE 0 END) AS OVCA_count,
       SUM(CASE
               WHEN p.PERSON_ID IN (SELECT PERSON_ID
                                    FROM CALCULATED_DX_DATA
                                    GROUP BY PERSON_ID
                                    HAVING COUNT(DISTINCT CANCER) = 2) THEN 1
               ELSE 0 END)                             AS 2_cancer_count,
       SUM(CASE
               WHEN p.PERSON_ID IN (SELECT PERSON_ID
                                    FROM CALCULATED_DX_DATA
                                    GROUP BY PERSON_ID
                                    HAVING COUNT(DISTINCT CANCER) = 3) THEN 1
               ELSE 0 END)                             AS 3_cancer_count,
       COUNT(*)                                        as total_cancer_count,
       COUNT(DISTINCT p.PERSON_ID)                     AS total_count
FROM CALCULATED_DX_DATA d,
     CALCULATED_PATIENT_DATA p
WHERE d.PERSON_ID = p.PERSON_ID
GROUP BY p.GENDER, p.GENDER