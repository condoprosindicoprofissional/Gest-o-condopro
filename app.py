import os, sqlite3, uuid, hashlib, calendar
from datetime import date, datetime
import streamlit as st
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image as RLImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm

BASE=os.path.dirname(os.path.abspath(__file__))
DB=os.path.join(BASE,"data","condopro.db"); UP=os.path.join(BASE,"uploads"); LOGO=os.path.join(BASE,"logo_condopro.jpg")
os.makedirs(os.path.dirname(DB),exist_ok=True); os.makedirs(UP,exist_ok=True)
NAVY=colors.HexColor("#123A5A"); BLUE=colors.HexColor("#075B9C"); LIGHT=colors.HexColor("#EAF2F8")

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def h(s): return hashlib.sha256(s.encode()).hexdigest()
def init():
    c=db(); c.executescript("""
    CREATE TABLE IF NOT EXISTS usuarios(id INTEGER PRIMARY KEY,nome TEXT,login TEXT UNIQUE,senha TEXT,perfil TEXT);
    CREATE TABLE IF NOT EXISTS condominios(id INTEGER PRIMARY KEY,nome TEXT NOT NULL,cnpj TEXT,endereco TEXT,sindico TEXT,banco TEXT,conta TEXT,saldo_inicial REAL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS unidades(id INTEGER PRIMARY KEY,condominio_id INTEGER,unidade TEXT,morador TEXT,fracao REAL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS fornecedores(id INTEGER PRIMARY KEY,nome TEXT NOT NULL,documento TEXT,categoria TEXT,contato TEXT);
    CREATE TABLE IF NOT EXISTS lancamentos(id INTEGER PRIMARY KEY,condominio_id INTEGER,competencia TEXT,data TEXT,tipo TEXT,categoria TEXT,descricao TEXT,fornecedor TEXT,forma TEXT,documento TEXT,credito REAL DEFAULT 0,debito REAL DEFAULT 0,comprovante TEXT,observacoes TEXT);
    CREATE TABLE IF NOT EXISTS contas(id INTEGER PRIMARY KEY,condominio_id INTEGER,tipo TEXT,descricao TEXT,fornecedor TEXT,vencimento TEXT,valor REAL,status TEXT DEFAULT 'Pendente',data_pagamento TEXT,comprovante TEXT);
    CREATE TABLE IF NOT EXISTS cobrancas(id INTEGER PRIMARY KEY,condominio_id INTEGER,unidade TEXT,competencia TEXT,vencimento TEXT,valor REAL,status TEXT DEFAULT 'Pendente',data_pagamento TEXT);
    CREATE TABLE IF NOT EXISTS fechamentos(id INTEGER PRIMARY KEY,condominio_id INTEGER,competencia TEXT,fechado_em TEXT, UNIQUE(condominio_id,competencia));
    CREATE TABLE IF NOT EXISTS auditoria(id INTEGER PRIMARY KEY,usuario TEXT,acao TEXT,entidade TEXT,referencia TEXT,data_hora TEXT);
    """)
    if c.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]==0:
        c.execute("INSERT INTO usuarios(nome,login,senha,perfil) VALUES(?,?,?,?)",("Administrador CondoPro","admin",h("condopro123"),"Administrador"))
    if c.execute("SELECT COUNT(*) FROM condominios").fetchone()[0]==0:
        c.execute("INSERT INTO condominios(nome,sindico,saldo_inicial) VALUES(?,?,?)",("Condomínio do Edifício Solar José Bonifácio","Bruno Costa Leandro",2229.32))
    c.commit(); c.close()
def brl(v):
    s=f"{float(v or 0):,.2f}"; return "R$ "+s.replace(",","X").replace(".",",").replace("X",".")
def conds():
    c=db(); r=c.execute("SELECT * FROM condominios ORDER BY nome").fetchall(); c.close(); return r
def bounds(comp):
    y,m=map(int,comp.split("-")); start=f"{y:04d}-{m:02d}-01"; end=f"{y+1:04d}-01-01" if m==12 else f"{y:04d}-{m+1:02d}-01"; return start,end
def moves(cid,comp):
    a,b=bounds(comp); c=db(); d=pd.read_sql_query("SELECT * FROM lancamentos WHERE condominio_id=? AND data>=? AND data<? ORDER BY data,id",c,params=(cid,a,b)); c.close(); return d
def closed(cid,comp):
    c=db(); x=c.execute("SELECT 1 FROM fechamentos WHERE condominio_id=? AND competencia=?",(cid,comp)).fetchone(); c.close(); return bool(x)
def summary(cid,comp):
    c=db(); co=c.execute("SELECT * FROM condominios WHERE id=?",(cid,)).fetchone(); c.close(); d=moves(cid,comp)
    rec=float(d.credito.sum()) if not d.empty else 0; desp=float(d.debito.sum()) if not d.empty else 0
    return co,d,rec,desp,float(co["saldo_inicial"] or 0)+rec-desp
