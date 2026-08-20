"""Large utility module.

Intentionally substantial to give EVOSIA a "large/complex area" structural
finding and a context question during M8. All logic is trivial and self-contained.
"""

from .config import DATABASE_URL, DEBUG


def health_check() -> dict:
    return {
        "status": "ok",
        "debug": DEBUG,
        "database": DATABASE_URL,
    }


def whoami() -> str:
    # The API key is never returned to callers in a real service.
    return "sample_service"


def add(a, b):
    return a + b


def subtract(a, b):
    return a - b


def multiply(a, b):
    return a * b


def divide(a, b):
    if b == 0:
        raise ZeroDivisionError("division by zero")
    return a / b


def power(a, b):
    return a ** b


def modulus(a, b):
    return a % b


def floor_divide(a, b):
    return a // b


def absolute(value):
    return abs(value)


def negate(value):
    return -value


def clamp(value, low, high):
    return max(low, min(high, value))


def round_half_up(value, digits=0):
    factor = 10 ** digits
    return int(value * factor + 0.5) / factor


def mean(values):
    if not values:
        return 0.0
    return sum(values) / len(values)


def median(values):
    if not values:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def max_value(values):
    return max(values) if values else 0


def min_value(values):
    return min(values) if values else 0


def range_of(values):
    if not values:
        return 0
    return max(values) - min(values)


def is_even(value):
    return value % 2 == 0


def is_odd(value):
    return value % 2 != 0


def factorial(value):
    result = 1
    for i in range(2, int(value) + 1):
        result *= i
    return result


def fibonacci(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def gcd(a, b):
    while b:
        a, b = b, a % b
    return a


def lcm(a, b):
    return abs(a * b) // gcd(a, b) if a and b else 0


def is_prime(value):
    if value < 2:
        return False
    for i in range(2, int(value ** 0.5) + 1):
        if value % i == 0:
            return False
    return True


def primes_up_to(limit):
    return [n for n in range(2, limit + 1) if is_prime(n)]


def sum_of_squares(values):
    return sum(v * v for v in values)


def product(values):
    result = 1
    for v in values:
        result *= v
    return result


def reverse_list(values):
    return list(reversed(values))


def unique(values):
    seen = []
    for v in values:
        if v not in seen:
            seen.append(v)
    return seen


def flatten(nested):
    result = []
    for item in nested:
        if isinstance(item, (list, tuple)):
            result.extend(flatten(item))
        else:
            result.append(item)
    return result


def chunk(values, size):
    return [values[i:i + size] for i in range(0, len(values), size)]


def group_by_key(items, key_fn):
    groups = {}
    for item in items:
        k = key_fn(item)
        groups.setdefault(k, []).append(item)
    return groups


def count_occurrences(values):
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    return counts


def zip_maps(a, b):
    return {k: (a.get(k), b.get(k)) for k in set(a) | set(b)}


def safe_get(mapping, key, default=None):
    return mapping.get(key, default)


def coalesce(*values):
    for v in values:
        if v is not None:
            return v
    return None
