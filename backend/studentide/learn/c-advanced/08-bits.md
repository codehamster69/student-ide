---
title: Bits and bitwise operators
summary: &, |, ^, ~, << and >>, and packing flags into one number.
---
Every integer is a row of bits. C lets you work on those bits directly:

| Operator | Meaning | `12 op 10` (1100 and 1010) |
|---|---|---|
| `a & b` | 1 where **both** bits are 1 | `8` (1000) |
| `a \| b` | 1 where **either** is 1 | `14` (1110) |
| `a ^ b` | 1 where they **differ** | `6` (0110) |
| `~a` | flips every bit | |
| `a << k` | shifts left `k` places (× 2ᵏ) | `12 << 1` is `24` |
| `a >> k` | shifts right `k` places (÷ 2ᵏ) | `12 >> 2` is `3` |

```c
#include <stdio.h>

void print_bits(unsigned x) {
    for (int i = 7; i >= 0; i--) {
        printf("%u", (x >> i) & 1u);     /* bit i */
    }
    printf("\n");
}

int main(void) {
    unsigned flags = 0;
    enum { READ = 1u << 0, WRITE = 1u << 1, EXEC = 1u << 2 };

    flags |= READ | EXEC;          /* turn bits on */
    print_bits(flags);             /* 00000101 */
    if (flags & WRITE) printf("can write\n");
    else printf("cannot write\n");
    flags &= ~EXEC;                /* turn a bit off */
    flags ^= WRITE;                /* toggle a bit */
    print_bits(flags);             /* 00000011 */
    return 0;
}
```

Tricks worth knowing: `x & 1` tells you if `x` is odd; `x & (x - 1)` removes the lowest 1 bit, so it is `0` exactly when `x` is a power of two (and not 0).

Use `unsigned` types for bit work: shifting negative numbers or shifting into the sign bit is undefined or implementation-defined in C.

Things to try:

1. Print `print_bits(200)` and check it by hand.
2. Swap two variables with three `^=` and no temporary.
3. Write `int is_power_of_two(unsigned x)`.

## Exercise

Read a non-negative whole number (it fits in an `unsigned int`) and print two things on one line: how many 1 bits it has, and its value in binary with no leading zeros (`0` for zero).

```input
37
```

```c starter
#include <stdio.h>

int main(void) {
    unsigned x;
    scanf("%u", &x);
    /* print: <number of 1 bits> <binary> */
    return 0;
}
```

```c solution
#include <stdio.h>

int main(void) {
    unsigned x;
    scanf("%u", &x);
    int ones = 0;
    for (unsigned y = x; y != 0; y &= y - 1) {
        ones++;
    }
    printf("%d ", ones);
    int started = 0;
    for (int i = 31; i >= 0; i--) {
        if ((x >> i) & 1u) started = 1;
        if (started) printf("%u", (x >> i) & 1u);
    }
    if (!started) printf("0");
    printf("\n");
    return 0;
}
```

```tests
{"name": "37", "stdin": "37\n", "expected": "3 100101"}
{"name": "zero", "stdin": "0\n", "expected": "0 0"}
{"name": "power of two", "stdin": "1024\n", "expected": "1 10000000000"}
{"name": "all ones", "stdin": "4294967295\n", "expected": "32 11111111111111111111111111111111", "hidden": true}
```
