"""DTO base: request and response bodies are frozen pydantic models.

FastAPI validates a request DTO declared as an endpoint parameter and answers every problem at
once as a 422 ``{"detail": [{"type", "loc", "msg", "input"}]}``; the same models generate the
OpenAPI schemas, so the DTO is the single description of a payload.

Request conventions: strings are stripped (``Secret`` keeps a password's spaces), and numbers
and booleans are strict (``StrictInt``, ``StrictFloat``, ``StrictBool``): JSON ``true`` is not
1 and ``"3"`` is not 3. ``Distinct`` rejects repeated list items.

A DTO may override ``check(self) -> list[tuple[str, str]]`` for cross-field rules
(``min <= max``); each ``(field, message)`` it returns becomes a ``value_error`` at that field.
It runs only when every field is valid.
"""

import re
from typing import Annotated, Any, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    StringConstraints,
    ValidationError,
    model_validator,
)
from pydantic_core import InitErrorDetails, PydanticCustomError

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

Email = Annotated[str, StringConstraints(to_lower=True, max_length=254, pattern=EMAIL_PATTERN)]
Secret = Annotated[str, StringConstraints(strip_whitespace=False)]


def _distinct[T](items: list[T]) -> list[T]:
    if len({repr(i) for i in items}) != len(items):
        raise PydanticCustomError("unique_items", "List items should be distinct")
    return items


Distinct = AfterValidator(_distinct)   # list[X] items must be distinct: Annotated[list[X], Distinct]


class DTO(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    def check(self) -> list[tuple[str, str]]:
        """Cross-field rules: ``(field, message)`` for each problem."""
        return []

    @model_validator(mode="after")
    def _run_check(self) -> Self:
        problems = self.check()
        if problems:
            raise ValidationError.from_exception_data(type(self).__name__, [
                InitErrorDetails(type=PydanticCustomError("value_error", msg), loc=(name,),
                                 input=_shown(getattr(self, name)))
                for name, msg in problems
            ])
        return self


def _shown(value: Any) -> Any:
    return value if isinstance(value, (str, int, float, bool)) or value is None else None
