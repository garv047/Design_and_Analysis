
holes = list(map(int, input("Enter memory holes: ").split()))
process = int(input("Enter process size: "))

best = -1
min_score = float('inf')

for i in range(len(holes)):
    if holes[i] >= process:

        remaining = holes[i] - process

        # Balanced Fit score
        score = abs(remaining - process)

        if score < min_score:
            min_score = score
            best = i

if best != -1:
    print("Process allocated in hole", best + 1)
    holes[best] -= process
else:
    print("Process rejected: No suitable hole")

print("Updated memory:", holes)
