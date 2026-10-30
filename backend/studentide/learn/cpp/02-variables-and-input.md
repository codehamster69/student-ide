---
title: Variables and input
summary: Types, auto, and reading values with cin.
---
C++ has the same basic types as C (`int`, `double`, `char`, `bool`) plus `std::string` for text. `auto` asks the compiler to work out the type from the value.

`std::cin >>` reads the next value from the input into a variable, skipping spaces and newlines. No `&` and no format specifiers needed.

```cpp
#include <iostream>
#include <string>

int main() {
    std::string name;
    int age;
    std::cin >> name >> age;

    auto next = age + 1;          // auto: an int here
    bool adult = age >= 18;
    double days = age * 365.25;

    std::cout << "Hi " << name << ", next year you will be " << next << ".\n";
    std::cout << "adult: " << std::boolalpha << adult << "\n";
    std::cout << "about " << days << " days old\n";
    return 0;
}
```

Change the name and age in the **Input** box and run again.

- `std::boolalpha` prints `true`/`false` instead of `1`/`0`.
- `cin >> name` reads one word. The strings lesson shows how to read a whole line.
- Variables declared without a value hold garbage, as in C. Give them a value: `int count = 0;` or `int count{0};`.

Things to try:

1. Type letters where the age should be. What does the program print?
2. Read two doubles and print their average.
3. Use `std::fixed << std::setprecision(2)` (from `<iomanip>`) to print `days` with two decimals.

## Exercise

Read a price (a decimal number) and a quantity (a whole number), then print the total with exactly two decimals, adding 18% tax: `total = price * quantity * 1.18`.

```input
49.50 3
```

```cpp starter
#include <iostream>
#include <iomanip>

int main() {
    double price;
    int qty;
    std::cin >> price >> qty;
    // print the total with tax, two decimals
    return 0;
}
```

```cpp solution
#include <iostream>
#include <iomanip>

int main() {
    double price;
    int qty;
    std::cin >> price >> qty;
    std::cout << std::fixed << std::setprecision(2) << price * qty * 1.18 << "\n";
    return 0;
}
```

```tests
{"name": "three items", "stdin": "49.50 3\n", "expected": "175.23"}
{"name": "one item", "stdin": "100 1\n", "expected": "118.00"}
{"name": "zero", "stdin": "9.99 0\n", "expected": "0.00", "hidden": true}
```
