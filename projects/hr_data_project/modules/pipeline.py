from __future__ import annotations

import json

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


SKILL_KEYWORDS = {
    "SK001": ("Data engineering", ("data engineering", "data integration", "pipeline")),
    "SK002": (
        "Artificial intelligence and machine learning",
        ("artificial intelligence", "machine learning", "ai ", "predictive"),
    ),
    "SK003": ("Digital product management", ("product ownership", "product manager")),
    "SK004": ("Monitoring and evaluation", ("monitoring", "evaluation", "results")),
    "SK005": ("Climate resilience", ("climate", "resilience", "adaptation")),
    "SK006": ("Gender analysis", ("gender", "inclusion")),
    "SK011": ("Cybersecurity", ("cybersecurity", "information security", "security")),
    "SK017": ("Programme management", ("programme management", "portfolio delivery")),
    "SK020": ("Crisis response", ("crisis", "surge", "emergency")),
}


def source_register_to_bronze(source: DataFrame, run_id: str) -> DataFrame:
    columns = [
        "source_id",
        "source_file",
        "format",
        "document_type",
        "office_id",
        "country",
        "region",
        "reporting_period",
        "processing_status",
        "extraction_method",
        "evidence_text",
        "source_size_bytes",
    ]
    hash_columns = [F.coalesce(F.col(name).cast("string"), F.lit("")) for name in columns]
    return (
        source.select(
            *(F.col(name).cast("string").alias(name) for name in columns[:-1]),
            F.col("source_size_bytes").cast("long"),
        )
        .withColumn("_source_uri", F.col("source_file"))
        .withColumn("_run_id", F.lit(run_id))
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_record_hash", F.sha2(F.concat_ws("||", *hash_columns), 256))
    )


def structured_rows_to_bronze(source: DataFrame, run_id: str) -> DataFrame:
    hash_columns = [
        F.coalesce(F.col(name).cast("string"), F.lit(""))
        for name in ("source_id", "sheet_name", "row_number", "row_json")
    ]
    return (
        source.select(
            "source_id",
            "source_file",
            "sheet_name",
            "sheet_key",
            F.col("row_number").cast("long").alias("row_number"),
            "row_json",
        )
        .withColumn("_source_uri", F.col("source_file"))
        .withColumn("_run_id", F.lit(run_id))
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_record_hash", F.sha2(F.concat_ws("||", *hash_columns), 256))
    )


def _skill_stack_sql() -> str:
    rows = []
    for skill_id, (skill_name, keywords) in SKILL_KEYWORDS.items():
        rows.append(f"'{skill_id}', '{skill_name}', array({', '.join(repr(k) for k in keywords)})")
    return "stack({0}, {1}) AS (skill_id, skill_name, keywords)".format(len(rows), ", ".join(rows))


