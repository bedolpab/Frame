from typing import TypeVar

_T = TypeVar("_T")

class error(Exception): ...

def python_method(function: _T) -> _T: ...
