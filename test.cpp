#include<bits/stdc++.h>
using namespace std;


int sol(int x, int vec[], vector<int> &b){
    if(x==0) return 0;
    if(x==1) return vec[0];

    int n = b.size();
    int idx = upper_bound(b.begin(), b.end(), x)-b.begin(); //O(logn)

    int ans = n-idx;

    //y==0 ans y==1
    ans += vec[0] +vec[1];

    if(x == 2){
        //remove
        ans -= (vec[3] + vec[4]);
    }

    if(x == 3){
        //add
        ans += vec[2];
    }

    return ans;
}
//o(n+m(logn))
int solve(vector<int> &a, vector<int> &b){
    sort(b.begin(), b.end()); //O(nlogn)

    int vec[5] = {0};
    for(int y:b){             //O(n)
        if(y<5)vec[y]++;
    }

    int ans = 0;
    for(int x:a){             //O(m)
        ans += sol(x, vec, b);
    }
    return ans;
}

int main(){
    vector<int> a = {2,1,6};
    vector<int> b = {1,5};

    cout<<solve(a,b)<<endl;

    vector<int> v = {2,3,4,5};
    vector<int> u = {1,2,3};

    cout<<solve(v,u)<<endl;
    return 0;
}