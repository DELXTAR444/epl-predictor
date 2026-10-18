import json,math,os,re,urllib.request,datetime as dt
from collections import defaultdict
R=os.path.dirname(os.path.abspath(__file__));DOCS=R+'/docs';DATA=R+'/data'
os.makedirs(DOCS,exist_ok=True);os.makedirs(DATA,exist_ok=True)
TODAY=dt.date.fromisoformat(os.environ['FAKE_TODAY']) if os.environ.get('FAKE_TODAY') else dt.date.today()
COEF=0.5  # ความแรงของผลตัวเจ็บ (ค่าเดา ยังไม่ได้จูน ดูผลจากแท็บ "ความแม่น")
def get(u):
    return json.load(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=30))
y0=TODAY.year if TODAY.month>=7 else TODAY.year-1
SEASONS=[f'{y}-{str(y+1)[2:]}' for y in range(y0-7,y0+1)]
M=[];FX=[]
for s in SEASONS:
    try:j=get(f'https://raw.githubusercontent.com/openfootball/football.json/master/{s}/en.1.json')
    except Exception as e:print('skip',s,e);continue
    for m in j['matches']:
        sc=m.get('score');ft=sc.get('ft') if isinstance(sc,dict) else sc
        d=dt.date.fromisoformat(m['date'])
        if ft:M.append((d,m['team1'],m['team2'],ft[0],ft[1]))
        else:FX.append((d,m['team1'],m['team2']))
CANON={t for _,h,a,_,_ in M for t in(h,a)}|{t for _,h,a in FX for t in(h,a)}
def strip(n):return re.sub(r'\s+',' ',re.sub(r'\b(AFC|FC)\b','',n).replace('&','and')).strip().lower()
ALIAS={'man city':'manchester city','man utd':'manchester united','spurs':'tottenham hotspur','wolves':'wolverhampton wanderers',"nott'm forest":'nottingham forest','brighton':'brighton and hove albion','newcastle':'newcastle united','west ham':'west ham united','leeds':'leeds united','leicester':'leicester city','ipswich':'ipswich town','norwich':'norwich city','sheffield utd':'sheffield united','luton':'luton town'}
def canon(n):
    k=strip(n);k=ALIAS.get(k,k)
    for c in CANON:
        if strip(c)==k:return c
    for c in CANON:
        if k in strip(c) or strip(c) in k:return c
# ---------- FPL: ผลล่าสุด/ตารางแข่ง (อัปเดตไวกว่า openfootball) + ตัวเจ็บ ----------
INJ={};inj_ok=False
def unavail(e):
    c=e.get('chance_of_playing_next_round')
    if c is not None:return 1-c/100
    return {'a':0,'d':.25,'i':1,'s':1}.get(e['status'],0)
try:
    B='https://fantasy.premierleague.com/api/'
    bs=get(B+'bootstrap-static/');fx=get(B+'fixtures/')
    tmap={t['id']:canon(t['name']) for t in bs['teams']}
    if all(tmap.values()):
        start=dt.date(y0,7,1)
        M=[m for m in M if m[0]<start];FX=[f for f in FX if f[0]<start]
        for f in fx:
            if not f.get('kickoff_time'):continue
            d=dt.date.fromisoformat(f['kickoff_time'][:10]);h,a=tmap[f['team_h']],tmap[f['team_a']]
            if (f.get('finished') or f.get('finished_provisional')) and f['team_h_score'] is not None:M.append((d,h,a,f['team_h_score'],f['team_a_score']))
            else:FX.append((d,h,a))
        for t in bs['teams']:
            P=[e for e in bs['elements'] if e['team']==t['id'] and e['status']!='u']
            def share(types):
                tot=sum(e['total_points'] for e in P if e['element_type'] in types) or 1
                return min(.4,sum(e['total_points']*unavail(e) for e in P if e['element_type'] in types)/tot)
            out=sorted([e for e in P if unavail(e)>=.5],key=lambda e:-e['total_points'])[:5]
            INJ[tmap[t['id']]]=dict(attf=round(1-COEF*share([3,4]),3),deff=round(1+COEF*share([1,2]),3),
                players=[dict(n=e['web_name'],news=e.get('news',''),pts=e['total_points']) for e in out])
        inj_ok=True
    else:print('FPL team mapping incomplete, skip')