def extract_workforce_signals(source_register: DataFrame, structured_rows: DataFrame) -> DataFrame:
    spark = source_register.sparkSession
    source_register.createOrReplaceTempView("_hr_source_register")
    structured_rows.createOrReplaceTempView("_hr_structured_rows")
    skill_sql = _skill_stack_sql()
    return spark.sql(
        f"""
        WITH skill_reference AS (
          SELECT {skill_sql}
        ),
        document_evidence AS (
          SELECT
            source_id,
            source_file,
            document_type,
            office_id,
            country,
            region,
            reporting_period,
            lower(coalesce(evidence_text, '')) AS evidence_lower,
            evidence_text
          FROM _hr_source_register
          WHERE document_type <> 'structured_workbook'
            AND coalesce(evidence_text, '') <> ''
        ),
        structured_evidence AS (
          SELECT
            row.source_id,
            row.source_file,
            'workforce_planning_survey' AS document_type,
            get_json_object(row.row_json, '$.office_id') AS office_id,
            get_json_object(row.row_json, '$.country') AS country,
            get_json_object(row.row_json, '$.region') AS region,
            get_json_object(row.row_json, '$.survey_quarter') AS reporting_period,
            lower(coalesce(get_json_object(row.row_json, '$.narrative_response'), '')) AS evidence_lower,
            get_json_object(row.row_json, '$.narrative_response') AS evidence_text
          FROM _hr_structured_rows row
          WHERE row.sheet_key = 'survey_responses'
        ),
        combined AS (
          SELECT * FROM document_evidence
          UNION ALL
          SELECT * FROM structured_evidence
        ),
        matched AS (
          SELECT
            evidence.source_id,
            evidence.source_file,
            evidence.document_type,
            evidence.office_id,
            evidence.country,
            evidence.region,
            evidence.reporting_period,
            skill.skill_id,
            skill.skill_name,
            evidence.evidence_lower,
            evidence.evidence_text,
            exists(skill.keywords, keyword -> instr(evidence.evidence_lower, keyword) > 0) AS mentioned
          FROM combined evidence
          CROSS JOIN skill_reference skill
        )
        SELECT
          source_id,
          source_file,
          document_type,
          office_id,
          country,
          region,
          reporting_period,
          skill_id,
          skill_name,
          CASE
            WHEN evidence_lower RLIKE 'no evidence|do not|not currently|no shortage|adequate' THEN 'stable'
            WHEN evidence_lower RLIKE 'declin|less demand' THEN 'decreasing'
            WHEN evidence_lower RLIKE 'increase|rising|expansion|required|shortage|gap|priority|demand' THEN 'increasing'
            ELSE 'unclear'
          END AS demand_direction,
          CASE
            WHEN evidence_lower RLIKE 'urgent|critical|shortage|surge|emergency|risk' THEN 'high'
            WHEN evidence_lower RLIKE 'next two quarters|planned|increasing|required' THEN 'medium'
            ELSE 'low'
          END AS urgency,
          substring(evidence_text, 1, 750) AS evidence_text,
          CASE
            WHEN document_type = 'workforce_planning_survey' THEN 0.85D
            WHEN document_type IN ('country_programme_document', 'office_workplan') THEN 0.75D
            ELSE 0.60D
          END AS confidence,
          evidence_lower RLIKE 'no evidence|do not|not currently|no shortage|adequate' AS negated
        FROM matched
        WHERE mentioned
        """
    )