def save_upload(f):
    if not f:return ""
    p=os.path.join(UP,uuid.uuid4().hex+os.path.splitext(f.name)[1])
    open(p,"wb").write(f.getbuffer()); return p

def audit(acao, entidade, referencia=""):
    try:
        c=db(); c.execute("INSERT INTO auditoria(usuario,acao,entidade,referencia,data_hora) VALUES(?,?,?,?,?)",(st.session_state.get("user",{}).get("login","sistema"),acao,entidade,str(referencia),datetime.now().isoformat(timespec="seconds")))
        c.commit(); c.close()
    except Exception: pass


def pdf(cid,comp):
    co,d,rec,desp,saldo=summary(cid,comp); p=os.path.join(BASE,f"Livro_CondoPro_{cid}_{comp}.pdf")
    ss=getSampleStyleSheet(); ss.add(ParagraphStyle(name="T",parent=ss["Title"],textColor=NAVY,fontSize=22,alignment=TA_CENTER)); ss.add(ParagraphStyle(name="H",parent=ss["Heading2"],textColor=NAVY))
    doc=SimpleDocTemplate(p,pagesize=A4,rightMargin=14*mm,leftMargin=14*mm,topMargin=14*mm,bottomMargin=14*mm)
    s=[]
    if os.path.exists(LOGO): s += [RLImage(LOGO,width=55*mm,height=36*mm)]
    s += [Paragraph("LIVRO DE PRESTAÇÃO DE CONTAS",ss["T"]),Spacer(1,5*mm),Paragraph(co["nome"],ss["Heading2"]),Paragraph(f"Competência: {comp[5:]}/{comp[:4]} | Síndico: {co['sindico'] or ''}",ss["Normal"]),Spacer(1,8*mm)]
    t=Table([["Saldo anterior",brl(co["saldo_inicial"])],["Receitas",brl(rec)],["Despesas",brl(desp)],["Saldo atual",brl(saldo)]],colWidths=[75*mm,55*mm])
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),LIGHT),("TEXTCOLOR",(0,0),(-1,-1),NAVY),("GRID",(0,0),(-1,-1),.3,colors.lightgrey),("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),("PADDING",(0,0),(-1,-1),7)])); s += [t,PageBreak(),Paragraph("Livro diário de lançamentos",ss["H"])]
    run=float(co["saldo_inicial"] or 0); rows=[["Data","Descrição","Crédito","Débito","Saldo"]]
    for _,r in d.iterrows():
        run += float(r.credito or 0)-float(r.debito or 0); rows.append([pd.to_datetime(r.data).strftime("%d/%m/%Y"),str(r.descricao)[:48],brl(r.credito),brl(r.debito),brl(run)])
    tt=Table(rows,repeatRows=1,colWidths=[23*mm,83*mm,27*mm,27*mm,27*mm]); tt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTSIZE",(0,0),(-1,-1),7),("GRID",(0,0),(-1,-1),.25,colors.lightgrey)])); s += [tt,PageBreak(),Paragraph("Demonstrativo do resultado do exercício",ss["H"])]
    if not d.empty:
        g=d.groupby("categoria",as_index=False)[["credito","debito"]].sum(); rr=[["Categoria","Receitas","Despesas"]]+[[x.categoria,brl(x.credito),brl(x.debito)] for _,x in g.iterrows()]+[["TOTAL",brl(rec),brl(desp)]]
        q=Table(rr,repeatRows=1,colWidths=[90*mm,45*mm,45*mm]); q.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.3,colors.lightgrey)])); s += [q]
    s += [PageBreak(),Paragraph("Relatório de despesas e comprovantes",ss["H"])]
    for _,r in d[d.debito>0].iterrows():
        s += [Paragraph(f"<b>{pd.to_datetime(r.data).strftime('%d/%m/%Y')} — {r.categoria} — {brl(r.debito)}</b>",ss["Normal"]),Paragraph(f"{r.descricao} | Prestador: {r.fornecedor or '-'} | Documento: {r.documento or '-'}",ss["Normal"]),Spacer(1,3*mm)]
        if r.comprovante and os.path.exists(r.comprovante) and r.comprovante.lower().endswith((".jpg",".jpeg",".png")):
            try:s += [RLImage(r.comprovante,width=145*mm,height=90*mm),Spacer(1,5*mm)]
            except:pass
    s += [PageBreak(),Paragraph("Assinaturas",ss["H"]),Spacer(1,30*mm),Paragraph("____________________________________<br/>Bruno Costa Leandro — Síndico",ss["Normal"])]
    doc.build(s); return p

