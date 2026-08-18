import streamlit as st

# OBRIGATÓRIA: Deve ser a primeira instrução
st.set_page_config(page_title="PCP Avelan", page_icon="🏭", layout="wide")

# Removemos o código que escondia o header (os 3 pontinhos voltam!)
st.markdown("""
    <style>
    /* Puxa o painel para cima apenas, sem esconder o menu superior */
    .block-container {
        padding-top: 1.5rem !important; 
        padding-bottom: 2rem !important;
    }
    </style>
""", unsafe_allow_html=True)

import banco
import configuracoes
import filtros
import disponibilidade
import importacao

st.title("🏭 PCP Avelan")

# 1. Carrega DADOS GLOBAIS do banco apenas 1 vez (Velocidade máxima!)
df_nuvem = banco.obter_dados_nuvem()
df_codigos = banco.obter_codigos()
meta, jornada, m_das, m_as, t_das, t_as = configuracoes.obter_parametros()

# 2. Renderiza a BARRA GERAL DE FILTROS (Fica ACIMA das abas)
filtros_selecionados = filtros.renderizar(df_nuvem)

# 3. Criação da BARRA DE ABAS (Fica ABAIXO dos filtros)
aba_dashboard, aba_producao, aba_codigos_tab, aba_configuracoes = st.tabs([
    "📈 Disponibilidade", 
    "📥 Importar Produção", 
    "📋 Importar Códigos", 
    "⚙️ Configurações"
])

# 4. Distribuição do conteúdo para a aba correspondente
with aba_dashboard:
    if filtros_selecionados: # Só renderiza se houver dados
        # A aba não cuida de botões de filtro, ela só obedece à ordem passada pelo pacote "filtros_selecionados"
        disponibilidade.renderizar(df_nuvem, df_codigos, filtros_selecionados, jornada, meta)
    else:
        st.info("O banco de dados está vazio no momento.")

with aba_producao:
    importacao.renderizar_producao()

with aba_codigos_tab:
    importacao.renderizar_codigos()

with aba_configuracoes:
    configuracoes.renderizar()