import streamlit as st
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
import gerenciador # NOVO MÓDULO IMPORTADO AQUI
from streamlit_option_menu import option_menu

cfg = banco.obter_configuracoes()
titulo_app = cfg.get('titulo_programa', 'PCP Avelan')

st.set_page_config(page_title=titulo_app, page_icon="🏭", layout="wide")

try:
    params = st.query_params
    if 'codigo_alvo' in params:
        st.session_state['codigo_alvo'] = params['codigo_alvo']
        st.session_state['aba_atual'] = "🔎 Ocorrências"
        filtros.salvar_memoria() 
        st.query_params.clear()
except AttributeError:
    params = st.experimental_get_query_params()
    if 'codigo_alvo' in params:
        st.session_state['codigo_alvo'] = params['codigo_alvo'][0]
        st.session_state['aba_atual'] = "🔎 Ocorrências"
        filtros.salvar_memoria()
        st.experimental_set_query_params()

st.markdown("""
    <style>
    header[data-testid="stHeader"] { display: none !important; }
    .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; }
    .cabecalho-responsivo { display: flex; align-items: center; gap: 20px; margin-bottom: 15px; justify-content: flex-start; }
    .logo-responsiva { max-height: 60px; object-fit: contain; }
    .titulo-responsivo { margin: 0; padding: 0; font-size: 2.5rem; }
    
    ul.nav-pills {
        flex-wrap: nowrap !important;
        overflow-x: auto !important;
        overflow-y: hidden !important;
        -webkit-overflow-scrolling: touch !important; 
        scrollbar-width: none !important; 
    }
    ul.nav-pills::-webkit-scrollbar {
        display: none !important; 
    }
    li.nav-item {
        white-space: nowrap !important; 
    }
    
    @media (max-width: 768px) {
        .cabecalho-responsivo { flex-direction: column; justify-content: center; text-align: center; gap: 10px; margin-top: 10px; }
        .logo-responsiva { max-height: 80px; }
        .titulo-responsivo { font-size: 2rem; }
    }
    </style>
""", unsafe_allow_html=True)

df_nuvem = banco.obter_dados_nuvem()
df_codigos = banco.obter_codigos()
meta, jornada, m_das, m_as, t_das, t_as = configuracoes.obter_parametros()

logo_b64 = cfg.get('logo_base64', None)
if logo_b64:
    st.markdown(f"""
        <div class="cabecalho-responsivo">
            <img src="data:image/png;base64,{logo_b64}" class="logo-responsiva">
            <h1 class="titulo-responsivo">{titulo_app}</h1>
        </div>
    """, unsafe_allow_html=True)
else:
    st.markdown(f"""
        <div class="cabecalho-responsivo">
            <h1 class="titulo-responsivo">🏭 {titulo_app}</h1>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<hr style='margin-top: 0px; margin-bottom: 10px; opacity: 0.2;'>", unsafe_allow_html=True)

todas_abas_padrao = ["📱 Chão de Fábrica", "🔴 Ao Vivo", "💡 Plano de Ação", "📈 Disponibilidade", "📋 Apontamentos", "🔎 Ocorrências", "⚙️ Configurações"]
ordem_str = cfg.get('ordem_abas', None)

if ordem_str:
    todas_abas = [a.strip() for a in ordem_str.split(',') if a.strip() in todas_abas_padrao]
    for a in todas_abas_padrao:
        if a not in todas_abas:
            todas_abas.append(a)
else:
    todas_abas = todas_abas_padrao.copy()

aba_padrao_salva = cfg.get('aba_padrao', '💡 Plano de Ação')
lembrar_aba_ligado = cfg.get('lembrar_aba', True)

if 'aba_atual' not in st.session_state:
    if lembrar_aba_ligado:
        memoria = filtros.carregar_memoria()
        aba_cache = memoria.get("aba_atual", "")
        if aba_cache in todas_abas:
            st.session_state.aba_atual = aba_cache
        else:
            st.session_state.aba_atual = aba_padrao_salva
    else:
        st.session_state.aba_atual = aba_padrao_salva

if st.session_state.aba_atual not in todas_abas:
    st.session_state.aba_atual = todas_abas[0]

# --- LÓGICA DE EXIBIÇÃO DO FILTRO ---
if st.session_state.aba_atual not in ["📱 Chão de Fábrica", "🔴 Ao Vivo"]:
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
        "container": {
            "padding": "0!important", 
            "background-color": "#f8f9fa", 
            "border-radius": "5px", 
            "margin-bottom": "25px"
        },
        "icon": {
            "display": "none" 
        },
        "nav-link": {
            "font-size": "15px", 
            "text-align": "center", 
            "margin": "0px 5px", 
            "white-space": "nowrap", 
            "--hover-color": "#eee"
        },
        "nav-link-selected": {
            "background-color": "#2980b9"
        },
    }
)

if escolha != st.session_state.aba_atual:
    st.session_state.aba_atual = escolha
    filtros.salvar_memoria() 
    st.rerun()

# Roteamento
if st.session_state.aba_atual == "📱 Chão de Fábrica":
    chao_de_fabrica.renderizar(df_nuvem, df_codigos)
    
elif st.session_state.aba_atual == "🔴 Ao Vivo":
    ao_vivo.renderizar(df_nuvem, df_codigos, filtros_selecionados)
    
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
        
elif st.session_state.aba_atual == "⚙️ Configurações":
    # --- ROTEAMENTO ATUALIZADO COM A ABA GERENCIADOR ---
    aba_interna, aba_config_abas, aba_importacoes, aba_backup, aba_gerenciador = st.tabs([
        "⚙️ Ajustes Gerais", 
        "📑 Config. de Abas", 
        "📥 Importação", 
        "💾 Backup",
        "🛠️ Gerenciador de Dados"
    ])
    with aba_interna: configuracoes.renderizar()
    with aba_config_abas: configuracoes.renderizar_config_abas()
    with aba_importacoes:
        importacao.renderizar_producao()
        st.markdown("<br>", unsafe_allow_html=True)
        importacao.renderizar_codigos()
    with aba_backup: backups.renderizar()
    with aba_gerenciador: gerenciador.renderizar(df_nuvem)