import streamlit as st
import streamlit.components.v1 as components
import banco
import configuracoes
import filtros
import disponibilidade
import importacao
import apontamentos

# 1. Puxa as configurações do banco ANTES da página carregar
cfg = banco.obter_configuracoes()
titulo_app = cfg.get('titulo_programa', 'PCP Avelan')

st.set_page_config(page_title=titulo_app, page_icon="🏭", layout="wide")

st.markdown("""
    <style>
    /* OCULTA A BARRA SUPERIOR INÚTIL (Menu e botão Deploy) */
    header[data-testid="stHeader"] {
        display: none !important;
    }
    
    /* Ajusta o espaço para aproveitar bem o topo da tela */
    .block-container {
        padding-top: 2rem !important; 
        padding-bottom: 2rem !important;
    }

    /* REGRAS DO CABEÇALHO (PADRÃO PARA PC) */
    .cabecalho-responsivo {
        display: flex;
        align-items: center;
        gap: 20px;
        margin-bottom: 15px;
        justify-content: flex-start;
    }
    
    .logo-responsiva {
        max-height: 60px;
        object-fit: contain;
    }

    .titulo-responsivo {
        margin: 0;
        padding: 0;
        font-size: 2.5rem;
    }

    /* REGRAS DO CABEÇALHO (EXCLUSIVO PARA CELULAR) */
    @media (max-width: 768px) {
        .cabecalho-responsivo {
            flex-direction: column;
            justify-content: center;
            text-align: center;
            gap: 10px;
            margin-top: 10px;
        }
        .logo-responsiva {
            max-height: 80px;
        }
        .titulo-responsivo {
            font-size: 2rem;
        }
    }
    </style>
""", unsafe_allow_html=True)


# 2. Carrega os dados básicos
df_nuvem = banco.obter_dados_nuvem()
df_codigos = banco.obter_codigos()
meta, jornada, m_das, m_as, t_das, t_as = configuracoes.obter_parametros()

# ========================================================
# CABEÇALHO DINÂMICO E RESPONSIVO
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
# ========================================================

# FILTRO GLOBAL DE SETOR FIXO NA TELA
col_setor, _ = st.columns([4, 6]) 
with col_setor:
    filtros.renderizar_filtro_setor(df_nuvem)
st.markdown("<br>", unsafe_allow_html=True)

filtros_selecionados = filtros.obter_filtros_atuais()

# ========================================================
# LÓGICA DE ORDENAÇÃO EXATAMENTE COMO DEFINIDA (Visual)
# ========================================================
todas_abas_padrao = ["🔍 Filtros", "📈 Disponibilidade", "📋 Apontamentos", "⚙️ Configurações"]
ordem_str = cfg.get('ordem_abas', None)

if ordem_str:
    todas_abas = [a.strip() for a in ordem_str.split(',') if a.strip() in todas_abas_padrao]
    for a in todas_abas_padrao:
        if a not in todas_abas:
            todas_abas.append(a)
else:
    todas_abas = todas_abas_padrao.copy()

aba_padrao_salva = cfg.get('aba_padrao', '🔍 Filtros')

# ========================================================

abas_nativas = st.tabs(todas_abas)

for i, nome_aba in enumerate(todas_abas):
    with abas_nativas[i]:
        if nome_aba == "🔍 Filtros":
            filtros.renderizar_ui(df_nuvem)
            
        elif nome_aba == "📈 Disponibilidade":
            if not df_nuvem.empty:
                disponibilidade.renderizar(df_nuvem, df_codigos, filtros_selecionados, jornada, meta)
            else:
                st.info("O banco de dados está vazio no momento.")
                
        elif nome_aba == "📋 Apontamentos":
            if not df_nuvem.empty:
                apontamentos.renderizar(df_nuvem, df_codigos, filtros_selecionados)
            else:
                st.info("O banco de dados está vazio no momento.")
                
        elif nome_aba == "⚙️ Configurações":
            aba_interna, aba_config_abas, aba_importacoes = st.tabs([
                "⚙️ Ajustes Gerais do Sistema", 
                "📑 Configurações de Abas", 
                "📥 Importação de Dados"
            ])
            
            with aba_interna:
                configuracoes.renderizar()
                
            with aba_config_abas:
                configuracoes.renderizar_config_abas()
                
            with aba_importacoes:
                st.markdown("### Selecione o tipo de importação:")
                tipo_importacao = st.radio("", ["📦 Importar Planilha de Produção", "📋 Importar Planilha de Códigos"], horizontal=True, label_visibility="collapsed")
                st.markdown("<hr style='margin-top: 5px; margin-bottom: 20px;'>", unsafe_allow_html=True)
                
                if tipo_importacao == "📦 Importar Planilha de Produção":
                    importacao.renderizar_producao()
                else:
                    importacao.renderizar_codigos()


# ========================================================
# NOVO TRUQUE JS: Radar inteligente de carregamento
# ========================================================
if 'iniciou_aba' not in st.session_state:
    st.session_state['iniciou_aba'] = True
    
    if aba_padrao_salva in todas_abas:
        idx = todas_abas.index(aba_padrao_salva)
        
        if idx != 0:
            # Esse script cria um "radar" que verifica a tela a cada 50ms.
            # Quando ele acha as abas na tela, ele clica na que você escolheu e se desliga.
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
                
                // Trava de segurança para não ficar rodando infinito (para em 3 seg)
                setTimeout(() => clearInterval(checkInterval), 3000);
            </script>
            """
            components.html(js, height=0)