
pages = list(map(int, input("Enter page reference string: ").split()))
n = int(input("Enter number of frames: "))

frames = []
freq = {}
last_used = {}

hits = 0
faults = 0

for time, page in enumerate(pages):

    if page in frames:
        hits += 1
        freq[page] += 1
        last_used[page] = time
        print(page, "HIT", frames)

    else:
        faults += 1

        if len(frames) < n:
            frames.append(page)

        else:
            # Adaptive score: frequency and recent usage
            score = {}

            for p in frames:
                score[p] = freq[p] / (time - last_used[p] + 1)

            replace = min(frames, key=lambda p: score[p])

            frames.remove(replace)
            del freq[replace]
            del last_used[replace]

            frames.append(page)

        freq[page] = 1
        last_used[page] = time

        print(page, "FAULT", frames)

print("\nTotal Hits:", hits)
print("Total Faults:", faults)
print("Final Frames:", frames)
