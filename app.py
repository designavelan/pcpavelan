import streamlit as st
# 🔒 REGRA DE SEGURANÇA: Configuração da página DEVE ser a primeira linha do Streamlit!
st.set_page_config(page_title="PCP Avelan", page_icon="🏭", layout="wide")

import streamlit.components.v1 as components
import banco
import configuracoes
import filtros
import disponibilidade
import ocorrencias 
import importacao
import apontamentos
import backups 
import plano_acao 
import chao_de_fabrica
import ao_vivo 
import gerenciador
import usuarios
from streamlit_option_menu import option_menu
import base64

# Carrega configurações visuais
try:
    cfg = banco.obter_configuracoes()
    titulo_app = cfg.get('titulo_programa', 'PCP Avelan')
except:
    cfg = {}
    titulo_app = 'PCP Avelan'

# ==========================================
# 1. SISTEMA DE LOGIN COM PERSISTÊNCIA (F5)
# ==========================================
if 'usuario_logado' not in st.session_state:
    st.session_state['usuario_logado'] = None

# Tenta fazer o Auto-Login se a pessoa recarregou a página
if st.session_state['usuario_logado'] is None:
    try:
        if hasattr(st, 'query_params') and 'session' in st.query_params:
            decoded_user = base64.b64decode(st.query_params['session']).decode('utf-8')
            user_valido = banco.obter_usuario_por_login(decoded_user)
            if user_valido:
                st.session_state['usuario_logado'] = user_valido
        elif hasattr(st, 'experimental_get_query_params'):
            params = st.experimental_get_query_params()
            if 'session' in params:
                decoded_user = base64.b64decode(params['session'][0]).decode('utf-8')
                user_valido = banco.obter_usuario_por_login(decoded_user)
                if user_valido:
                    st.session_state['usuario_logado'] = user_valido
    except:
        pass

# Desenha a Tela de Login se realmente não tiver ninguém
if st.session_state['usuario_logado'] is None:
    st.markdown("""
        <style>
        header[data-testid="stHeader"] { display: none !important; }
        .block-container { max-width: 450px !important; padding-top: 5rem !important; }
        </style>
    """, unsafe_allow_html=True)
    
    logo_b64 = cfg.get('logo_base64', None)
    if logo_b64:
        st.markdown(f'<div style="text-align:center;"><img src="data:image/png;base64,{logo_b64}" style="max-height: 80px; margin-bottom: 20px;"></div>', unsafe_allow_html=True)
    
    st.markdown(f"<h2 style='text-align: center; color: #2c3e50;'>🏭 {titulo_app}</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #7f8c8d; margin-bottom: 30px;'>Acesso Restrito</p>", unsafe_allow_html=True)
    
    with st.form("form_login"):
        login = st.text_input("Usuário", placeholder="Digite seu login")
        senha = st.text_input("Senha", type="password", placeholder="Digite sua senha")
        submit = st.form_submit_button("Entrar no Sistema", use_container_width=True, type="primary")
        
        if submit:
            if login and senha:
                user_valido = banco.autenticar_usuario(login, senha)
                if user_valido:
                    st.session_state['usuario_logado'] = user_valido
                    encoded_user = base64.b64encode(user_valido['username'].encode('utf-8')).decode('utf-8')
                    try: st.query_params['session'] = encoded_user
                    except: st.experimental_set_query_params(session=encoded_user)
                    st.rerun()
                else:
                    st.error("❌ Usuário ou senha incorretos, ou conta desativada.")
            else:
                st.warning("⚠️ Preencha usuário e senha.")
    st.stop() 

# ==========================================
# 2. APLICAÇÃO PRINCIPAL 
# ==========================================
usuario_atual = st.session_state['usuario_logado']
perfil_atual = usuario_atual.get('perfis_acesso', {})
is_admin = perfil_atual.get('is_admin', False)
abas_permitidas_str = perfil_atual.get('abas_permitidas', '')

