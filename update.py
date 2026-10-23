import json,math,os,re,urllib.request,datetime as dt
from collections import defaultdict
R=os.path.dirname(os.path.abspath(__file__));DOCS=R+'/docs';DATA=R+'/data'
os.makedirs(DOCS,exist_ok=True);os.makedirs(DATA,exist_ok=True)
TODAY=dt.date.fromisoformat(os.environ['FAKE_TODAY']) if os.environ.get('FAKE_TODAY') else dt.date.today()
def get(u):
    return json.load(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=30))
y0=TODAY.year if TODAY.month>=7 else TODAY.year-1
SEASONS=[f'{y}-{str(y+1)[2:]}' for y in range(y0-7,y0+1)]
M=[];FX=[];KO={}
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
ALIAS={'man city':'manchester city','man utd':'manchester united','spurs':'tottenham hotspur','wolves':'wolverhampton wanderers',"nott'm forest":'nottingham forest','brighton':'brighton and hove albion','newcastle':'newcastle united','west ham':'west ham united','leeds':'leeds united','leicester':'leicester city','ipswich':'ipswich town','norwich':'norwich city','sheffield utd':'sheffield united','luton':'luton town','man united':'manchester united','tottenham':'tottenham hotspur','west brom':'west bromwich albion','cardiff':'cardiff city','huddersfield':'huddersfield town','stoke':'stoke city','swansea':'swansea city','hull':'hull city','norwich':'norwich city','millwall':'millwall'}
def canon(n):
    k=strip(n);k=ALIAS.get(k,k)
    if not k:return None
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
            else:FX.append((d,h,a));KO[(d,h,a)]=f['kickoff_time']
        for t in bs['teams']:
            P=[e for e in bs['elements'] if e['team']==t['id'] and e['status']!='u']
            def share(types):
                tot=sum(e['total_points'] for e in P if e['element_type'] in types) or 1
                return min(.4,sum(e['total_points']*unavail(e) for e in P if e['element_type'] in types)/tot)
            out=sorted([e for e in P if unavail(e)>=.5],key=lambda e:-e['total_points'])[:5]
            INJ[tmap[t['id']]]=dict(sa=round(share([3,4]),3),sd=round(share([1,2]),3),
                players=[dict(n=e['web_name'],news=e.get('news',''),pts=e['total_points']) for e in out])
        inj_ok=True
    else:print('FPL team mapping incomplete, skip')
except Exception as e:print('FPL skip:',e)
M.sort();FX=sorted(set(FX))
print('matches',len(M),'last',M[-1][0],'fixtures',len(FX),'injuries',inj_ok)
# ---------- ข่าว (RSS ฟรี): ใช้แสดงผลอย่างเดียว ยังไม่ปรับสกอร์ เพราะไม่มีข่าวย้อนหลังให้ทดสอบ ----------
import csv,io,xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from bisect import bisect_left
UA={'User-Agent':'Mozilla/5.0'}
NT=sorted({t for _,h,a in FX for t in(h,a)})
EXTRA={'nottingham forest':['forest'],'aston villa':['villa'],'crystal palace':['palace'],'tottenham hotspur':['spurs'],'manchester united':['man utd','man united'],'manchester city':['man city'],'wolverhampton wanderers':['wolves'],'brighton and hove albion':['brighton'],'newcastle united':['newcastle'],'west ham united':['west ham'],'leeds united':['leeds']}
def tnames(t):
    k=strip(t);return {k,*EXTRA.get(k,[])}|{x for x,v in ALIAS.items() if v==k}