def extract_skill_supply(structured_rows: DataFrame) -> DataFrame:
    spark = structured_rows.sparkSession
    structured_rows.createOrReplaceTempView("_hr_structured_rows_supply")
    return spark.sql(
        """
        WITH rows AS (
          SELECT sheet_key, from_json(row_json, 'map<string,string>') AS m
          FROM _hr_structured_rows_supply
        ),
        employees AS (
          SELECT
            m['employee_id'] AS employee_id,
            m['office_id'] AS office_id,
            m['country'] AS country,
            m['region'] AS region,
            m['employment_status'] AS employment_status
          FROM rows
          WHERE sheet_key = 'employee_master'
        ),
        skills AS (
          SELECT
            m['employee_id'] AS employee_id,
            m['office_id'] AS office_id,
            m['skill_id'] AS skill_id,
            m['skill_name'] AS skill_name,
            CAST(m['assessed_proficiency'] AS DOUBLE) AS assessed_proficiency
          FROM rows
          WHERE sheet_key = 'employee_skills'
        ),
        talent AS (
          SELECT
            m['employee_id'] AS employee_id,
            m['mobility_readiness'] AS mobility_readiness,
            m['retention_risk'] AS retention_risk
          FROM rows
          WHERE sheet_key = 'talent_intelligence'
        ),
        planned AS (
          SELECT
            m['office_id'] AS office_id,
            m['primary_skill_id'] AS skill_id,
            m['primary_skill'] AS skill_name,
            SUM(CASE
              WHEN m['position_status'] = 'Approved' THEN CAST(m['funding_probability'] AS DOUBLE)
              WHEN m['position_status'] = 'Planned' THEN CAST(m['funding_probability'] AS DOUBLE) * 0.55D
              ELSE 0D
            END) AS planned_supply_fte
          FROM rows
          WHERE sheet_key = 'planned_positions'
          GROUP BY m['office_id'], m['primary_skill_id'], m['primary_skill']
        ),
        employee_supply AS (
          SELECT
            skills.office_id,
            employees.country,
            employees.region,
            skills.skill_id,
            skills.skill_name,
            COUNT(DISTINCT skills.employee_id) AS employees_with_skill,
            SUM(
              CASE WHEN employees.employment_status = 'Active' THEN 1D ELSE 0.35D END
              * coalesce(skills.assessed_proficiency, 0D) / 5D
              * CASE
                  WHEN coalesce(talent.retention_risk, '') = 'High' THEN 0.65D
                  WHEN coalesce(talent.retention_risk, '') = 'Medium' THEN 0.85D
                  ELSE 1D
                END
              * CASE
                  WHEN coalesce(talent.mobility_readiness, '') = 'Ready now' THEN 1.05D
                  WHEN coalesce(talent.mobility_readiness, '') = 'Ready in 6-12 months' THEN 0.90D
                  ELSE 0.75D
                END
            ) AS current_supply_fte,
            SUM(CASE WHEN coalesce(talent.mobility_readiness, '') = 'Ready now' THEN 1 ELSE 0 END)
              AS ready_now_count,
            SUM(CASE WHEN coalesce(talent.retention_risk, '') = 'High' THEN 1 ELSE 0 END)
              AS high_retention_risk_count
          FROM skills
          LEFT JOIN employees
            ON skills.employee_id = employees.employee_id
          LEFT JOIN talent
            ON skills.employee_id = talent.employee_id
          WHERE skills.skill_id IS NOT NULL
          GROUP BY skills.office_id, employees.country, employees.region, skills.skill_id, skills.skill_name
        )
        SELECT
          coalesce(employee_supply.office_id, planned.office_id) AS office_id,
          employee_supply.country,
          employee_supply.region,
          coalesce(employee_supply.skill_id, planned.skill_id) AS skill_id,
          coalesce(employee_supply.skill_name, planned.skill_name) AS skill_name,
          coalesce(employee_supply.employees_with_skill, 0L) AS employees_with_skill,
          coalesce(employee_supply.current_supply_fte, 0D) AS current_supply_fte,
          coalesce(planned.planned_supply_fte, 0D) AS planned_supply_fte,
          coalesce(employee_supply.current_supply_fte, 0D)
            + coalesce(planned.planned_supply_fte, 0D) AS supply_fte,
          coalesce(employee_supply.ready_now_count, 0L) AS ready_now_count,
          coalesce(employee_supply.high_retention_risk_count, 0L) AS high_retention_risk_count
        FROM employee_supply
        FULL OUTER JOIN planned
          ON employee_supply.office_id = planned.office_id
         AND employee_supply.skill_id = planned.skill_id
        """
    )


def classify_silver(
    source_register: DataFrame, structured_rows: DataFrame
) -> tuple[DataFrame, DataFrame, DataFrame]:
    signals = extract_workforce_signals(source_register, structured_rows)
    reasons = F.filter(
        F.array(
            F.when(F.col("office_id").isNull() | (F.col("office_id") == ""), "missing_office"),
            F.when(F.col("skill_id").isNull() | (F.col("skill_id") == ""), "missing_skill"),
            F.when(
                F.col("evidence_text").isNull() | (F.length("evidence_text") == 0),
                "missing_evidence",
            ),
            F.when(F.col("negated").eqNullSafe(True), "negated_demand"),
        ),
        lambda reason: reason.isNotNull(),
    )
    classified = signals.withColumn("quarantine_reasons", reasons)
    quarantine = classified.where(F.size("quarantine_reasons") > 0)
    accepted = classified.where(F.size("quarantine_reasons") == 0).drop("quarantine_reasons")
    supply = extract_skill_supply(structured_rows)
    return accepted, quarantine, supply


