---
title: Queues, heaps and graph search
summary: std::queue, std::priority_queue and breadth-first search on a grid.
---
The STL has container *adaptors* with a small, focused interface:

- **`std::stack<T>`**: `push`, `top`, `pop`. Last in, first out.
- **`std::queue<T>`**: `push` at the back, `front` and `pop` at the front. First in, first out.
- **`std::priority_queue<T>`**: a heap. `top` is always the **largest** element; `push` and `pop` take about log₂(n) steps.

```cpp
#include <functional>
#include <iostream>
#include <queue>
#include <vector>

int main() {
    std::priority_queue<int> maxheap;
    for (int x : {5, 1, 8, 3, 9}) maxheap.push(x);
    while (!maxheap.empty()) {
        std::cout << maxheap.top() << " ";        // 9 8 5 3 1
        maxheap.pop();
    }
    std::cout << "\n";

    // smallest first: give the comparison greater<int>
    std::priority_queue<int, std::vector<int>, std::greater<int>> minheap;
    for (int x : {5, 1, 8}) minheap.push(x);
    std::cout << minheap.top() << "\n";           // 1

    std::queue<std::string> line;
    line.push("asha"); line.push("ravi");
    std::cout << line.front() << " is served first\n";
    return 0;
}
```

A queue is exactly what **breadth-first search (BFS)** needs: explore everything one step away, then two steps, and so on. On a grid, BFS finds the shortest path:

```cpp
#include <iostream>
#include <queue>
#include <string>
#include <vector>

int main() {
    std::vector<std::string> g = {
        "S.#.",
        "..#.",
        "...E",
    };
    int R = g.size(), C = g[0].size();
    std::vector<std::vector<int>> dist(R, std::vector<int>(C, -1));
    std::queue<std::pair<int, int>> q;
    q.push({0, 0});
    dist[0][0] = 0;
    int dr[] = {1, -1, 0, 0}, dc[] = {0, 0, 1, -1};
    while (!q.empty()) {
        auto [r, c] = q.front();
        q.pop();
        for (int k = 0; k < 4; k++) {
            int nr = r + dr[k], nc = c + dc[k];
            if (nr >= 0 && nr < R && nc >= 0 && nc < C && g[nr][nc] != '#' && dist[nr][nc] == -1) {
                dist[nr][nc] = dist[r][c] + 1;
                q.push({nr, nc});
            }
        }
    }
    std::cout << "steps to E: " << dist[2][3] << "\n";   // 5
    return 0;
}
```

Things to try:

1. Put the top-3 largest numbers of a list into a min-heap of size 3 (pop whenever it grows past 3).
2. Block the path in the grid completely. What does `dist` hold for `E`?
3. Store `std::pair<int, std::string>` in a priority queue. How does it order them?

## Exercise

Read a grid: the first line is `R C`, then `R` lines of `C` characters, with `S` the start, `E` the exit, `#` walls and `.` open cells. Print the smallest number of steps from `S` to `E` moving up, down, left or right, or `-1` if there is no way.

```input
3 4
S.#.
..#.
...E
```

```cpp starter
#include <iostream>
#include <queue>
#include <string>
#include <vector>

int main() {
    int R, C;
    std::cin >> R >> C;
    std::vector<std::string> g(R);
    for (auto &row : g) std::cin >> row;
    // find S and E, then breadth-first search
    return 0;
}
```

```cpp solution
#include <iostream>
#include <queue>
#include <string>
#include <vector>

int main() {
    int R, C;
    std::cin >> R >> C;
    std::vector<std::string> g(R);
    for (auto &row : g) std::cin >> row;
    std::vector<std::vector<int>> dist(R, std::vector<int>(C, -1));
    std::queue<std::pair<int, int>> q;
    int er = -1, ec = -1;
    for (int r = 0; r < R; r++) {
        for (int c = 0; c < C; c++) {
            if (g[r][c] == 'S') { dist[r][c] = 0; q.push({r, c}); }
            if (g[r][c] == 'E') { er = r; ec = c; }
        }
    }
    int dr[] = {1, -1, 0, 0}, dc[] = {0, 0, 1, -1};
    while (!q.empty()) {
        auto [r, c] = q.front();
        q.pop();
        for (int k = 0; k < 4; k++) {
            int nr = r + dr[k], nc = c + dc[k];
            if (nr >= 0 && nr < R && nc >= 0 && nc < C && g[nr][nc] != '#' && dist[nr][nc] == -1) {
                dist[nr][nc] = dist[r][c] + 1;
                q.push({nr, nc});
            }
        }
    }
    std::cout << dist[er][ec] << "\n";
    return 0;
}
```

```tests
{"name": "example", "stdin": "3 4\nS.#.\n..#.\n...E\n", "expected": "5"}
{"name": "walled off", "stdin": "2 3\nS#E\n.#.\n", "expected": "-1"}
{"name": "next door", "stdin": "1 2\nSE\n", "expected": "1"}
{"name": "maze", "stdin": "5 5\nS#...\n.#.#.\n.#.#.\n...#E\n####.\n", "expected": "13", "hidden": true}
```
