from __future__ import annotations

import re
from typing import Any

from config import Settings


_REGEX_META_RE = re.compile(r"[.*+?^${}()|\[\]\\]")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")

_CIS_MARKERS_RE = re.compile(
    r"\b(беларусь|минск|казахстан|алматы|астана|узбекистан|ташкент|"
    r"армения|ереван|грузия|тбилиси|азербайджан|баку|кыргызстан|бишкек|"
    r"молдова|кишинев|таджикистан|душанбе|снг|ближн\w*\s+зарубеж\w*)\b",
    re.IGNORECASE,
)
_MOSCOW_MO_RE = re.compile(
    r"\b(москва|московск\w*\s+област\w*|зеленоград|химки|мытищ\w*|"
    r"королев|королёв|балаших\w*|люберц\w*|одинцов\w*|красногорск|"
    r"подольск|домодедово|реутов|долгопрудн\w*|раменск\w*|жуковск\w*|"
    r"истра|чехов|серпухов|клин|дмитров|ногинск|электросталь|видное)\b",
    re.IGNORECASE,
)
_PURE_SALES_TITLE_RE = re.compile(
    r"\b(продаж\w*|sales|менеджер\s+по\s+продажам|активных\s+продаж)\b",
    re.IGNORECASE,
)
_OPS_PROJECT_RE = re.compile(
    r"\b(операцион\w*|проект\w*|координатор\w*|кпэ|kpi|регламент\w*|процесс\w*|безопасност\w*|риск\w*)\b",
    re.IGNORECASE,
)


def _strip_html(text: str | None) -> str:
    if not text:
        return ""
    cleaned = _HTML_TAG_RE.sub(" ", text)
    return _SPACE_RE.sub(" ", cleaned).strip().lower()


def _get_description_raw(vacancy: dict[str, Any]) -> str:
    for key in ("description", "raw_text", "body", "snippet_text"):
        val = vacancy.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return ""


def _compile_kw(pattern: str) -> re.Pattern[str]:
    p = pattern.strip().lower()
    if _REGEX_META_RE.search(p):
        return re.compile(p, re.IGNORECASE)
    return re.compile(rf"(?<!\w){re.escape(p)}\w*(?!\w)", re.IGNORECASE)


def _extract_salary_net(vacancy: dict[str, Any]) -> float | None:
    for key in ("salary_net_avg", "salary_avg_net", "salary_net"):
        val = vacancy.get(key)
        if isinstance(val, (int, float)) and val > 0:
            return float(val)

    sal = vacancy.get("salary")
    if isinstance(sal, dict):
        s_from = sal.get("from")
        s_to = sal.get("to")
        gross = sal.get("gross")
        vals = [float(x) for x in (s_from, s_to) if isinstance(x, (int, float)) and x > 0]
        if not vals:
            return None
        avg = sum(vals) / len(vals)
        if gross is True:
            avg *= 0.87
        return avg

    s_from = vacancy.get("salary_from")
    s_to = vacancy.get("salary_to")
    gross = bool(vacancy.get("salary_gross", False))
    vals = [float(x) for x in (s_from, s_to) if isinstance(x, (int, float)) and x > 0]
    if not vals:
        return None
    avg = sum(vals) / len(vals)
    if gross:
        avg *= 0.87
    return avg


def _geo_salary_threshold(vacancy: dict[str, Any], search_cfg: dict[str, Any]) -> tuple[str, float]:
    moscow_min = float(search_cfg.get("min_salary_moscow_mo", search_cfg.get("min_salary_net", 200000)))
    rf_min = float(search_cfg.get("min_salary_regions_rf", 350000))
    cis_min = float(search_cfg.get("min_salary_cis", 500000))

    area_name = str(vacancy.get("area") or vacancy.get("area_name") or "")
    title = str(vacancy.get("title") or vacancy.get("name") or "")
    desc = _strip_html(_get_description_raw(vacancy))
    geo_haystack = f"{area_name} {title}".lower()

    if _CIS_MARKERS_RE.search(geo_haystack) or _CIS_MARKERS_RE.search(desc[:600]):
        return "СНГ/ближнее зарубежье", cis_min
    if _MOSCOW_MO_RE.search(geo_haystack):
        return "Москва/МО", moscow_min
    return "регионы РФ", rf_min


def _detect_format(vacancy: dict[str, Any], text_all: str) -> str:
    schedule = str(vacancy.get("schedule") or vacancy.get("schedule_name") or "").lower()
    if "remote" in schedule or "удален" in schedule or "удалён" in schedule:
        return "удаленка"
    if "shift" in schedule or "вахт" in schedule or "вахт" in text_all:
        return "вахта"
    if "командиров" in text_all:
        return "командировки"
    if "разъездн" in text_all:
        return "разъездной"
    if "гибрид" in text_all:
        return "гибрид"
    if "офис" in text_all:
        return "офис"
    return "не указан"