NEG=['ruled out','injur','suspend','doubt','sidelined','out for','blow','setback','absence','banned','red card','miss ','misses']
POS=['return','back in training','fit again','boost','recovered','cleared']
NEWS=defaultdict(list);NETW=defaultdict(int);seen=set()
for u in('https://feeds.bbci.co.uk/sport/football/rss.xml','https://www.theguardian.com/football/premierleague/rss','https://www.skysports.com/rss/12040'):
    try:root=ET.fromstring(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=20).read())
    except Exception as e:print('news skip',u,e);continue
    src=u.split('/')[2]
    for it in root.iter('item'):
        ti=(it.findtext('title') or '').strip();ln=(it.findtext('link') or '').strip()
        try:pdt=parsedate_to_datetime(it.findtext('pubDate')).date()
        except Exception:pdt=TODAY
        low=ti.lower();sc_=-1 if any(k in low for k in NEG) else 1 if any(k in low for k in POS) else 0
        if not ti or sc_==0 or (TODAY-pdt).days>5:continue
        for t in NT:
            if (t,ti) not in seen and any(re.search(r'\b'+re.escape(n)+r'\b',low) for n in tnames(t)):
                seen.add((t,ti));NETW[t]+=sc_
                if len(NEWS[t])<3:NEWS[t].append(dict(t=ti,l=ln,s=sc_,src=src))
print('news teams',len(NEWS))
# ---------- ราคาเจ้ามือ + สถิติยิง (football-data.co.uk ฟรี ถ้าดึงไม่ได้จะข้ามไป) ----------
def fd_csv(u):
    t=urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=30).read().decode('utf-8-sig','ignore')
    return list(csv.DictReader(io.StringIO(t)))
def pdate(x):
    for f in('%d/%m/%Y','%d/%m/%y'):
        try:return dt.datetime.strptime((x or '').strip(),f).date()
        except ValueError:pass
def num(v):
    try:return float(v)
    except(TypeError,ValueError):return None
def mprob(r):
    for p in('Avg','B365'):
        o=[num(r.get(p+c)) for c in'HDA']
        if all(x and x>1 for x in o):i=[1/x for x in o];t=sum(i);return tuple(x/t for x in i)
ODDS={};SHOTS={};odds_src=[]
def addrows(rows):
    n=0
    for r in rows:
        if r.get('Div','E0')!='E0':continue
        d=pdate(r.get('Date'));h=canon(r.get('HomeTeam') or '');a=canon(r.get('AwayTeam') or '')
        if not(d and h and a):continue
        p=mprob(r)
        if p:ODDS[(d,h,a)]=p;n+=1
        sh=[num(r.get(c)) for c in('HS','AS','HST','AST')]
        if None not in sh:SHOTS[(d,h,a)]=tuple(sh)
    return n
for s_ in SEASONS:
    try:odds_src.append((s_,addrows(fd_csv(f'https://www.football-data.co.uk/mmz4281/{s_[2:4]}{s_[5:7]}/E0.csv'))))
    except Exception as e:print('odds skip',s_,e)
try:odds_src.append(('fixtures',addrows(fd_csv('https://www.football-data.co.uk/fixtures.csv'))))
except Exception as e:print('fixtures odds skip',e)
print('odds',odds_src,'shots',len(SHOTS))
def lk(D_,d,h,a):
    for k in(0,-1,1):
        v=D_.get((d+dt.timedelta(k),h,a))
        if v:return v
odds_for=lambda d,h,a:lk(ODDS,d,h,a)
GM={(d,h,a):(x,y) for d,h,a,x,y in M}
def fit_xg(cut=None):  # ประตูที่คาดจากยิงตรงกรอบ/ยิงนอกกรอบ (ถดถอยกำลังสองน้อยสุด)
    sa=sb=sab=sag=sbg=n=0
    for k,s in SHOTS.items():
        g=GM.get(k)
        if not g or (cut and k[0]>=cut):continue
        for sh,st,go in((s[0],s[2],g[0]),(s[1],s[3],g[1])):
            a_,b_=st,sh-st;sa+=a_*a_;sb+=b_*b_;sab+=a_*b_;sag+=a_*go;sbg+=b_*go;n+=1
    det=sa*sb-sab*sab
    if n<200 or det<=0:return None
    return max((sag*sb-sab*sbg)/det,0),max((sa*sbg-sab*sag)/det,0)
