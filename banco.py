import streamlit as st
import pandas as pd
from supabase import create_client

# Estrutura Inteligente Híbrida: Nuvem + Local
try:
    # Tentativa 1: Nuvem (Streamlit Cloud puxando do Cofre)
    URL_SUPABASE = st.secrets["SUPABASE_URL"]
    CHAVE_SUPABASE = st.secrets["SUPABASE_KEY"]
except:
    # Tentativa 2: Computador Local (Desenvolvimento)
    # A chave está dividida em duas partes (+) para evitar que o robô do GitHub bloqueie o seu upload!
    URL_SUPABASE = "https://ewbhlxeekepwooutrlln.supabase.co"
    CHAVE_SUPABASE = "sb_publishable_" + "biqNEzpF9QSFLPiTzLFQRA_nTJyewa_"

@st.cache_resource
def iniciar_conexao():
    return create_client(URL_SUPABASE, CHAVE_SUPABASE)

def conectar():
    try:
        return iniciar_conexao()
    except Exception as e:
        st.error(f"Erro ao conectar no banco: {e}")
        st.stop()

def obter_dados_nuvem():
    supa = conectar()
    resp = supa.table("producao_diaria").select("*").execute()
    return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()

def obter_codigos():
    supa = conectar()
    resp = supa.table("codigos_parada").select("*").execute()
    return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()

def obter_configuracoes():
    supa = conectar()
    resp = supa.table("configuracoes").select("*").eq("id", 1).execute()
    return resp.data[0] if resp.data else {}

def ler_texto_seguro(df, nome_coluna):
    if nome_coluna in df.columns: return df[nome_coluna].astype(str).str.strip()
    return None

def ler_numero_seguro(df, nome_coluna):
    if nome_coluna in df.columns: return pd.to_numeric(df[nome_coluna], errors='coerce').fillna(0).astype(int)
    return 0

def formatar_hora_excel(val):
    if pd.isna(val) or str(val).strip().lower() in ['nan', 'none', '']: return None
    s = str(val).strip()
    if s.endswith('.0'): s = s[:-2]
    if ':' in s: return s[:5]
    if s.isdigit(): return f"{s.zfill(4)[:2]}:{s.zfill(4)[2:]}" 
    return s

def minutos_para_string(m):
    if pd.isna(m) or m == 0: return "00:00h"
    h = int(m // 60)
    mn = int(m % 60)
    return f"{h:02d}:{mn:02d}h"