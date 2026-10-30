---
title: Hello, world
summary: The shape of every C program, and printing a line.
---
Every C program starts running at a function called `main`. The lines between its `{` and `}` run from top to bottom, and `return 0;` at the end tells the operating system that everything went fine.

```c
#include <stdio.h>

int main(void) {
    printf("Hello, world!\n");
    return 0;
}
```

- `#include <stdio.h>` brings in the **st**andar**d** **i**nput/**o**utput library, which is where `printf` lives.
- `printf` prints text. The `\n` at the end is a *newline*: without it the next thing printed would start on the same line.
- Every statement ends with a semicolon `;`. Forgetting one is the most common compile error, so try deleting one and pressing **Run** to see what the compiler says.

Things to try:

1. Change the message and run it again.
2. Remove the `\n` and add a second `printf`. Where does the second text appear?
3. Print the same line three times.

## Exercise

Make the program print exactly two lines:

```
I am learning C
and it is going well
```

Press **Check** when you think it is right.

```c starter
#include <stdio.h>

int main(void) {
    printf("Hello, world!\n");
    return 0;
}
```

```c solution
#include <stdio.h>

int main(void) {
    printf("I am learning C\n");
    printf("and it is going well\n");
    return 0;
}
```

```tests
{"name": "two lines", "stdin": "", "expected": "I am learning C\nand it is going well"}
```
