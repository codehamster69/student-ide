---
title: Strings by hand
summary: Write strlen, strcpy and friends yourself, and read whole lines safely.
---
The functions in `<string.h>` are just loops over characters until `'\0'`. Writing them yourself is the best way to understand strings and pointers together.

```c
#include <stdio.h>

int my_strlen(const char *s) {
    int n = 0;
    while (s[n] != '\0') {
        n++;
    }
    return n;
}

void my_strcpy(char *dst, const char *src) {
    while ((*dst++ = *src++) != '\0') {
        /* copies each char, including the final '\0' */
    }
}

int main(void) {
    char buf[32];
    my_strcpy(buf, "pointer");
    printf("%s has %d letters\n", buf, my_strlen(buf));
    return 0;
}
```

- `const char *s` promises the function won't change the text.
- `*dst++ = *src++` copies one character and moves both pointers on. It is compact; write it the long way first if it looks like magic.
- `scanf("%s")` stops at the first space. To read a whole line, use `fgets(buf, sizeof buf, stdin)`. It keeps the newline, which you usually cut off: `buf[strcspn(buf, "\n")] = '\0';`
- Writing past the end of the buffer (a *buffer overflow*) is one of the most common security bugs in C. `fgets` takes the buffer size so it can't overflow.

Things to try:

1. Write `int my_strcmp(const char *a, const char *b)`: walk while the characters are equal, then return their difference.
2. Read a line with `fgets` and print it in upper case (use `toupper` from `<ctype.h>`).
3. Make `buf` only 4 characters long and copy "pointer" into it. Run it a few times.

## Exercise

Read one whole line (at most 200 characters, may contain spaces) and print it with the words in reverse order, separated by single spaces. Words are separated by one or more spaces.

```input
the quick brown fox
```

```c starter
#include <stdio.h>
#include <string.h>

int main(void) {
    char line[256];
    fgets(line, sizeof line, stdin);
    line[strcspn(line, "\n")] = '\0';
    /* print the words in reverse order */
    return 0;
}
```

```c solution
#include <stdio.h>
#include <string.h>

int main(void) {
    char line[256];
    fgets(line, sizeof line, stdin);
    line[strcspn(line, "\n")] = '\0';
    char *words[128];
    int n = 0;
    for (char *w = strtok(line, " "); w != NULL; w = strtok(NULL, " ")) {
        words[n++] = w;
    }
    for (int i = n - 1; i >= 0; i--) {
        printf("%s%s", words[i], i > 0 ? " " : "");
    }
    printf("\n");
    return 0;
}
```

```tests
{"name": "four words", "stdin": "the quick brown fox\n", "expected": "fox brown quick the"}
{"name": "one word", "stdin": "hello\n", "expected": "hello"}
{"name": "extra spaces", "stdin": "  a   b  c \n", "expected": "c b a", "hidden": true}
```
