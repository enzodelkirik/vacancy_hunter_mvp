from __future__ import annotations

import logging
import random
import re
import time
from typing import Any

import requests
from bs4 import BeautifulSoup

from config import Settings


class HHSearcher:
    BASE_URL = "https://hh.ru"

    ROLE_TITLE_PATTERNS = [
        r"\bруководител\w*\b",
        r"\bдиректор\w*\b",
        r"\bначальник\w*\b",
        r"\bзаместител\w*\b",
        r"\bменеджер\w*\b",
        r"\bmanager\b",
        r"\bкоординатор\w*\b",
        r"\bспециалист\w*\b",
        r"\bассистент\w*\b",
    ]

    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/128.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,"
                    "application/xml;q=0.9,*/*;q=0.8"
                ),
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            }
        )
        self._compiled_role_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.ROLE_TITLE_PATTERNS
        ]

    def _sleep(self) -> None:
        delay = random.uniform(
            self.settings.search.request_delay_min,
            self.settings.search.request_delay_max,
        )
        time.sleep(delay)

    def _request(self, url: str, params: dict[str, Any] | None = None) -> requests.Response:
        retries = max(1, self.settings.search.max_retries)
        last_exc: Exception | None = None

        for attempt in range(1, retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=30)
                if response.status_code == 429:
                    wait_seconds = 10 * attempt
                    logging.warning(
                        "Получен 429 Too Many Requests (попытка %s/%s). Пауза %s сек.",
                        attempt,
                        retries,
                        wait_seconds,
                    )
                    time.sleep(wait_seconds)
                    continue

                if response.status_code >= 500:
                    wait_seconds = 3 * attempt
                    logging.warning(
                        "Ошибка сервера hh.ru %s (попытка %s/%s). Пауза %s сек.",
                        response.status_code,
                        attempt,
                        retries,
                        wait_seconds,
                    )
                    time.sleep(wait_seconds)
                    continue

                if response.status_code >= 400:
                    raise RuntimeError(f"Ошибка запроса {response.status_code}: {url}")

                return response
            except requests.RequestException as exc:
                last_exc = exc
                wait_seconds = 3 * attempt
                logging.warning(
                    "Сетевая ошибка при запросе %s (попытка %s/%s): %s",
                    url,
                    attempt,
                    retries,
                    exc,
                )
                if attempt < retries:
                    time.sleep(wait_seconds)

        if last_exc:
            raise RuntimeError(f"Не удалось выполнить запрос к {url}: {last_exc}") from last_exc
        raise RuntimeError(f"Превышено число попыток запроса к {url}")

    @staticmethod
    def _extract_vacancy_id(link: str) -> str | None:
        match = re.search(r"/vacancy/(\d+)", link or "")
        return match.group(1) if match else None

    @staticmethod
    def _clean_text(value: str) -> str:
        text = str(value or "").replace("\u200b", " ").replace("\xa0", " ")
        return re.sub(r"\s+", " ", text).strip()

    def _extract_salary(
        self, container: Any
    ) -> tuple[str, int | None, int | None, str, bool | None]:
        if container is None:
            return "", None, None, "", None

        text = self._clean_text(container.get_text(" ", strip=True))
        if not text:
            return "", None, None, "", None

        currency_match = re.search(
            r"(₽|руб\.?|RUB|USD|\$|EUR|€)", text, re.IGNORECASE
        )
        currency = currency_match.group(1) if currency_match else ""

        gross: bool | None = None
        if re.search(r"до\s+вычета\s+налогов|gross", text, re.IGNORECASE):
            gross = True
        elif re.search(r"на\s+руки|net", text, re.IGNORECASE):
            gross = False

        raw_numbers = re.findall(r"\d[\d\s]*(?:[.,]\d+)?", text)
        numbers: list[int] = []
        for raw_num in raw_numbers:
            digits_only = re.sub(r"[\s,]", "", raw_num).split(".")[0]
            if digits_only.isdigit():
                numbers.append(int(digits_only))

        salary_from: int | None = None
        salary_to: int | None = None

        has_from = bool(re.search(r"\bот\b", text, re.IGNORECASE))
        has_to = bool(re.search(r"\bдо\b", text, re.IGNORECASE))

        if has_from and numbers:
            salary_from = numbers[0]
        if has_to and len(numbers) >= 2:
            salary_to = numbers[-1]
        elif has_to and numbers and not has_from:
            salary_to = numbers[0]
        if salary_from is None and salary_to is None and len(numbers) == 1:
            salary_from = numbers[0]

        return text, salary_from, salary_to, currency, gross

    def _is_title_relevant(self, title: str) -> bool:
        normalized_title = self._clean_text(title).lower()
        if not normalized_title:
            return False
        return any(pattern.search(normalized_title) for pattern in self._compiled_role_patterns)

    def _parse_search_page(self, html: str, source_query: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("a[data-qa='serp-item__title']")
        vacancies: list[dict[str, Any]] = []

        for card in cards:
            link = (card.get("href") or "").strip()
            if link.startswith("/"):
                link = self.BASE_URL + link

            vacancy_id = self._extract_vacancy_id(link)
            if not vacancy_id:
                continue

            title = self._clean_text(card.get_text(" ", strip=True))
            if not self._is_title_relevant(title):
                logging.debug("Отфильтровано по заголовку: %s", title)
                continue

            card_container = card.find_parent(attrs={"data-qa": "vacancy-serp__vacancy"})
            if card_container is None:
                card_container = card.find_parent("article") or card.find_parent("div")

            salary_container = None
            experience_container = None
            if card_container:
                salary_container = card_container.select_one(
                    "[data-qa='vacancy-serp__vacancy-compensation']"
                )
                experience_container = card_container.select_one(
                    "[data-qa='vacancy-serp__vacancy-work-experience']"
                )

            salary_text, salary_from, salary_to, currency, gross = self._extract_salary(
                salary_container
            )
            experience = (
                self._clean_text(experience_container.get_text(" ", strip=True))
                if experience_container
                else ""
            )

            vacancies.append(
                {
                    "vacancy_id": vacancy_id,
                    "title": title,
                    "company": "",
                    "salary": salary_text,
                    "salary_from": salary_from,
                    "salary_to": salary_to,
                    "salary_currency": currency,
                    "salary_gross": gross,
                    "area": "",
                    "experience": experience,
                    "employment": "",
                    "schedule": "",
                    "published_at": "",
                    "url": link,
                    "source_queries": [source_query],
                    "raw_text": "",
                }
            )

        return vacancies

    def _extract_field_by_label(self, soup: BeautifulSoup, label_pattern: str) -> str:
        labels = soup.find_all(string=re.compile(label_pattern, re.IGNORECASE))
        for label in labels:
            parent = label.find_parent(["p", "div", "li", "span"])
            if parent:
                text = self._clean_text(parent.get_text(" ", strip=True))
                cleaned = re.sub(
                    rf"^{label_pattern}\s*:?\s*", "", text, flags=re.IGNORECASE
                )
                cleaned = self._clean_text(cleaned)
                if cleaned:
                    return cleaned
        return ""

    def _extract_published_at(self, soup: BeautifulSoup) -> str:
        time_tag = soup.find("time")
        if time_tag:
            dt_val = time_tag.get("datetime") or time_tag.get_text(" ", strip=True)
            cleaned = self._clean_text(str(dt_val or ""))
            if cleaned:
                return cleaned

        text = self._clean_text(soup.get_text(" ", strip=True))
        match = re.search(
            r"(?:Опубликована|Опубликовано)\s*:?\s*(\d{1,2}\s+\w+\s+\d{4})",
            text,
            re.IGNORECASE,
        )
        return match.group(1) if match else ""

    def _extract_description(self, soup: BeautifulSoup) -> str:
        desc = soup.select_one("[data-qa='vacancy-description']")
        if not desc:
            return ""
        raw = desc.get_text("\n", strip=True)
        lines = [self._clean_text(line) for line in raw.splitlines()]
        return "\n".join(line for line in lines if line)

    def _parse_vacancy_page(self, html: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")

        company_el = soup.select_one("[data-qa='vacancy-company-name']")
        company = self._clean_text(company_el.get_text(" ", strip=True)) if company_el else ""

        area_el = soup.select_one(
            "[data-qa='vacancy-view-location'], [data-qa='vacancy-view-raw-address']"
        )
        area = self._clean_text(area_el.get_text(" ", strip=True)) if area_el else ""

        salary_el = soup.select_one("[data-qa='vacancy-salary']")
        salary_text, salary_from, salary_to, currency, gross = self._extract_salary(salary_el)

        exp_el = soup.select_one("[data-qa='vacancy-experience']")
        experience = self._clean_text(exp_el.get_text(" ", strip=True)) if exp_el else ""

        employment = self._extract_field_by_label(soup, r"Занятость")
        schedule = self._extract_field_by_label(soup, r"(?:График\s+работы|Формат\s+работы)")

        return {
            "company": company,
            "salary": salary_text,
            "salary_from": salary_from,
            "salary_to": salary_to,
            "salary_currency": currency,
            "salary_gross": gross,
            "area": area,
            "experience": experience,
            "employment": employment,
            "schedule": schedule,
            "published_at": self._extract_published_at(soup),
            "raw_text": self._extract_description(soup),
        }

    def _load_vacancy_details(self, vacancy: dict[str, Any]) -> dict[str, Any]:
        response = self._request(vacancy["url"])
        details = self._parse_vacancy_page(response.text)
        merged = {**vacancy}
        for key, val in details.items():
            if val not in ("", None):
                merged[key] = val
        return merged

    def search_query(self, query: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        url = f"{self.BASE_URL}/search/vacancy"

        for page in range(self.settings.search.pages):
            params: dict[str, Any] = {
                "text": query,
                "area": self.settings.search.area_id,
                "per_page": self.settings.search.per_page,
                "page": page,
            }
            if self.settings.search.experience:
                params["experience"] = self.settings.search.experience
            if self.settings.search.schedule:
                params["schedule"] = self.settings.search.schedule

            logging.info("Поиск: '%s' | страница %s", query, page)
            response = self._request(url, params=params)
            soup = BeautifulSoup(response.text, "html.parser")
            raw_cards = soup.select("a[data-qa='serp-item__title']")

            if not raw_cards:
                logging.info("Карточек больше нет на странице %s по запросу '%s'", page, query)
                break

            page_results = self._parse_search_page(response.text, source_query=query)
            results.extend(page_results)
            self._sleep()

        return results

    def collect_queries(self) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for profile in self.settings.profiles:
            for q in profile.queries:
                q_clean = self._clean_text(q)
                if q_clean and q_clean not in seen:
                    seen.add(q_clean)
                    ordered.append(q_clean)
        return ordered

    def search_all(self, skip_ids: set[str] | None = None) -> list[dict[str, Any]]:
        skip_ids = skip_ids or set()
        queries = self.collect_queries()
        if not queries:
            raise ValueError("Не найдено ни одного поискового запроса в профилях.")

        vacancies_by_id: dict[str, dict[str, Any]] = {}

        for query in queries:
            found = self.search_query(query)
            for item in found:
                vid = item["vacancy_id"]
                if vid not in vacancies_by_id:
                    vacancies_by_id[vid] = item
                else:
                    existing_q = vacancies_by_id[vid].setdefault("source_queries", [])
                    if query not in existing_q:
                        existing_q.append(query)

        vacancies = list(vacancies_by_id.values())
        logging.info("Уникальных вакансий после предфильтра заголовка: %s", len(vacancies))

        to_load = [v for v in vacancies if v["vacancy_id"] not in skip_ids]
        skipped_count = len(vacancies) - len(to_load)
        if skipped_count:
            logging.info("Пропущено уже загруженных ранее вакансий: %s", skipped_count)

        loaded_vacancies: list[dict[str, Any]] = []
        for idx, vacancy in enumerate(to_load, start=1):
            logging.info(
                "Загрузка карточки %s/%s: %s", idx, len(to_load), vacancy["title"]
            )
            try:
                enriched = self._load_vacancy_details(vacancy)
                loaded_vacancies.append(enriched)
            except Exception:
                logging.exception("Ошибка при загрузке карточки %s", vacancy["url"])
                loaded_vacancies.append(vacancy)
            self._sleep()

        return loaded_vacancies