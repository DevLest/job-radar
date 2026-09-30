from __future__ import annotations

from dataclasses import dataclass, field

from ...lib.key_value_store import KeyValueStore
from ...shared.utils.dict_utils import get_path, set_path
from .preference_fields import PREFS, SHOW_IF, all_fields
from .preference_form_codec import from_form, to_form
from .profile_repository import ProfileRepository

SAVED_FLAG = "prefs_saved"


@dataclass
class PrefField:
    path: str
    label: str
    kind: str
    options: list | None
    help: str
    value: object
    show_if: str = ""


@dataclass
class PrefSection:
    title: str
    desc: str
    fields: list[PrefField]
    layout: str = ""
    grid: bool = False
    collapsed: bool = False
    collapsed_note: str = ""


@dataclass
class PrefTab:
    key: str
    label: str
    icon: str
    sections: list[PrefSection] = field(default_factory=list)


class PreferencesError(ValueError):
    def __init__(self, message: str, tab: str):
        super().__init__(message)
        self.tab = tab


def _collapsed_note(fields: list[PrefField]) -> str:
    switches = [f for f in fields if f.kind == "switch"]
    switched_on = sum(1 for f in switches if f.value)
    if len(switches) > 1:
        return f"({switched_on} of {len(switches)} on)"
    if switches:
        return "(on)" if switched_on else "(off)"
    return "(optional)"


class PreferencesService:
    def __init__(self, profiles: ProfileRepository, meta: KeyValueStore):
        self.profiles, self.meta = profiles, meta

    def form_values(self) -> dict:
        profile = self.profiles.load()
        return {path: to_form(get_path(profile, path), kind) for path, _, kind, *_ in all_fields()}

    def tabs(self) -> list[PrefTab]:
        values = self.form_values()
        tabs = []
        for key, label, icon, sections in PREFS:
            tab = PrefTab(key, label, icon)
            for spec in sections:
                fields = [PrefField(path, flabel, kind, options, help_text, values[path], SHOW_IF.get(path, ""))
                          for path, flabel, kind, options, help_text in spec["fields"]]
                section = PrefSection(spec["title"], spec["desc"], fields, spec.get("layout", ""),
                                      spec.get("grid", False), spec.get("collapsed", False))
                if section.collapsed:
                    section.collapsed_note = _collapsed_note(fields)
                tab.sections.append(section)
            tabs.append(tab)
        return tabs

    def save(self, form, tab: str):
        """Raises PreferencesError (with the tab to show) when the form is invalid."""
        profile = self.profiles.load()
        try:
            for path, _, kind, *_ in all_fields():
                set_path(profile, path, from_form(form, path, kind))
        except ValueError as e:
            raise PreferencesError(str(e), tab) from e
        if not profile["work_setup"].get("work_types"):
            raise PreferencesError("Pick at least one way of working (remote, hybrid or on-site)", "work")
        self.profiles.save(profile)
        self.meta.set(SAVED_FLAG, "1")

    def were_saved(self) -> bool:
        return self.meta.get(SAVED_FLAG) == "1"
