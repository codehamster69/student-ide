---
title: Exceptions
summary: throw, try, catch, standard exception types, and staying safe when things fail.
---
When a function can't do its job, it can **throw** an exception. The program jumps out of the function (running the destructors of everything on the way, thanks to RAII) to the nearest matching **catch**.

```cpp
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

double safe_sqrt(double x) {
    if (x < 0) {
        throw std::invalid_argument("negative input: " + std::to_string(x));
    }
    double r = x;
    for (int i = 0; i < 30; i++) r = (r + x / r) / 2;   // Newton's method
    return x == 0 ? 0 : r;
}

int main() {
    for (double x : {16.0, -4.0}) {
        try {
            std::cout << safe_sqrt(x) << "\n";
        } catch (const std::invalid_argument &e) {
            std::cout << "invalid: " << e.what() << "\n";
        }
    }

    std::vector<int> v = {1, 2, 3};
    try {
        std::cout << v.at(10) << "\n";            // at() checks and throws
    } catch (const std::out_of_range &e) {
        std::cout << "out of range\n";
    } catch (const std::exception &e) {           // any other standard exception
        std::cout << "something else: " << e.what() << "\n";
    }

    try {
        std::stoi("abc");
    } catch (const std::exception &e) {
        std::cout << "stoi failed: " << e.what() << "\n";
    }
    return 0;
}
```

- Throw by value, catch by `const &`. Standard types live in `<stdexcept>`: `invalid_argument`, `out_of_range`, `runtime_error`, `logic_error`; they all derive from `std::exception`, whose `what()` gives the message.
- Catch blocks are tried in order, so put specific types before general ones.
- An exception nobody catches ends the program (`terminate`).
- Use exceptions for things that really are errors, not for normal control flow. Destructors must never throw.

Things to try:

1. Remove the `try` around `v.at(10)` and run it.
2. Define your own exception: `struct InsufficientFunds : std::runtime_error { using runtime_error::runtime_error; };`
3. Swap the two catch blocks for `v.at(10)`. Which one runs now?

## Exercise

Write `int parse_age(const std::string &s)` that returns the age, or throws `std::invalid_argument("not a number")` if `s` isn't a whole number, and `std::out_of_range("impossible age")` if it is below 0 or above 150. `main` reads several values and prints, for each, the age or the error message as `error: <message>`. Then it prints how many were valid.

```input
5
21
abc
-3
200
150
```

```cpp starter
#include <iostream>
#include <stdexcept>
#include <string>

int parse_age(const std::string &s) {
    return std::stoi(s);
}

int main() {
    int n, valid = 0;
    std::cin >> n;
    for (int i = 0; i < n; i++) {
        std::string s;
        std::cin >> s;
        std::cout << parse_age(s) << "\n";
        valid++;
    }
    std::cout << valid << " valid\n";
    return 0;
}
```

```cpp solution
#include <cctype>
#include <iostream>
#include <stdexcept>
#include <string>

int parse_age(const std::string &s) {
    std::size_t start = (!s.empty() && s[0] == '-') ? 1 : 0;
    if (s.size() == start || s.size() > 6) throw std::invalid_argument("not a number");
    for (std::size_t i = start; i < s.size(); i++) {
        if (!std::isdigit(static_cast<unsigned char>(s[i]))) throw std::invalid_argument("not a number");
    }
    int age = std::stoi(s);
    if (age < 0 || age > 150) throw std::out_of_range("impossible age");
    return age;
}

int main() {
    int n, valid = 0;
    std::cin >> n;
    for (int i = 0; i < n; i++) {
        std::string s;
        std::cin >> s;
        try {
            std::cout << parse_age(s) << "\n";
            valid++;
        } catch (const std::exception &e) {
            std::cout << "error: " << e.what() << "\n";
        }
    }
    std::cout << valid << " valid\n";
    return 0;
}
```

```tests
{"name": "example", "stdin": "5\n21\nabc\n-3\n200\n150\n", "expected": "21\nerror: not a number\nerror: impossible age\nerror: impossible age\n150\n2 valid"}
{"name": "half a number", "stdin": "2\n12abc\n0\n", "expected": "error: not a number\n0\n1 valid"}
{"name": "huge", "stdin": "1\n99999999999\n", "expected": "error: not a number\n0 valid", "hidden": true}
```
