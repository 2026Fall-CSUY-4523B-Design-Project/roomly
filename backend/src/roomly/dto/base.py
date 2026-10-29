"""DTO base: request/response objects are frozen dataclasses; this module validates JSON into them.

fastapi-reborn binds no JSON bodies (there is no pydantic), so controllers call
``parse(SomeRequest, await request.json())``. Constraints live in field metadata through
``rule(...)``. Every problem is collected and raised as one 422 in the same pydantic-style
shape fastapi-reborn uses for query errors: ``{"type", "loc", "msg", "input"}``.

A DTO may define ``check(self) -> list[tuple[str, str]]`` for cross-field rules (``min <= max``);
each ``(field, message)`` it returns becomes a ``value_error`` at that field.

``schema_of`` turns the same dataclasses into JSON Schema for the OpenAPI document, so the
DTO is the single description of a payload.
"""

import datetime as dt
import math
import re
import types
import typing
import uuid
from dataclasses import MISSING, Field, dataclass, field, fields, is_dataclass
from typing import Any, Literal, get_args, get_origin

from fastapi_reborn.params import RequestValidationError

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class Rule:
    min_len: int | None = None
    max_len: int | None = None
    ge: float | None = None
    le: float | None = None
    pattern: re.Pattern[str] | None = None
    min_items: int | None = None
    max_items: int | None = None
    unique: bool = False     # list items must be distinct
    lower: bool = False      # lowercase the (stripped) string, e.g. emails
    strip: bool = True       # False for secrets: a password keeps its spaces


def rule(*, default: Any = MISSING, default_factory: Any = MISSING, **constraints: Any) -> Any:
    """``name: str = rule(min_len=1, max_len=80)``: a dataclass field carrying validation rules."""
    meta = {"rule": Rule(**constraints)}
    if default_factory is not MISSING:
        return field(default_factory=default_factory, metadata=meta)
    return field(default=default, metadata=meta)


_NO_RULE = Rule()


def _rule_of(f: Field[Any]) -> Rule:
    return f.metadata.get("rule", _NO_RULE)


def parse[T](cls: type[T], data: Any, *, loc: tuple[str, ...] = ("body",)) -> T:
    """Validate ``data`` (decoded JSON) into ``cls`` or raise a 422 listing every error."""
    errors: list[dict[str, Any]] = []
    value = _parse_dataclass(cls, data, list(loc), errors)
    if errors:
        raise RequestValidationError(errors)
    return value


def _error(errors: list[dict[str, Any]], kind: str, loc: list[Any], msg: str, value: Any) -> None:
    shown = value if isinstance(value, (str, int, float, bool)) or value is None else None
    errors.append({"type": kind, "loc": loc, "msg": msg, "input": shown})


def _parse_dataclass(cls: Any, data: Any, loc: list[Any], errors: list[dict[str, Any]]) -> Any:
    if not isinstance(data, dict):
        _error(errors, "dict_type", loc, "Input should be a valid dictionary or object", data)
        return None
    hints = typing.get_type_hints(cls)
    kwargs: dict[str, Any] = {}
    before = len(errors)
    for f in fields(cls):
        if not f.init:
            continue
        where = [*loc, f.name]
        if f.name in data:
            kwargs[f.name] = _coerce(hints[f.name], data[f.name], where, errors, _rule_of(f))
        elif f.default is not MISSING:
            kwargs[f.name] = f.default
        elif f.default_factory is not MISSING:
            kwargs[f.name] = f.default_factory()
        else:
            _error(errors, "missing", where, "Field required", None)
    if len(errors) != before:
        return None
    value = cls(**kwargs)
    check = getattr(value, "check", None)
    if check is not None:
        for name, msg in check():
            _error(errors, "value_error", [*loc, name], msg, None)
    return value


def _optional_inner(tp: Any) -> Any | None:
    """``X | None`` -> X; anything else -> None."""
    if get_origin(tp) in (typing.Union, types.UnionType):
        args = [a for a in get_args(tp) if a is not type(None)]
        if len(args) == 1 and len(get_args(tp)) == 2:
            return args[0]
    return None


