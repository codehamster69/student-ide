#include <stdio.h>
#include <ctype.h>

int main() {
    static char buf[10005];
    int len = 0, ch;
    while ((ch = getchar()) != EOF && ch != '\n') buf[len++] = (char)ch;
    int end = len, first = 1;
    while (end > 0) {
        while (end > 0 && isspace((unsigned char)buf[end - 1])) end--;
        int start = end;
        while (start > 0 && !isspace((unsigned char)buf[start - 1])) start--;
        if (start == end) break;
        if (!first) putchar(' ');
        fwrite(buf + start, 1, end - start, stdout);
        first = 0;
        end = start;
    }
    putchar('\n');
    return 0;
}
