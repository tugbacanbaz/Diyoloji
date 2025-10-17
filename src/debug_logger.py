import sys
from functools import wraps
from typing import Any, Callable

def debug_log(prefix: str = "") -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            print(f"\n=== {prefix} Debug Start ===", file=sys.stderr)
            try:
                print(f"Function: {func.__name__}", file=sys.stderr)
                print(f"Args: {args}", file=sys.stderr)
                print(f"Kwargs: {kwargs}", file=sys.stderr)
                result = func(*args, **kwargs)
                print(f"Success: {func.__name__} completed", file=sys.stderr)
                return result
            except Exception as e:
                print(f"Error in {func.__name__}: {str(e)}", file=sys.stderr)
                raise
            finally:
                print(f"=== {prefix} Debug End ===\n", file=sys.stderr)
        return wrapper
    return decorator