def _coerce(tp: Any, value: Any, loc: list[Any], errors: list[dict[str, Any]], r: Rule) -> Any:
    inner = _optional_inner(tp)
    if inner is not None:
        return None if value is None else _coerce(inner, value, loc, errors, r)
    if value is None:
        _error(errors, "none_forbidden", loc, "Input should not be null", None)
        return None
    origin = get_origin(tp)
    if origin is Literal:
        allowed = get_args(tp)
        if value in allowed and type(value) is type(allowed[0]):
            return value
        _error(errors, "literal_error", loc, "Input should be " + " or ".join(repr(a) for a in allowed), value)
        return None
    if is_dataclass(tp):
        return _parse_dataclass(tp, value, loc, errors)
    if origin is list:
        return _coerce_list(get_args(tp)[0], value, loc, errors, r)
    if origin is dict:
        if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
            _error(errors, "dict_type", loc, "Input should be a valid dictionary or object", value)
            return None
        value_type = get_args(tp)[1]
        return {k: _coerce(value_type, v, [*loc, k], errors, _NO_RULE) for k, v in value.items()}
    if tp is Any:
        return value
    if tp is str:
        return _coerce_str(value, loc, errors, r)
    if tp is bool:
        if isinstance(value, bool):
            return value
        _error(errors, "bool_type", loc, "Input should be a valid boolean", value)
        return None
    if tp in (int, float):
        return _coerce_number(tp, value, loc, errors, r)
    if tp in (uuid.UUID, dt.date, dt.datetime, dt.time):
        return _coerce_text_type(tp, value, loc, errors)
    raise TypeError(f"unsupported DTO field type {tp!r}")


def _coerce_list(item_type: Any, value: Any, loc: list[Any], errors: list[dict[str, Any]], r: Rule) -> Any:
    if not isinstance(value, list):
        _error(errors, "list_type", loc, "Input should be a valid list", value)
        return None
    items = [_coerce(item_type, v, [*loc, i], errors, _NO_RULE) for i, v in enumerate(value)]
    if r.min_items is not None and len(items) < r.min_items:
        _error(errors, "too_short", loc, f"List should have at least {r.min_items} items", None)
    if r.max_items is not None and len(items) > r.max_items:
        _error(errors, "too_long", loc, f"List should have at most {r.max_items} items", None)
    if r.unique and len({repr(i) for i in items}) != len(items):
        _error(errors, "unique_items", loc, "List items should be distinct", None)
    return items


def _coerce_str(value: Any, loc: list[Any], errors: list[dict[str, Any]], r: Rule) -> Any:
    if not isinstance(value, str):
        _error(errors, "string_type", loc, "Input should be a valid string", value)
        return None
    text = value.strip() if r.strip else value
    if r.lower:
        text = text.lower()
    if r.min_len is not None and len(text) < r.min_len:
        _error(errors, "string_too_short", loc, f"String should have at least {r.min_len} characters", value)
    elif r.max_len is not None and len(text) > r.max_len:
        _error(errors, "string_too_long", loc, f"String should have at most {r.max_len} characters", None)
    elif r.pattern is not None and not r.pattern.fullmatch(text):
        _error(errors, "string_pattern_mismatch", loc, "String has an invalid format", value)
    return text


def _coerce_number(tp: type, value: Any, loc: list[Any], errors: list[dict[str, Any]], r: Rule) -> Any:
    ok = isinstance(value, int) and not isinstance(value, bool)
    if tp is float:
        ok = ok or (isinstance(value, float) and math.isfinite(value))
    if not ok:
        kind = "int_type" if tp is int else "float_type"
        _error(errors, kind, loc, f"Input should be a valid {'integer' if tp is int else 'number'}", value)
        return None
    if r.ge is not None and value < r.ge:
        _error(errors, "greater_than_equal", loc, f"Input should be greater than or equal to {r.ge:g}", value)
    elif r.le is not None and value > r.le:
        _error(errors, "less_than_equal", loc, f"Input should be less than or equal to {r.le:g}", value)
    return tp(value)