init()
st.set_page_config(page_title="CondoPro Gestão",page_icon="🏢",layout="wide")
st.markdown("<style>.block-container{padding-top:1rem}h1,h2,h3{color:#123A5A}.stMetric{border:1px solid #dbe8f1;border-radius:10px;padding:10px}</style>",unsafe_allow_html=True)
if "user" not in st.session_state:
    st.title("CondoPro Gestão")
    with st.form("login"):
        u=st.text_input("Usuário"); pw=st.text_input("Senha",type="password")
        if st.form_submit_button("Entrar",type="primary"):
            c=db(); x=c.execute("SELECT * FROM usuarios WHERE login=? AND senha=?",(u,h(pw))).fetchone(); c.close()
            if x: st.session_state.user=dict(x); st.rerun()
            else: st.error("Usuário ou senha inválidos.")
    st.info("Primeiro acesso: admin / condopro123")
    st.stop()

st.sidebar.write(f"**{st.session_state.user['nome']}**")
if st.sidebar.button("Sair"): del st.session_state.user; st.rerun()
st.title("CondoPro — Gestão Condominial")
pages=["Dashboard","Lançamentos","Contas a pagar/receber","Inadimplência","Condomínios e unidades","Fornecedores","Fechamento e livro","Auditoria e backup"]
pg=st.sidebar.radio("Menu",pages)
cs=conds(); lab={f"{x['nome']} (ID {x['id']})":x["id"] for x in cs}

if pg=="Dashboard":
    a,b=st.columns(2); sel=a.selectbox("Condomínio",list(lab)); comp=b.text_input("Competência",date.today().strftime("%Y-%m"))
    try:
        co,d,r,e,s=summary(lab[sel],comp); x1,x2,x3,x4=st.columns(4); x1.metric("Saldo anterior",brl(co["saldo_inicial"]));x2.metric("Receitas",brl(r));x3.metric("Despesas",brl(e));x4.metric("Saldo atual",brl(s))
        if not d.empty:
            g=d.groupby("categoria")[["credito","debito"]].sum(); st.bar_chart(g)
        st.dataframe(d[["data","tipo","categoria","descricao","credito","debito"]] if not d.empty else d,use_container_width=True,hide_index=True)
    except Exception as ex: st.error(str(ex))

