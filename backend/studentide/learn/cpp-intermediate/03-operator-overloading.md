---
title: Operator overloading
summary: Make +, ==, < and << work on your own types.
---
You can teach C++ what `+`, `==`, `<` or `<<` mean for your own classes by writing functions named `operator+`, `operator==` and so on. Used well, it makes code read like maths.

```cpp
#include <iostream>

struct Vec2 {
    double x, y;
};

Vec2 operator+(Vec2 a, Vec2 b) { return {a.x + b.x, a.y + b.y}; }
Vec2 operator*(Vec2 a, double k) { return {a.x * k, a.y * k}; }
bool operator==(Vec2 a, Vec2 b) { return a.x == b.x && a.y == b.y; }

std::ostream &operator<<(std::ostream &out, Vec2 v) {    // so cout << v works
    return out << "(" << v.x << ", " << v.y << ")";
}

int main() {
    Vec2 a{1, 2}, b{3, -1};
    std::cout << a + b << " " << a * 3 << "\n";
    std::cout << std::boolalpha << (a + b == Vec2{4, 1}) << "\n";
    return 0;
}
```

- `operator<<` takes the stream by reference and returns it, so `cout << a << b` can chain.
- Keep the meaning unsurprising: `+` should add, not print or delete.
- Defining `operator<` lets `std::sort` and `std::set` order your type.

Things to try:

1. Add `operator-` and unary `operator-` (negation).
2. Add `operator+=` as a member function that changes the object and returns `*this`.
3. Define `operator<` comparing by length and sort a `std::vector<Vec2>`.

## Exercise

Complete the `Money` type, which stores an amount in **paise** (whole number) to avoid rounding errors. Implement `operator+`, `operator<` and `operator<<` (printing as `Rs 12.05`: rupees, a dot, two digits of paise). `main` reads amounts like `12.05`, prints the total and the largest.

```input
3
12.05
0.99
100.5
```

```cpp starter
#include <iostream>
#include <string>
#include <vector>

struct Money {
    long paise;
};

Money parse(const std::string &s) {
    std::size_t dot = s.find('.');
    if (dot == std::string::npos) return {std::stol(s) * 100};
    std::string frac = (s.substr(dot + 1) + "00").substr(0, 2);
    return {std::stol(s.substr(0, dot)) * 100 + std::stol(frac)};
}

// operator+, operator< and operator<< here

int main() {
    int n;
    std::cin >> n;
    std::vector<Money> v;
    for (int i = 0; i < n; i++) {
        std::string s;
        std::cin >> s;
        v.push_back(parse(s));
    }
    Money total{0}, best = v[0];
    for (Money m : v) {
        total = total + m;
        if (best < m) best = m;
    }
    std::cout << total << "\n" << best << "\n";
    return 0;
}
```

```cpp solution
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

struct Money {
    long paise;
};

Money parse(const std::string &s) {
    std::size_t dot = s.find('.');
    if (dot == std::string::npos) return {std::stol(s) * 100};
    std::string frac = (s.substr(dot + 1) + "00").substr(0, 2);
    return {std::stol(s.substr(0, dot)) * 100 + std::stol(frac)};
}

Money operator+(Money a, Money b) { return {a.paise + b.paise}; }
bool operator<(Money a, Money b) { return a.paise < b.paise; }
std::ostream &operator<<(std::ostream &out, Money m) {
    return out << "Rs " << m.paise / 100 << "." << std::setw(2) << std::setfill('0') << m.paise % 100
               << std::setfill(' ');
}

int main() {
    int n;
    std::cin >> n;
    std::vector<Money> v;
    for (int i = 0; i < n; i++) {
        std::string s;
        std::cin >> s;
        v.push_back(parse(s));
    }
    Money total{0}, best = v[0];
    for (Money m : v) {
        total = total + m;
        if (best < m) best = m;
    }
    std::cout << total << "\n" << best << "\n";
    return 0;
}
```

```tests
{"name": "example", "stdin": "3\n12.05\n0.99\n100.5\n", "expected": "Rs 113.54\nRs 100.50"}
{"name": "whole rupees", "stdin": "2\n5\n7\n", "expected": "Rs 12.00\nRs 7.00"}
{"name": "carry", "stdin": "2\n0.55\n0.55\n", "expected": "Rs 1.10\nRs 0.55", "hidden": true}
```