XG=fit_xg();print('xg coef',XG)
def adj(ms,g,co):
    out=[]
    for d,h,a,x,y in ms:
        s=lk(SHOTS,d,h,a)
        if s:out.append((d,h,a,(1-g)*x+g*(co[0]*s[2]+co[1]*(s[0]-s[2])),(1-g)*y+g*(co[0]*s[3]+co[1]*(s[1]-s[3]))))
        else:out.append((d,h,a,x,y))
    return out
ADJ={0:M}
if XG:
    for g_ in(.25,.5,1.0):ADJ[g_]=adj(M,g_,XG)
# ---------- วันพัก ----------
DATES=defaultdict(list)
for d,h,a,x,y in M:DATES[h].append(d);DATES[a].append(d)
for d,h,a in FX:DATES[h].append(d);DATES[a].append(d)
for v in DATES.values():v.sort()
def rest(t,d):
    L=DATES.get(t,[]);i=bisect_left(L,d);return (d-L[i-1]).days if i>0 else None
rfac=lambda r,rc:1.0 if (r is None or not rc) else 1-rc*max(0,5-min(r,5))
# ---------- Elo (โมเดลที่สอง ผสมเฉพาะผลแพ้/เสมอ/ชนะ) ----------
def elo_pass(K,hfa):
    R=defaultdict(lambda:1500.0);pre=[]
    for d,h,a,x,y in M:
        dr=R[h]-R[a]+hfa;pre.append(dr);e=1/(1+10**(-dr/400));sc=1 if x>y else .5 if x==y else 0
        gd=abs(x-y);m=1 if gd<2 else 1.5 if gd==2 else (11+gd)/8
        R[h]+=K*m*(sc-e);R[a]-=K*m*(sc-e)
    return pre,R
def elo3(dr,c):
    u=dr*math.log(10)/400;ph=1/(1+math.exp(-(u-c)));pa=1/(1+math.exp(u+c));return [ph,max(1-ph-pa,1e-6),pa]
def elo_tune():
    cut=len(M)-300;best=None
    for K in(12,20,30):
        for hfa in(40,70,100):
            pre,_=elo_pass(K,hfa)
            for c in(.1,.2,.3,.4,.5,.6,.7,.8,1.0):
                ll=0
                for i in range(200,cut):
                    p=elo3(pre[i],c);x,y=M[i][3],M[i][4];ll+=math.log(max(p[0] if x>y else p[1] if x==y else p[2],1e-9))
                if not best or ll>best[0]:best=(ll,K,hfa,c)
    return list(best[1:])
# ---------- โมเดลหลัก: Poisson + Dixon-Coles ----------
def fit(ms,ref,hl):
    W=[(0.5**(max((ref-d).days,0)/hl),h,a,x,y) for d,h,a,x,y in ms]
    T={t for w,h,a,x,y in W for t in(h,a)};A={t:1.0 for t in T};Dd=dict(A);H=1.3
    for _ in range(35):
        n=defaultdict(float);dn=defaultdict(float)
        for w,h,a,x,y in W:n[h]+=w*x;dn[h]+=w*Dd[a]*H;n[a]+=w*y;dn[a]+=w*Dd[h]
        A={t:(n[t]+2)/(dn[t]+2) for t in T}
        n=defaultdict(float);dn=defaultdict(float)
        for w,h,a,x,y in W:n[h]+=w*y;dn[h]+=w*A[a];n[a]+=w*x;dn[a]+=w*A[h]*H
        Dd={t:(n[t]+2)/(dn[t]+2) for t in T}
        H=sum(w*x for w,h,a,x,y in W)/sum(w*A[h]*Dd[a] for w,h,a,x,y in W)
        k=sum(A.values())/len(A);A={t:v/k for t,v in A.items()};Dd={t:v*k for t,v in Dd.items()}
    return A,Dd,H