try:
    if hasattr(st, 'query_params') and 'codigo_alvo' in st.query_params:
        st.session_state['codigo_alvo'] = st.query_params['codigo_alvo']
        st.session_state['aba_atual'] = "🔎 Ocorrências"
        filtros.salvar_memoria() 
        st.query_params.clear()
        try: st.query_params['session'] = base64.b64encode(usuario_atual['username'].encode('utf-8')).decode('utf-8')
        except: pass
    elif hasattr(st, 'experimental_get_query_params') and 'codigo_alvo' in st.experimental_get_query_params():
        st.session_state['codigo_alvo'] = st.experimental_get_query_params()['codigo_alvo'][0]
        st.session_state['aba_atual'] = "🔎 Ocorrências"
        filtros.salvar_memoria()
        st.experimental_set_query_params(session=base64.b64encode(usuario_atual['username'].encode('utf-8')).decode('utf-8'))
except: pass

st.markdown("""
    <style>
    header[data-testid="stHeader"] { display: none !important; }
    .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; max-width: 100% !important; }
    .cabecalho-responsivo { display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px; }
    .logo-container { display: flex; align-items: center; gap: 20px; }
    .logo-responsiva { max-height: 60px; object-fit: contain; }
    .titulo-responsivo { margin: 0; padding: 0; font-size: 2.5rem; }
    ul.nav-pills { flex-wrap: nowrap !important; overflow-x: auto !important; overflow-y: hidden !important; scrollbar-width: none !important; }
    ul.nav-pills::-webkit-scrollbar { display: none !important; }
    li.nav-item { white-space: nowrap !important; }
    @media (max-width: 768px) {
        .cabecalho-responsivo { flex-direction: column; justify-content: center; text-align: center; gap: 10px; margin-top: 10px; }
        .logo-responsiva { max-height: 80px; } .titulo-responsivo { font-size: 2rem; }
    }
    </style>
""", unsafe_allow_html=True)

df_nuvem = banco.obter_dados_nuvem()
df_codigos = banco.obter_codigos()
meta, jornada, m_das, m_as, t_das, t_as = configuracoes.obter_parametros()

