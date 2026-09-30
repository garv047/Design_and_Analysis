#include <stdio.h>
typedef struct {
    int pid, at, bt, pr, rem;
    int ct, first;
} Process;
float score(Process p, int time, float alpha) {
    int wait = time - p.at - (p.bt - p.rem);
    return p.rem + p.pr - alpha * wait;
}
int main() {
    int n, time=0, done=0, last=-1, cs=0, tq=2;
    float alpha=0.5;
    printf("Enter number of processes: ");
    scanf("%d",&n);
    Process p[n];
    for(int i=0;i<n;i++) {
        p[i].pid=i+1;
        printf("P%d: AT BT Priority: ",i+1);
        scanf("%d%d%d",&p[i].at,&p[i].bt,&p[i].pr);
        p[i].rem=p[i].bt;
        p[i].first=-1;
    }
    printf("\nDAPS Gantt Chart:\n");
    while(done<n) {
        int best=-1;
        float bestScore=1e9;
        for(int i=0;i<n;i++) {
            if(p[i].rem>0 && p[i].at<=time) {
                float x=score(p[i],time,alpha);
                if(x<bestScore ||
                  (x==bestScore && p[i].at<p[best].at)) {
                    bestScore=x;
                    best=i;
                }
            }
        }
        if(best==-1) {
            time++;
            continue;
        }
        if(p[best].first==-1)
            p[best].first=time;
        if(last!=-1 && last!=best)
            cs++;
        last=best;
        int run=(p[best].rem<tq)?p[best].rem:tq;
        printf("| P%d %d-%d ",p[best].pid,time,time+run);
        p[best].rem-=run;
        time+=run;
        if(p[best].rem==0) {
            p[best].ct=time;
            done++;
        }
    }
    printf("|\nContext switches = %d\n",cs);
    return 0;
}
