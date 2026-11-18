#include <stdio.h>

int n, board[20];

int safe(int row, int col) {
    for (int i = 0; i < row; i++) {
        if (board[i] == col || 
            (row - i) == (col - board[i]) ||
            (row - i) == (board[i] - col))
            return 0;
    }
    return 1;
}

void solve(int row) {
    if (row == n) {
        for (int i = 0; i < n; i++)
            printf("%d ", board[i]);
        printf("\n");
        return;
    }

    for (int col = 0; col < n; col++) {
        if (safe(row, col)) {
            board[row] = col;
            solve(row + 1);
        }
    }
}

int main() {
    scanf("%d", &n);

    solve(0);

    return 0;
}
