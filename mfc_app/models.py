from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .utils.text import clean_html


@dataclass(slots=True)
class Service:
    id: str
    name: str
    description: str = ""
    recipients: str = ""
    documents: str = ""
    payment: str = ""
    time: str = ""
    result: str = ""
    reject_reasons: str = ""

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Service":
        return cls(
            id=str(row.get("id") or ""),
            name=clean_html(row.get("service_title_text")),
            description=clean_html(row.get("description_text")),
            recipients=clean_html(row.get("service_recipients")),
            documents=clean_html(row.get("documents_text")),
            payment=clean_html(row.get("payment_info_text")),
            time=clean_html(row.get("time_term_text")),
            result=clean_html(row.get("service_result_text")),
            reject_reasons=clean_html(row.get("reject_reasons_text")),
        )

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
