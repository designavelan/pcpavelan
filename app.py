import streamlit as st
import streamlit.components.v1 as components
import banco
import configuracoes
import filtros
import disponibilidade
import analise 
import importacao
import apontamentos
import backups 

cfg = banco.obter_configuracoes()
titulo_app = cfg.get('titulo_programa', 'PCP Avelan')

st.set_page_config(page_title=titulo_app, page_icon="🏭", layout="wide")

st.markdown("""
    <style>
    header[data-testid="stHeader"] { display: none !important; }
    .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; }
    .cabecalho-responsivo { display: flex; align-items: center; gap: 20px; margin-bottom: 15px; justify-content: flex-start; }
    .logo-responsiva { max-height: 60px; object-fit: contain; }
    .titulo-responsivo { margin: 0; padding: 0; font-size: 2.5rem; }
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
filtros.renderizar_barra_superior(df_nuvem)
st.markdown("<hr style='margin-top: 10px; margin-bottom: 20px; opacity: 0.2;'>", unsafe_allow_html=True)

filtros_selecionados = filtros.obter_filtros_atuais()

# === ABA DE FILTROS REMOVIDA ===
todas_abas_padrao = ["📈 Disponibilidade", "🔎 Análise por Ocorrência", "📋 Apontamentos", "⚙️ Configurações"]
ordem_str = cfg.get('ordem_abas', None)

if ordem_str:
    todas_abas = [a.strip() for a in ordem_str.split(',') if a.strip() in todas_abas_padrao]
    for a in todas_abas_padrao:
        if a not in todas_abas:
            todas_abas.append(a)
else:
    todas_abas = todas_abas_padrao.copy()

aba_padrao_salva = cfg.get('aba_padrao', '📈 Disponibilidade')

abas_nativas = st.tabs(todas_abas)

for i, nome_aba in enumerate(todas_abas):
    with abas_nativas[i]:
        if nome_aba == "📈 Disponibilidade":
            if not df_nuvem.empty:
                disponibilidade.renderizar(df_nuvem, df_codigos, filtros_selecionados, jornada, meta)
            else:
                st.info("O banco de dados está vazio no momento.")
                
        elif nome_aba == "🔎 Análise por Ocorrência":
            if not df_nuvem.empty:
                analise.renderizar(df_nuvem, df_codigos, filtros_selecionados)
            else:
                st.info("O banco de dados está vazio no momento.")
                
        elif nome_aba == "📋 Apontamentos":
            if not df_nuvem.empty:
                apontamentos.renderizar(df_nuvem, df_codigos, filtros_selecionados)
            else:
                st.info("O banco de dados está vazio no momento.")
                
        elif nome_aba == "⚙️ Configurações":
            aba_interna, aba_config_abas, aba_importacoes, aba_backup = st.tabs([
                "⚙️ Ajustes Gerais do Sistema", 
                "📑 Configurações de Abas", 
                "📥 Importação de Dados",
                "💾 Backup"
            ])
            with aba_interna: configuracoes.renderizar()
            with aba_config_abas: configuracoes.renderizar_config_abas()
            with aba_importacoes:
                importacao.renderizar_producao()
                st.markdown("<br>", unsafe_allow_html=True)
                importacao.renderizar_codigos()
            with aba_backup: backups.renderizar()

if 'iniciou_aba' not in st.session_state:
    st.session_state['iniciou_aba'] = True
    if aba_padrao_salva in todas_abas:
        idx = todas_abas.index(aba_padrao_salva)
        if idx != 0:
            js = f"""
            <script>
                const checkInterval = setInterval(function() {{
                    const parentDoc = window.parent.document;
                    const tabs = parentDoc.querySelectorAll('button[data-baseweb="tab"]');
                    if (tabs && tabs.length >= {len(todas_abas)}) {{
                        tabs[{idx}].click();
                        clearInterval(checkInterval);
                    }}
                }}, 50);
                setTimeout(() => clearInterval(checkInterval), 3000);
            </script>
            """
            components.html(js, height=0)