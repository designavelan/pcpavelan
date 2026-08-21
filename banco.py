import streamlit as st
import pandas as pd
from supabase import create_client
import hashlib

try:
    URL_SUPABASE = st.secrets["SUPABASE_URL"]
    CHAVE_SUPABASE = st.secrets["SUPABASE_KEY"]
except:
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

# ==========================================
# FUNÇÕES DE AUTENTICAÇÃO E USUÁRIOS
# ==========================================

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

def autenticar_usuario(username, senha_texto):
    try:
        supa = conectar()
        username_limpo = username.strip().lower()
        resp = supa.table("usuarios").select("*").eq("username", username_limpo).execute()
        
        if not resp.data: return None
        user = resp.data[0]
        
        if not user.get('ativo', False): return None
        
        if user['senha'] == senha_texto or user['senha'] == hash_senha(senha_texto):
            if user.get('perfil_id'):
                resp_perfil = supa.table("perfis_acesso").select("*").eq("id", user['perfil_id']).execute()
                user['perfis_acesso'] = resp_perfil.data[0] if resp_perfil.data else {}
            else:
                user['perfis_acesso'] = {}
            return user
        return None
    except Exception as e:
        st.error(f"Erro de comunicação com o banco: {e}")
        return None

def obter_usuario_por_login(username):
    """Função para o Auto-Login (F5 da página)"""
    try:
        supa = conectar()
        resp = supa.table("usuarios").select("*").eq("username", username).execute()
        if not resp.data: return None
        user = resp.data[0]
        if not user.get('ativo', False): return None
        
        if user.get('perfil_id'):
            resp_perfil = supa.table("perfis_acesso").select("*").eq("id", user['perfil_id']).execute()
            user['perfis_acesso'] = resp_perfil.data[0] if resp_perfil.data else {}
        else:
            user['perfis_acesso'] = {}
        return user
    except:
        return None

def obter_perfis():
    supa = conectar()
    resp = supa.table("perfis_acesso").select("*").order("id").execute()
    return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()

def obter_usuarios_completo():
    supa = conectar()
    resp = supa.table("usuarios").select("*, perfis_acesso(nome_perfil)").order("id").execute()
    return resp.data if resp.data else []

def atualizar_perfil(id_perfil, dados):
    supa = conectar()
    supa.table("perfis_acesso").update(dados).eq("id", id_perfil).execute()

def atualizar_usuario(id_usuario, dados):
    supa = conectar()
    supa.table("usuarios").update(dados).eq("id", id_usuario).execute()

# ==========================================
# FUNÇÕES DE ESTRUTURA DA FÁBRICA (CASCATA)
# ==========================================

def obter_estrutura():
    supa = conectar()
    resp = supa.table("estrutura_fabrica").select("*").order("setor").order("maquina").execute()
    return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()

def adicionar_estrutura(setor, maquina):
    supa = conectar()
    supa.table("estrutura_fabrica").insert({"setor": setor, "maquina": maquina, "ativo": True}).execute()

def atualizar_estrutura_cascata(id_est, setor_antigo, maquina_antiga, setor_novo, maquina_novo):
    supa = conectar()
    # 1. Atualiza na estrutura
    supa.table("estrutura_fabrica").update({"setor": setor_novo, "maquina": maquina_novo}).eq("id", id_est).execute()
    
    # 2. Efeito Cascata: Histórico de Produção
    supa.table("producao_diaria").update({"setor": setor_novo, "maquina": maquina_novo}).eq("setor", setor_antigo).eq("maquina", maquina_antiga).execute()
    
    # 3. Efeito Cascata: Usuários vinculados
    supa.table("usuarios").update({"setor": setor_novo, "maquina": maquina_novo}).eq("setor", setor_antigo).eq("maquina", maquina_antiga).execute()
    
    # 4. Efeito Cascata: Status Ao Vivo
    supa.table("status_maquinas").update({"setor": setor_novo, "maquina": maquina_novo}).eq("setor", setor_antigo).eq("maquina", maquina_antiga).execute()