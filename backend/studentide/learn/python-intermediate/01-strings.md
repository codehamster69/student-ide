---
title: Working with strings
summary: Indexing, slicing, and the string methods you will use every day.
---
A string is a sequence of characters, so it can be indexed and sliced like a list. Strings are **immutable**: methods return a *new* string and leave the old one alone.

```python
s = "  Student IDE  "
t = s.strip()                 # "Student IDE"
print(t.lower(), t.upper(), len(t))
print(t[0], t[-1], t[0:7], t[::-1])
print(t.split())              # ['Student', 'IDE']
print("-".join(["a", "b", "c"]))
print(t.replace("IDE", "lab"), t.find("IDE"), "IDE" in t)
print(t.startswith("Stu"), "42".isdigit(), "abc".isalpha())
print(f"{'left':<8}|{'right':>8}|{3.14159:.2f}")
```

- `split()` with no argument splits on any run of spaces; `split(",")` splits on commas.
- `" ".join(words)` is the reverse of `split`.
- `s[a:b]` runs from index `a` up to but not including `b`; `s[::-1]` is reversed.

Things to try:

1. Count how often each vowel appears with `s.count("a")` and friends.
2. Try `t[0] = "s"`. Why does Python refuse?
3. Print a word centred in 20 characters with `f"{word:^20}"`.

## Exercise

Read a sentence and print it in "title case" with these rules: every word gets a capital first letter and the rest lower case, except the small words `a`, `an`, `the`, `of`, `and`, `in`, which stay lower case unless they are the first word. Words are separated by single spaces.

```input
the lord OF the rings
```

```python starter
words = input().split()
```

```python solution
SMALL = {"a", "an", "the", "of", "and", "in"}
words = input().split()
out = []
for i, w in enumerate(words):
    w = w.lower()
    out.append(w if i > 0 and w in SMALL else w.capitalize())
print(" ".join(out))
```

```tests
{"name": "lord of the rings", "stdin": "the lord OF the rings\n", "expected": "The Lord of the Rings"}
{"name": "one word", "stdin": "python\n", "expected": "Python"}
{"name": "small first", "stdin": "a tale of two cities\n", "expected": "A Tale of Two Cities", "hidden": true}
```
