#include <stdio.h>

int T;
int meltsAt(int temperature) {
    if (temperature >= T)
        return 1;
    else
        return 0;
}

int findMeltingPoint(int low, int high) {
    if (low == high) {
        return low;
    }

    int mid = (low + high) / 2;

    if (meltsAt(mid)) {
        return findMeltingPoint(low, mid);
    } else {
        return findMeltingPoint(mid + 1, high);
    }
}

int main() {
    scanf("%d", &T);

    int result = findMeltingPoint(0, 100);

    printf("%d\n", result);

    return 0;
}