elif pg=="Lançamentos":
    with st.form("lan"):
        a,b,c1=st.columns(3); sel=a.selectbox("Condomínio",list(lab)); dt=b.date_input("Data"); tipo=c1.selectbox("Tipo",["Receita","Despesa"])
        cat=st.text_input("Categoria"); desc=st.text_input("Descrição"); forn=st.text_input("Fornecedor / Prestador")
        d1,d2,d3=st.columns(3); forma=d1.selectbox("Forma",["PIX","Boleto","Débito automático","Transferência","Outro"]); doc=d2.text_input("Documento"); val=d3.number_input("Valor",min_value=0.0,step=.01)
        arq=st.file_uploader("Comprovante"); obs=st.text_area("Observações")
        if st.form_submit_button("Salvar",type="primary"):
            comp=dt.strftime("%Y-%m")
            if closed(lab[sel],comp): st.error("Esta competência está fechada.")
            else:
                c=db(); c.execute("INSERT INTO lancamentos(condominio_id,competencia,data,tipo,categoria,descricao,fornecedor,forma,documento,credito,debito,comprovante,observacoes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(lab[sel],comp,dt.isoformat(),tipo,cat,desc,forn,forma,doc,val if tipo=="Receita" else 0,val if tipo=="Despesa" else 0,save_upload(arq),obs)); c.commit();c.close();audit("CRIAR","Lançamento",desc);st.success("Lançamento salvo.")

elif pg=="Contas a pagar/receber":
    with st.form("conta"):
        a,b,c1=st.columns(3); sel=a.selectbox("Condomínio",list(lab)); tipo=a.selectbox("Tipo",["Pagar","Receber"]); venc=b.date_input("Vencimento"); val=c1.number_input("Valor",min_value=0.0,step=.01)
        desc=st.text_input("Descrição"); forn=st.text_input("Fornecedor / responsável")
        if st.form_submit_button("Cadastrar"):
            c=db();c.execute("INSERT INTO contas(condominio_id,tipo,descricao,fornecedor,vencimento,valor) VALUES(?,?,?,?,?,?)",(lab[sel],tipo,desc,forn,venc.isoformat(),val));c.commit();c.close();audit("CRIAR","Conta",desc);st.success("Conta cadastrada.")
    c=db(); d=pd.read_sql_query("SELECT * FROM contas ORDER BY vencimento",c);c.close();st.dataframe(d,use_container_width=True,hide_index=True)

elif pg=="Inadimplência":
    with st.form("cob"):
        a,b,c1=st.columns(3);sel=a.selectbox("Condomínio",list(lab));uni=b.text_input("Unidade/Apto");comp=c1.text_input("Competência",date.today().strftime("%Y-%m"))
        venc=st.date_input("Vencimento");val=st.number_input("Valor",min_value=0.0,step=.01)
        if st.form_submit_button("Gerar cobrança"):
            c=db();c.execute("INSERT INTO cobrancas(condominio_id,unidade,competencia,vencimento,valor) VALUES(?,?,?,?,?)",(lab[sel],uni,comp,venc.isoformat(),val));c.commit();c.close();audit("CRIAR","Cobrança",uni+" "+comp);st.success("Cobrança cadastrada.")
    c=db();d=pd.read_sql_query("SELECT * FROM cobrancas WHERE status='Pendente' ORDER BY vencimento",c);c.close()
    st.metric("Total pendente",brl(d.valor.sum() if not d.empty else 0));st.dataframe(d,use_container_width=True,hide_index=True)

elif pg=="Condomínios e unidades":
    with st.form("co"):
        nome=st.text_input("Condomínio");cnpj=st.text_input("CNPJ");end=st.text_input("Endereço");sind=st.text_input("Síndico");banco=st.text_input("Banco");conta=st.text_input("Conta");saldo=st.number_input("Saldo inicial",step=.01)
        if st.form_submit_button("Cadastrar condomínio"):
            c=db();c.execute("INSERT INTO condominios(nome,cnpj,endereco,sindico,banco,conta,saldo_inicial) VALUES(?,?,?,?,?,?,?)",(nome,cnpj,end,sind,banco,conta,saldo));c.commit();c.close();st.success("Cadastrado.")
    st.subheader("Unidades")
    with st.form("uni"):
        sel=st.selectbox("Condomínio",list(lab),key="unico");u=st.text_input("Unidade/Apto");m=st.text_input("Morador");f=st.number_input("Fração ideal",min_value=0.0)
        if st.form_submit_button("Cadastrar unidade"):
            c=db();c.execute("INSERT INTO unidades(condominio_id,unidade,morador,fracao) VALUES(?,?,?,?)",(lab[sel],u,m,f));c.commit();c.close();st.success("Unidade cadastrada.")

elif pg=="Fornecedores":
    with st.form("fo"):
        n=st.text_input("Nome");doc=st.text_input("CNPJ/CPF");cat=st.text_input("Categoria");ct=st.text_input("Contato")
        if st.form_submit_button("Cadastrar"):
            c=db();c.execute("INSERT INTO fornecedores(nome,documento,categoria,contato) VALUES(?,?,?,?)",(n,doc,cat,ct));c.commit();c.close();st.success("Cadastrado.")
    c=db();d=pd.read_sql_query("SELECT * FROM fornecedores ORDER BY nome",c);c.close();st.dataframe(d,use_container_width=True,hide_index=True)

elif pg=="Fechamento e livro":
    a,b=st.columns(2);sel=a.selectbox("Condomínio",list(lab));comp=b.text_input("Competência",date.today().strftime("%Y-%m"))
    co,d,r,e,s=summary(lab[sel],comp);st.write(f"Receitas: **{brl(r)}** | Despesas: **{brl(e)}** | Saldo: **{brl(s)}**")
    if closed(lab[sel],comp): st.success("Competência fechada.")
    elif st.button("Fechar competência",type="primary"):
        c=db();c.execute("INSERT INTO fechamentos(condominio_id,competencia,fechado_em) VALUES(?,?,?)",(lab[sel],comp,datetime.now().isoformat()));c.commit();c.close();audit("FECHAR","Competência",comp);st.success("Competência fechada.");st.rerun()
    if st.button("Gerar Livro PDF CondoPro"):
        p=pdf(lab[sel],comp)
        with open(p,"rb") as f: st.download_button("Baixar livro",f,file_name=os.path.basename(p),mime="application/pdf")


elif pg=="Auditoria e backup":
    st.subheader("Auditoria")
    c=db()
    aud=pd.read_sql_query("SELECT usuario,acao,entidade,referencia,data_hora FROM auditoria ORDER BY id DESC LIMIT 500",c)
    st.dataframe(aud,use_container_width=True,hide_index=True)
    st.subheader("Backup e exportação")
    st.caption("Guarde uma cópia de segurança fora do computador do sistema.")
    if os.path.exists(DB):
        with open(DB,"rb") as f:
            st.download_button("Baixar banco de dados completo (.db)",f,file_name=f"condopro_backup_{date.today().isoformat()}.db",mime="application/octet-stream")
    tabela=st.selectbox("Exportar tabela",["condominios","unidades","fornecedores","lancamentos","contas","cobrancas","fechamentos","auditoria"])
    exp=pd.read_sql_query(f"SELECT * FROM {tabela}",c)
    st.download_button("Baixar CSV",exp.to_csv(index=False).encode("utf-8-sig"),file_name=f"{tabela}.csv",mime="text/csv")
    c.close()
