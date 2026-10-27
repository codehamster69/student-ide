#include <stdio.h>
#include <stdlib.h>

static int cmp_int(const void *p, const void *q) {
    int x = *(const int *)p, y = *(const int *)q;
    return (x > y) - (x < y);
}

int main(void) {
    int n, queries;
    if (scanf("%d%d", &n, &queries) != 2) return 0;
    int *arr = malloc(n * sizeof *arr);
    for (int k = 0; k < n; ++k) scanf("%d", arr + k);
    for (; queries > 0; --queries) {
        int key;
        scanf("%d", &key);
        int *hit = bsearch(&key, arr, n, sizeof *arr, cmp_int);
        if (!hit) { puts("-1"); continue; }
        while (hit > arr && *(hit - 1) == key) hit--;
        printf("%ld\n", (long)(hit - arr) + 1);
    }
    free(arr);
    return 0;
}
