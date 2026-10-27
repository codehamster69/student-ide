import math


def is_prime(x):
    if x < 2:
        return False
    for d in range(2, int(math.isqrt(x)) + 1):
        if x % d == 0:
            return False
    return True


def main():
    limit = int(input().strip())
    print(sum(1 for k in range(limit + 1) if is_prime(k)))


main()
