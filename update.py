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
            INJ[tmap[t['id']]]=dict(attf=round(1-COEF*share([3,4]),3),deff=round(1+COEF*share([1,2]),3),
                players=[dict(n=e['web_name'],news=e.get('news',''),pts=e['total_points']) for e in out])
        inj_ok=True
    else:print('FPL team mapping incomplete, skip')
except Exception as e:print('FPL skip:',e)
M.sort();FX=sorted(set(FX))
print('matches',len(M),'last',M[-1][0],'fixtures',len(FX),'injuries',inj_ok)
# ---------- ราคาเจ้ามือ (football-data.co.uk ฟรี ถ้าดึงไม่ได้จะข้ามไป) ----------
import csv,io
def fd_csv(u):
    t=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=30).read().decode('utf-8-sig','ignore')
    return list(csv.DictReader(io.StringIO(t)))
def pdate(s):
    for f in('%d/%m/%Y','%d/%m/%y'):
        try:return dt.datetime.strptime((s or '').strip(),f).date()
        except ValueError:pass
def mprob(r):
    for p in('Avg','B365'):
        try:o=[float(r[p+c]) for c in'HDA']
        except(KeyError,ValueError,TypeError):continue
        if all(x>1 for x in o):i=[1/x for x in o];t=sum(i);return tuple(x/t for x in i)
ODDS={};odds_src=[]
def addodds(rows):
    n=0
    for r in rows:
        if r.get('Div','E0')!='E0':continue
        d=pdate(r.get('Date'));h=canon(r.get('HomeTeam') or '');a=canon(r.get('AwayTeam') or '');p=mprob(r)
        if d and h and a and p:ODDS[(d,h,a)]=p;n+=1
    return n
for s_ in SEASONS[-3:]:
    try:odds_src.append((s_,addodds(fd_csv(f'https://www.football-data.co.uk/mmz4281/{s_[2:4]}{s_[5:7]}/E0.csv'))))
    except Exception as e:print('odds skip',s_,e)
try:odds_src.append(('fixtures',addodds(fd_csv('https://www.football-data.co.uk/fixtures.csv'))))
except Exception as e:print('fixtures odds skip',e)
print('odds',odds_src)
def odds_for(d,h,a):
    for k in(0,-1,1):
        v=ODDS.get((d+dt.timedelta(k),h,a))
        if v:return v
# ---------- โมเดล: Poisson + Dixon-Coles ----------
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
def fit_rho(ms,A,Dd,H,ref,hl):  # ค่าแก้ Dixon-Coles สำหรับสกอร์ต่ำ
    sub=[m for m in ms if m[3]<2 and m[4]<2 and m[1] in A and m[2] in A];best=(0,-1e18)
    for k in range(-20,11,2):
        r=k/100;ll=0
        for d,h,a,x,y in sub:
            t=tau(x,y,A[h]*Dd[a]*H,A[a]*Dd[h],r)
            if t<=0:ll=-1e18;break
            ll+=0.5**(max((ref-d).days,0)/hl)*math.log(t)
        if ll>best[1]:best=(r,ll)
    return best[0]
