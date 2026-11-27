from __future__ import annotations

import argparse
import logging
from pathlib import Path

from config import Settings
from database import VacancyDatabase
from hh_search import HHSearcher
from report import ReportGenerator
from scoring import VacancyScorer


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )


def run_search(settings: Settings) -> None:
    db = VacancyDatabase(settings.paths.db_path)
    searcher = HHSearcher(settings)
    scorer = VacancyScorer(settings)
    reporter = ReportGenerator(settings)

    existing_ids = db.get_existing_ids_with_details()
    found_vacancies = searcher.search_all(skip_ids=existing_ids)

    saved_count = 0
    for vacancy in found_vacancies:
        score_data = scorer.score(vacancy)
        merged = {**vacancy, **score_data}
        db.upsert_vacancy(merged)
        saved_count += 1

    logging.info("Сохранено/обновлено вакансий в БД: %s", saved_count)

    all_vacancies = db.get_all_vacancies()
    excel_path = reporter.export_excel(all_vacancies)
    report_path = reporter.export_markdown(all_vacancies)

    logging.info("Excel-выгрузка обновлена: %s", excel_path)
    logging.info("Markdown-отчёт обновлён: %s", report_path)


def run_rescore(settings: Settings) -> None:
    db = VacancyDatabase(settings.paths.db_path)
    scorer = VacancyScorer(settings)
    reporter = ReportGenerator(settings)

    all_vacancies = db.get_all_vacancies()
    if not all_vacancies:
        logging.warning("База данных пуста. Сначала выполните команду 'search'.")
        return

    for vacancy in all_vacancies:
        score_data = scorer.score(vacancy)
        db.update_score(vacancy["vacancy_id"], score_data)

    logging.info("Пересчитано вакансий: %s", len(all_vacancies))

    updated_vacancies = db.get_all_vacancies()
    excel_path = reporter.export_excel(updated_vacancies)
    report_path = reporter.export_markdown(updated_vacancies)

    logging.info("Excel-выгрузка обновлена: %s", excel_path)
    logging.info("Markdown-отчёт обновлён: %s", report_path)


def run_reset(settings: Settings) -> None:
    targets = [
        Path(settings.paths.db_path),
        Path(settings.paths.excel_path),
        Path(settings.paths.report_path),
    ]
    for target in targets:
        if target.exists():
            target.unlink()
            logging.info("Удалён файл: %s", target)
        else:
            logging.info("Файл не найден (пропущено): %s", target)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Vacancy Hunter MVP — поиск и оценка вакансий под 5 резюме."
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="search",
        choices=["search", "rescore", "reset"],
        help="Режим запуска: search (по умолчанию), rescore или reset.",
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Путь к JSON-файлу настроек (по умолчанию: config.json).",
    )
    return parser


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    settings = Settings.load(args.config)

    if args.command == "search":
        run_search(settings)
    elif args.command == "rescore":
        run_rescore(settings)
    elif args.command == "reset":
        run_reset(settings)


if __name__ == "__main__":
    main()