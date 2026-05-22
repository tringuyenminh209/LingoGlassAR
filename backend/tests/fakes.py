from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


class FakeRedis:
    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.sets: dict[str, set[str]] = {}
        self.expires: dict[str, int] = {}
        self.hset_calls: list[tuple[str, dict[str, str]]] = []
        self.hincrby_calls: list[tuple[str, str, int]] = []
        self.hincrbyfloat_calls: list[tuple[str, str, float]] = []
        self.expire_calls: list[tuple[str, int]] = []
        self.hgetall_calls: list[str] = []
        self.pipeline_calls: list[list[tuple[str, tuple[Any, ...]]]] = []

    async def hset(
        self,
        name: str,
        key: str | None = None,
        value: str | None = None,
        mapping: dict[str, str] | None = None,
    ) -> int:
        fields = dict(mapping or {})
        if key is not None and value is not None:
            fields[key] = value
        self.hashes.setdefault(name, {}).update(fields)
        self.hset_calls.append((name, fields))
        return len(fields)

    async def hincrby(self, name: str, key: str, amount: int) -> int:
        fields = self.hashes.setdefault(name, {})
        value = int(fields.get(key, "0")) + amount
        fields[key] = str(value)
        self.hincrby_calls.append((name, key, amount))
        return value

    async def hincrbyfloat(self, name: str, key: str, amount: float) -> float:
        fields = self.hashes.setdefault(name, {})
        value = float(fields.get(key, "0")) + amount
        fields[key] = str(value)
        self.hincrbyfloat_calls.append((name, key, amount))
        return value

    async def sadd(self, name: str, value: str) -> int:
        members = self.sets.setdefault(name, set())
        if value in members:
            return 0
        members.add(value)
        return 1

    async def expire(self, name: str, time: int) -> bool:
        self.expires[name] = time
        self.expire_calls.append((name, time))
        return True

    async def hgetall(self, name: str) -> dict[str, str]:
        self.hgetall_calls.append(name)
        return self.hashes.get(name, {})

    def pipeline(self) -> "FakePipeline":
        return FakePipeline(self)


class FakePipeline:
    def __init__(self, redis: FakeRedis) -> None:
        self.redis = redis
        self.commands: list[tuple[str, tuple[Any, ...]]] = []

    def hset(self, name: str, key: str, value: str) -> "FakePipeline":
        self.commands.append(("hset", (name, key, value)))
        return self

    def hincrby(self, name: str, key: str, amount: int) -> "FakePipeline":
        self.commands.append(("hincrby", (name, key, amount)))
        return self

    def hincrbyfloat(self, name: str, key: str, amount: float) -> "FakePipeline":
        self.commands.append(("hincrbyfloat", (name, key, amount)))
        return self

    def sadd(self, name: str, value: str) -> "FakePipeline":
        self.commands.append(("sadd", (name, value)))
        return self

    def expire(self, name: str, time: int) -> "FakePipeline":
        self.commands.append(("expire", (name, time)))
        return self

    async def execute(self) -> list[object]:
        self.redis.pipeline_calls.append(list(self.commands))
        results = []
        for name, args in self.commands:
            command = getattr(self.redis, name)
            results.append(await _call(command, *args))
        return results


async def _call(command: Callable[..., Awaitable[object]], *args: object) -> object:
    return await command(*args)