def grid(lh,la,rho):
    pi=[math.exp(-lh)*lh**i/math.factorial(i) for i in range(10)];pj=[math.exp(-la)*la**j/math.factorial(j) for j in range(10)]
    G=[[max(tau(i,j,lh,la,rho),1e-6)*pi[i]*pj[j] for j in range(10)] for i in range(10)]
    t=sum(map(sum,G));return [[v/t for v in r] for r in G]
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
    c=sorted(cells,reverse=True);b=next(z for z in c if ('H' if z[1]>z[2] else 'D' if z[1]==z[2] else 'A')==k)
    return dict(w=round(w,3),d=round(d,3),l=round(l,3),k=k,s=[b[1],b[2]],t3=[[z[1],z[2],round(z[0],3)] for z in c[:3]],o=round(o,3),bt=round(bt,3))
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
def pr(A,Dd,H,rho,h,a,I=None,mk=None,lam=0):
    lh=A.get(h,1)*Dd.get(a,1)*H;la=A.get(a,1)*Dd.get(h,1)
    if I and h in I and a in I:lh*=I[h]['attf']*I[a]['deff'];la*=I[a]['attf']*I[h]['deff']
    G=grid(lh,la,rho)
    if mk and lam>0:
        w,d,l=s3(G);G=rescale(G,(1-lam)*w+lam*mk[0],(1-lam)*d+lam*mk[1],(1-lam)*l+lam*mk[2])
    r=summ(G);r['lh']=round(sum(i*sum(G[i]) for i in range(10)),2);r['la']=round(sum(j*G[i][j] for i in range(10) for j in range(10)),2)
    if mk:r['mk']=[round(v,3) for v in mk]
    return r
pick=lambda p:p.get('k') or max((p['w'],'H'),(p['d'],'D'),(p['l'],'A'))[1]
res3=lambda x,y:'H' if x>y else 'D' if x==y else 'A'
def mets(G,x,y):
    x,y=min(x,9),min(y,9);S=summ(G);act=res3(x,y)
    E=sum((i+j)*G[i][j] for i in range(10) for j in range(10))
    return dict(ll=math.log(max(G[x][y],1e-9)),acc=S['k']==act,ex=S['s']==[x,y],t3=any(c[0]==x and c[1]==y for c in S['t3']),ou=(S['o']>.5)==(x+y>=3),bt=(S['bt']>.5)==(x>0 and y>0),mae=abs(E-x-y))
def agg(L):
    n=len(L);o={k:round(sum(m[k] for m in L)/n*100,1) for k in('acc','ex','t3','ou','bt')}
    o['ll']=round(sum(m['ll'] for m in L)/n,3);o['mae']=round(sum(m['mae'] for m in L)/n,2);return o
BL,NB=6,50
def blend_eval(rec):
    out={}
    for lam in(0,.25,.5,.75,1):
        L=[]
        for G,x,y,mk in rec:
            if mk is None:continue
            w,d,l=s3(G);L.append(mets(rescale(G,(1-lam)*w+lam*mk[0],(1-lam)*d+lam*mk[1],(1-lam)*l+lam*mk[2]),x,y))
        if L:out[str(lam)]={**agg(L),'n':len(L)}
    return out
def evaluate(hl):  # backtest เดินหน้า: ฝึกด้วยข้อมูลก่อนแต่ละช่วง แล้วทายช่วงนั้น
    R={'dc':[],'po':[],'base':[],'rec':[]};tot=len(M)
    for b in range(BL):
        s0=tot-(BL-b)*NB;blk=M[s0:s0+NB];tr=M[:s0];ref=blk[0][0]
        A,Dd,H=fit(tr,ref,hl);rho=fit_rho(tr,A,Dd,H,ref,hl)
        mh=sum(m[3] for m in tr)/len(tr);ma=sum(m[4] for m in tr)/len(tr)
        for d,h,a,x,y in blk:
            if h not in A or a not in A:continue
            lh=A[h]*Dd[a]*H;la=A[a]*Dd[h]
            G=grid(lh,la,rho);R['rec'].append((G,x,y,odds_for(d,h,a)));R['dc'].append(mets(G,x,y));R['po'].append(mets(grid(lh,la,0),x,y));R['base'].append(mets(grid(mh,ma,0),x,y))
    return R
TP=DATA+'/tune.json';tune=None
if os.path.exists(TP):
    t=json.load(open(TP))
    if (TODAY-dt.date.fromisoformat(t['date'])).days<14 and t.get('odds_tested')==bool(ODDS):tune=t
