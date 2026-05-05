from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from core.exceptions import PromptCatalogError, PromptNotFoundError


_PLACEHOLDER_PATTERN = re.compile(r"{{\s*(?P<name>[a-zA-Z0-9_]+)\s*}}")


class PromptTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system: str
    user: str


class PromptCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rewrite_article: PromptTemplate
    rewrite_telegram: PromptTemplate

    def template(self, name: str) -> PromptTemplate:
        try:
            return getattr(self, name)
        except AttributeError as exc:
            raise PromptNotFoundError(f"Prompt template '{name}' is not defined.") from exc

    def rewrite_article_prompt(self) -> PromptTemplate:
        return self.rewrite_article

    def rewrite_telegram_prompt(self) -> PromptTemplate:
        return self.rewrite_telegram


def render_template(template: str, **values: str) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group("name")
        return values.get(key, match.group(0))

    return _PLACEHOLDER_PATTERN.sub(replace, template)


@lru_cache(maxsize=4)
def load_prompts(path: str | Path) -> PromptCatalog:
    prompt_path = Path(path).expanduser().resolve()
    if not prompt_path.exists():
        raise PromptCatalogError(f"Prompt catalog file not found: {prompt_path}")

    try:
        raw_data = yaml.safe_load(prompt_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise PromptCatalogError(f"Invalid YAML in prompt catalog: {prompt_path}") from exc

    try:
        return PromptCatalog.model_validate(raw_data)
    except ValidationError as exc:
        raise PromptCatalogError(f"Prompt catalog validation failed for: {prompt_path}") from exc
