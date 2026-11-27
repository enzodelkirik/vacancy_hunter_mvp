from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator


SCORING_VERSION: str = "mvp-5resumes-v2"


class _AttrDict(dict[str, Any]):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'") from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class _ProfilesCollection(dict[int, _AttrDict]):
    def __iter__(self) -> Iterator[_AttrDict]:
        for key in sorted(self.keys()):
            yield self[key]


def _to_attr_dict(data: dict[str, Any]) -> _AttrDict:
    result = _AttrDict()
    for k, v in data.items():
        if isinstance(v, dict):
            result[k] = _to_attr_dict(v)
        else:
            result[k] = v
    return result


DEFAULT_CONFIG: dict[str, Any] = {
    "scoring_version": SCORING_VERSION,
    "search": {
        "area_id": "1",
        "pages": 2,
        "per_page": 50,
        "experience": "",
        "schedule": "",
        "min_salary_net": 200000,
        "min_salary_moscow_mo": 200000,
        "min_salary_regions_rf": 350000,
        "min_salary_cis": 500000,
        "request_delay_min": 1.8,
        "request_delay_max": 3.2,
        "max_retries": 3,
    },
    "scoring": {
        "min_score_to_export": 14,
        "priority_high": 22,
        "priority_medium": 14,
    },
    "paths": {
        "db_path": "data/vacancies_mvp.db",
        "excel_path": "output/vacancies_mvp.xlsx",
        "report_path": "output/report_mvp.md",
        "stopwords_path": "config/stopwords.txt",
    },
    "queries": [
        "спортивный директор",
        "руководитель спортивных проектов",
        "руководитель спортивного объекта",
        "организация спортивных мероприятий",
        "спортивный маркетинг партнерство",
        "работа с федерациями спорт",
        "хоккейный клуб футбольный клуб руководитель",
        "проверка контрагентов безопасность",
        "комплаенс проверка контрагентов",
        "кадровая безопасность экономическая безопасность",
        "развитие партнерской сети",
        "работа с ключевыми клиентами корпоративные",
        "руководитель направления тендеры контракты",
        "операционный руководитель проекты регламенты",
    ],
    "profiles": {
        1: {
            "id": 1,
            "code": "P1_SPORT_PROJ",
            "title": "1. Спорт: проекты, клубы, федерации и мероприятия",
            "name": "1. Спорт: проекты, клубы, федерации и мероприятия",
            "priority_weight": 1.30,
            "allowed_formats": ["офис", "гибрид", "разъездной", "командировки", "вахта", "удаленка", "не указан"],
            "queries": [
                "спортивный директор",
                "руководитель спортивных проектов",
                "организация спортивных мероприятий",
                "работа с федерациями спорт",
                "хоккейный клуб футбольный клуб руководитель",
            ],
            "title_boost": [
                ("спорт", 5.0),
                ("спортивн", 5.0),
                ("хокке", 5.5),
                ("футбол", 5.5),
                ("теннис", 5.0),
                ("федерац", 5.0),
                ("клуб", 4.0),
                ("турнир", 4.0),
                ("мероприят", 3.5),
                ("event", 3.5),
            ],
            "body_boost": [
                ("спортивн.*объект|спортсооружен", 4.0),
                ("федерац.*(фигурн|легк|футбол|хокке|теннис|спорт)", 4.5),
                ("хокке.*клуб|футбол.*клуб|спортивн.*клуб|фк|хк", 4.5),
                ("соревнован|турнир|матч|сбор|чемпионат", 3.5),
                ("мероприят|ивент|event", 2.5),
                ("подрядчик|площадк|арен", 2.0),
                ("командировк|выезд", 2.0),
            ],
            "negative": [
                ("холодн.*звонк", 8.0),
                ("кадров.*делопроизводств|кдп", 7.0),
            ],
        },
        2: {
            "id": 2,
            "code": "P2_SPORT_OBJ",
            "title": "2. Спорт: объекты, партнёрства и спонсорство",
            "name": "2. Спорт: объекты, партнёрства и спонсорство",
            "priority_weight": 1.25,
            "allowed_formats": ["офис", "гибрид", "разъездной", "командировки", "вахта", "удаленка", "не указан"],
            "queries": [
                "руководитель спортивного объекта",
                "спортивный маркетинг партнерство",
                "спонсорство спорт партнерство",
                "управление спортивным комплексом",
            ],
            "title_boost": [
                ("спорт", 4.5),
                ("спортивн", 4.5),
                ("партнер", 4.0),
                ("спонсор", 5.0),
                ("объект", 3.5),
                ("площадк", 3.5),
            ],
            "body_boost": [
                ("спонсор.*|партнер.*спорт|спортивн.*партнер", 5.0),
                ("спортивн.*объект|стадион|дворец спорт|ледов|спорткомплекс", 4.5),
                ("переговор|презентац|коммерческ.*предложен", 3.0),
                ("подрядчик|арендатор", 2.5),
                ("командировк|выезд", 2.0),
            ],
            "negative": [
                ("холодн.*звонк", 8.0),
                ("кадров.*делопроизводств|кдп", 7.0),
            ],
        },
        3: {
            "id": 3,
            "code": "P3_SEC_COMP",
            "title": "3. Проверка контрагентов, экономическая и кадровая безопасность",
            "name": "3. Проверка контрагентов, экономическая и кадровая безопасность",
            "priority_weight": 1.15,
            "allowed_formats": ["офис", "гибрид", "разъездной", "командировки", "вахта", "удаленка", "не указан"],
            "queries": [
                "проверка контрагентов безопасность",
                "комплаенс проверка контрагентов",
                "экономическая безопасность проверка контрагентов",
                "кадровая безопасность экономическая безопасность",
            ],
            "title_boost": [
                ("контрагент", 5.5),
                ("комплаенс", 4.5),
                ("due diligence", 4.5),
                ("экономическ.*безопасн", 4.0),
                ("кадров.*безопасн", 3.5),
                ("риск", 3.5),
            ],
            "body_boost": [
                ("проверк.*контрагент|благонадежност.*контрагент", 5.5),
                ("безопасн.*сдел|экономическ.*безопасн", 4.5),
                ("кадров.*безопасн|проверк.*кандидат|аффилированн", 3.5),
                ("комплаенс|due diligence|фрод|риск.*сдел", 4.5),
                ("контур.*фокус|спарк|инфопрактик|аналитик.*данн", 4.0),
                ("тендер|закупк|регламент", 2.5),
                ("переговор|согласован", 2.0),
            ],
            "negative": [
                ("кадров.*делопроизводств|кдп|воинск.*учет|табел", 10.0),
                ("охрана|пропускн.*режим|физическ.*охрана", 9.0),
                ("холодн.*звонк", 8.0),
            ],
        },
        4: {
            "id": 4,
            "code": "P4_CORP_PART",
            "title": "4. Корпоративные партнёрства, развитие и переговоры",
            "name": "4. Корпоративные партнёрства, развитие и переговоры",
            "priority_weight": 1.15,
            "allowed_formats": ["офис", "гибрид", "разъездной", "командировки", "вахта", "удаленка", "не указан"],
            "queries": [
                "развитие партнерской сети",
                "работа с ключевыми клиентами корпоративные",
                "руководитель направления тендеры контракты",
            ],
            "title_boost": [
                ("партнер", 4.5),
                ("ключев.*клиент|key account|kam", 4.5),
                ("корпоратив", 4.0),
                ("развит", 3.5),
                ("тендер", 3.5),
            ],
            "body_boost": [
                ("развит.*партнер|партнерск.*сет|стратегическ.*партнер", 4.5),
                ("ключев.*клиент|корпоратив.*клиент|b2b", 4.0),
                ("переговор|презентац|коммерческ.*предложен", 3.5),
                ("тендер|контракт|сопровожден.*сдел", 3.0),
                ("командировк|встреч", 2.0),
            ],
            "negative": [
                ("холодн.*звонк|холодн.*поиск|холодн.*баз", 10.0),
                ("план.*звонк|количество.*звонк|телемаркетинг", 8.0),
                ("кадров.*делопроизводств|кдп", 7.0),
            ],
        },
        5: {
            "id": 5,
            "code": "P5_OPS_COORD",
            "title": "5. Операционная координация и проекты (регламенты, SMART, поле)",
            "name": "5. Операционная координация и проекты (регламенты, SMART, поле)",
            "priority_weight": 1.10,
            "allowed_formats": ["офис", "гибрид", "разъездной", "командировки", "вахта", "удаленка", "не указан"],
            "queries": [
                "операционный руководитель проекты регламенты",
                "координатор проектов регламенты kpi",
            ],
            "title_boost": [
                ("операцион", 4.0),
                ("проект", 3.5),
                ("координатор", 3.5),
                ("руководитель", 2.5),
                ("директор", 2.5),
            ],
            "body_boost": [
                ("регламент|процесс|бизнес.*процесс|стандарт", 4.0),
                ("kpi|smart|цел.*показател|бюджет|срок", 3.5),
                ("командировк|вахт|площадк|объект|подрядчик", 3.0),
                ("команд|взаимодейств|согласован", 2.0),
            ],
            "negative": [
                ("холодн.*звонк", 8.0),
                ("кадров.*делопроизводств|кдп", 7.0),
            ],
        },
    },
    "global_title_penalties": [
        ("стажер|стажёр|intern", -8.0),
        ("junior|младш", -4.0),
        ("юрист|адвокат|нотариус", -8.0),
        ("бухгалтер|главн.*бухгалтер|аудитор", -8.0),
        ("кадровик|специалист по кадрам|инспектор ок", -9.0),
        ("оператор call|колл-центр|холодн", -10.0),
    ],
    "global_body_penalties": [
        ("холодн.*звонк|холодн.*продаж|холодн.*баз", -7.0),
        ("кадров.*делопроизводств|ведение кдп", -6.0),
    ],
}