if not tune:
    best=None
    for hl in(120,250,400,700):
        R=evaluate(hl);ll=sum(m['ll'] for m in R['dc'])/len(R['dc']);print('half-life',hl,'score loglik',round(ll,4))
        if not best or ll>best[0]:best=(ll,hl,R)
    R=best[2];ag={k:agg(R[k]) for k in('dc','po','base')}
    tune=dict(date=str(TODAY),hl=best[1],use_dc=ag['dc']['ll']>ag['po']['ll'],n=len(R['dc']),odds_tested=bool(ODDS),lam=0.0,blend={},**ag)
    if ODDS:
        bl=blend_eval(R['rec'])
        if bl and min(v['n'] for v in bl.values())>=60:
            tune['blend']=bl;tune['lam']=float(max(bl,key=lambda k:bl[k]['ll']))
    json.dump(tune,open(TP,'w'))
HL=tune['hl'];A,Dd,H=fit(M,TODAY,HL);rho=fit_rho(M,A,Dd,H,TODAY,HL) if tune['use_dc'] else 0.0
print('tuned',HL,tune['use_dc'],rho)
# ---------- บันทึกผลทาย (เทียบกับผลจริงทีหลัง) ----------
LAM=tune.get('lam',0.0) if ODDS else 0.0
PRED={}
for d,h,a in FX:
    if TODAY<=d<=TODAY+dt.timedelta(6):
        mk=odds_for(d,h,a)
        PRED[(d,h,a)]=dict(b=pr(A,Dd,H,rho,h,a,None,mk,LAM),i=pr(A,Dd,H,rho,h,a,INJ,mk,LAM) if inj_ok else None)
LP=DATA+'/predictions.json';log=json.load(open(LP)) if os.path.exists(LP) else {}
for (d,h,a),p in PRED.items():
    k=f'{d}|{h}|{a}'
    if d>TODAY or k not in log:log[k]=dict(d=str(d),h=h,a=a,**p)
json.dump(log,open(LP,'w'),ensure_ascii=False,indent=0)
res={f'{d}|{h}|{a}':(x,y) for d,h,a,x,y in M};hist=[];s=dict(n=0,b=0,i=0,ni=0,eb=0,ei=0,nt=0,t3=0)
for k,v in sorted(log.items(),reverse=True):
    if k in res:
        x,y=res[k];r=res3(x,y);s['n']+=1;s['b']+=pick(v['b'])==r;s['eb']+=tuple(v['b']['s'])==(x,y)
        h3=None
        if 't3' in v['b']:h3=any((c[0],c[1])==(x,y) for c in v['b']['t3']);s['nt']+=1;s['t3']+=h3
        if v['i']:s['ni']+=1;s['i']+=pick(v['i'])==r;s['ei']+=tuple(v['i']['s'])==(x,y)
        hist.append(dict(d=v['d'],h=v['h'],a=v['a'],x=x,y=y,b=v['b']['s'],i=v['i']['s'] if v['i'] else None,okb=pick(v['b'])==r,oki=bool(v['i']) and pick(v['i'])==r,pb=pick(v['b']),pi=pick(v['i']) if v['i'] else None,r=r,h3=h3))
T=sorted(t for t in CANON if t in {h for _,h,_ in FX}|{a for _,_,a in FX})
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
D=dict(updated=str(TODAY),updated_at=NOW,table=table,last=str(M[-1][0]),n=len(M),seasons=SEASONS,inj_ok=inj_ok,teams=T,H=round(H,3),rho=round(rho,3),
    att={t:round(A.get(t,1),3) for t in T},**{'def':{t:round(Dd.get(t,1),3) for t in T}},inj=INJ,
    fx=[[str(d),h,a,KO.get((d,h,a),''),PRED[(d,h,a)]] for (d,h,a) in sorted(PRED)],bt=tune,acc=s,hist=hist[:40])
json.dump(D,open(DOCS+'/data.json','w'),ensure_ascii=False,separators=(',',':'))
print('ok',tune['dc'],tune['blend'],tune['lam'],s)
