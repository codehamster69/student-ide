#include <stdio.h>
#include <stdlib.h>

/* brute force over prefix sums: fine for n <= 5000 */
int main(void) {
    int n;
    if (scanf("%d", &n) != 1) return 0;
    long long *pre = malloc(sizeof(long long) * (n + 1));
    pre[0] = 0;
    for (int i = 1; i <= n; i++) {
        long long v;
        scanf("%lld", &v);
        pre[i] = pre[i - 1] + v;
    }
    long long ans = pre[1];
    long long lowest = 0;
    for (int r = 1; r <= n; r++) {
        if (pre[r] - lowest > ans) ans = pre[r] - lowest;
        if (pre[r] < lowest) lowest = pre[r];
    }
    printf("%lld\n", ans);
    free(pre);
    return 0;
}
