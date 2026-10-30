---
title: Command-line arguments and errors
summary: argc and argv, exit codes, printing to stderr, and checking for errors with errno and perror.
---
`main` can take two parameters. `argc` is the number of words on the command line, and `argv` is an array of those words as strings. `argv[0]` is the program's own name.

```c
#include <stdio.h>

int main(int argc, char *argv[]) {
    printf("%d words\n", argc);
    for (int i = 0; i < argc; i++) printf("argv[%d] = %s\n", i, argv[i]);
    return 0;
}
```

If you ran it as `./greet Asha 42`, `argc` would be 3, and `argv` would hold `"./greet"`, `"Asha"` and `"42"`. Arguments are always strings: turn `"42"` into a number with `strtol` or `atoi`. The Run button here starts the program with no arguments, so the examples below build an `argv` array themselves.

The value `main` returns is the program's **exit code**. 0 means success and anything else means failure; scripts and other programs check it. `exit(code)` from `<stdlib.h>` ends the program at once from anywhere.

Error messages should go to `stderr`, not `stdout`, so they don't mix with real output: `fprintf(stderr, "...")`. Many library functions report *why* they failed by setting `errno`, and `perror("context")` prints a readable message for it.

```c
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>

int main(void) {
    FILE *f = fopen("no-such-file.txt", "r");
    if (f == NULL) {
        perror("opening no-such-file.txt");   /* prints the reason to stderr */
        return 1;
    }
    fclose(f);
    return 0;
}
```

`strtol` tells you where it stopped reading, so you can detect input that is not a number:

```c
#include <stdio.h>
#include <stdlib.h>

int main(void) {
    const char *words[] = {"42", "7x", "-3"};
    for (int i = 0; i < 3; i++) {
        char *end;
        long v = strtol(words[i], &end, 10);
        if (*end != '\0') printf("%s is not a whole number\n", words[i]);
        else printf("%s -> %ld\n", words[i], v);
    }
    return 0;
}
```

Things to try:

1. In the `fopen` example, open a file that does exist after writing it with `fopen(name, "w")`.
2. Change `"7x"` to `"   7"`. Does `strtol` accept leading spaces?
3. Make the first example print the arguments in reverse.

## Exercise

Write `int run(int argc, char *argv[])`. It treats `argv[1]` to `argv[argc - 1]` as whole numbers and prints their sum, returning 0. If an argument is not a whole number, it prints `bad argument: ` followed by the argument, and returns 1 without printing a sum. The `main` function is given: it reads words from the input, builds an `argv` from them and prints the exit code `run` returned.

```input
3 4 5
```

```c starter
#include <stdio.h>
#include <stdlib.h>

int run(int argc, char *argv[]) {
    return 0;
}

int main(void) {
    static char buf[64][64];
    char *argv[65] = {"sum"};
    int argc = 1;
    while (argc < 65 && scanf("%63s", buf[argc - 1]) == 1) {
        argv[argc] = buf[argc - 1];
        argc++;
    }
    int code = run(argc, argv);
    printf("exit code %d\n", code);
    return 0;
}
```

```c solution
#include <stdio.h>
#include <stdlib.h>

int run(int argc, char *argv[]) {
    long sum = 0;
    for (int i = 1; i < argc; i++) {
        char *end;
        long v = strtol(argv[i], &end, 10);
        if (*end != '\0' || end == argv[i]) {
            printf("bad argument: %s\n", argv[i]);
            return 1;
        }
        sum += v;
    }
    printf("%ld\n", sum);
    return 0;
}

int main(void) {
    static char buf[64][64];
    char *argv[65] = {"sum"};
    int argc = 1;
    while (argc < 65 && scanf("%63s", buf[argc - 1]) == 1) {
        argv[argc] = buf[argc - 1];
        argc++;
    }
    int code = run(argc, argv);
    printf("exit code %d\n", code);
    return 0;
}
```

```tests
{"name": "sum", "stdin": "3 4 5\n", "expected": "12\nexit code 0"}
{"name": "negative", "stdin": "10 -15\n", "expected": "-5\nexit code 0"}
{"name": "bad", "stdin": "1 two 3\n", "expected": "bad argument: two\nexit code 1"}
{"name": "no arguments", "stdin": "", "expected": "0\nexit code 0", "hidden": true}
{"name": "half number", "stdin": "5 6x\n", "expected": "bad argument: 6x\nexit code 1", "hidden": true}
```
