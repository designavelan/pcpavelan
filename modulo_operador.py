import streamlit as st
import pandas as pd
import banco

def efetuar_logout():
    """Limpa a sessão do operador e devolve para a tela de login."""
    st.session_state.clear()
    st.session_state['usuario_logado'] = None
    st.session_state['logout_explicito'] = True
    try: st.query_params.clear()
    except: 
        try: st.experimental_set_query_params()
        except: pass
    st.rerun()

# ==========================================
# 1. MOTOR DE CACHE (DADOS NA MEMÓRIA)
# ==========================================
# O "ttl=60" significa que ele só vai no banco de dados a cada 60 segundos. 
# O resto do tempo, a tela usa a memória local do computador, deixando a navegação instantânea.
@st.cache_data(ttl=60, show_spinner=False)
def cache_dados_operador():
    supa = banco.conectar()
    
    # 1. Tabela de Produtos (Matriz)
    df_produtos = banco.obter_produtos_matriz()
    
    # 2. OPs Ativas
    try:
        resp_ops = supa.table("planejamento_ops").select("produto_formula").eq("status", "Em Andamento").execute()
        ops_ativas = [r['produto_formula'] for r in resp_ops.data] if resp_ops.data else []
    except:
        ops_ativas = []
        
    # 3. Dicionário de Códigos (Para resposta instantânea do teclado)
    df_codigos = banco.obter_codigos()
    dict_codigos = {}
    if not df_codigos.empty:
        for _, r in df_codigos.iterrows():
            dict_codigos[str(r['codigo']).strip()] = str(r['descricao']).strip()
            
    return df_produtos, ops_ativas, dict_codigos

# Função acionada ao tocar num botão do teclado
def registrar_tecla(tecla):
    if tecla == "C":
        st.session_state.parada_codigo = ""
    elif tecla == "<":
        st.session_state.parada_codigo = st.session_state.parada_codigo[:-1]
    else:
        if len(st.session_state.parada_codigo) < 4:
            st.session_state.parada_codigo += str(tecla)