def tau(i,j,lh,la,r):
    if i==0 and j==0:return 1-lh*la*r
    if i==0 and j==1:return 1+lh*r
    if i==1 and j==0:return 1+la*r
    if i==1 and j==1:return 1-r
    return 1
def fit_rho(ms,A,Dd,H,ref,hl):
    sub=[m for m in ms if m[3]<2 and m[4]<2 and m[1] in A and m[2] in A];best=(0,-1e18)
    for k in range(-20,11,2):
        r=k/100;ll=0
        for d,h,a,x,y in sub:
            t=tau(x,y,A[h]*Dd[a]*H,A[a]*Dd[h],r)
            if t<=0:ll=-1e18;break
            ll+=0.5**(max((ref-d).days,0)/hl)*math.log(t)
        if ll>best[1]:best=(r,ll)
    return best[0]
def hfac(ms,A,Dd,H,ref,hl,k=12):  # ค่าเจ้าบ้านรายทีม (หดเข้าหาค่ากลาง)
    n=defaultdict(float);e=defaultdict(float)
    for d,h,a,x,y in ms:
        if h in A and a in A:w=0.5**(max((ref-d).days,0)/hl);n[h]+=w*x;e[h]+=w*A[h]*Dd[a]*H
    return {t:(n[t]+k)/(e[t]+k) for t in e}
def grid(lh,la,rho):
    pi=[math.exp(-lh)*lh**i/math.factorial(i) for i in range(10)];pj=[math.exp(-la)*la**j/math.factorial(j) for j in range(10)]
    G=[[max(tau(i,j,lh,la,rho),1e-6)*pi[i]*pj[j] for j in range(10)] for i in range(10)]
    t=sum(map(sum,G));return [[v/t for v in r] for r in G]
res3=lambda x,y:'H' if x>y else 'D' if x==y else 'A'
def s3(G):
    w=d=l=0
    for i in range(10):
        for j in range(10):
            if i>j:w+=G[i][j]
            elif i==j:d+=G[i][j]
            else:l+=G[i][j]
    return w,d,l
def rescale(G,pw,pd,pl):
    w,d,l=s3(G);f={'H':pw/w,'D':pd/d,'A':pl/l};H2=[[G[i][j]*f[res3(i,j)] for j in range(10)] for i in range(10)];t=sum(map(sum,H2));return [[v/t for v in r] for r in H2]
def summ(G):
    w=d=l=o=bt=0;cells=[]
    for i in range(10):
        for j in range(10):
            p=G[i][j];cells.append((p,i,j))
            if i>j:w+=p
            elif i==j:d+=p
            else:l+=p
            if i+j>=3:o+=p
            if i>0 and j>0:bt+=p
    k='H' if w>=max(d,l) else 'D' if d>=l else 'A'
    c=sorted(cells,reverse=True);b=next(z for z in c if res3(z[1],z[2])==k)
    return dict(w=round(w,3),d=round(d,3),l=round(l,3),k=k,s=[b[1],b[2]],t3=[[z[1],z[2],round(z[0],3)] for z in c[:3]],o=round(o,3),bt=round(bt,3))
pick=lambda p:p.get('k') or max((p['w'],'H'),(p['d'],'D'),(p['l'],'A'))[1]
def mix(G,el,mk,eps,lam):
    t=list(s3(G))
    if eps>0 and el:t=[(1-eps)*t[i]+eps*el[i] for i in range(3)]
    if lam>0 and mk:t=[(1-lam)*t[i]+lam*mk[i] for i in range(3)]
    return rescale(G,*t) if (eps>0 and el) or (lam>0 and mk) else G
def build_G(r,hf=False,rc=0,dc=True,eps=0,lam=0):
    lh=r['lh']*(r['hf'] if hf else 1)*rfac(r['rh'],rc);la=r['la']*rfac(r['ra'],rc)
    return mix(grid(lh,la,r['rho'] if dc else 0),r['el'],r['mk'],eps,lam)