def to_gold(signals: DataFrame, supply: DataFrame) -> DataFrame:
    signals.createOrReplaceTempView("_silver_workforce_signals_for_gold")
    supply.createOrReplaceTempView("_silver_skill_supply_for_gold")
    return signals.sparkSession.sql(
        """
        WITH demand AS (
          SELECT
            office_id,
            country,
            region,
            skill_id,
            skill_name,
            COUNT(DISTINCT source_id) AS source_count,
            AVG(confidence) AS avg_confidence,
            MAX(CASE urgency WHEN 'high' THEN 3 WHEN 'medium' THEN 2 ELSE 1 END) AS urgency_score,
            SUM(CASE demand_direction WHEN 'increasing' THEN confidence ELSE 0D END) AS demand_score,
            concat_ws(' ', collect_set(substring(evidence_text, 1, 180))) AS evidence_summary
          FROM _silver_workforce_signals_for_gold
          WHERE negated = false
          GROUP BY office_id, country, region, skill_id, skill_name
        ),
        combined AS (
          SELECT
            demand.office_id,
            demand.country,
            demand.region,
            demand.skill_id,
            demand.skill_name,
            ROUND(demand.demand_score + demand.urgency_score * 0.5D, 2) AS demand_score,
            ROUND(coalesce(supply.supply_fte, 0D), 2) AS supply_fte,
            demand.source_count,
            demand.urgency_score,
            demand.evidence_summary,
            coalesce(supply.ready_now_count, 0L) AS ready_now_count,
            coalesce(supply.high_retention_risk_count, 0L) AS high_retention_risk_count
          FROM demand
          LEFT JOIN _silver_skill_supply_for_gold supply
            ON demand.office_id = supply.office_id
           AND demand.skill_id = supply.skill_id
        )
        SELECT
          office_id,
          country,
          region,
          skill_id,
          skill_name,
          demand_score,
          supply_fte,
          ROUND(greatest(demand_score - supply_fte, 0D), 2) AS gap_value,
          CASE
            WHEN greatest(demand_score - supply_fte, 0D) >= 3D THEN 'Critical'
            WHEN greatest(demand_score - supply_fte, 0D) >= 1.5D THEN 'High'
            WHEN greatest(demand_score - supply_fte, 0D) > 0D THEN 'Moderate'
            ELSE 'Covered'
          END AS gap_severity,
          CASE urgency_score WHEN 3 THEN 'high' WHEN 2 THEN 'medium' ELSE 'low' END AS urgency,
          CASE
            WHEN skill_name RLIKE 'Climate|Data|Artificial|Digital|Cybersecurity' THEN 'high'
            WHEN source_count >= 2 THEN 'medium'
            ELSE 'targeted'
          END AS strategic_alignment,
          source_count,
          CASE
            WHEN greatest(demand_score - supply_fte, 0D) >= 3D AND ready_now_count = 0 THEN 'Recruit'
            WHEN greatest(demand_score - supply_fte, 0D) >= 2D AND ready_now_count > 0 THEN 'Mobilize talent'
            WHEN urgency_score = 3 AND greatest(demand_score - supply_fte, 0D) >= 1D THEN 'Temporary surge support'
            WHEN greatest(demand_score - supply_fte, 0D) > 0D THEN 'Capability development'
            ELSE 'Monitor'
          END AS recommended_action,
          substring(evidence_summary, 1, 900) AS evidence_summary,
          concat(
            'Supply uses proficiency-adjusted active staff, mobility readiness, retention risk and ',
            'funding-weighted planned positions; high retention-risk contributors=',
            CAST(high_retention_risk_count AS STRING),
            '.'
          ) AS assumption_or_model_note
        FROM combined
        """
    )


def fixture_rows() -> list[dict[str, str | None]]:
    return [
        {
            "office_id": "CO001",
            "country": "Uganda",
            "region": "Africa",
            "skill_id": "SK001",
            "skill_name": "Data engineering",
            "narrative_response": "Demand for data integration is increasing.",
        },
        {
            "office_id": "CO003",
            "country": "Ghana",
            "region": "Africa",
            "skill_id": "SK011",
            "skill_name": "Cybersecurity",
            "narrative_response": None,
        },
    ]


def fixture_json() -> str:
    return json.dumps(fixture_rows(), sort_keys=True)
