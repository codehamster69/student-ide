#include <stdio.h>

int a[200005];

int lower_bound(int n, int x) {
    int lo = 0, hi = n;
    while (lo < hi) {
        int mid = lo + (hi - lo) / 2;
        if (a[mid] < x) lo = mid + 1;
        else hi = mid;
    }
    return lo;
}

int main(void) {
    int n, q;
    scanf("%d %d", &n, &q);
    for (int i = 0; i < n; i++) scanf("%d", &a[i]);
    while (q--) {
        int x;
        scanf("%d", &x);
        int pos = lower_bound(n, x);
        printf("%d\n", pos < n && a[pos] == x ? pos + 1 : -1);
    }
    return 0;
}
