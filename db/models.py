from dataclasses import dataclass


@dataclass
class Project:
    external_id: str
    title: str
    description: str
    url: str
    budget: str
    source: str
