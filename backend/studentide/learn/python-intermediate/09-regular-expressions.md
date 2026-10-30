---
title: Regular expressions
summary: Describe a text pattern once and use re to find, check, take apart or replace it.
---
A **regular expression** (regex) is a small pattern language for text. Python's `re` module uses it. Write patterns as raw strings, `r"..."`, so backslashes stay as they are.

The building blocks:

- `\d` a digit, `\w` a letter, digit or `_`, `\s` a space or tab, `.` any character.
- `[A-Z]` one character from a set, `[^0-9]` one character *not* in it.
- `+` one or more, `*` zero or more, `?` optional, `{2}` exactly two, `{2,4}` two to four.
- `^` start of the text, `$` end, `( )` a group you can read back, `|` or.

```python
import re

text = "Call 98765-43210 or 91234-56789 before 5pm."
print(re.findall(r"\d{5}-\d{5}", text))        # every match, as a list
m = re.search(r"(\d+)pm", text)                 # the first match, or None
if m:
    print("hour:", m.group(1))
print(re.sub(r"\d", "#", "pin 4821"))           # replace every match
print(re.split(r"[,;]\s*", "a, b;c ,d"))
```

To check that a **whole** string fits a pattern, use `re.fullmatch` (or anchor the pattern with `^...$`); `re.search` is happy with a match anywhere inside.

```python
import re

for code in ["PG25CS07", "pg25cs07", "PG25CS7", "UG24EE12"]:
    ok = re.fullmatch(r"(PG|UG)(\d{2})([A-Z]{2})(\d{2})", code)
    if ok:
        print(code, "->", ok.groups())
    else:
        print(code, "is not a roll number")
```

Regexes are powerful but get unreadable fast. For simple jobs, string methods like `split`, `startswith` and `isdigit` are clearer.

Things to try:

1. Change `\d{5}-\d{5}` to `\d+`. What does `findall` return now?
2. Add the `re.IGNORECASE` flag to the roll-number check.
3. Use `re.sub` to turn `2026-10-30` into `30/10/2026` with groups (`\3/\2/\1` in the replacement).

## Exercise

Each input line may contain an email address. For every line, print the first email address found in it, or `none`. For this exercise an email is: one or more letters, digits, dots, underscores or hyphens, then `@`, then one or more letters, digits or hyphens, then one or more groups of a dot followed by letters.

```input
write to asha.k@iiitsurat.ac.in today
no address here
ravi_2@mail.com, dev@x.org
```

```python starter
import sys

for line in sys.stdin:
    print("none")
```

```python solution
import re
import sys

EMAIL = re.compile(r"[\w.-]+@[A-Za-z0-9-]+(?:\.[A-Za-z]+)+")

for line in sys.stdin:
    m = EMAIL.search(line)
    print(m.group(0) if m else "none")
```

```tests
{"name": "example", "stdin": "write to asha.k@iiitsurat.ac.in today\nno address here\nravi_2@mail.com, dev@x.org\n", "expected": "asha.k@iiitsurat.ac.in\nnone\nravi_2@mail.com"}
{"name": "at sign only", "stdin": "meet @ 5\n", "expected": "none"}
{"name": "no dot", "stdin": "root@localhost\n", "expected": "none", "hidden": true}
```
