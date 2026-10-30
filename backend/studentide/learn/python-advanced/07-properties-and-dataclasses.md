---
title: Properties, class methods and dataclasses
summary: Attributes with checks behind them, methods on the class itself, and classes that write their own boilerplate.
---
A **property** looks like a plain attribute from outside, but runs a method when it is read or set. Use it to compute a value on the fly or to check values before storing them, without changing how callers use the class.

```python
class Temperature:
    def __init__(self, celsius):
        self.celsius = celsius          # goes through the setter below

    @property
    def celsius(self):
        return self._celsius

    @celsius.setter
    def celsius(self, value):
        if value < -273.15:
            raise ValueError("below absolute zero")
        self._celsius = value

    @property
    def fahrenheit(self):               # read-only: computed each time
        return self._celsius * 9 / 5 + 32

t = Temperature(25)
print(t.fahrenheit)
t.celsius = 100
print(t.fahrenheit)
```

A **class method** (`@classmethod`) gets the class as its first argument (`cls`) instead of an object. It is often used as another way to create objects. A **static method** (`@staticmethod`) gets neither; it is just a function that lives in the class because it belongs there.

```python
class Date:
    def __init__(self, day, month, year):
        self.day, self.month, self.year = day, month, year

    @classmethod
    def from_text(cls, text):           # "30-10-2026" -> Date
        d, m, y = map(int, text.split("-"))
        return cls(d, m, y)

    @staticmethod
    def is_leap(year):
        return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

d = Date.from_text("29-02-2024")
print(d.year, Date.is_leap(d.year))
```

A **dataclass** writes `__init__`, `__repr__` and `__eq__` for you from the fields you list. `order=True` adds `<`, `>` and friends (comparing field by field), and `frozen=True` makes objects read-only.

```python
from dataclasses import dataclass, field

@dataclass(order=True)
class Student:
    marks: int
    name: str
    subjects: list = field(default_factory=list)   # a fresh list for each object

a = Student(81, "Asha")
b = Student(72, "Ravi", ["maths"])
print(a, a == Student(81, "Asha"), sorted([a, b])[0].name)
```

Things to try:

1. Set `t.celsius = -300`. Then try `t.fahrenheit = 50`.
2. Add `frozen=True` to the dataclass and change `a.marks`.
3. Make a subclass of `Date` and call `from_text` on it. What type do you get back, and why does `cls` matter?

## Exercise

Write a dataclass `Item` with fields `name` (str), `price` (float) and `qty` (int), and a read-only property `total` (price times qty). Add a class method `from_line` that builds an `Item` from a line like `pen 9.5 3`. The given code reads items, sorts them by total (largest first) and prints them.

```input
3
pen 9.5 3
book 120 1
eraser 5 4
```

```python starter
class Item:
    pass

n = int(input())
items = [Item.from_line(input()) for _ in range(n)]
for it in sorted(items, key=lambda i: i.total, reverse=True):
    print(f"{it.name} {it.total:.2f}")
```

```python solution
from dataclasses import dataclass


@dataclass
class Item:
    name: str
    price: float
    qty: int

    @property
    def total(self):
        return self.price * self.qty

    @classmethod
    def from_line(cls, line):
        name, price, qty = line.split()
        return cls(name, float(price), int(qty))


n = int(input())
items = [Item.from_line(input()) for _ in range(n)]
for it in sorted(items, key=lambda i: i.total, reverse=True):
    print(f"{it.name} {it.total:.2f}")
```

```tests
{"name": "example", "stdin": "3\npen 9.5 3\nbook 120 1\neraser 5 4\n", "expected": "book 120.00\npen 28.50\neraser 20.00"}
{"name": "one", "stdin": "1\ncap 2.25 2\n", "expected": "cap 4.50"}
{"name": "zero qty", "stdin": "2\na 10 0\nb 1 1\n", "expected": "b 1.00\na 0.00", "hidden": true}
```
