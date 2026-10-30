---
title: Namespaces, enum class and constexpr
summary: Keep names apart with namespaces, name a fixed set of values with enum class, and compute constants at compile time.
---
A **namespace** groups names so they don't clash with names elsewhere. The whole standard library lives in `std`, which is why you write `std::cout`. You can make your own and nest them.

```cpp
#include <iostream>

namespace geometry {
    constexpr double pi = 3.14159265358979;
    double circle_area(double r) { return pi * r * r; }
}

namespace physics {
    double circle_area(double r) { return 0; }   // a different function, no clash
}

int main() {
    std::cout << geometry::circle_area(2) << "\n";
    using geometry::pi;                          // bring one name in
    std::cout << pi << "\n";
    return 0;
}
```

`using namespace std;` brings in every name in `std`. It saves typing in tiny programs, but in bigger ones it causes clashes (your `count` versus `std::count`), and you must never put it in a header.

An **enum class** names a fixed set of values. Unlike a plain `enum` or a bunch of `int` constants, its values don't convert to `int` by accident and their names are scoped: you write `Color::Red`.

```cpp
#include <iostream>

enum class Light { Red, Yellow, Green };

Light next(Light l) {
    switch (l) {
        case Light::Red: return Light::Green;
        case Light::Green: return Light::Yellow;
        case Light::Yellow: return Light::Red;
    }
    return Light::Red;
}

int main() {
    Light l = Light::Red;
    for (int i = 0; i < 4; i++) {
        std::cout << static_cast<int>(l) << " ";   // convert on purpose
        l = next(l);
    }
    std::cout << "\n";
    return 0;
}
```

`const` means "this won't change after it is set". `constexpr` goes further: the value is worked out **while compiling**, so it can size an array or be a template argument. A `constexpr` function can run at compile time when its arguments are constants.

```cpp
#include <array>
#include <iostream>

constexpr int square(int x) { return x * x; }

int main() {
    constexpr int n = square(4);       // computed by the compiler
    std::array<int, n> table{};        // needs a compile-time size
    std::cout << table.size() << "\n";
    return 0;
}
```

Things to try:

1. Add `using namespace geometry;` and `using namespace physics;` and call `circle_area(1)`. What does the compiler say?
2. Try `int x = Light::Red;`. Why is it rejected?
3. Make `n` read from `std::cin` and keep `constexpr`. What goes wrong?

## Exercise

A robot faces `North`, `East`, `South` or `West`. Use an `enum class Direction` and write `Direction turn_right(Direction d)` and `std::string name(Direction d)`. Read the starting direction's name and a number of right turns `k`, and print where the robot faces at the end.

```input
North 3
```

```cpp starter
#include <iostream>
#include <string>

int main() {
    std::string start;
    int k;
    std::cin >> start >> k;
    std::cout << start << "\n";
    return 0;
}
```

```cpp solution
#include <iostream>
#include <string>

enum class Direction { North, East, South, West };

Direction turn_right(Direction d) {
    switch (d) {
        case Direction::North: return Direction::East;
        case Direction::East: return Direction::South;
        case Direction::South: return Direction::West;
        case Direction::West: return Direction::North;
    }
    return d;
}

std::string name(Direction d) {
    switch (d) {
        case Direction::North: return "North";
        case Direction::East: return "East";
        case Direction::South: return "South";
        case Direction::West: return "West";
    }
    return "";
}

Direction parse(const std::string& s) {
    if (s == "East") return Direction::East;
    if (s == "South") return Direction::South;
    if (s == "West") return Direction::West;
    return Direction::North;
}

int main() {
    std::string start;
    int k;
    std::cin >> start >> k;
    Direction d = parse(start);
    for (int i = 0; i < k % 4; i++) d = turn_right(d);
    std::cout << name(d) << "\n";
    return 0;
}
```

```tests
{"name": "North 3", "stdin": "North 3\n", "expected": "West"}
{"name": "East 1", "stdin": "East 1\n", "expected": "South"}
{"name": "South 0", "stdin": "South 0\n", "expected": "South"}
{"name": "many turns", "stdin": "West 1000001\n", "expected": "North", "hidden": true}
```
