---
title: Hello, C++
summary: The shape of a C++ program, and printing with cout.
---
A C++ program starts at `main`, just like C. Instead of `printf`, C++ prints with **streams**: `std::cout` is the screen, and `<<` sends values into it, one after another.

```cpp
#include <iostream>

int main() {
    std::cout << "Hello, C++!" << std::endl;
    std::cout << "2 + 3 = " << 2 + 3 << "\n";
    std::cout << "pi is about " << 3.14159 << '\n';
    return 0;
}
```

- `#include <iostream>` brings in the input/output streams.
- `std::` means "from the standard library". Many programs write `using namespace std;` near the top so they can say just `cout`. That is fine in small programs, but in bigger ones it can cause name clashes, so these lessons keep `std::`.
- `std::endl` ends the line *and* flushes the output; `"\n"` just ends the line and is faster. Either is fine here.
- No format specifiers: `<<` works out how to print each type by itself.

Things to try:

1. Print your name and your age on one line using several `<<`.
2. Remove a semicolon and read the compiler's message.
3. Print `10 / 4` and `10.0 / 4`. Integer division works as in C.

## Exercise

Print exactly these three lines. The second line must be computed (`7 * 6`), not typed.

```
C++ is C with classes
42
done
```

```cpp starter
#include <iostream>

int main() {
    std::cout << "Hello, C++!" << std::endl;
    return 0;
}
```

```cpp solution
#include <iostream>

int main() {
    std::cout << "C++ is C with classes\n";
    std::cout << 7 * 6 << "\n";
    std::cout << "done\n";
    return 0;
}
```

```tests
{"name": "three lines", "stdin": "", "expected": "C++ is C with classes\n42\ndone"}
```