_TEXT_TYPES: dict[Any, tuple[str, str, Any]] = {
    uuid.UUID: ("uuid_parsing", "Input should be a valid UUID", uuid.UUID),
    dt.date: ("date_parsing", "Input should be a valid date (YYYY-MM-DD)", dt.date.fromisoformat),
    dt.datetime: ("datetime_parsing", "Input should be a valid ISO 8601 datetime", dt.datetime.fromisoformat),
    dt.time: ("time_parsing", "Input should be a valid time (HH:MM)", dt.time.fromisoformat),
}


def _coerce_text_type(tp: Any, value: Any, loc: list[Any], errors: list[dict[str, Any]]) -> Any:
    kind, msg, convert = _TEXT_TYPES[tp]
    if isinstance(value, str):
        try:
            return convert(value)
        except ValueError:
            pass
    _error(errors, kind, loc, msg, value)
    return None


# --- JSON Schema for OpenAPI -----------------------------------------------------------

_FORMATS = {uuid.UUID: "uuid", dt.date: "date", dt.datetime: "date-time", dt.time: "time"}


def schema_of(tp: Any, r: Rule = _NO_RULE) -> dict[str, Any]:
    """JSON Schema for a DTO type (dataclass, list, scalar, Literal, ``X | None``)."""
    inner = _optional_inner(tp)
    if inner is not None:
        return {"anyOf": [schema_of(inner, r), {"type": "null"}]}
    origin = get_origin(tp)
    if origin is Literal:
        return {"enum": list(get_args(tp))}
    if is_dataclass(origin) or (origin is None and is_dataclass(tp)):
        return _dataclass_schema(tp, origin)
    if origin is list:
        s: dict[str, Any] = {"type": "array", "items": schema_of(get_args(tp)[0])}
        if r.min_items is not None:
            s["minItems"] = r.min_items
        if r.max_items is not None:
            s["maxItems"] = r.max_items
        return s
    if origin is dict:
        return {"type": "object", "additionalProperties": schema_of(get_args(tp)[1])}
    if tp is Any:
        return {}
    if tp in _FORMATS:
        return {"type": "string", "format": _FORMATS[tp]}
    scalar = {str: "string", bool: "boolean", int: "integer", float: "number"}[tp]
    s = {"type": scalar}
    for key, attr in (("minLength", "min_len"), ("maxLength", "max_len"), ("minimum", "ge"), ("maximum", "le")):
        if getattr(r, attr) is not None:
            s[key] = getattr(r, attr)
    return s


def _dataclass_schema(tp: Any, origin: Any) -> dict[str, Any]:
    cls = origin or tp
    hints = typing.get_type_hints(cls)
    if origin is not None:  # Page[ListingSummary]: substitute the type parameters
        sub = dict(zip(cls.__type_params__, get_args(tp)))
        for name, hint in hints.items():
            if hint in sub:
                hints[name] = sub[hint]
            elif getattr(hint, "__parameters__", ()):
                hints[name] = hint[tuple(sub[p] for p in hint.__parameters__)]
    props = {f.name: schema_of(hints[f.name], _rule_of(f)) for f in fields(cls)}
    required = [f.name for f in fields(cls) if f.default is MISSING and f.default_factory is MISSING]
    title = cls.__name__ + "".join(getattr(a, "__name__", "") for a in get_args(tp))
    out: dict[str, Any] = {"type": "object", "title": title, "properties": props}
    if cls.__doc__ and not cls.__doc__.startswith(cls.__name__ + "("):
        out["description"] = cls.__doc__.strip()
    if required:
        out["required"] = required
    return out


def body(cls: Any) -> dict[str, Any]:
    """OpenAPI ``requestBody`` for a JSON DTO (pass as ``request_body=`` on a route)."""
    return {"required": True, "content": {"application/json": {"schema": schema_of(cls)}}}


def returns(tp: Any, status: int = 200) -> dict[int, dict[str, Any]]:
    """OpenAPI ``responses`` entry for a DTO (pass as ``responses=`` on a route)."""
    return {status: {"description": "Successful Response", "content": {"application/json": {"schema": schema_of(tp)}}}}