except Exception as e:print('FPL skip:',e)
M.sort();FX=sorted(set(FX))
print('matches',len(M),'last',M[-1][0],'fixtures',len(FX),'injuries',inj_ok)
# ---------- โมเดล Poisson ----------
def fit(ms,ref,hl=300):
    W=[(0.5**(max((ref-d).days,0)/hl),h,a,x,y) for d,h,a,x,y in ms]
    T={t for w,h,a,x,y in W for t in(h,a)};A={t:1.0 for t in T};Dd=dict(A);H=1.3
    for _ in range(50):
        n=defaultdict(float);dn=defaultdict(float)
        for w,h,a,x,y in W:n[h]+=w*x;dn[h]+=w*Dd[a]*H;n[a]+=w*y;dn[a]+=w*Dd[h]
        A={t:(n[t]+2)/(dn[t]+2) for t in T}
        n=defaultdict(float);dn=defaultdict(float)
        for w,h,a,x,y in W:n[h]+=w*y;dn[h]+=w*A[a];n[a]+=w*x;dn[a]+=w*A[h]*H
        Dd={t:(n[t]+2)/(dn[t]+2) for t in T}
        H=sum(w*x for w,h,a,x,y in W)/sum(w*A[h]*Dd[a] for w,h,a,x,y in W)
        k=sum(A.values())/len(A);A={t:v/k for t,v in A.items()};Dd={t:v*k for t,v in Dd.items()}
    return A,Dd,H
def pr(A,Dd,H,h,a,I=None):
    lh=A.get(h,1)*Dd.get(a,1)*H;la=A.get(a,1)*Dd.get(h,1)
    if I and h in I and a in I:lh*=I[h]['attf']*I[a]['deff'];la*=I[a]['attf']*I[h]['deff']
    w=d=l=0;b=(0,0,-1)
    for i in range(10):
        pi=math.exp(-lh)*lh**i/math.factorial(i)
        for j in range(10):
            p=pi*math.exp(-la)*la**j/math.factorial(j)
            if p>b[2]:b=(i,j,p)
            if i>j:w+=p
            elif i==j:d+=p
            else:l+=p
    t=w+d+l;return dict(w=round(w/t,3),d=round(d/t,3),l=round(l/t,3),s=[b[0],b[1]])
pick=lambda p:max((p['w'],'H'),(p['d'],'D'),(p['l'],'A'))[1]
res3=lambda x,y:'H' if x>y else 'D' if x==y else 'A'
# backtest: ฝึกด้วยข้อมูลก่อน 100 นัดล่าสุด แล้วทาย 100 นัดนั้น
N=100;tr,te=M[:-N],M[-N:];A0,D0,H0=fit(tr,te[0][0]);ok=ex=bs_=n=0
for d,h,a,x,y in te:
    if h in A0 and a in A0:
        p=pr(A0,D0,H0,h,a);n+=1;ok+=pick(p)==res3(x,y);ex+=tuple(p['s'])==(x,y);bs_+=res3(x,y)=='H'
bt=dict(n=n,acc=round(ok/n*100),exact=round(ex/n*100),base=round(bs_/n*100))
A,Dd,H=fit(M,TODAY)
# ---------- บันทึกผลทาย (เทียบกับผลจริงทีหลัง) ----------
LP=DATA+'/predictions.json';log=json.load(open(LP)) if os.path.exists(LP) else {}
for d,h,a in FX:
    k=f'{d}|{h}|{a}'
    if d>=TODAY and d<=TODAY+dt.timedelta(10) and (d>TODAY or k not in log):
        log[k]=dict(d=str(d),h=h,a=a,b=pr(A,Dd,H,h,a),i=pr(A,Dd,H,h,a,INJ) if inj_ok else None)
json.dump(log,open(LP,'w'),ensure_ascii=False,indent=0)
res={f'{d}|{h}|{a}':(x,y) for d,h,a,x,y in M};hist=[];s=dict(n=0,b=0,i=0,eb=0,ei=0)
for k,v in sorted(log.items(),reverse=True):
    if k in res:
        x,y=res[k];r=res3(x,y);s['n']+=1;s['b']+=pick(v['b'])==r;s['eb']+=tuple(v['b']['s'])==(x,y)
        if v['i']:s['i']+=pick(v['i'])==r;s['ei']+=tuple(v['i']['s'])==(x,y)
        hist.append(dict(d=v['d'],h=v['h'],a=v['a'],x=x,y=y,b=v['b']['s'],i=v['i']['s'] if v['i'] else None,okb=pick(v['b'])==r,oki=bool(v['i']) and pick(v['i'])==r))
T=sorted(t for t in CANON if t in {h for _,h,_ in FX}|{a for _,_,a in FX})
D=dict(updated=str(TODAY),last=str(M[-1][0]),n=len(M),seasons=SEASONS,inj_ok=inj_ok,teams=T,H=round(H,3),
    att={t:round(A.get(t,1),3) for t in T},**{'def':{t:round(Dd.get(t,1),3) for t in T}},inj=INJ,
    fx=[[str(d),h,a] for d,h,a in FX if TODAY<=d<=TODAY+dt.timedelta(90)],bt=bt,acc=s,hist=hist[:40])
json.dump(D,open(DOCS+'/data.json','w'),ensure_ascii=False,separators=(',',':'))
print('ok',bt,s)
