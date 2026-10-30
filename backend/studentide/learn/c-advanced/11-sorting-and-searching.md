---
title: Sorting and binary search
summary: Insertion sort by hand, binary search on a sorted array, and why it is so much faster.
---
**Insertion sort** works like sorting cards in your hand: take the next card and slide it left until the card before it is not bigger.

```c
#include <stdio.h>

void insertion_sort(int a[], int n) {
    for (int i = 1; i < n; i++) {
        int key = a[i];
        int j = i - 1;
        while (j >= 0 && a[j] > key) {
            a[j + 1] = a[j];   /* shift the bigger one right */
            j--;
        }
        a[j + 1] = key;
    }
}

int main(void) {
    int a[] = {5, 2, 9, 1, 7};
    int n = sizeof a / sizeof a[0];
    insertion_sort(a, n);
    for (int i = 0; i < n; i++) printf("%d ", a[i]);
    printf("\n");
    return 0;
}
```

For `n` items, insertion sort can take about `n * n / 2` steps, so it is fine for hundreds of items and slow for millions. For big arrays use `qsort` (see the function pointers lesson), which takes about `n log n` steps.

Looking for a value one item at a time (**linear search**) takes up to `n` steps. If the array is sorted, **binary search** is much faster. Look at the middle: if the value you want is smaller, it can only be in the left half, so throw the right half away, and repeat. Each step halves the range, so a million items need only about 20 steps.

```c
#include <stdio.h>

/* index of x in the sorted array a, or -1 */
int binary_search(const int a[], int n, int x) {
    int lo = 0, hi = n - 1;
    while (lo <= hi) {
        int mid = lo + (hi - lo) / 2;   /* avoids overflow of lo + hi */
        if (a[mid] == x) return mid;
        if (a[mid] < x) lo = mid + 1;
        else hi = mid - 1;
    }
    return -1;
}

int main(void) {
    int a[] = {1, 3, 4, 8, 10, 15};
    printf("%d %d\n", binary_search(a, 6, 8), binary_search(a, 6, 5));
    return 0;
}
```

Things to try:

1. Add a counter to `insertion_sort` that counts the shifts. Compare an already sorted array with a reversed one.
2. Change `lo <= hi` to `lo < hi` in `binary_search`. Which value can it no longer find?
3. Print `lo`, `mid` and `hi` on each step of the search.

## Exercise

Read `n` and then `n` different integers. Sort them with your own sort, then read `q` and `q` queries. For each query print the position of that value in the sorted array (counting from 0), or `-1` if it is not there. Use binary search for the queries.

```input
5
40 10 30 50 20
3
30 35 10
```

```c starter
#include <stdio.h>

int main(void) {
    int n;
    scanf("%d", &n);
    int a[1000];
    for (int i = 0; i < n; i++) scanf("%d", &a[i]);
    /* sort a, then answer the queries */
    return 0;
}
```

```c solution
#include <stdio.h>

void insertion_sort(int a[], int n) {
    for (int i = 1; i < n; i++) {
        int key = a[i], j = i - 1;
        while (j >= 0 && a[j] > key) {
            a[j + 1] = a[j];
            j--;
        }
        a[j + 1] = key;
    }
}

int binary_search(const int a[], int n, int x) {
    int lo = 0, hi = n - 1;
    while (lo <= hi) {
        int mid = lo + (hi - lo) / 2;
        if (a[mid] == x) return mid;
        if (a[mid] < x) lo = mid + 1;
        else hi = mid - 1;
    }
    return -1;
}

int main(void) {
    int n, q, x;
    scanf("%d", &n);
    int a[1000];
    for (int i = 0; i < n; i++) scanf("%d", &a[i]);
    insertion_sort(a, n);
    scanf("%d", &q);
    while (q--) {
        scanf("%d", &x);
        printf("%d\n", binary_search(a, n, x));
    }
    return 0;
}
```

```tests
{"name": "example", "stdin": "5\n40 10 30 50 20\n3\n30 35 10\n", "expected": "2\n-1\n0"}
{"name": "one item", "stdin": "1\n7\n2\n7 8\n", "expected": "0\n-1"}
{"name": "negatives", "stdin": "6\n-5 3 0 -9 12 4\n4\n12 -9 4 1\n", "expected": "5\n0\n4\n-1", "hidden": true}
```
