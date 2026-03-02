from dataclasses import dataclass, field


@dataclass
class Project:
    external_id: str
    title: str
    description: str
    url: str
    budget: str
    source: str
    content_hash: str = ""
    notified_at: str | None = None