c1, c2 = st.columns([8, 2])
with c1:
    logo_b64 = cfg.get('logo_base64', None)
    if logo_b64:
        st.markdown(f'<div class="logo-container"><img src="data:image/png;base64,{logo_b64}" class="logo-responsiva"><h1 class="titulo-responsivo">{titulo_app}</h1></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="logo-container"><h1 class="titulo-responsivo">🏭 {titulo_app}</h1></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f"<div style='text-align: right; color: #7f8c8d; font-size: 14px; margin-bottom: 5px;'>👤 Olá, <b>{usuario_atual['nome']}</b></div>", unsafe_allow_html=True)
    if st.button("🚪 Sair do Sistema", use_container_width=True):
        st.session_state['usuario_logado'] = None
        try: st.query_params.clear()
        except: st.experimental_set_query_params()
        st.rerun()

st.markdown("<hr style='margin-top: 5px; margin-bottom: 10px; opacity: 0.2;'>", unsafe_allow_html=True)

# ==========================================
# 3. LÓGICA DE PERMISSÃO DE ABAS
# ==========================================
todas_abas_padrao = ["📱 Chão de Fábrica", "🔴 Ao Vivo", "💡 Plano de Ação", "📈 Disponibilidade", "📋 Apontamentos", "🔎 Ocorrências", "⚙️ Configurações", "👥 Controle de Acessos"]

if is_admin or abas_permitidas_str.upper() == 'TODAS': abas_usuario = todas_abas_padrao.copy()
else:
    abas_usuario = [aba for aba in todas_abas_padrao if aba in abas_permitidas_str]
    if not abas_usuario: abas_usuario = ["📱 Chão de Fábrica"]

ordem_str = cfg.get('ordem_abas', None)
if ordem_str:
    todas_abas = [a.strip() for a in ordem_str.split(',') if a.strip() in abas_usuario]
    for a in abas_usuario:
        if a not in todas_abas: todas_abas.append(a)
else: todas_abas = abas_usuario.copy()

aba_padrao_salva = cfg.get('aba_padrao', todas_abas[0])
if aba_padrao_salva not in todas_abas: aba_padrao_salva = todas_abas[0]

lembrar_aba_ligado = cfg.get('lembrar_aba', True)

if 'aba_atual' not in st.session_state:
    if lembrar_aba_ligado:
        memoria = filtros.carregar_memoria()
        aba_cache = memoria.get("aba_atual", "")
        st.session_state.aba_atual = aba_cache if aba_cache in todas_abas else aba_padrao_salva
    else: st.session_state.aba_atual = aba_padrao_salva

if st.session_state.aba_atual not in todas_abas: st.session_state.aba_atual = todas_abas[0]

if st.session_state.aba_atual not in ["📱 Chão de Fábrica", "🔴 Ao Vivo", "⚙️ Configurações", "👥 Controle de Acessos"]:
    filtros.renderizar_barra_superior(df_nuvem)
    filtros_selecionados = filtros.obter_filtros_atuais()
    st.markdown("<hr style='margin-top: 10px; margin-bottom: 20px; opacity: 0.2;'>", unsafe_allow_html=True)
else:
    filtros_selecionados = filtros.obter_filtros_atuais()
    if st.session_state.aba_atual == "🔴 Ao Vivo":
        st.markdown(f"<div style='text-align:right; margin-bottom:15px;'><span style='background:#f1f1f1; padding:5px 15px; border-radius:5px;'>Filtro Atual: <b>{filtros_selecionados['setor']}</b></span></div>", unsafe_allow_html=True)

idx_atual = todas_abas.index(st.session_state.aba_atual)

escolha = option_menu(
    menu_title=None,
    options=todas_abas,
    default_index=idx_atual,
    orientation="horizontal",
    icons=[''] * len(todas_abas), 
    styles={
        "container": {"padding": "0!important", "background-color": "#f8f9fa", "border-radius": "5px", "margin-bottom": "25px"},
        "icon": {"display": "none"},
        "nav-link": {"font-size": "15px", "text-align": "center", "margin": "0px 5px", "white-space": "nowrap", "--hover-color": "#eee"},
        "nav-link-selected": {"background-color": "#2980b9"},
    }
)

if escolha != st.session_state.aba_atual:
    st.session_state.aba_atual = escolha
    filtros.salvar_memoria() 
    st.rerun()

# Roteamento 
if st.session_state.aba_atual == "📱 Chão de Fábrica": chao_de_fabrica.renderizar(df_nuvem, df_codigos)
elif st.session_state.aba_atual == "🔴 Ao Vivo": ao_vivo.renderizar(df_nuvem, df_codigos, filtros_selecionados)
elif st.session_state.aba_atual == "💡 Plano de Ação": 
    if not df_nuvem.empty: plano_acao.renderizar(df_nuvem, df_codigos, filtros_selecionados, jornada)
    else: st.info("O banco de dados está vazio.")
elif st.session_state.aba_atual == "📈 Disponibilidade":
    if not df_nuvem.empty: disponibilidade.renderizar(df_nuvem, df_codigos, filtros_selecionados, jornada, meta)
    else: st.info("O banco de dados está vazio.")
elif st.session_state.aba_atual == "🔎 Ocorrências":
    if not df_nuvem.empty: ocorrencias.renderizar(df_nuvem, df_codigos, filtros_selecionados)
    else: st.info("O banco de dados está vazio.")
elif st.session_state.aba_atual == "📋 Apontamentos":
    if not df_nuvem.empty: apontamentos.renderizar(df_nuvem, df_codigos, filtros_selecionados)
    else: st.info("O banco de dados está vazio.")
elif st.session_state.aba_atual == "👥 Controle de Acessos":
    usuarios.renderizar(df_nuvem)
elif st.session_state.aba_atual == "⚙️ Configurações":
    aba_interna, aba_config_abas, aba_estrutura, aba_importacoes, aba_backup, aba_gerenciador = st.tabs(["⚙️ Ajustes Gerais", "📑 Config. de Abas", "🏭 Estrutura", "📥 Importação", "💾 Backup", "🛠️ Gerenciador de Dados"])
    with aba_interna: configuracoes.renderizar()
    with aba_config_abas: configuracoes.renderizar_config_abas()
    with aba_estrutura: configuracoes.renderizar_estrutura()
    with aba_importacoes:
        importacao.renderizar_producao()
        st.markdown("<br>", unsafe_allow_html=True)
        importacao.renderizar_codigos()
    with aba_backup: backups.renderizar()
    with aba_gerenciador: gerenciador.renderizar(df_nuvem)