# ==========================================
# 2. TELA PRINCIPAL
# ==========================================
def renderizar(df_nuvem, df_codigos_geral):
    # --- A MÁGICA VISUAL (TEMA ESCURO, CARDS E TECLADO GRID) ---
    st.markdown("""
    <style>
        /* Força Tema Escuro no Módulo */
        .stApp { background-color: #0e1117 !important; color: #ffffff !important; }
        
        /* Cabeçalho Limpo */
        div[data-testid="stHeader"] { display: none !important; }
        
        /* Remove o Título do Selectbox (1. Selecione o Produto) */
        div[data-testid="stSelectbox"] label { display: none !important; }
        div[data-baseweb="select"] > div { background-color: #1e1e1e !important; border-color: #333 !important; color: white !important; font-size: 18px !important; min-height: 50px !important; }
        
        /* Transformar st.radio em CARDS SELECIONÁVEIS */
        div[data-testid="stRadio"] > div { gap: 12px; }
        div[data-testid="stRadio"] label {
            background-color: #1e1e1e;
            border: 2px solid #333333;
            border-radius: 10px;
            padding: 15px 20px;
            width: 100%;
            cursor: pointer;
            margin: 0;
            transition: all 0.2s;
        }
        /* Ocultar a bolinha nativa do Radio */
        div[data-testid="stRadio"] label > div:first-child { display: none !important; }
        div[data-testid="stRadio"] label[data-checked="true"] {
            background-color: #0b2e13 !important;
            border-color: #27ae60 !important;
        }
        /* Título da Peça no Card */
        div[data-testid="stRadio"] p { font-size: 18px !important; font-weight: bold !important; color: white !important; }
        /* Descrição Extra da Peça no Card (Captions) */
        div[data-testid="stRadio"] div[data-testid="stCaptionContainer"] { color: #aaaaaa !important; font-size: 14px !important; margin-top: 4px !important; }
        
        /* ----------------------------------------------------
           FORÇAR O TECLADO A FICAR EM 3 COLUNAS NO CELULAR
           ---------------------------------------------------- */
        @media (max-width: 768px) {
            div[data-testid="stHorizontalBlock"]:has(button[kind="secondary"]) {
                display: flex !important;
                flex-direction: row !important;
                flex-wrap: nowrap !important;
            }
            div[data-testid="stHorizontalBlock"]:has(button[kind="secondary"]) > div {
                min-width: 30% !important;
                flex: 1 !important;
            }
            /* Ajuste para o botão Sair no topo não quebrar a interface */
            .btn-sair-mobile {
                margin-bottom: -15px !important;
            }
        }
        
        /* Estilo dos Botões do Teclado (Gigantes e Limpos) */
        button[kind="secondary"] {
            height: 80px !important;
            font-size: 32px !important;
            font-weight: 900 !important;
            background-color: #1e1e1e !important;
            color: white !important;
            border: 2px solid #333 !important;
            border-radius: 12px !important;
        }
        button[kind="secondary"]:active { border-color: #27ae60 !important; transform: scale(0.95) !important; }
        
        /* Botões de Ação (Iniciar/Parar) */
        button[kind="primary"] {
            height: 70px !important;
            font-size: 22px !important;
            font-weight: 900 !important;
            border-radius: 10px !important;
            text-transform: uppercase !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # Inicia a memória do Teclado
    if 'parada_codigo' not in st.session_state:
        st.session_state.parada_codigo = ""

    # Carrega as tabelas do Supabase da memória local (Super Rápido)
    df_produtos, ops_ativas, dict_codigos = cache_dados_operador()

    # ==========================================
    # CABEÇALHO DO OPERADOR
    # ==========================================
    usuario = st.session_state.get('usuario_logado', {})
    setor = str(usuario.get('setor', 'Setor Não Definido')).strip()
    maquina = str(usuario.get('maquina', 'Máquina Não Definida')).strip()
    nome_operador = str(usuario.get('nome', 'Operador Desconhecido')).strip().upper()

    # Botão de Logout no Topo Direito
    c_espaco, c_sair = st.columns([8, 2])
    with c_sair:
        st.markdown("<div class='btn-sair-mobile'>", unsafe_allow_html=True)
        if st.button("🚪 Sair", use_container_width=True):
            efetuar_logout()
        st.markdown("</div>", unsafe_allow_html=True)

    # Logomarca e Informações (Ajuste de margem negativa para compensar o botão de sair)
    st.markdown("<h1 style='text-align: center; color: white; margin-bottom: 0px; margin-top: -30px;'>👷 MÓDULO OPERADOR</h1>", unsafe_allow_html=True)
    st.markdown(f"<div style='text-align: center; color: #7f8c8d; font-size: 16px; margin-bottom: 25px; text-transform: uppercase; font-weight: 800;'>{setor} &nbsp;|&nbsp; {maquina} &nbsp;|&nbsp; {nome_operador}</div>", unsafe_allow_html=True)
    
    if setor == 'Setor Não Definido' or maquina == 'Máquina Não Definida':
        st.warning("⚠️ Atenção: Nenhuma máquina foi selecionada para este perfil. Volte e selecione seu local de trabalho.")
        return

    # ==========================================
    # ABAS DA MÁQUINA LIVRE
    # ==========================================
    aba_producao, aba_parada = st.tabs(["▶️ MODO PRODUÇÃO", "🔴 MODO PARADA"])

    # ------------------------------------------
    # 1. ABA MODO PRODUÇÃO
    # ------------------------------------------
    with aba_producao:
        st.markdown("<h3 style='color: white; margin-top: 10px; margin-bottom: 10px;'>Produto</h3>", unsafe_allow_html=True)
        
        if not df_produtos.empty:
            lista_todos = sorted(df_produtos['produto_formula'].dropna().unique().tolist())
            
            # Puxa OPs ativas pro Topo da lista
            lista_em_op = [p for p in ops_ativas if p in lista_todos]
            lista_resto = [p for p in lista_todos if p not in lista_em_op]
            
            opcoes_produto = []
            if lista_em_op:
                opcoes_produto.extend([f"[EM OP] {p}" for p in lista_em_op])
                opcoes_produto.append("--------------------------------------")
            opcoes_produto.extend(lista_resto)
            
            # Combobox do Produto (Sem Label)
            sel_prod_tela = st.selectbox("Produto", opcoes_produto, key="mod_op_select_prod", label_visibility="collapsed")
            
            if sel_prod_tela and sel_prod_tela != "--------------------------------------":
                produto_real = sel_prod_tela.replace("[EM OP] ", "")
                df_pecas = df_produtos[df_produtos['produto_formula'] == produto_real]
                
                # Montando os Cards das Peças
                nomes_pecas = []
                infos_pecas = [] # Textos adicionais (Captions)
                
                for _, row in df_pecas.iterrows():
                    codigo_peca = row['cod']
                    nome = str(row['descricao'])
                    
                    nomes_pecas.append(nome)
                    # No futuro, podemos ler a qtd produzida hoje e colocar aqui!
                    infos_pecas.append(f"Cód: {codigo_peca} | Mais informações da peça aqui...")
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                # Renderizando os CARDS (Radio)
                sel_peca = st.radio("Selecione a Peça", nomes_pecas, captions=infos_pecas, label_visibility="collapsed", key="mod_op_select_peca")
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                if st.button("▶ INICIAR PRODUÇÃO", type="primary", use_container_width=True):
                    st.success(f"Ação Computada! Produto: {produto_real} | Peça: {sel_peca}")
        else:
            st.warning("Nenhum produto encontrado no banco de dados.")

    # ------------------------------------------
    # 2. ABA MODO PARADA (Teclado)
    # ------------------------------------------
    with aba_parada:
        st.markdown("<h3 style='text-align: center; color: white;'>Código da Ocorrência</h3>", unsafe_allow_html=True)
        
        # 1. VISOR DO CÓDIGO
        codigo_atual = st.session_state.parada_codigo
        visor_display = codigo_atual if codigo_atual != "" else "---"
        
        # 2. INTELIGÊNCIA DA DESCRIÇÃO (Usando o Dicionário em Cache)
        cor_desc = "#7f8c8d"
        bloquear_botao = True
        
        if codigo_atual == "":
            desc_display = "Aguardando código..."
        elif codigo_atual in dict_codigos:
            desc_display = dict_codigos[codigo_atual]
            cor_desc = "#27ae60"
            bloquear_botao = False
        else:
            desc_display = "Código não encontrado"
            cor_desc = "#e74c3c"
            
        # Renderiza a caixa do Visor
        st.markdown(f"""
        <div style='background-color: #1e1e1e; padding: 15px; border-radius: 12px; border: 2px solid #333; text-align: center; margin-bottom: 20px;'>
            <h1 style='color: #e74c3c; font-family: monospace; font-size: 55px; letter-spacing: 10px; margin: 0;'>{visor_display}</h1>
            <p style='color: {cor_desc}; font-size: 18px; font-weight: bold; margin: 5px 0 0 0;'>{desc_display}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # 3. O TECLADO NUMÉRICO (3 Colunas Perfeitas)
        matriz_teclado = [
            ("1", "2", "3"),
            ("4", "5", "6"),
            ("7", "8", "9"),
            ("C", "0", "<")
        ]
        
        _, col_teclado, _ = st.columns([1, 6, 1]) # Margens laterais para não esticar muito no PC
        
        with col_teclado:
            for linha in matriz_teclado:
                c1, c2, c3 = st.columns(3)
                
                c1.button(linha[0], key=f"btn_{linha[0]}", use_container_width=True, on_click=registrar_tecla, args=(linha[0],))
                c2.button(linha[1], key=f"btn_{linha[1]}", use_container_width=True, on_click=registrar_tecla, args=(linha[1],))
                c3.button(linha[2], key=f"btn_{linha[2]}", use_container_width=True, on_click=registrar_tecla, args=(linha[2],))
                
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 4. BOTÃO DE INICIAR PARADA
        if st.button("🔴 CONFIRMAR REGISTRO", type="primary", use_container_width=True, disabled=bloquear_botao):
            st.success(f"Parada Iniciada! Código validado: {codigo_atual} - {desc_display}")
            st.session_state.parada_codigo = "" # Zera o visor após confirmar
            st.rerun()