def mets(G,x,y):
    x,y=min(x,9),min(y,9);S=summ(G);act=res3(x,y);E=sum((i+j)*G[i][j] for i in range(10) for j in range(10))
    return dict(ll=math.log(max(G[x][y],1e-9)),acc=S['k']==act,ex=S['s']==[x,y],t3=any(c[0]==x and c[1]==y for c in S['t3']),ou=(S['o']>.5)==(x+y>=3),bt=(S['bt']>.5)==(x>0 and y>0),mae=abs(E-x-y))
def agg(L):
    n=len(L);o={k:round(sum(m[k] for m in L)/n*100,1) for k in('acc','ex','t3','ou','bt')}
    o['ll']=round(sum(m['ll'] for m in L)/n,3);o['mae']=round(sum(m['mae'] for m in L)/n,2);return o
KW=lambda P:{k:P[k] for k in('hf','rc','dc','eps','lam')}
aggr=lambda recs,**kw:agg([mets(build_G(r,**kw),r['x'],r['y']) for r in recs])
def llmean(recs,**kw):return sum(math.log(max(build_G(r,**kw)[min(r['x'],9)][min(r['y'],9)],1e-9)) for r in recs)/len(recs)
BL,NB=6,50
def evaluate(hl,g):  # backtest เดินหน้า: ฝึกด้วยข้อมูลก่อนแต่ละช่วง แล้วทายช่วงนั้น
    recs=[];tot=len(M)
    for b in range(BL):
        s0=tot-(BL-b)*NB;ref=M[s0][0]
        co=fit_xg(ref) if g else None;ADs=adj(M[:s0],g,co) if co else M[:s0]
        A,Dd,H=fit(ADs,ref,hl);rho=fit_rho(M[:s0],A,Dd,H,ref,hl);HF=hfac(ADs,A,Dd,H,ref,hl)
        mh=sum(m[3] for m in M[:s0])/s0;ma=sum(m[4] for m in M[:s0])/s0
        for k in range(s0,min(s0+NB,tot)):
            d,h,a,x,y=M[k]
            if h in A and a in A:recs.append(dict(lh=A[h]*Dd[a]*H,la=A[a]*Dd[h],hf=HF.get(h,1),rho=rho,x=x,y=y,mk=odds_for(d,h,a),el=ELO3[k],rh=rest(h,d),ra=rest(a,d),bh=mh,ba=ma))
    return recs
def lls(recs,**kw):return [math.log(max(build_G(r,**kw)[min(r['x'],9)][min(r['y'],9)],1e-9)) for r in recs]
def better(a,b):  # b ดีกว่า a ชัดเจนไหม: ผลต่างเฉลี่ยรายนัดต้องเกิน 1 ค่าคลาดเคลื่อนมาตรฐานแบบจับคู่
    if len(a)!=len(b) or len(a)<30:return False
    d=[y-x for x,y in zip(a,b)];n=len(d);m=sum(d)/n;se=(sum((v-m)**2 for v in d)/(n-1)/n)**.5
    return m>se
def choose(recs):
    P=dict(dc=False,hf=False,rc=0.0,eps=0.0,lam=0.0);cur=lls(recs,**KW(P))
    for key,opts in(('dc',[False,True]),('hf',[False,True]),('rc',[0.0,.01,.02,.03]),('eps',[0.0,.25,.5])):
        for v in opts[1:]:
            c=lls(recs,**KW({**P,key:v}))
            if better(cur,c):P[key]=v;cur=c
    return P
TP=DATA+'/tune.json';tune=None
if os.path.exists(TP):
    t=json.load(open(TP))
    if (TODAY-dt.date.fromisoformat(t['date'])).days<14 and t.get('odds_tested')==bool(ODDS) and t.get('shots_tested')==bool(XG) and t.get('v')==3:tune=t
