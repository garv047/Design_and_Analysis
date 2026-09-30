#include <stdio.h>
#include <limits.h>
typedef struct {
    int task, job;
    int release, exec, rem, deadline;
    int done;
} Job;
int main() {
    int n, sim, m=0;
    printf("Enter tasks and simulation time: ");
    scanf("%d%d",&n,&sim);
    int C[n],T[n],D[n];
    for(int i=0;i<n;i++) {
        printf("T%d: C T D: ",i+1);
        scanf("%d%d%d",&C[i],&T[i],&D[i]);
    }
    Job job[200];
    for(int i=0;i<n;i++) {
        for(int r=0,k=1;r<sim;r+=T[i],k++) {
            job[m].task=i+1;
            job[m].job=k;
            job[m].release=r;
            job[m].exec=C[i];
            job[m].rem=C[i];
            job[m].deadline=r+D[i];
            job[m].done=0;
            m++;
        }
    }
    int idle=0, misses=0;
    printf("\nSAFS Gantt Chart:\n");
    for(int time=0;time<sim;time++) {
        /* deadline-risk / miss check */
        for(int j=0;j<m;j++) {
            if(!job[j].done &&
               job[j].release<=time &&
               job[j].rem>0 &&
               job[j].deadline<=time) {
                job[j].done=1;
                misses++;
            }
        }
        /* select minimum slack */
        int best=-1, minSlack=INT_MAX;
        for(int j=0;j<m;j++) {
            if(!job[j].done &&
               job[j].release<=time &&
               job[j].rem>0) {
                int slack=job[j].deadline-job[j].rem;
                if(slack<minSlack) {
                    minSlack=slack;
                    best=j;
                }
            }
        }
        if(best==-1) {
            printf("| IDLE ");
            idle++;
        } else {
            printf("| T%d-J%d ",job[best].task,job[best].job);
            job[best].rem--;
            if(job[best].rem==0)
                job[best].done=1;
        }
    }
    printf("|\n");
    printf("Busy Time = %d\n",sim-idle);
    printf("Idle Time = %d\n",idle);
    printf("Utilization = %.2f%%\n",
           ((double)(sim-idle)/sim)*100);
    printf("Deadline Misses = %d\n",misses);
    return 0;
}
