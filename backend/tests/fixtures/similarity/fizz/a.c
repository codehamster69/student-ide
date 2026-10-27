#include <stdio.h>

int main(void) {
    int n;
    scanf("%d", &n);
    for (int i = 1; i <= n; i++) {
        if (i % 15 == 0) printf("ChaiSamosa\n");
        else if (i % 3 == 0) printf("Chai\n");
        else if (i % 5 == 0) printf("Samosa\n");
        else printf("%d\n", i);
    }
    return 0;
}
