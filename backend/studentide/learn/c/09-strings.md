---
title: Strings
summary: Text in C is an array of characters that ends with '\0'.
---
C has no separate string type. A **string** is an array of `char` with a special character `'\0'` (the *null character*) after the last letter, so code can tell where the text ends.

```c
#include <stdio.h>
#include <string.h>

int main(void) {
    char name[20] = "Ada";        /* 'A' 'd' 'a' '\0' and spare room */
    printf("%s has %zu letters\n", name, strlen(name));

    name[0] = 'E';                /* strings are arrays, so this works */
    printf("now: %s\n", name);

    for (int i = 0; name[i] != '\0'; i++) {
        printf("[%c]", name[i]);
    }
    printf("\n");
    return 0;
}
```

- `%s` prints (or with `scanf`, reads) a whole string. `scanf("%s", word)` reads one word, stops at a space, and needs **no** `&` because an array already gives its address.
- `<string.h>` has helpers: `strlen` (length), `strcpy` (copy), `strcmp` (compare: 0 means equal) and `strcat` (join).
- You can't compare strings with `==`. That compares where they live in memory, not their letters. Use `strcmp`.

Things to try:

1. Print the name backwards with a loop that starts at `strlen(name) - 1`.
2. Count the vowels in a word read with `scanf("%s", ...)`.
3. Make `name` exactly 3 characters long: `char name[3] = "Ada";`. What goes wrong when you print it?

## Exercise

Read one word (lower-case letters, at most 100 of them) and print `palindrome` if it reads the same backwards, otherwise `not palindrome`.

```input
level
```

```c starter
#include <stdio.h>
#include <string.h>

int main(void) {
    char w[101];
    scanf("%100s", w);
    /* is w a palindrome? */
    return 0;
}
```

```c solution
#include <stdio.h>
#include <string.h>

int main(void) {
    char w[101];
    scanf("%100s", w);
    int n = strlen(w), ok = 1;
    for (int i = 0; i < n / 2; i++) {
        if (w[i] != w[n - 1 - i]) {
            ok = 0;
        }
    }
    printf(ok ? "palindrome\n" : "not palindrome\n");
    return 0;
}
```

```tests
{"name": "level", "stdin": "level\n", "expected": "palindrome"}
{"name": "lever", "stdin": "lever\n", "expected": "not palindrome"}
{"name": "one letter", "stdin": "a\n", "expected": "palindrome"}
{"name": "even length", "stdin": "abba\n", "expected": "palindrome"}
{"name": "almost", "stdin": "abca\n", "expected": "not palindrome", "hidden": true}
```
