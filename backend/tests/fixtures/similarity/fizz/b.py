n = int(input())
for k in range(1, n + 1):
    word = ("Chai" if k % 3 == 0 else "") + ("Samosa" if k % 5 == 0 else "")
    print(word or k)
