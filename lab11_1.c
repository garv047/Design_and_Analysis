#include <stdio.h>
#include <string.h>

int main() {
    char a[1001], b[1001];
    int dp[1001][1001];

    scanf("%s", a);
    scanf("%s", b);

    int m = strlen(a);
    int n = strlen(b);

    for (int i = 0; i <= m; i++) {
        for (int j = 0; j <= n; j++) {
            if (i == 0 || j == 0)
                dp[i][j] = 0;
            else if (a[i - 1] == b[j - 1])
                dp[i][j] = dp[i - 1][j - 1] + 1;
            else
                dp[i][j] = (dp[i - 1][j] > dp[i][j - 1])
                           ? dp[i - 1][j] : dp[i][j - 1];
        }
    }

    printf("%d\n", dp[m][n]);
    return 0;
}
