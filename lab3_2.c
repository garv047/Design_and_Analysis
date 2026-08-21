#include <stdio.h>

int main() {
    int n, K;
    
    printf("Enter size of array: ");
    scanf("%d", &n);

    int arr[n];

    printf("Enter sorted array: ");
    for (int i = 0; i < n; i++) {
        scanf("%d", &arr[i]);
    }

    printf("Enter K: ");
    scanf("%d", &K);

    int left = 0;
    int right = n - 1;
    int found = 0;

    while (left < right) {
        int sum = arr[left] + arr[right];

        if (sum == K) {
            printf("(%d, %d)\n", arr[left], arr[right]);
            found = 1;


            int x = arr[left];
            int y = arr[right];

            while (left < right && arr[left] == x)
                left++;

            while (left < right && arr[right] == y)
                right--;
        }
        else if (sum < K) {
            left++;
        }
        else {
            right--;
        }
    }

    if (found == 0) {
        printf("-1\n");
    }

    return 0;
}