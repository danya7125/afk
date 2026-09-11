from __future__ import annotations

from collections.abc import Iterable

from ..catalog import CATEGORY_KEYWORDS
from ..db import get_connection
from ..models import Service

_REAL_SERVICE_FILTER = """
    s.service_title_text IS NOT NULL
    AND NULLIF(BTRIM(s.service_title_text), '') IS NOT NULL
    AND s.service_title_text <> 'SmevRequestService'
    AND (
          NULLIF(BTRIM(COALESCE(s.description_text, '')), '') IS NOT NULL
       OR NULLIF(BTRIM(COALESCE(s.documents_text, '')), '') IS NOT NULL
       OR NULLIF(BTRIM(COALESCE(s.payment_info_text, '')), '') IS NOT NULL
       OR NULLIF(BTRIM(COALESCE(s.time_term_text, '')), '') IS NOT NULL
       OR NULLIF(BTRIM(COALESCE(s.service_result_text, '')), '') IS NOT NULL
       OR NULLIF(BTRIM(COALESCE(s.reject_reasons_text, '')), '') IS NOT NULL
    )
"""

_SUMMARY_COLUMNS = """
    s.id,
    s.service_title_text,
    s.description_text
"""

_SERVICE_COLUMNS = """
    s.id,
    s.service_title_text,
    s.description_text,
    s.service_recipients,
    s.documents_text,
    s.payment_info_text,
    s.time_term_text,
    s.service_result_text,
    s.reject_reasons_text
"""


class ServiceRepository:
    def count(self) -> int:
        with get_connection() as conn:
            row = conn.execute(
                f"SELECT COUNT(*) AS count FROM services s WHERE {_REAL_SERVICE_FILTER}"
            ).fetchone()
        return int(row["count"])

    def list(
        self,
        *,
        query: str = "",
        category: str = "",
        status: str = "",
        limit: int = 100,
    ) -> list[Service]:
        where = [_REAL_SERVICE_FILTER]
        params: list[object] = []

        if query:
            where.append("s.service_title_text ILIKE %s")
            params.append(f"%{query}%")

        self._apply_status_filter(where, status)
        self._apply_category_filter(where, params, category)

        params.append(limit)
        sql = f"""
            SELECT {_SUMMARY_COLUMNS}
            FROM services s
            WHERE {' AND '.join(f'({item})' for item in where)}
            ORDER BY s.service_title_text
            LIMIT %s
        """

        with get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [Service.from_row(row) for row in rows]

    def get_by_id(self, service_id: str) -> Service | None:
        with get_connection() as conn:
            row = conn.execute(
                f"""
                SELECT {_SERVICE_COLUMNS}
                FROM services s
                WHERE s.id = %s
                  AND ({_REAL_SERVICE_FILTER})
                """,
                (service_id,),
            ).fetchone()

        return Service.from_row(row) if row else None

    def search_for_ai(self, terms: Iterable[str], limit: int = 5) -> list[Service]:
        terms = [term.strip().lower() for term in terms if term and term.strip()]
        if not terms:
            return []

        title_candidates = self._search_candidates(terms, title_only=True, limit=max(limit * 4, 20))
        if len(title_candidates) >= limit:
            return self._rank(title_candidates, terms)[:limit]

        all_candidates = self._search_candidates(terms[:8], title_only=False, limit=max(limit * 10, 50))

        deduped: dict[str, Service] = {service.id: service for service in title_candidates}
        for service in all_candidates:
            deduped.setdefault(service.id, service)

        return self._rank(list(deduped.values()), terms)[:limit]

    def _search_candidates(
        self,
        terms: list[str],
        *,
        title_only: bool,
        limit: int,
    ) -> list[Service]:
        conditions: list[str] = []
        params: list[object] = []

        for term in terms:
            like = f"%{term}%"
            if title_only:
                conditions.append("LOWER(s.service_title_text) LIKE %s")
                params.append(like)
            else:
                conditions.append(
                    """
                    (
                        LOWER(COALESCE(s.service_title_text, '')) LIKE %s
                        OR LOWER(COALESCE(s.description_text, '')) LIKE %s
                        OR LOWER(COALESCE(s.documents_text, '')) LIKE %s
                        OR LOWER(COALESCE(s.service_result_text, '')) LIKE %s
                    )
                    """
                )
                params.extend([like, like, like, like])

        params.append(limit)
        sql = f"""
            SELECT {_SERVICE_COLUMNS}
            FROM services s
            WHERE ({_REAL_SERVICE_FILTER})
              AND ({' OR '.join(conditions)})
            ORDER BY length(s.service_title_text), s.service_title_text
            LIMIT %s
        """

        with get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [Service.from_row(row) for row in rows]

    @staticmethod
    def _rank(services: list[Service], terms: list[str]) -> list[Service]:
        def score(service: Service) -> float:
            title = service.name.lower()
            description = service.description.lower()
            documents = service.documents.lower()
            result = service.result.lower()
            total = 0.0

            for index, term in enumerate(terms):
                weight = 1.0 + min(len(term), 60) / 60
                if term in title:
                    total += 10 * weight
                if term in description:
                    total += 4 * weight
                if term in result:
                    total += 2.5 * weight
                if term in documents:
                    total += 1.5 * weight
                if index == 0 and term in title:
                    total += 3

            return total

        return sorted(services, key=lambda item: (-score(item), len(item.name), item.name))

    @staticmethod
    def _apply_status_filter(where: list[str], status: str) -> None:
        filters = {
            "with_time": "NULLIF(BTRIM(COALESCE(s.time_term_text, '')), '') IS NOT NULL",
            "with_documents": "NULLIF(BTRIM(COALESCE(s.documents_text, '')), '') IS NOT NULL",
            "with_payment": "NULLIF(BTRIM(COALESCE(s.payment_info_text, '')), '') IS NOT NULL",
        }
        if status in filters:
            where.append(filters[status])

    @staticmethod
    def _apply_category_filter(where: list[str], params: list[object], category: str) -> None:
        searchable = "LOWER(COALESCE(s.service_title_text, '') || ' ' || COALESCE(s.description_text, ''))"

        if category in CATEGORY_KEYWORDS:
            conditions = []
            for keyword in CATEGORY_KEYWORDS[category]:
                conditions.append(f"{searchable} LIKE %s")
                params.append(f"%{keyword.lower()}%")
            where.append("(" + " OR ".join(conditions) + ")")
            return

        if category == "other":
            all_keywords = sorted({kw for values in CATEGORY_KEYWORDS.values() for kw in values})
            conditions = []
            for keyword in all_keywords:
                conditions.append(f"{searchable} LIKE %s")
                params.append(f"%{keyword.lower()}%")
            where.append("NOT (" + " OR ".join(conditions) + ")")
