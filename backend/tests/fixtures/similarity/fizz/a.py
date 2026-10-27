n = int(input())
for i in range(1, n + 1):
    if i % 15 == 0:
        print("ChaiSamosa")
    elif i % 3 == 0:
        print("Chai")
    elif i % 5 == 0:
        print("Samosa")
    else:
        print(i)
