from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from config import SCORING_VERSION, Settings


class ReportGenerator:
    def __init__(self, settings: Settings):
        self.settings = settings

    def export_excel(self, vacancies: list[dict[str, Any]]) -> Path:
        out_path = Path(self.settings.paths.excel_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        threshold = self.settings.scoring.min_score_to_export
        filtered = [
            v for v in vacancies if int(v.get("total_score") or 0) >= threshold
        ]
        filtered.sort(
            key=lambda v: (
                int(v.get("total_score") or 0),
                str(v.get("updated_at") or ""),
            ),
            reverse=True,
        )

        wb = Workbook()
        ws = wb.active
        ws.title = "Vacancies"

        profile_codes = [p.code for p in self.settings.profiles]

        headers = [
            "ID",
            "Балл",
            "Приоритет",
            "Рекомендуемое резюме",
            "Название вакансии",
            "Компания",
            "Зарплата",
            "Локация",
            "Опыт",
            "Формат / График",
            "Статус",
            *[f"Балл: {code}" for code in profile_codes],
            "Стоп-слова",
            "Обоснование",
            "Ссылка",
            "Версия правил",
        ]

        header_fill = PatternFill(
            start_color="1F4E78", end_color="1F4E78", fill_type="solid"
        )
        header_font = Font(color="FFFFFF", bold=True, size=10)

        ws.append(headers)
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(vertical="center", wrap_text=True)

        for v in filtered:
            scores_map = v.get("profile_scores") or {}
            if not isinstance(scores_map, dict):
                scores_map = {}

            schedule_or_emp = " / ".join(
                part
                for part in (
                    str(v.get("schedule") or "").strip(),
                    str(v.get("employment") or "").strip(),
                )
                if part
            )

            row = [
                str(v.get("vacancy_id") or ""),
                int(v.get("total_score") or 0),
                str(v.get("priority") or ""),
                str(
                    v.get("recommended_resume_title")
                    or v.get("recommended_resume")
                    or ""
                ),
                str(v.get("title") or ""),
                str(v.get("company") or ""),
                str(v.get("salary") or ""),
                str(v.get("area") or ""),
                str(v.get("experience") or ""),
                schedule_or_emp,
                str(v.get("status") or "new"),
                *[int(scores_map.get(code) or 0) for code in profile_codes],
                str(v.get("stopwords") or ""),
                str(v.get("matched_keywords") or ""),
                str(v.get("url") or ""),
                str(v.get("scoring_version") or SCORING_VERSION),
            ]
            ws.append(row)

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:{self._col_letter(len(headers))}{max(1, len(filtered) + 1)}"

        column_widths = {
            "A": 13,
            "B": 8,
            "C": 12,
            "D": 36,
            "E": 40,
            "F": 28,
            "G": 22,
            "H": 22,
            "I": 18,
            "J": 22,
            "K": 12,
        }
        for col_letter, width in column_widths.items():
            ws.column_dimensions[col_letter].width = width

        for idx in range(len(profile_codes)):
            letter = self._col_letter(12 + idx)
            ws.column_dimensions[letter].width = 16

        wb.save(out_path)
        return out_path

    @staticmethod
    def _col_letter(col_num: int) -> str:
        result = ""
        while col_num > 0:
            col_num, remainder = divmod(col_num - 1, 26)
            result = chr(65 + remainder) + result
        return result

    def export_markdown(self, vacancies: list[dict[str, Any]]) -> Path:
        report_path = Path(self.settings.paths.report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)

        threshold = self.settings.scoring.min_score_to_export
        total_count = len(vacancies)
        with_desc_count = sum(
            1 for v in vacancies if str(v.get("raw_text") or "").strip()
        )
        passed_count = sum(
            1 for v in vacancies if int(v.get("total_score") or 0) >= threshold
        )
        below_count = total_count - passed_count

        resume_counter = Counter(
            str(v.get("recommended_resume_title") or v.get("recommended_resume") or "не определено")
            for v in vacancies
            if int(v.get("total_score") or 0) >= threshold
        )
        priority_counter = Counter(
            str(v.get("priority") or "low") for v in vacancies
        )
        status_counter = Counter(
            str(v.get("status") or "new") for v in vacancies
        )

        sorted_vacancies = sorted(
            vacancies,
            key=lambda v: int(v.get("total_score") or 0),
            reverse=True,
        )
        top_vacancies = [
            v for v in sorted_vacancies if int(v.get("total_score") or 0) >= threshold
        ][:20]
        below_sample = [
            v for v in reversed(sorted_vacancies) if int(v.get("total_score") or 0) < threshold
        ][:15]

        lines: list[str] = [
            "# Отчёт по поиску вакансий (Vacancy Hunter MVP)",
            "",
            f"- **Версия правил скоринга:** `{SCORING_VERSION}`",
            f"- **Порог выгрузки в Excel (`min_score_to_export`):** `{threshold}`",
            f"- **Всего вакансий в базе:** `{total_count}`",
            f"- **С загруженным описанием:** `{with_desc_count}`",
            f"- **Прошли порог выгрузки:** `{passed_count}`",
            f"- **Ниже порога:** `{below_count}`",
            "",
            "## Распределение прошедших порог по 5 резюме",
            "",
        ]

        for profile in self.settings.profiles:
            cnt = resume_counter.get(profile.title, 0)
            lines.append(f"- **{profile.title}:** {cnt}")

        lines.extend(
            [
                "",
                "## Распределение по приоритетам (вся база)",
                "",
                f"- **high:** {priority_counter.get('high', 0)}",
                f"- **medium:** {priority_counter.get('medium', 0)}",
                f"- **low:** {priority_counter.get('low', 0)}",
                "",
                "## Распределение по статусам (вся база)",
                "",
            ]
        )

        for st, cnt in sorted(status_counter.items()):
            lines.append(f"- **{st}:** {cnt}")

        lines.extend(
            [
                "",
                "## Топ вакансий для рассмотрения",
                "",
            ]
        )

        if not top_vacancies:
            lines.append("Подходящих вакансий выше порога пока нет.")
        else:
            for item in top_vacancies:
                title = str(item.get("title") or "Без названия")
                company = str(item.get("company") or "Компания не указана")
                salary = str(item.get("salary") or "з/п не указана")
                score = int(item.get("total_score") or 0)
                rec = str(
                    item.get("recommended_resume_title")
                    or item.get("recommended_resume")
                    or ""
                )
                url = str(item.get("url") or "")
                reasons = str(item.get("matched_keywords") or "")
                lines.append(
                    f"- **[{score} б.] {title}** — *{company}* ({salary}) | "
                    f"Резюме: `{rec}` | [Ссылка]({url})"
                )
                if reasons:
                    lines.append(f"  - Причины: {reasons}")

        lines.extend(
            [
                "",
                "## Примеры вакансий ниже порога (для калибровки правил)",
                "",
            ]
        )

        if not below_sample:
            lines.append("Вакансий ниже порога нет.")
        else:
            for item in below_sample:
                title = str(item.get("title") or "Без названия")
                score = int(item.get("total_score") or 0)
                url = str(item.get("url") or "")
                reasons = str(item.get("matched_keywords") or "")
                lines.append(f"- **[{score} б.] {title}** — [Ссылка]({url})")
                if reasons:
                    lines.append(f"  - Причины: {reasons}")

        report_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        return report_path