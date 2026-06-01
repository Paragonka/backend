import json
from pathlib import Path


class I18n:
    def __init__(self, locales_dir: str = "locales"):
        self._translations: dict[str, dict[str, str]] = {}
        self._locales_dir = Path(locales_dir)
        self._load_all()

    def _load_all(self) -> None:
        for path in sorted(self._locales_dir.glob("*.json")):
            lang = path.stem

            try:
                with open(path) as f:
                    self._translations[lang] = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._translations[lang] = {}

    def gettext(self, key: str, lang: str = "pl") -> str:
        if lang in self._translations and key in self._translations[lang]:
            return self._translations[lang][key]

        return key

    def supported_langs(self) -> list[str]:
        return sorted(self._translations.keys())

    def lang_name(self, lang: str) -> str:
        names = {"ru": "Русский", "en": "English", "pl": "Polski"}

        return names.get(lang, lang)


i18n = I18n()
