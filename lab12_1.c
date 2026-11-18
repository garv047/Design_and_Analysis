#include <stdio.h>

int main() {
    int n, a[100], S;
    int dp[101][1001];

    scanf("%d", &n);

    for (int i = 0; i < n; i++)
        scanf("%d", &a[i]);

    scanf("%d", &S);

    for (int i = 0; i <= n; i++)
        dp[i][0] = 1;

    for (int j = 1; j <= S; j++)
        dp[0][j] = 0;

    for (int i = 1; i <= n; i++) {
        for (int j = 1; j <= S; j++) {
            if (a[i-1] <= j)
                dp[i][j] = dp[i-1][j] || dp[i-1][j-a[i-1]];
            else
                dp[i][j] = dp[i-1][j];
        }
    }

    if (dp[n][S]) {
        printf("YES\n");

        int j = S;
        for (int i = n; i > 0; i--) {
            if (dp[i][j] && !dp[i-1][j]) {
                printf("%d ", a[i-1]);
                j -= a[i-1];
            }
        }
    }
    else {
        printf("NO");
    }

    return 0;
}
