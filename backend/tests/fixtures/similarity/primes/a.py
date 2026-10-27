n = int(input())
sieve = [True] * (n + 1)
count = 0
for i in range(2, n + 1):
    if sieve[i]:
        count += 1
        for j in range(i * i, n + 1, i):
            sieve[j] = False
print(count)