EL=tune['elo'] if tune else elo_tune()
PRE,ELOR=elo_pass(EL[0],EL[1]);ELO3=[elo3(v,EL[2]) for v in PRE]
if not tune:
    r0=evaluate(400,0);best=[400,0,r0,lls(r0,dc=True)]  # ตั้งต้นที่ 400 วัน/ไม่ใช้สถิติยิง ตัวอื่นต้องชนะชัดเจนถึงจะแทนที่
    for hl in(120,250,700):
        r_=evaluate(hl,0);c=lls(r_,dc=True);print('half-life',hl,round(sum(c)/len(c),4))
        if better(best[3],c):best=[hl,0,r_,c]
    if XG:
        for g in(.25,.5,1.0):
            r_=evaluate(best[0],g);c=lls(r_,dc=True);print('shots weight',g,round(sum(c)/len(c),4))
            if better(best[3],c):best=[best[0],g,r_,c]
    recs=best[2];P=choose(recs);P['hl']=best[0];P['g']=best[1];blend={}
    mr=[r for r in recs if r['mk']]
    if ODDS and len(mr)>=60:
        cur=lls(mr,**KW(P))
        for lam in(.25,.5,.75):
            c=lls(mr,**KW({**P,'lam':lam}))
            if better(cur,c):P['lam']=lam;cur=c
        blend={str(l):{**aggr(mr,**KW({**P,'lam':l})),'n':len(mr)} for l in(0,.25,.5,.75,1)}
    tb=dict(base=agg([mets(grid(r['bh'],r['ba'],0),r['x'],r['y']) for r in recs]),po=aggr(recs,dc=False),full=aggr(recs,**KW({**P,'lam':0.0})))
    tune=dict(v=3,date=str(TODAY),odds_tested=bool(ODDS),shots_tested=bool(XG),elo=EL,P=P,n=len(recs),tb=tb,blend=blend)
    json.dump(tune,open(TP,'w'))
P=tune['P'];HL=P['hl'];GW=P['g'];AD=ADJ.get(GW,M)
A,Dd,H=fit(AD,TODAY,HL);rho=fit_rho(M,A,Dd,H,TODAY,HL);HF=hfac(AD,A,Dd,H,TODAY,HL) if P['hf'] else {}
LAM=P['lam'] if ODDS else 0.0
print('params',P)
# ---------- ผลทายที่บันทึกไว้ + จูนค่าถ่วงตัวเจ็บจากผลจริงที่สะสม ----------
LP=DATA+'/predictions.json';log=json.load(open(LP)) if os.path.exists(LP) else {}
res={f'{d}|{h}|{a}':(x,y) for d,h,a,x,y in M}
def final_G(raw,sh=None,coef=0.0):
    lh,la=raw['lh'],raw['la']
    if sh:lh*=(1-coef*sh[0])*(1+coef*sh[3]);la*=(1-coef*sh[2])*(1+coef*sh[1])
    return mix(grid(lh,la,raw['rho']),raw['el'],raw['mk'],raw['eps'],raw['lam'])
def coef_pick():
    rows=[(v,res[k]) for k,v in log.items() if k in res and v.get('raw') and v.get('sh')]
    if len(rows)<40:return 0.5,len(rows)
    sc={c:sum(math.log(max(final_G(v['raw'],v['sh'],c)[min(x,9)][min(y,9)],1e-9)) for v,(x,y) in rows) for c in(0,.25,.5,.75,1.0)}
    b=0
    for c in(.25,.5,.75,1.0):
        if sc[c]>sc[b]+0.0005*len(rows):b=c
    return b,len(rows)
COEF,NCOEF=coef_pick()
def raw_for(d,h,a):
    return dict(lh=A.get(h,1)*Dd.get(a,1)*H*HF.get(h,1)*rfac(rest(h,d),P['rc']),la=A.get(a,1)*Dd.get(h,1)*rfac(rest(a,d),P['rc']),rho=rho if P['dc'] else 0.0,
        el=elo3(ELOR[h]-ELOR[a]+EL[1],EL[2]),mk=odds_for(d,h,a),eps=P['eps'],lam=LAM)
