import aiosqlite
import logging
from db.models import Project

logger = logging.getLogger(__name__)


class ProjectRepository:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def _get_db(self) -> aiosqlite.Connection:
        if self._db is None:
            self._db = await aiosqlite.connect(self._db_path)
            await self._db.execute("PRAGMA journal_mode=WAL")
        return self._db

    async def init_db(self) -> None:
        db = await self._get_db()
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
                content_hash TEXT DEFAULT '',
                notified_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await self._migrate(db)
        await db.commit()
        logger.info("Database initialized")

    @staticmethod
    async def _migrate(db: aiosqlite.Connection) -> None:
        cursor = await db.execute("PRAGMA table_info(projects)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "content_hash" not in columns:
            await db.execute(
                "ALTER TABLE projects ADD COLUMN content_hash TEXT DEFAULT ''"
            )
        if "notified_at" not in columns:
            await db.execute(
                "ALTER TABLE projects ADD COLUMN notified_at TIMESTAMP"
            )

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None
            logger.info("Database connection closed")

    async def project_exists(self, external_id: str) -> bool:
        db = await self._get_db()
        cursor = await db.execute(
            "SELECT 1 FROM projects WHERE external_id = ?",
            (external_id,),
        )
        row = await cursor.fetchone()
        return row is not None

    async def get_content_hash(self, external_id: str) -> str | None:
        db = await self._get_db()
        cursor = await db.execute(
            "SELECT content_hash FROM projects WHERE external_id = ?",
            (external_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return row[0] or ""

    async def save_project(self, project: Project) -> None:
        db = await self._get_db()
        await db.execute(
            """
            INSERT OR IGNORE INTO projects
                (external_id, title, description, url, budget, source, content_hash, notified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project.external_id,
                project.title,
                project.description,
                project.url,
                project.budget,
                project.source,
                project.content_hash,
                project.notified_at,
            ),
        )
        await db.commit()

    async def update_project(self, project: Project) -> None:
        db = await self._get_db()
        await db.execute(
            """
            UPDATE projects
            SET title = ?, description = ?, budget = ?, content_hash = ?, notified_at = ?
            WHERE external_id = ?
            """,
            (
                project.title,
                project.description,
                project.budget,
                project.content_hash,
                project.notified_at,
                project.external_id,
            ),
        )
        await db.commit()

    async def get_project(self, external_id: str) -> Project | None:
        db = await self._get_db()
        cursor = await db.execute(
            "SELECT external_id, title, description, url, budget, source, "
            "content_hash, notified_at "
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
            content_hash=row[6] or "",
            notified_at=row[7],
        )
