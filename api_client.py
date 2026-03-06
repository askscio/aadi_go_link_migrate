from __future__ import annotations

import asyncio
import functools
import logging
import random
import time
from typing import Any, Callable, TypeVar

from glean.api_client import Glean, models
from glean.api_client.errors import GleanError

logger = logging.getLogger(__name__)
F = TypeVar("F", bound=Callable[..., Any])

REQUEST_TIMEOUT_MS = 30_000


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, GleanError):
        code = getattr(exc, "status_code", None)
        if code == 429 or (isinstance(code, int) and 500 <= code < 600):
            return True
    return False


def with_retry(max_retries: int = 5) -> Callable[[F], F]:
    """Decorator: exponential backoff with jitter on 429 / 5xx."""

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(1, max_retries + 2):
                try:
                    return await fn(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if not _is_retryable(exc) or attempt > max_retries:
                        raise
                    base_delay = min(2 ** attempt, 60)
                    jitter = random.uniform(0, base_delay * 0.5)
                    delay = base_delay + jitter
                    logger.warning(
                        "Retryable error (attempt %d/%d): %s -- sleeping %.1fs",
                        attempt,
                        max_retries,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
            raise last_exc  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator


class GleanClient:
    """Thin async wrapper around the Glean Python SDK for shortcut operations."""

    def __init__(self, api_token: str, base_url: str, max_retries: int = 5) -> None:
        self._token = api_token
        self._base_url = base_url
        self._max_retries = max_retries
        self._sdk = Glean(api_token=api_token, server_url=base_url)

    def close(self) -> None:
        self._sdk.__exit__(None, None, None)

    async def list_all_shortcuts(
        self, page_size: int = 100
    ) -> list[models.Shortcut]:
        """Paginate through all shortcuts visible to the authenticated user."""
        all_shortcuts: list[models.Shortcut] = []
        cursor: str | None = None

        while True:
            resp = await self._list_page(page_size=page_size, cursor=cursor)
            all_shortcuts.extend(resp.shortcuts)
            logger.info(
                "Fetched page (%d shortcuts, total so far: %d)",
                len(resp.shortcuts),
                len(all_shortcuts),
            )
            if not resp.meta.has_next_page:
                break
            cursor = resp.meta.cursor

        return all_shortcuts

    @with_retry()
    async def _list_page(
        self,
        page_size: int,
        cursor: str | None = None,
    ) -> models.ListShortcutsPaginatedResponse:
        return await asyncio.to_thread(
            self._sdk.client.shortcuts.list,
            page_size=page_size,
            cursor=cursor,
        )

    @with_retry()
    async def get_shortcut_by_alias(self, alias: str) -> models.Shortcut | None:
        """Return the shortcut for *alias*, or None if not found."""
        try:
            resp = await asyncio.to_thread(
                self._sdk.client.shortcuts.retrieve,
                get_shortcut_request=models.GetShortcutRequest1(alias=alias),
            )
        except GleanError as exc:
            if getattr(exc, "status_code", None) == 400:
                return None
            raise
        if resp is None:
            return None
        return resp.shortcut if resp.shortcut else None

    @with_retry()
    async def create_shortcut(
        self, props: models.ShortcutMutableProperties
    ) -> models.Shortcut | None:
        resp = await asyncio.to_thread(
            self._sdk.client.shortcuts.create,
            data=props,
        )
        return resp.shortcut if resp and resp.shortcut else None

    @with_retry()
    async def update_shortcut(
        self,
        shortcut_id: int,
        *,
        input_alias: str | None = None,
        destination_url: str | None = None,
        description: str | None = None,
        unlisted: bool | None = None,
        url_template: str | None = None,
    ) -> models.Shortcut | None:
        resp = await asyncio.to_thread(
            self._sdk.client.shortcuts.update,
            id=shortcut_id,
            input_alias=input_alias,
            destination_url=destination_url,
            description=description,
            unlisted=unlisted,
            url_template=url_template,
        )
        return resp.shortcut if resp and resp.shortcut else None

    @with_retry()
    async def delete_shortcut(self, shortcut_id: int) -> None:
        await asyncio.to_thread(
            self._sdk.client.shortcuts.delete,
            id=shortcut_id,
        )
