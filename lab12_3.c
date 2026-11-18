#include <stdio.h>

int n, W;
int w[100], p[100];
int bestProfit = 0;
int selected[100], bestSelected[100];

void knapsack(int i, int weight, int profit) {
    if (i == n) {
        if (profit > bestProfit) {
            bestProfit = profit;

            for (int j = 0; j < n; j++)
                bestSelected[j] = selected[j];
        }
        return;
    }

    // Include item
    if (weight + w[i] <= W) {
        selected[i] = 1;
        knapsack(i + 1, weight + w[i], profit + p[i]);
    }

    // Exclude item
    selected[i] = 0;
    knapsack(i + 1, weight, profit);
}

int main() {
    scanf("%d", &n);

    for (int i = 0; i < n; i++)
        scanf("%d", &w[i]);

    for (int i = 0; i < n; i++)
        scanf("%d", &p[i]);

    scanf("%d", &W);

    knapsack(0, 0, 0);

    printf("Max profit is %d\n", bestProfit);

    printf("Selected items: ");
    for (int i = 0; i < n; i++) {
        if (bestSelected[i])
            printf("%d ", i + 1);
    }

    return 0;
}
