#include <stdio.h>

int main(void) {
    int n;
    scanf("%d", &n);
    long long best = -1000000000000LL, cur = 0;
    for (int i = 0; i < n; i++) {
        long long x;
        scanf("%lld", &x);
        cur = cur + x > x ? cur + x : x;
        if (cur > best) best = cur;
    }
    printf("%lld\n", best);
    return 0;
}
