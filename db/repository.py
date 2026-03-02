import aiosqlite
import logging
from db.models import Project

logger = logging.getLogger(__name__)


class ProjectRepository:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def init_db(self) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    external_id TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    url TEXT,
                    budget TEXT,
                    source TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.commit()
        logger.info("Database initialized")

    async def project_exists(self, external_id: str) -> bool:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT 1 FROM projects WHERE external_id = ?",
                (external_id,),
            )
            row = await cursor.fetchone()
            return row is not None

    async def save_project(self, project: Project) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO projects
                    (external_id, title, description, url, budget, source)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project.external_id,
                    project.title,
                    project.description,
                    project.url,
                    project.budget,
                    project.source,
                ),
            )
            await db.commit()
        logger.debug("Saved project %s", project.external_id)

    async def get_project(self, external_id: str) -> Project | None:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT external_id, title, description, url, budget, source "
                "FROM projects WHERE external_id = ?",
                (external_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return Project(
                external_id=row[0],
                title=row[1],
                description=row[2],
                url=row[3],
                budget=row[4],
                source=row[5],
            )