def score_vacancy(
    vacancy: dict[str, Any],
    config: Settings,
    stopwords: set[str] | None = None,
) -> dict[str, Any]:
    title_raw = str(vacancy.get("title") or vacancy.get("name") or "")
    title = title_raw.lower().strip()
    desc_raw = _get_description_raw(vacancy)
    desc = _strip_html(desc_raw)
    text_all = f"{title} {desc}".strip()

    reasons: list[str] = []
    global_delta = 0.0

    for pat, weight in config.global_title_penalties:
        if _compile_kw(pat).search(title):
            global_delta += float(weight)
            reasons.append(f"стоп в заголовке: {pat} ({weight:+.1f})")

    for pat, weight in config.global_body_penalties:
        if _compile_kw(pat).search(desc):
            global_delta += float(weight)
            reasons.append(f"стоп в описании: {pat} ({weight:+.1f})")

    if _PURE_SALES_TITLE_RE.search(title) and not re.search(
        r"\b(спорт\w*|хокке\w*|футбол\w*|теннис\w*|федерац\w*|партнер\w*|спонсор\w*)\b",
        text_all,
        re.IGNORECASE,
    ):
        global_delta -= 2.5
        reasons.append("линейные продажи в заголовке (-2.5)")

    if _OPS_PROJECT_RE.search(title):
        global_delta += 2.0
        reasons.append("профильный фокус в заголовке (+2.0)")

    if stopwords:
        for sw in stopwords:
            sw_clean = sw.strip().lower()
            if sw_clean and _compile_kw(sw_clean).search(title):
                global_delta -= 4.0
                reasons.append(f"стоп-слово: {sw_clean} (-4.0)")

    zone_label, min_needed = _geo_salary_threshold(vacancy, config.search)
    salary_net = _extract_salary_net(vacancy)
    salary_delta = 0.0
    if salary_net is None:
        reasons.append("з/п не указана (уточнить)")
    elif salary_net >= min_needed:
        salary_delta = 2.0
        reasons.append(f"з/п ок для {zone_label} (~{int(salary_net):,} ₽ net >= {int(min_needed):,})".replace(",", " "))
    elif salary_net >= min_needed * 0.80:
        salary_delta = 0.5
        reasons.append(f"з/п близко к порогу {zone_label} (~{int(salary_net):,} ₽ net)".replace(",", " "))
    else:
        salary_delta = -1.5
        reasons.append(f"з/п ниже порога {zone_label} (~{int(salary_net):,} ₽ net < {int(min_needed):,})".replace(",", " "))

    fmt = _detect_format(vacancy, text_all)

    best_id = 1
    best_name = ""
    best_score = -999.0
    best_reasons: list[str] = []
    profile_scores: dict[str, float] = {}

    for pid, pcfg in config.profiles.items():
        p_code = str(pcfg.get("code") or f"P{pid}_PROFILE")
        p_name = str(pcfg.get("title") or pcfg.get("name") or f"Профиль {pid}")
        p_weight = float(pcfg.get("priority_weight", 1.0))
        allowed = [str(x).lower() for x in pcfg.get("allowed_formats", ["не указан"])]

        raw_score = 0.0
        matched_tags: list[str] = []

        for kw, w in pcfg.get("title_boost", []):
            if _compile_kw(str(kw)).search(title):
                raw_score += float(w)
                matched_tags.append(f"+{kw} [заг]")

        for kw, w in pcfg.get("body_boost", []):
            if _compile_kw(str(kw)).search(desc):
                raw_score += float(w)
                matched_tags.append(f"+{kw} [опис]")

        for kw, w in pcfg.get("negative", []):
            if _compile_kw(str(kw)).search(text_all):
                penalty = abs(float(w))
                raw_score -= penalty
                matched_tags.append(f"-{kw} (-{penalty:g})")

        total_p = round(raw_score * p_weight + salary_delta + global_delta, 2)
        if fmt not in allowed and allowed:
            total_p = round(total_p - 2.0, 2)
            matched_tags.append(f"формат {fmt} вне списка (-2)")

        profile_scores[p_code] = total_p
        profile_scores[str(pid)] = total_p

        if total_p > best_score:
            best_score = total_p
            best_id = pid
            best_name = p_name
            best_reasons = matched_tags[:8]

    high_th = float(config.scoring.get("priority_high", 12))
    med_th = float(config.scoring.get("priority_medium", 6))
    if best_score >= high_th:
        priority = "high"
    elif best_score >= med_th:
        priority = "medium"
    else:
        priority = "low"

    full_reasons_str = "; ".join(
        [
            f"профиль: {best_name} ({best_score:g} б.)",
            *reasons,
            *best_reasons,
        ]
    )

    return {
        "scoring_version": config.scoring_version,
        "best_profile_id": best_id,
        "best_profile_name": best_name,
        "recommended_resume": best_name,
        "recommended_resume_title": best_name,
        "best_score": best_score,
        "score": best_score,
        "total_score": best_score,
        "priority": priority,
        "reasons": full_reasons_str,
        "matched_keywords": full_reasons_str,
        "profile_scores": profile_scores,
    }


class VacancyScorer:
    def __init__(self, config: Settings, stopwords: set[str] | None = None) -> None:
        self.config = config
        self.stopwords = stopwords or set()

    def score(self, vacancy: dict[str, Any]) -> dict[str, Any]:
        return score_vacancy(vacancy, self.config, self.stopwords)

    def score_vacancy(self, vacancy: dict[str, Any]) -> dict[str, Any]:
        return score_vacancy(vacancy, self.config, self.stopwords)