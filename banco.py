import streamlit as st
import pandas as pd
from supabase import create_client
import hashlib
from datetime import datetime, timedelta

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

@st.cache_data(ttl=5)
def obter_estrutura():
    """Retorna APENAS as máquinas ativas no sistema (Filtro Mestre)"""
    try:
        supa = conectar()
        resp = supa.table("estrutura_fabrica").select("*").eq("ativo", True).order("setor").order("maquina").execute()
        return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    except Exception as e:
        print(f"Erro ao obter estrutura: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=5)
def obter_estrutura_completa():
    """Retorna TODAS as máquinas (ativas e desativadas) para a aba de Configurações"""
    try:
        supa = conectar()
        resp = supa.table("estrutura_fabrica").select("*").order("setor").order("maquina").execute()
        return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    except Exception as e:
        print(f"Erro ao obter estrutura completa: {e}")
        return pd.DataFrame()

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

# ==========================================
# FUNÇÕES DE PRODUTOS E PEÇAS (MATRIZ)
# ==========================================
def obter_produtos_matriz():
    supa = conectar()
    resp = supa.table("produtos_matriz").select("*").limit(10000).execute()
    return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()

def sincronizar_produtos(lista_dicionarios):
    supa = conectar()
    supa.table("produtos_matriz").delete().neq("id", 0).execute()
    
    tamanho_lote = 500
    for i in range(0, len(lista_dicionarios), tamanho_lote):
        lote = lista_dicionarios[i:i+tamanho_lote]
        supa.table("produtos_matriz").insert(lote).execute()

def atualizar_peca_individual(id_peca, dados):
    supa = conectar()
    supa.table("produtos_matriz").update(dados).eq("id", id_peca).execute()

# ==========================================
# FUNÇÕES DE CORREÇÃO DE QUANTIDADES (AUDITORIA)
# ==========================================
def obter_solicitacoes_pendentes():
    supa = conectar()
    resp = supa.table("solicitacoes_correcao").select("*, producao_diaria(nome_peca, setor, maquina)").eq("status", "Pendente").execute()
    return resp.data if resp.data else []

def enviar_solicitacao_correcao(id_producao, operador, qtd_antiga, qtd_nova, motivo):
    supa = conectar()
    # Verifica se o operador já clicou e há uma pendente
    resp = supa.table("solicitacoes_correcao").select("id").eq("id_producao", id_producao).eq("status", "Pendente").execute()
    if resp.data: return False, "Já existe uma solicitação pendente para este registro."
        
    agora = (datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
    dados = {
        "id_producao": id_producao, "operador_solicitante": operador,
        "data_solicitacao": agora, "qtd_antiga": qtd_antiga, "qtd_nova": qtd_nova, 
        "motivo": motivo, "status": "Pendente"
    }
    supa.table("solicitacoes_correcao").insert(dados).execute()
    return True, ""

def aprovar_solicitacao(id_solic, id_prod, nova_qtd, admin_nome):
    supa = conectar()
    agora = (datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
    # Atualiza o registro original na fábrica
    supa.table("producao_diaria").update({"quantidade": nova_qtd}).eq("id", id_prod).execute()
    # Registra a auditoria da aprovação
    supa.table("solicitacoes_correcao").update({
        "status": "Aprovada", "aprovado_por": admin_nome, "data_decisao": agora
    }).eq("id", id_solic).execute()

def recusar_solicitacao(id_solic, admin_nome):
    supa = conectar()
    agora = (datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
    supa.table("solicitacoes_correcao").update({
        "status": "Recusada", "aprovado_por": admin_nome, "data_decisao": agora
    }).eq("id", id_solic).execute()

def obter_registro_por_id(id_producao):
    """Busca os dados completos de um apontamento pelo seu ID."""
    supa = conectar()
    resp = supa.table("producao_diaria").select("*").eq("id", id_producao).execute()
    return resp.data[0] if resp.data else None

def corrigir_registro_manual(id_prod, nova_qtd, motivo, admin_nome):
    supa = conectar()
    agora = (datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
    
    # Puxa a quantidade antiga para o histórico
    resp = supa.table("producao_diaria").select("quantidade").eq("id", id_prod).execute()
    if not resp.data: return False, "ID não encontrado na tabela de produção."
    qtd_antiga = int(float(resp.data[0]['quantidade']))
    
    # Altera diretamente a produção
    supa.table("producao_diaria").update({"quantidade": nova_qtd}).eq("id", id_prod).execute()
    
    # Salva a ação na caixa preta
    dados = {
        "id_producao": id_prod, "operador_solicitante": admin_nome,
        "data_solicitacao": agora, "qtd_antiga": qtd_antiga, "qtd_nova": nova_qtd,
        "motivo": motivo, "status": "Aprovada Direta", 
        "aprovado_por": admin_nome, "data_decisao": agora
    }
    supa.table("solicitacoes_correcao").insert(dados).execute()
    return True, ""

# ==========================================
# FUNÇÕES DE IDENTIFICAÇÃO POR CORES
# ==========================================
@st.cache_data(ttl=60, show_spinner=False)
def obter_mapa_cores():
    supa = conectar()
    resp = supa.table("config_cores").select("*").execute()
    if resp.data:
        return {row['tipo'].strip().upper(): row['cor_hex'] for row in resp.data}
    return {}

def atualizar_cor(tipo, cor_hex):
    supa = conectar()
    resp = supa.table("config_cores").select("id").eq("tipo", tipo).execute()
    if resp.data:
        supa.table("config_cores").update({"cor_hex": cor_hex}).eq("tipo", tipo).execute()
    else:
        supa.table("config_cores").insert({"tipo": tipo, "cor_hex": cor_hex}).execute()
    st.cache_data.clear() # Limpa a memória para espalhar a cor pelo sistema todo na hora

# ==========================================
# FUNÇÕES DE MEMÓRIA DO SISTEMA (KEY-VALUE)
# ==========================================
def salvar_memoria_sistema(aba, local_aplicacao, chave, valor):
    """
    Salva ou atualiza uma configuração na tabela coringa 'memoria_sistema'.
    """
    try:
        supa = conectar()
        resp = supa.table("memoria_sistema").select("id").eq("aba", aba).eq("local_aplicacao", local_aplicacao).eq("chave", chave).execute()
        
        if resp.data:
            id_registro = resp.data[0]['id']
            supa.table("memoria_sistema").update({"valor": str(valor)}).eq("id", id_registro).execute()
        else:
            dados = {
                "aba": aba,
                "local_aplicacao": local_aplicacao,
                "chave": chave,
                "valor": str(valor)
            }
            supa.table("memoria_sistema").insert(dados).execute()
    except Exception as e:
        print(f"Erro ao salvar memoria_sistema: {e}")

def obter_memoria_sistema(aba, local_aplicacao, chave, valor_padrao=None):
    """
    Busca uma configuração na tabela coringa 'memoria_sistema'. Retorna o valor_padrao se não encontrar.
    """
    try:
        supa = conectar()
        resp = supa.table("memoria_sistema").select("valor").eq("aba", aba).eq("local_aplicacao", local_aplicacao).eq("chave", chave).execute()
        
        if resp.data:
            return resp.data[0]['valor']
        return valor_padrao
    except Exception as e:
        print(f"Erro ao obter memoria_sistema: {e}")
        return valor_padrao