@dataclass
class Settings:
    scoring_version: str
    search: _AttrDict
    scoring: _AttrDict
    paths: _AttrDict
    queries: list[str]
    profiles: _ProfilesCollection
    global_title_penalties: list[tuple[str, float]] = field(default_factory=list)
    global_body_penalties: list[tuple[str, float]] = field(default_factory=list)

    @classmethod
    def load(cls, config_path: str | Path = "config.json") -> Settings:
        return load_settings(config_path)


AppConfig = Settings


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_settings(config_path: str | Path = "config.json") -> Settings:
    global SCORING_VERSION

    raw = dict(DEFAULT_CONFIG)
    path = Path(config_path)
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            raw = _deep_merge(raw, loaded)

    version = str(raw.get("scoring_version", SCORING_VERSION))
    SCORING_VERSION = version

    profiles_raw = raw.get("profiles", {})
    profiles = _ProfilesCollection()
    for k, v in profiles_raw.items():
        pid = int(k)
        p_dict = _to_attr_dict(v) if isinstance(v, dict) else _AttrDict()
        p_dict.setdefault("id", pid)
        p_dict.setdefault("code", f"P{pid}_PROFILE")
        default_label = p_dict.get("name") or f"Профиль {pid}"
        p_dict.setdefault("title", default_label)
        p_dict.setdefault("name", default_label)
        p_dict.setdefault("queries", [])
        profiles[pid] = p_dict

    return Settings(
        scoring_version=version,
        search=_to_attr_dict(dict(raw.get("search", {}))),
        scoring=_to_attr_dict(dict(raw.get("scoring", {}))),
        paths=_to_attr_dict(dict(raw.get("paths", {}))),
        queries=list(raw.get("queries", [])),
        profiles=profiles,
        global_title_penalties=[tuple(x) for x in raw.get("global_title_penalties", [])],
        global_body_penalties=[tuple(x) for x in raw.get("global_body_penalties", [])],
    )


load_config = load_settings