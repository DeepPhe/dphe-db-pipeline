SELECT DISTINCT ccid.PERSON_ID              as OMOP_PERSON_ID,
                ccid.CONDITION_SOURCE_VALUE AS OMOP_CONDITION_SOURCE_VALUE,
                s.concept_id                AS OMOP_CONCEPT_ID,
                S.concept_code              as OMOP_CONCEPT_CODE__SNOMED__,
                s.concept_name              as OMOP_CONCEPT_NAME,
                o.GENDER_CONCEPT_ID         as OMOP_GENDER_CONCEPT_ID
FROM (SELECT PERSON_ID, CONDITION_CONCEPT_ID, CONDITION_SOURCE_VALUE
      from omop.DIAGNOSIS_BRCAOVCA_HOSP_VW
      UNION ALL
      SELECT PERSON_ID, CONDITION_CONCEPT_ID, CONDITION_SOURCE_VALUE
      from omop.DIAGNOSIS_BRCAOVCA_OUTPT_VW) as CCID,
     lookup.SNOMED_CODES s,
     omop.DEMOGRAPHIC_BRCAOVCA_VW o
WHERE s.concept_id = ccid.CONDITION_CONCEPT_ID
  AND o.PERSON_ID = ccid.PERSON_ID
  AND ccid.PERSON_ID in (select distinct(d.PERSON_ID) AS PERSON_ID
                         from CALCULATED_DX_DATA d,
                              CALCULATED_PATIENT_DATA p
                         WHERE d.CANCER = 'O'
                           AND p.GENDER = 'M'
                           AND d.PERSON_ID = p.PERSON_ID)