def out(G,raw):
    r=summ(G);r['lh']=round(sum(i*sum(G[i]) for i in range(10)),2);r['la']=round(sum(j*G[i][j] for i in range(10) for j in range(10)),2)
    if raw['mk']:r['mk']=[round(v,3) for v in raw['mk']]
    return r
PRED={};LOGP={}
for d,h,a in FX:
    if TODAY<=d<=TODAY+dt.timedelta(6):
        raw=raw_for(d,h,a);sh=None
        if inj_ok:g=lambda t,k:INJ.get(t,{}).get(k,0);sh=[g(h,'sa'),g(h,'sd'),g(a,'sa'),g(a,'sd')]
        PRED[(d,h,a)]=dict(b=out(final_G(raw),raw),i=out(final_G(raw,sh,COEF),raw) if sh else None)
        LOGP[(d,h,a)]=dict(raw=raw,sh=sh,nw=[NETW.get(h,0),NETW.get(a,0)])
for (d,h,a),p in PRED.items():
    k=f'{d}|{h}|{a}'
    if d>TODAY or k not in log:log[k]=dict(d=str(d),h=h,a=a,**p,**LOGP[(d,h,a)])
json.dump(log,open(LP,'w'),ensure_ascii=False,indent=0)
hist=[];ST=dict(n=0,b=0,i=0,ni=0,eb=0,ei=0,nt=0,t3=0)
for k,v in sorted(log.items(),reverse=True):
    if k in res:
        x,y=res[k];r=res3(x,y);ST['n']+=1;ST['b']+=pick(v['b'])==r;ST['eb']+=tuple(v['b']['s'])==(x,y);h3=None
        if 't3' in v['b']:h3=any((c[0],c[1])==(x,y) for c in v['b']['t3']);ST['nt']+=1;ST['t3']+=h3
        if v['i']:ST['ni']+=1;ST['i']+=pick(v['i'])==r;ST['ei']+=tuple(v['i']['s'])==(x,y)
        hist.append(dict(d=v['d'],h=v['h'],a=v['a'],x=x,y=y,b=v['b']['s'],i=v['i']['s'] if v['i'] else None,okb=pick(v['b'])==r,oki=bool(v['i']) and pick(v['i'])==r,pb=pick(v['b']),pi=pick(v['i']) if v['i'] else None,r=r,h3=h3))
T=sorted(t for t in CANON if t in set(NT))
TB={t:[0]*6 for t in T}
for d,h,a,x,y in M:
    if d<dt.date(y0,7,1):continue
    for t,gf,ga in((h,x,y),(a,y,x)):
        r=TB.setdefault(t,[0]*6);r[0]+=1;r[4]+=gf;r[5]+=ga
        if gf>ga:r[1]+=1
        elif gf==ga:r[2]+=1
        else:r[3]+=1
table=sorted(([t,r[0],r[1],r[2],r[3],r[4],r[5],r[4]-r[5],r[1]*3+r[2]] for t,r in TB.items() if t in T),key=lambda z:(-z[8],-z[7],-z[5]))
NOW=os.environ['FAKE_TODAY']+' 00:00' if os.environ.get('FAKE_TODAY') else dt.datetime.now(dt.timezone(dt.timedelta(hours=7))).strftime('%Y-%m-%d %H:%M')
INJ_OUT={t:dict(players=v['players']) for t,v in INJ.items()}
D=dict(updated=str(TODAY),updated_at=NOW,table=table,last=str(M[-1][0]),n=len(M),seasons=SEASONS,inj_ok=inj_ok,teams=T,inj=INJ_OUT,news=NEWS,
    fx=[[str(d),h,a,KO.get((d,h,a),''),PRED[(d,h,a)]] for (d,h,a) in sorted(PRED)],bt=tune,coef=COEF,ncoef=NCOEF,acc=ST,hist=hist[:40])
json.dump(D,open(DOCS+'/data.json','w'),ensure_ascii=False,separators=(',',':'))
print('ok',tune['tb'],tune['blend'].get('0.5'),COEF,NCOEF)
