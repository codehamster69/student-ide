---
title: Files and with
summary: Write and read text files safely with a with-block.
---
`open` gives you a file object. Use it in a **`with` block**: the file is closed automatically when the block ends, even if an error happens inside.

```python
with open("notes.txt", "w") as f:        # "w" write, "a" append, "r" read
    f.write("first line\n")
    f.write("second line\n")
    print("third line", file=f)          # print can write to a file too

with open("notes.txt") as f:             # reading is the default
    for i, line in enumerate(f, start=1):
        print(i, line.rstrip("\n"))

with open("notes.txt") as f:
    text = f.read()                      # the whole file as one string
print(len(text.splitlines()), "lines")
```

- Looping over a file gives one line at a time, each ending in `"\n"`, so `rstrip("\n")` or `strip()` it.
- Opening a missing file for reading raises `FileNotFoundError`.
- The `csv` and `json` modules read and write those formats for you.

Each run here gets a fresh folder, so files don't survive between runs.

Things to try:

1. Append a line with mode `"a"` and read the file again.
2. Open `"missing.txt"` and catch the `FileNotFoundError`.
3. Write a list of dictionaries with `json.dump` and read it back with `json.load`.

## Exercise

The input is CSV text: a header line `name,subject,marks` and then one row per line. Write it to a file `marks.csv` exactly as given, close it, then read the file back with the `csv` module and print each subject with its average mark (one decimal), subjects in alphabetical order, as `subject average`.

```input
name,subject,marks
asha,maths,90
ravi,maths,70
asha,physics,85
neel,physics,80
```

```python starter
import csv
import sys

data = sys.stdin.read()
```

```python solution
import csv
import sys

data = sys.stdin.read()
with open("marks.csv", "w", newline="") as f:
    f.write(data)

totals = {}
with open("marks.csv", newline="") as f:
    for row in csv.DictReader(f):
        totals.setdefault(row["subject"], []).append(float(row["marks"]))
for subject in sorted(totals):
    m = totals[subject]
    print(subject, f"{sum(m) / len(m):.1f}")
```

```tests
{"name": "two subjects", "stdin": "name,subject,marks\nasha,maths,90\nravi,maths,70\nasha,physics,85\nneel,physics,80\n", "expected": "maths 80.0\nphysics 82.5"}
{"name": "one row", "stdin": "name,subject,marks\nzoya,c,77\n", "expected": "c 77.0", "hidden": true}
```
