---
title: Files
summary: fopen, fprintf, fscanf and fclose.
---
A program can write data to a **file** and read it back later. You open a file with `fopen`, which returns a `FILE *` (or `NULL` if it fails), use it with the `f` versions of the functions you know, and close it with `fclose`.

```c
#include <stdio.h>

int main(void) {
    FILE *out = fopen("scores.txt", "w");      /* "w": write, replacing the file */
    if (out == NULL) {
        perror("scores.txt");                  /* prints why it failed */
        return 1;
    }
    fprintf(out, "asha 95\nravi 80\nneel 88\n");
    fclose(out);

    FILE *in = fopen("scores.txt", "r");       /* "r": read */
    char name[32];
    int score, total = 0;
    while (fscanf(in, "%31s %d", name, &score) == 2) {
        printf("read %s %d\n", name, score);
        total += score;
    }
    fclose(in);
    printf("total %d\n", total);
    return 0;
}
```

- Modes: `"r"` read, `"w"` write (empties the file first), `"a"` append to the end.
- `fscanf` returns how many values it read. Looping `while (... == 2)` stops cleanly at the end of the file.
- `fgets(buf, size, file)` reads a line; `fputs` writes a string.
- `stdin`, `stdout` and `stderr` are `FILE *`s too: `fprintf(stderr, "oops\n")` prints an error message separately from normal output.
- Always `fclose` what you open: written data may sit in a buffer until then.

Each run here gets a fresh folder, so files don't survive between runs.

Things to try:

1. Open the file with `"a"` instead of `"w"` and write twice. What is in it?
2. Try to open a file that doesn't exist for reading and look at what `perror` prints.
3. Count the lines of the file with `fgets`.

## Exercise

Read `n` and then `n` whole numbers from the input. Write the even ones to a file `evens.txt`, one per line, and close it. Then open `evens.txt` again, read it back, and print how many numbers it holds and their sum, as `count sum`.

```input
6
3 8 5 12 7 2
```

```c starter
#include <stdio.h>

int main(void) {
    int n;
    scanf("%d", &n);
    FILE *f = fopen("evens.txt", "w");
    /* write the even numbers to f, close it, then read the file back */
    return 0;
}
```

```c solution
#include <stdio.h>

int main(void) {
    int n, x;
    scanf("%d", &n);
    FILE *f = fopen("evens.txt", "w");
    if (f == NULL) {
        return 1;
    }
    for (int i = 0; i < n; i++) {
        scanf("%d", &x);
        if (x % 2 == 0) {
            fprintf(f, "%d\n", x);
        }
    }
    fclose(f);
    f = fopen("evens.txt", "r");
    int count = 0;
    long sum = 0;
    while (fscanf(f, "%d", &x) == 1) {
        count++;
        sum += x;
    }
    fclose(f);
    printf("%d %ld\n", count, sum);
    return 0;
}
```

```tests
{"name": "mixed", "stdin": "6\n3 8 5 12 7 2\n", "expected": "3 22"}
{"name": "no evens", "stdin": "2\n1 3\n", "expected": "0 0"}
{"name": "negative evens", "stdin": "3\n-4 4 -1\n", "expected": "2 0", "hidden": true}
```
