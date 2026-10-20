# Test: da li RIK odgovara sa ovog servera i koliko brzo.
import json,subprocess,time
R="https://www.rik.parlament.gov.rs"
def run(a): t=time.time(); o=subprocess.run(["curl","-sS","--http1.1","--max-time","60"]+a,capture_output=True,text=True); return o,round(time.time()-t,2)
o,t=run(["-c","ck","-o","/dev/null","-w","%{http_code}",R+"/542645/rezultati/"]); print("stranica:",o.stdout,o.stderr.strip(),t,"s")
H=["-b","ck","-X","POST","-H","X-Requested-With: XMLHttpRequest","-H","Referer: "+R+"/542645/rezultati/"]
o,t=run(H+["--data","election_type=2&election_round=341140&election_region=4&election_municipality=149",R+"/get-election-stations/"])
st=json.loads(o.stdout)["election_stations"]; print("spisak BM Kursumlija 2023:",len(st),t,"s")
ts=[]
for sid in list(st)[:20]:
    o,t=run(H+["--data",f"should_update_pies=1&type=2&election_round=341140&region=4&municipality=149&election_station={sid}",R+"/get_results/"]); ts.append(t)
    json.loads(o.stdout)
print("20 x get_results: ukupno",round(sum(ts),1),"s, prosek",round(sum(ts)/len(ts),2),"s, max",max(ts))
o,t=run(H+["--data","should_update_pies=1&type=2&election_round=341140&region=4&municipality=149&election_station=0",R+"/get_results/"])
print("zbir opstine:",json.loads(o.stdout).get("stat_sum_numbers"),t,"s")
