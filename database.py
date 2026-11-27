from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class VacancyDatabase:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vacancies (
                    vacancy_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    company TEXT DEFAULT '',
                    salary TEXT DEFAULT '',
                    salary_from INTEGER,
                    salary_to INTEGER,
                    salary_currency TEXT DEFAULT '',
                    salary_gross INTEGER,
                    area TEXT DEFAULT '',
                    experience TEXT DEFAULT '',
                    employment TEXT DEFAULT '',
                    schedule TEXT DEFAULT '',
                    published_at TEXT DEFAULT '',
                    url TEXT NOT NULL,
                    source_queries TEXT DEFAULT '[]',
                    raw_text TEXT DEFAULT '',
                    details_loaded INTEGER DEFAULT 0,
                    total_score INTEGER DEFAULT 0,
                    priority TEXT DEFAULT 'low',
                    recommended_resume TEXT DEFAULT '',
                    recommended_resume_title TEXT DEFAULT '',
                    profile_scores TEXT DEFAULT '{}',
                    matched_keywords TEXT DEFAULT '',
                    stopwords TEXT DEFAULT '',
                    scoring_version TEXT DEFAULT '',
                    status TEXT DEFAULT 'new',
                    date_found TEXT DEFAULT '',
                    date_reviewed TEXT DEFAULT '',
                    updated_at TEXT DEFAULT ''
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_vacancies_score ON vacancies(total_score DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_vacancies_status ON vacancies(status)"
            )

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    @staticmethod
    def _merge_queries(existing_json: str, new_queries: list[str]) -> str:
        try:
            current = json.loads(existing_json or "[]")
            if not isinstance(current, list):
                current = []
        except json.JSONDecodeError:
            current = []

        seen = set(current)
        for q in new_queries:
            q_clean = str(q or "").strip()
            if q_clean and q_clean not in seen:
                current.append(q_clean)
                seen.add(q_clean)

        return json.dumps(current, ensure_ascii=False)

    def upsert_vacancy(self, vacancy: dict) -> None:
        now = self._now_iso()
        vacancy_id = str(vacancy["vacancy_id"])

        incoming_queries = vacancy.get("source_queries")
        if isinstance(incoming_queries, str):
            incoming_queries = [incoming_queries]
        elif not isinstance(incoming_queries, list):
            single_q = vacancy.get("source_query")
            incoming_queries = [single_q] if single_q else []

        gross_val = vacancy.get("salary_gross")
        gross_int = None if gross_val is None else (1 if gross_val else 0)
        raw_text = str(vacancy.get("raw_text") or "").strip()
        details_loaded = 1 if raw_text else int(bool(vacancy.get("details_loaded", 0)))

        profile_scores = vacancy.get("profile_scores") or {}
        if not isinstance(profile_scores, str):
            profile_scores = json.dumps(profile_scores, ensure_ascii=False)

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT source_queries, raw_text, details_loaded, status, date_found, date_reviewed "
                "FROM vacancies WHERE vacancy_id = ?",
                (vacancy_id,),
            ).fetchone()

            if existing is None:
                conn.execute(
                    """
                    INSERT INTO vacancies (
                        vacancy_id, title, company, salary, salary_from, salary_to,
                        salary_currency, salary_gross, area, experience, employment,
                        schedule, published_at, url, source_queries, raw_text,
                        details_loaded, total_score, priority, recommended_resume,
                        recommended_resume_title, profile_scores, matched_keywords,
                        stopwords, scoring_version, status, date_found, date_reviewed,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        vacancy_id,
                        str(vacancy.get("title") or "").strip(),
                        str(vacancy.get("company") or "").strip(),
                        str(vacancy.get("salary") or "").strip(),
                        vacancy.get("salary_from"),
                        vacancy.get("salary_to"),
                        str(vacancy.get("salary_currency") or "").strip(),
                        gross_int,
                        str(vacancy.get("area") or "").strip(),
                        str(vacancy.get("experience") or "").strip(),
                        str(vacancy.get("employment") or "").strip(),
                        str(vacancy.get("schedule") or "").strip(),
                        str(vacancy.get("published_at") or "").strip(),
                        str(vacancy.get("url") or "").strip(),
                        self._merge_queries("[]", incoming_queries),
                        raw_text,
                        details_loaded,
                        int(vacancy.get("total_score") or 0),
                        str(vacancy.get("priority") or "low"),
                        str(vacancy.get("recommended_resume") or ""),
                        str(vacancy.get("recommended_resume_title") or ""),
                        profile_scores,
                        str(vacancy.get("matched_keywords") or ""),
                        str(vacancy.get("stopwords") or ""),
                        str(vacancy.get("scoring_version") or ""),
                        str(vacancy.get("status") or "new"),
                        str(vacancy.get("date_found") or now),
                        str(vacancy.get("date_reviewed") or ""),
                        now,
                    ),
                )
            else:
                merged_queries = self._merge_queries(
                    existing["source_queries"], incoming_queries
                )
                effective_raw_text = raw_text or existing["raw_text"]
                effective_details = 1 if effective_raw_text else existing["details_loaded"]

                conn.execute(
                    """
                    UPDATE vacancies SET
                        title = COALESCE(NULLIF(?, ''), title),
                        company = COALESCE(NULLIF(?, ''), company),
                        salary = COALESCE(NULLIF(?, ''), salary),
                        salary_from = COALESCE(?, salary_from),
                        salary_to = COALESCE(?, salary_to),
                        salary_currency = COALESCE(NULLIF(?, ''), salary_currency),
                        salary_gross = COALESCE(?, salary_gross),
                        area = COALESCE(NULLIF(?, ''), area),
                        experience = COALESCE(NULLIF(?, ''), experience),
                        employment = COALESCE(NULLIF(?, ''), employment),
                        schedule = COALESCE(NULLIF(?, ''), schedule),
                        published_at = COALESCE(NULLIF(?, ''), published_at),
                        url = COALESCE(NULLIF(?, ''), url),
                        source_queries = ?,
                        raw_text = ?,
                        details_loaded = ?,
                        total_score = ?,
                        priority = ?,
                        recommended_resume = ?,
                        recommended_resume_title = ?,
                        profile_scores = ?,
                        matched_keywords = ?,
                        stopwords = ?,
                        scoring_version = ?,
                        updated_at = ?
                    WHERE vacancy_id = ?
                    """,
                    (
                        str(vacancy.get("title") or "").strip(),
                        str(vacancy.get("company") or "").strip(),
                        str(vacancy.get("salary") or "").strip(),
                        vacancy.get("salary_from"),
                        vacancy.get("salary_to"),
                        str(vacancy.get("salary_currency") or "").strip(),
                        gross_int,
                        str(vacancy.get("area") or "").strip(),
                        str(vacancy.get("experience") or "").strip(),
                        str(vacancy.get("employment") or "").strip(),
                        str(vacancy.get("schedule") or "").strip(),
                        str(vacancy.get("published_at") or "").strip(),
                        str(vacancy.get("url") or "").strip(),
                        merged_queries,
                        effective_raw_text,
                        effective_details,
                        int(vacancy.get("total_score") or 0),
                        str(vacancy.get("priority") or "low"),
                        str(vacancy.get("recommended_resume") or ""),
                        str(vacancy.get("recommended_resume_title") or ""),
                        profile_scores,
                        str(vacancy.get("matched_keywords") or ""),
                        str(vacancy.get("stopwords") or ""),
                        str(vacancy.get("scoring_version") or ""),
                        now,
                        vacancy_id,
                    ),
                )

    def update_score(self, vacancy_id: str, score_result: dict) -> None:
        now = self._now_iso()
        profile_scores = score_result.get("profile_scores") or {}
        if not isinstance(profile_scores, str):
            profile_scores = json.dumps(profile_scores, ensure_ascii=False)

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE vacancies SET
                    total_score = ?,
                    priority = ?,
                    recommended_resume = ?,
                    recommended_resume_title = ?,
                    profile_scores = ?,
                    matched_keywords = ?,
                    stopwords = ?,
                    scoring_version = ?,
                    updated_at = ?
                WHERE vacancy_id = ?
                """,
                (
                    int(score_result.get("total_score") or 0),
                    str(score_result.get("priority") or "low"),
                    str(score_result.get("recommended_resume") or ""),
                    str(score_result.get("recommended_resume_title") or ""),
                    profile_scores,
                    str(score_result.get("matched_keywords") or ""),
                    str(score_result.get("stopwords") or ""),
                    str(score_result.get("scoring_version") or ""),
                    now,
                    str(vacancy_id),
                ),
            )

    def get_existing_ids_with_details(self) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT vacancy_id FROM vacancies WHERE details_loaded = 1"
            ).fetchall()
            return {row["vacancy_id"] for row in rows}

    def get_all_vacancies(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM vacancies ORDER BY total_score DESC, updated_at DESC"
            ).fetchall()
            return [self._row_to_dict(row) for row in rows]

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        item = dict(row)
        gross = item.get("salary_gross")
        item["salary_gross"] = None if gross is None else bool(gross)
        try:
            item["source_queries"] = json.loads(item.get("source_queries") or "[]")
        except json.JSONDecodeError:
            item["source_queries"] = []
        try:
            item["profile_scores"] = json.loads(item.get("profile_scores") or "{}")
        except json.JSONDecodeError:
            item["profile_scores"] = {}
        return item