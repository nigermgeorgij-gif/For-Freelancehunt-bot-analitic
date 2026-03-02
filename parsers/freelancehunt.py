@staticmethod
def _parse_html(html: str) -> list[Project]:
    tree = HTMLParser(html)
    projects: list[Project] = []
    seen_ids = set()

    # ищем ссылки на проекты
    for link in tree.css("a[href*='/project/']"):
        href = link.attributes.get("href", "")
        if not href.endswith(".html"):
            continue

        # вытаскиваем id из URL
        external_id = ""
        parts = href.rstrip("/").split("/")
        for part in reversed(parts):
            clean = part.replace(".html", "")
            if clean.isdigit():
                external_id = clean
                break

        if not external_id or external_id in seen_ids:
            continue

        seen_ids.add(external_id)

        title = link.text(strip=True)
        if not title:
            continue

<<<<<<< HEAD
        url = href if href.startswith("http") else f"https://freelancehunt.com{href}"

        projects.append(Project(
            external_id=external_id,
            title=title,
            description="",
            url=url,
            budget="N/A",
            source="freelancehunt",
        ))

        if len(projects) >= MAX_PROJECTS:
            break

    logger.info("Parsed %d projects from Freelancehunt", len(projects))
    return projects
=======
    @staticmethod
    def _parse_html(html: str) -> list[Project]:
        tree = HTMLParser(html)
        projects: list[Project] = []
        seen_ids: set[str] = set()

        for link_node in tree.css('a[href*="/project/"]'):
            if len(projects) >= MAX_PROJECTS:
                break
            try:
                href = link_node.attributes.get("href", "")
                if not href.endswith(".html"):
                    continue

                parts = href.rstrip("/").split("/")
                external_id = ""
                for part in reversed(parts):
                    clean = part.replace(".html", "")
                    if clean.isdigit():
                        external_id = clean
                        break
                if not external_id or external_id in seen_ids:
                    continue

                title = link_node.text(strip=True)
                if not title:
                    continue
                seen_ids.add(external_id)

                url = href if href.startswith("http") else f"https://freelancehunt.com{href}"

                projects.append(Project(
                    external_id=external_id,
                    title=title,
                    description="",
                    url=url,
                    budget="N/A",
                    source="freelancehunt",
                ))
            except Exception as e:
                logger.error("Error parsing project link: %s", e)
                continue

        logger.info("Parsed %d projects from Freelancehunt", len(projects))
        return projects

    async def close(self) -> None:
        await self._client.aclose()
>>>>>>> 52aadd1d43dfcd7845d86d5879d890c7c4adfebd
