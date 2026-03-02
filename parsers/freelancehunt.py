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