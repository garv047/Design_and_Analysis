#include <stdio.h>
#include <stdlib.h>

void merge(long long arr[], int left, int mid, int right) {
    int i = left;
    int j = mid + 1;
    int k = 0;

    int size = right - left + 1;
    long long *temp = (long long *)malloc(size * sizeof(long long));

    while (i <= mid && j <= right) {
        if (arr[i] <= arr[j]) {
            temp[k++] = arr[i++];
        } else {
            temp[k++] = arr[j++];
        }
    }

    while (i <= mid) {
        temp[k++] = arr[i++];
    }

    while (j <= right) {
        temp[k++] = arr[j++];
    }

    for (i = 0; i < size; i++) {
        arr[left + i] = temp[i];
    }

    free(temp);
}

void mergeSort(long long arr[], int left, int right) {
    if (left >= right)
        return;

    int mid = left + (right - left) / 2;

    mergeSort(arr, left, mid);
    mergeSort(arr, mid + 1, right);

    merge(arr, left, mid, right);
}

int main() {
    int n;
    scanf("%d", &n);

    long long *arr = (long long *)malloc(n * sizeof(long long));

    for (int i = 0; i < n; i++) {
        scanf("%lld", &arr[i]);
    }

    mergeSort(arr, 0, n - 1);

    for (int i = 0; i < n; i++) {
        if (i > 0)
            printf(" ");
        printf("%lld", arr[i]);
    }

    printf("\n");

    free(arr);
    return 0;
}
