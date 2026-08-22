import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import banco
import streamlit.components.v1 as components
import json

# ==========================================
# MOTOR DE CACHE E FUNÇÕES AUXILIARES
# ==========================================
@st.cache_data(ttl=60, show_spinner=False)
def cache_obter_produtos():
    return banco.obter_produtos_matriz()

@st.cache_data(ttl=60, show_spinner=False)
def cache_obter_ativos():
    supa = banco.conectar()
    try:
        resp = supa.table("produtos_ativos").select("produto_formula").execute()
        return [r['produto_formula'] for r in resp.data] if resp.data else []
    except:
        return []

@st.cache_data(ttl=120, show_spinner=False)
def cache_obter_estrutura():
    return banco.obter_estrutura()

def obter_hora_atual():
    return datetime.utcnow() - timedelta(hours=3)

def obter_html_teclado_qtd(label):
    return f"""
    <style>
        body {{ font-family: sans-serif; margin: 0; padding: 10px; }}
        .lcd {{ background: #ffffff; padding: 15px; border-radius: 12px; text-align: center; border: 2px solid #dcdde1; box-shadow: inset 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 20px; }}
        .lcd-val {{ margin: 0; font-family: monospace; font-size: 50px; letter-spacing: 5px; color: #27ae60; min-height: 60px; font-weight: 900; }}
        .lcd-desc {{ margin: 5px 0 0 0; font-size: 16px; font-weight: bold; color: #7f8c8d; text-transform: uppercase; letter-spacing: 1px; }}
        .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; }}
        .btn-key {{ background: #ffffff; border: 1px solid #dcdde1; border-radius: 12px; font-size: 28px; font-weight: 900; color: #2c3e50; padding: 20px 0; cursor: pointer; transition: all 0.1s; box-shadow: 0 4px 6px rgba(0,0,0,0.05); -webkit-tap-highlight-color: transparent; }}
        .btn-key:active {{ transform: scale(0.95); background: #f1f2f6; }}
        .btn-c {{ color: #e74c3c; }}
        .btn-del {{ color: #e67e22; }}
    </style>
    <div class="lcd">
        <h2 id="lcd-val" class="lcd-val">0</h2>
        <p class="lcd-desc">Peças Produzidas</p>
    </div>
    <div class="grid">
        <button type="button" class="btn-key" onclick="pressKey('1')">1</button>
        <button type="button" class="btn-key" onclick="pressKey('2')">2</button>
        <button type="button" class="btn-key" onclick="pressKey('3')">3</button>
        <button type="button" class="btn-key" onclick="pressKey('4')">4</button>
        <button type="button" class="btn-key" onclick="pressKey('5')">5</button>
        <button type="button" class="btn-key" onclick="pressKey('6')">6</button>
        <button type="button" class="btn-key" onclick="pressKey('7')">7</button>
        <button type="button" class="btn-key" onclick="pressKey('8')">8</button>
        <button type="button" class="btn-key" onclick="pressKey('9')">9</button>
        <button type="button" class="btn-key btn-c" onclick="pressKey('C')">C</button>
        <button type="button" class="btn-key" onclick="pressKey('0')">0</button>
        <button type="button" class="btn-key btn-del" onclick="pressKey('<')">⌫</button>
    </div>
    <script>
        let currentQty = "";
        function updateLCD() {{
            const lcdVal = document.getElementById("lcd-val");
            lcdVal.innerText = currentQty === "" ? "0" : currentQty;
            const inputs = window.parent.document.querySelectorAll('input[aria-label="{label}"]');
            if (inputs.length > 0) {{
                const input = inputs[0]; 
                let nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                nativeSetter.call(input, currentQty === "" ? "0" : currentQty); 
                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }}
        }}
        function pressKey(k) {{ 
            if (k === 'C') currentQty = ""; 
            else if (k === '<') currentQty = currentQty.slice(0, -1); 
            else currentQty += k; 
            
            if (currentQty.length > 1 && currentQty.startsWith("0")) currentQty = currentQty.substring(1);
            if (currentQty.length > 6) currentQty = currentQty.slice(0, 6);
            
            updateLCD(); 
        }}
        setTimeout(updateLCD, 500);
    </script>
    """

def renderizar(df_nuvem, df_codigos):
    if 'tk_counter' not in st.session_state: st.session_state['tk_counter'] = 0

    st.markdown("""
        <style>
        /* Remove o espaço em branco desnecessário no topo */
        .block-container { padding-top: 0.5rem !important; }
        div[data-testid="stTabs"] { margin-top: -15px; }

        /* Oculta 100% os inputs de texto que recebem dados do JS */
        div[data-testid="stElementContainer"]:has(input[aria-label="input_codigo_js"]),
        div[data-testid="stElementContainer"]:has(input[aria-label="input_codigo_js_int"]),
        div[data-testid="stElementContainer"]:has(input[aria-label="input_qtd_js"]),
        div[data-testid="stElementContainer"]:has(input[aria-label="input_qtd_js_int"]) {
            position: absolute !important; left: -9999px !important; width: 0px !important; height: 0px !important; overflow: hidden !important;
        }
        
        div[data-baseweb="select"] > div {
            min-height: 65px !important; font-size: 20px !important; border-radius: 8px !important;
        }
        div[data-baseweb="select"] { font-size: 20px !important; }
        button[data-baseweb="tab"] { font-size: 20px !important; font-weight: 800 !important; padding: 20px 25px !important; }
        div[data-testid="stRadio"] label { padding: 5px 15px; cursor: pointer; font-size: 18px !important; }
        ::-webkit-scrollbar { display: none; }
        </style>
    """, unsafe_allow_html=True)

    supa = banco.conectar()
    df_est = cache_obter_estrutura()
    if df_est.empty:
        st.warning("⚠️ Nenhuma estrutura de fábrica cadastrada. Vá na aba Configurações > Estrutura.")
        return

    # ==========================================
    # LÓGICA DE IDENTIFICAÇÃO DO USUÁRIO
    # ==========================================
    usuario = st.session_state.get('usuario_logado', {})
    user_setor = usuario.get('setor', '[ Todos ]')
    user_maq = usuario.get('maquina', '[ Todas ]')

    is_travado = (user_setor != "[ Todos ]" and user_maq != "[ Todas ]" and user_setor != "" and user_maq != "")
    lista_setores_nuvem = sorted(df_est['setor'].dropna().unique().tolist())

    if is_travado:
        setor_selecionado = user_setor
        maquina_selecionada = user_maq
        nomes_operadores = usuario.get('nome', 'Operador Desconhecido')
        operadores_vinculados = [nomes_operadores]
    else:
        setor_selecionado = st.session_state.get("cf_setor", lista_setores_nuvem[0] if lista_setores_nuvem else "")
        if setor_selecionado not in lista_setores_nuvem and lista_setores_nuvem: setor_selecionado = lista_setores_nuvem[0]
            
        lista_maquinas_nuvem = sorted(df_est[df_est['setor'] == setor_selecionado]['maquina'].dropna().unique().tolist())
        maquina_selecionada = st.session_state.get("cf_maquina", lista_maquinas_nuvem[0] if lista_maquinas_nuvem else "")
        if maquina_selecionada not in lista_maquinas_nuvem and lista_maquinas_nuvem: maquina_selecionada = lista_maquinas_nuvem[0]

        usuarios_cadastrados = banco.obter_usuarios_completo()
        operadores_vinculados = [
            u['nome'] for u in usuarios_cadastrados 
            if str(u.get('setor')) == str(setor_selecionado) and str(u.get('maquina')) == str(maquina_selecionada) and u.get('ativo') == True
        ]
        nomes_operadores = " / ".join(operadores_vinculados) if operadores_vinculados else "Sem Operador"

    df_produtos = cache_obter_produtos()
    produtos_ativos = cache_obter_ativos()

    permite_dupla = False
    maq_row = df_est[(df_est['setor'] == setor_selecionado) & (df_est['maquina'] == maquina_selecionada)]
    if not maq_row.empty:
        val_raw = maq_row.iloc[0].get('permite_producao_dupla', False)
        permite_dupla = True if str(val_raw).strip().lower() == 'true' or val_raw is True else False

    # ==========================================
    # STATUS DA MÁQUINA
    # ==========================================
    response = supa.table("status_maquinas").select("*").eq("maquina", maquina_selecionada).execute()
    status_db = 'Livre'
    hora_inicio_str = None
    cod_ocorrencia = None
    cod_peca_atual = None
    
    if response.data:
        dados_maq = response.data[0]
        status_db = dados_maq.get('status', 'Livre')
        if status_db == 'Trabalhando': status_db = 'Livre'
        hora_inicio_str = dados_maq.get('hora_inicio')
        cod_ocorrencia = dados_maq.get('cod_ocorrencia')
        cod_peca_atual = dados_maq.get('cod_peca_atual')

    if not df_codigos.empty:
        if 'exibir_na_lista' in df_codigos.columns:
            setor_upper = str(setor_selecionado).strip().upper()
            def filtrar_por_setor(valor):
                if pd.isna(valor) or str(valor).strip() == '': return False
                partes = [p.strip().upper() for p in str(valor).split(',')]
                return 'TODOS' in partes or setor_upper in partes
            df_codigos_parado = df_codigos[df_codigos['exibir_na_lista'].apply(filtrar_por_setor)]
        else:
            if 'tipo' in df_codigos.columns: df_codigos_parado = df_codigos[(df_codigos['tipo'].astype(str).str.strip().str.upper() != 'PRODUÇÃO') & (df_codigos['codigo'].astype(str).str.strip().str.upper() != 'P')]
            else: df_codigos_parado = pd.DataFrame()
    else: df_codigos_parado = pd.DataFrame()

    # ==========================================
    # ESTADO 1: MÁQUINA LIVRE
    # ==========================================
    if status_db == 'Livre':
        tab_prod, tab_parada = st.tabs(["🟢 MODO PRODUÇÃO", "🔴 MODO PARADA"])
        
        with tab_prod:
            # --- MEMÓRIA SILENCIOSA DA MÁQUINA ---
            chave_last_prod = f"mem_prod_{maquina_selecionada}"
            chave_last_peca = f"mem_peca_{maquina_selecionada}"
            
            last_prod = st.session_state.get(chave_last_prod, "")
            last_peca = st.session_state.get(chave_last_peca, "")
            
            st.markdown("<br>", unsafe_allow_html=True)
            c_header1, c_header2 = st.columns([7, 3])
            with c_header1: st.markdown("<h4 style='color: #2c3e50; margin:0;'>📦 Seleção de Material</h4>", unsafe_allow_html=True)
            with c_header2: mostrar_todos = st.checkbox("Exibir Produtos Fora de Linha", value=False)
            
            if not df_produtos.empty:
                lista_todos = sorted(df_produtos['produto_formula'].dropna().unique().tolist())
                
                if mostrar_todos or not produtos_ativos: 
                    lista_exibicao = lista_todos.copy()
                else: 
                    lista_exibicao = [p for p in lista_todos if p in produtos_ativos]
                
                if last_prod and last_prod not in lista_exibicao and last_prod in lista_todos:
                    lista_exibicao.append(last_prod)
                    lista_exibicao = sorted(lista_exibicao)
                
                opcoes_prod = [""] + lista_exibicao
                
                chave_wid_prod = f"sel_prod_{maquina_selecionada}"
                
                if chave_wid_prod not in st.session_state and last_prod in opcoes_prod:
                    st.session_state[chave_wid_prod] = last_prod
                
                sel_prod = st.selectbox("1. Produto:", opcoes_prod, key=chave_wid_prod)
                
                # ==========================================
                # INTERFACE DE SELEÇÃO DA PEÇA (BOTÕES GIGANTES)
                # ==========================================
                if sel_prod:
                    df_pecas = df_produtos[df_produtos['produto_formula'] == sel_prod]
                    lista_pecas = [f"{row['descricao']} (Cód: {row['cod']})" for _, row in df_pecas.iterrows()]
                    
                    # Hack da Peça de Memória
                    if sel_prod == last_prod and last_peca and last_peca not in lista_pecas:
                        lista_pecas.append(last_peca)
                        
                    idx_peca = lista_pecas.index(last_peca) if (sel_prod == last_prod and last_peca in lista_pecas) else 0
                    
                    sel_peca = None
                    iniciar_producao_flag = False

                    st.markdown("""
                        <style>
                        /* Transforma o componente Radio Vertical em Botões Gigantes */
                        div[data-testid='stRadio']:has(div[aria-orientation='vertical']) > div {
                            gap: 12px;
                        }
                        div[data-testid='stRadio']:has(div[aria-orientation='vertical']) label {
                            background-color: #ffffff;
                            border: 1px solid #bdc3c7;
                            border-radius: 8px;
                            padding: 16px 20px;
                            width: 100%;
                            cursor: pointer;
                            transition: all 0.2s ease-in-out;
                            margin: 0;
                        }
                        div[data-testid='stRadio']:has(div[aria-orientation='vertical']) label[data-checked="true"] {
                            background-color: #ff4b4b !important;
                            border-color: #ff4b4b !important;
                        }
                        /* Oculta a bolinha redonda nativa do radio */
                        div[data-testid='stRadio']:has(div[aria-orientation='vertical']) label > div:first-child {
                            display: none !important;
                        }
                        /* Alinhamento do texto totalmente à esquerda */
                        div[data-testid='stRadio']:has(div[aria-orientation='vertical']) label p {
                            font-size: 16px;
                            font-weight: 600;
                            color: #2c3e50;
                            margin: 0;
                            text-align: left !important;
                            width: 100%;
                        }
                        /* Cor do texto quando selecionado */
                        div[data-testid='stRadio']:has(div[aria-orientation='vertical']) label[data-checked="true"] p {
                            color: #ffffff !important;
                        }
                        /* Adiciona um Checkmark via CSS na frente do texto quando selecionado */
                        div[data-testid='stRadio']:has(div[aria-orientation='vertical']) label[data-checked="true"] p::before {
                            content: '✅ ';
                        }
                        </style>
                    """, unsafe_allow_html=True)
                    
                    st.markdown("<h4 style='color: #2c3e50; font-size: 16px; margin-top: 15px;'>2. Toque na peça para selecionar:</h4>", unsafe_allow_html=True)
                    
                    sel_peca = st.radio("Selecione a Peça", lista_pecas, index=idx_peca, label_visibility="collapsed")
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("▶️ CONFIRMAR E INICIAR", type="primary", use_container_width=True):
                        iniciar_producao_flag = True

                    # ==========================================
                    # AÇÃO ÚNICA DE INÍCIO DA PRODUÇÃO
                    # ==========================================
                    if iniciar_producao_flag and sel_peca:
                        st.session_state[chave_last_prod] = sel_prod
                        st.session_state[chave_last_peca] = sel_peca
                        
                        codigo_peca = sel_peca.split("(Cód: ")[-1].replace(")", "").strip()
                        agora = obter_hora_atual().strftime("%Y-%m-%d %H:%M:%S")
                        
                        supa.table("status_maquinas").upsert({
                            "maquina": maquina_selecionada, "setor": setor_selecionado, 
                            "status": "Produzindo", "cod_peca_atual": codigo_peca, 
                            "hora_inicio": agora, "cod_ocorrencia": "P"
                        }).execute()
                        
                        if chave_wid_prod in st.session_state: del st.session_state[chave_wid_prod]
                        st.rerun()

            else:
                st.info("Nenhum produto cadastrado na Matriz.")

        with tab_parada:
            st.markdown("<br>", unsafe_allow_html=True)
            if not df_codigos_parado.empty:
                valid_codes = {str(row['codigo']).strip(): str(row['descricao']).strip() for _, row in df_codigos_parado.iterrows()}
                valid_codes_json = json.dumps(valid_codes)
                
                with st.form(key=f"form_parada_livre_{maquina_selecionada}"):
                    tab_tcl, tab_lst = st.tabs(["🔢 Teclado Numérico", "📄 Selecionar na Lista"])
                    
                    with tab_tcl:
                        chave_dinamica = f"input_js_{st.session_state['tk_counter']}"
                        codigo_js = st.text_input("input_codigo_js", key=chave_dinamica, label_visibility="collapsed")
                        
                        html_teclado = f"""
                        <style>
                            body {{ font-family: sans-serif; margin: 0; padding: 10px; }}
                            .lcd {{ background: #ffffff; padding: 15px; border-radius: 12px; text-align: center; border: 2px solid #dcdde1; box-shadow: inset 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 20px; }}
                            .lcd-val {{ margin: 0; font-family: monospace; font-size: 45px; letter-spacing: 5px; color: #2c3e50; min-height: 55px; }}
                            .lcd-desc {{ margin: 5px 0 0 0; font-size: 18px; font-weight: bold; min-height: 25px; transition: color 0.2s; }}
                            .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 25px; }}
                            .btn-key {{ background: #ffffff; border: 1px solid #dcdde1; border-radius: 12px; font-size: 28px; font-weight: 900; color: #2c3e50; padding: 20px 0; cursor: pointer; transition: all 0.1s; box-shadow: 0 4px 6px rgba(0,0,0,0.05); -webkit-tap-highlight-color: transparent; }}
                            .btn-key:active {{ transform: scale(0.95); background: #f1f2f6; }}
                            .btn-c {{ color: #e74c3c; }}
                            .btn-del {{ color: #e67e22; }}
                            .btn-start {{ width: 100%; background: #e74c3c; color: white; border: none; border-radius: 12px; font-size: 22px; font-weight: 900; text-transform: uppercase; padding: 25px 0; cursor: pointer; opacity: 0.5; -webkit-tap-highlight-color: transparent; }}
                            .btn-start.ready {{ opacity: 1; background: #c0392b; animation: pulse 2s infinite; }}
                            @keyframes pulse {{ 0% {{ box-shadow: 0 0 0 0 rgba(231, 76, 60, 0.7); }} 70% {{ box-shadow: 0 0 0 15px rgba(231, 76, 60, 0); }} 100% {{ box-shadow: 0 0 0 0 rgba(231, 76, 60, 0); }} }}
                        </style>
                        <div class="lcd"><h2 id="lcd-val" class="lcd-val">---</h2><p id="lcd-desc" class="lcd-desc" style="color: #7f8c8d;">Aguardando código...</p></div>
                        <div class="grid">
                            <button type="button" class="btn-key" onclick="pressKey('1')">1</button>
                            <button type="button" class="btn-key" onclick="pressKey('2')">2</button>
                            <button type="button" class="btn-key" onclick="pressKey('3')">3</button>
                            <button type="button" class="btn-key" onclick="pressKey('4')">4</button>
                            <button type="button" class="btn-key" onclick="pressKey('5')">5</button>
                            <button type="button" class="btn-key" onclick="pressKey('6')">6</button>
                            <button type="button" class="btn-key" onclick="pressKey('7')">7</button>
                            <button type="button" class="btn-key" onclick="pressKey('8')">8</button>
                            <button type="button" class="btn-key" onclick="pressKey('9')">9</button>
                            <button type="button" class="btn-key btn-c" onclick="pressKey('C')">C</button>
                            <button type="button" class="btn-key" onclick="pressKey('0')">0</button>
                            <button type="button" class="btn-key btn-del" onclick="pressKey('<')">⌫</button>
                        </div>
                        <button id="btn-start" class="btn-start" onclick="sendCode()" disabled>🔴 CONFIRMAR PARADA</button>
                        <script>
                            const validCodes = {valid_codes_json};
                            let currentCode = "";
                            function updateLCD() {{
                                const lcdVal = document.getElementById("lcd-val"); const lcdDesc = document.getElementById("lcd-desc"); const btnStart = document.getElementById("btn-start");
                                lcdVal.innerText = currentCode === "" ? "---" : currentCode;
                                if (currentCode === "") {{ lcdDesc.innerText = "Aguardando código..."; lcdDesc.style.color = "#7f8c8d"; btnStart.disabled = true; btnStart.classList.remove("ready"); }} 
                                else if (validCodes[currentCode]) {{ lcdDesc.innerText = "✅ " + validCodes[currentCode]; lcdDesc.style.color = "#27ae60"; btnStart.disabled = false; btnStart.classList.add("ready"); }} 
                                else {{ lcdDesc.innerText = "❌ Código não encontrado"; lcdDesc.style.color = "#e74c3c"; btnStart.disabled = true; btnStart.classList.remove("ready"); }}
                            }}
                            function pressKey(k) {{ if (k === 'C') currentCode = ""; else if (k === '<') currentCode = currentCode.slice(0, -1); else currentCode += k; updateLCD(); }}
                            function sendCode() {{
                                if (!validCodes[currentCode]) return;
                                document.getElementById("btn-start").innerText = "Processando...";
                                const inputs = window.parent.document.querySelectorAll('input[aria-label="input_codigo_js"]');
                                if (inputs.length > 0) {{
                                    const input = inputs[0]; let nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                                    nativeSetter.call(input, currentCode); input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                    setTimeout(() => {{ input.focus(); input.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', keyCode: 13, bubbles: true }})); input.blur(); }}, 50);
                                }}
                            }}
                        </script>
                        """
                        components.html(html_teclado, height=650)

                    with tab_lst:
                        opcoes_prob = [f"{str(row['descricao']).strip()} ({str(row['codigo']).strip()})" for _, row in df_codigos_parado.iterrows()]
                        problema_selecionado = st.selectbox("Selecione o problema:", [""] + opcoes_prob)
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        btn_submit_lista_parada = st.form_submit_button("🔴 CONFIRMAR PARADA", use_container_width=True)
                        
                    if btn_submit_lista_parada or (codigo_js and codigo_js in valid_codes):
                        cod_final = codigo_js if (codigo_js and codigo_js in valid_codes) else problema_selecionado.split("(")[-1].replace(")", "").strip() if problema_selecionado else None
                        if cod_final:
                            agora = obter_hora_atual().strftime("%Y-%m-%d %H:%M:%S")
                            supa.table("status_maquinas").upsert({
                                "maquina": maquina_selecionada, "setor": setor_selecionado, "status": "Parado", 
                                "cod_peca_atual": None, "cod_ocorrencia": cod_final, "hora_inicio": agora
                            }).execute()
                            st.session_state['tk_counter'] += 1 
                            st.rerun()
            else: st.warning(f"⚠️ Não há nenhum código configurado para este setor.")

    # ==========================================
    # ESTADO 2: PRODUZINDO LOTE ATUAL
    # ==========================================
    elif status_db == 'Produzindo':
        nome_peca = "Peça Desconhecida"
        if cod_peca_atual and not df_produtos.empty:
            df_filtro = df_produtos[df_produtos['cod'].astype(str) == str(cod_peca_atual)]
            if not df_filtro.empty:
                nome_peca = f"{df_filtro.iloc[0]['produto_formula']} ➔ {df_filtro.iloc[0]['descricao']}"

        hora_inicio_iso = hora_inicio_str.replace(" ", "T")

        js_cronometro = f"""
        <style>
            body {{ margin: 0; padding: 0; font-family: sans-serif; }}
            .caixa {{ background-color: #27ae60; color: white; padding: 25px 20px; border-radius: 12px; text-align: center; box-shadow: 0 4px 15px rgba(39, 174, 96, 0.4); box-sizing: border-box; margin: 0; }}
            .titulo {{ margin: 0; font-size: 34px; text-transform: uppercase; font-weight: 900; }}
            .sub {{ margin: 10px 0 15px 0; font-size: 18px; opacity: 0.95; }}
            .cronometro {{ font-size: 60px; font-weight: 900; font-family: monospace; letter-spacing: 2px; }}
            @media (max-width: 768px) {{ .caixa {{ padding: 20px 10px; }} .titulo {{ font-size: 24px; }} .sub {{ font-size: 15px; margin: 10px 0 10px 0; }} .cronometro {{ font-size: 40px; letter-spacing: 0px; }} }}
        </style>
        <div class="caixa">
            <h1 class="titulo">🟢 EM PRODUÇÃO</h1><p class="sub">Fabricando: <br><b>{nome_peca} (Cód: {cod_peca_atual})</b></p>
            <div id="stopwatch" class="cronometro">00:00:00</div>
        </div>
        <script>
            const startTime = new Date("{hora_inicio_iso}").getTime();
            setInterval(function() {{
                const now = new Date().getTime(); const distance = now - startTime;
                if (distance > 0) {{
                    const h = Math.floor(distance / (1000 * 60 * 60)); const m = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60)); const s = Math.floor((distance % (1000 * 60)) / 1000);
                    document.getElementById("stopwatch").innerHTML = (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
                }}
                
                const isLess1Min = distance < 60000;
                const btns = window.parent.document.querySelectorAll('button');
                btns.forEach(btn => {{
                    const txt = btn.innerText ? btn.innerText.toUpperCase() : "";
                    if(txt.includes('CANCELAR PRODUÇÃO (ERRO DE SELEÇÃO)')) {{
                        btn.closest('div[data-testid="stButton"]').style.display = isLess1Min ? 'block' : 'none';
                    }}
                    if(txt === '✅ FINALIZAR (CONCLUÍDO)' || txt === '🔴 INTERROMPER (POR FALHA)') {{
                        btn.closest('div[data-testid="stButton"]').style.display = isLess1Min ? 'none' : 'block';
                    }}
                }});
            }}, 500);
        </script>
        """
        components.html(js_cronometro, height=250)
        
        chave_estado_fin = f"fin_estado_{maquina_selecionada}"
        estado_fin = st.session_state.get(chave_estado_fin, None)
        
        if not estado_fin:
            st.markdown("<br>", unsafe_allow_html=True)
            
            btn_canc_prod = st.button("❌ CANCELAR PRODUÇÃO (Erro de Seleção)", use_container_width=True)
            c1, c2 = st.columns(2)
            with c1: btn_fin_prod = st.button("✅ FINALIZAR (Concluído)", use_container_width=True, type="primary")
            with c2: btn_int_prod = st.button("🔴 INTERROMPER (Por Falha)", use_container_width=True, type="primary")
                
            if btn_canc_prod:
                supa.table("status_maquinas").update({
                    "status": "Livre", "hora_inicio": None, "cod_ocorrencia": None, "cod_peca_atual": None
                }).eq("maquina", maquina_selecionada).execute()
                st.rerun()
                
            if btn_fin_prod:
                st.session_state[chave_estado_fin] = "CONCLUIDO"
                st.rerun()
                
            if btn_int_prod:
                st.session_state[chave_estado_fin] = "INTERROMPIDO"
                st.rerun()

        else:
            def salvar_producao_atual(codigo_parada_novo, qtd_informada, modalidade_escolhida):
                hora_fim = obter_hora_atual()
                hora_inicio_obj = datetime.strptime(hora_inicio_str, "%Y-%m-%d %H:%M:%S")
                duracao_segundos = (hora_fim - hora_inicio_obj).total_seconds()
                
                if duracao_segundos >= 60:
                    tipo_producao = "PRODUÇÃO"
                    if not df_codigos.empty:
                        f_prod = df_codigos[df_codigos['codigo'].astype(str).str.upper() == 'P']
                        if not f_prod.empty and 'tipo' in f_prod.columns:
                            tipo_producao = str(f_prod.iloc[0]['tipo']).strip().upper()
                            
                    dados_nuvem = {
                        "data_registro": hora_inicio_obj.strftime("%Y-%m-%d"),
                        "setor": setor_selecionado, "maquina": maquina_selecionada, 
                        "tipo": tipo_producao,  
                        "cod_peca": cod_peca_atual, "nome_peca": nome_peca, "quantidade": qtd_informada,
                        "operador": nomes_operadores, "cod_ocorrencia": "P",
                        "das": hora_inicio_obj.strftime("%H:%M"), "as_hora": hora_fim.strftime("%H:%M"), 
                        "origem": "Chão de Fábrica",
                        "modalidade_processo": modalidade_escolhida 
                    }
                    supa.table("producao_diaria").insert(dados_nuvem).execute()
                    
                    try:
                        qtd_valida = int(qtd_informada)
                        if qtd_valida > 0 and duracao_segundos >= 60:
                            duracao_min = float(duracao_segundos / 60.0)
                            p_hora_atual = float((qtd_valida / duracao_min) * 60.0)
                            
                            c_peca_str = str(cod_peca_atual).strip()
                            c_maq_str = str(maquina_selecionada).strip()
                            
                            resp_rec = supa.table("producao_recordes").select("*").eq("cod_peca", c_peca_str).eq("maquina", c_maq_str).eq("is_recorde_atual", "true").execute()
                            
                            bater_recorde = False
                            if not resp_rec.data:
                                bater_recorde = True
                            else:
                                recorde_banco = float(resp_rec.data[0].get("pecas_por_hora", 0))
                                if p_hora_atual > recorde_banco:
                                    bater_recorde = True
                                    id_antigo = int(resp_rec.data[0]["id"])
                                    supa.table("producao_recordes").update({"is_recorde_atual": False}).eq("id", id_antigo).execute()
                            
                            if bater_recorde:
                                dados_recorde = {
                                    "cod_peca": c_peca_str, "nome_peca": str(nome_peca).strip(),
                                    "setor": str(setor_selecionado).strip(), "maquina": c_maq_str,
                                    "operador": str(nomes_operadores).strip(), "quantidade_produzida": qtd_valida,
                                    "tempo_gasto_minutos": round(duracao_min, 2), "pecas_por_hora": round(p_hora_atual, 2),
                                    "data_recorde": hora_fim.strftime("%Y-%m-%d %H:%M:%S"),
                                    "is_recorde_atual": True, "modalidade_processo": str(modalidade_escolhida).strip()
                                }
                                supa.table("producao_recordes").insert(dados_recorde).execute()
                    except Exception as e:
                        st.error(f"⚠️ Aviso: Falha no processamento do recorde. Detalhe técnico: {e}")
                
                if codigo_parada_novo:
                    supa.table("status_maquinas").update({
                        "status": "Parado", "hora_inicio": hora_fim.strftime("%Y-%m-%d %H:%M:%S"),
                        "cod_ocorrencia": codigo_parada_novo, "cod_peca_atual": None
                    }).eq("maquina", maquina_selecionada).execute()
                else:
                    supa.table("status_maquinas").update({
                        "status": "Livre", "hora_inicio": None, "cod_ocorrencia": None, "cod_peca_atual": None
                    }).eq("maquina", maquina_selecionada).execute()
                    
                st.session_state[chave_estado_fin] = None
                st.cache_data.clear()
                st.rerun()

            # --- RENDERIZAÇÃO ESPECÍFICA CONCLUIDO VS INTERROMPIDO ---
            if estado_fin == "CONCLUIDO":
                with st.form(key=f"form_conc_{maquina_selecionada}"):
                    st.markdown("<h3 style='margin:0; color:#2c3e50;'>📊 Fechamento da Produção</h3>", unsafe_allow_html=True)
                    st.markdown("<hr style='opacity: 0.2; margin-top: 5px; margin-bottom: 20px;'>", unsafe_allow_html=True)
                    
                    qtd_str = st.text_input("input_qtd_js", value="0", label_visibility="collapsed")
                    components.html(obter_html_teclado_qtd("input_qtd_js"), height=480)
                    
                    modalidade_escolhida = "Simples"
                    if permite_dupla:
                        st.markdown("<div style='margin-top: 15px; margin-bottom: 5px; color: #2c3e50; font-weight: bold; font-size:18px;'>⚙️ Modalidade de Produção</div>", unsafe_allow_html=True)
                        modalidade_escolhida = st.radio("mod_inv", ["Simples", "Dupla"], horizontal=True, label_visibility="collapsed")
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    cb1, cb2 = st.columns(2)
                    with cb1:
                        btn_salvar = st.form_submit_button("💾 CONFIRMAR E SALVAR", type="primary", use_container_width=True)
                    with cb2:
                        btn_cancelar = st.form_submit_button("❌ Cancelar Operação", use_container_width=True)
                        
                    if btn_salvar:
                        try: qtd_final = int(qtd_str)
                        except: qtd_final = 0
                        salvar_producao_atual(codigo_parada_novo=None, qtd_informada=qtd_final, modalidade_escolhida=modalidade_escolhida)
                    if btn_cancelar:
                        st.session_state[chave_estado_fin] = None
                        st.rerun()
                        
            elif estado_fin == "INTERROMPIDO":
                with st.form(key=f"form_int_{maquina_selecionada}"):
                    st.markdown("<h3 style='margin:0; color:#2c3e50;'>🚨 Interrupção da Produção</h3>", unsafe_allow_html=True)
                    st.markdown("<hr style='opacity: 0.2; margin-top: 5px; margin-bottom: 20px;'>", unsafe_allow_html=True)
                    
                    qtd_str_int = st.text_input("input_qtd_js_int", value="0", label_visibility="collapsed")
                    components.html(obter_html_teclado_qtd("input_qtd_js_int"), height=480)
                    
                    modalidade_escolhida = "Simples"
                    if permite_dupla:
                        st.markdown("<div style='margin-top: 15px; margin-bottom: 5px; color: #2c3e50; font-weight: bold; font-size:18px;'>⚙️ Modalidade de Produção</div>", unsafe_allow_html=True)
                        modalidade_escolhida = st.radio("mod_inv_int", ["Simples", "Dupla"], horizontal=True, label_visibility="collapsed")
                    
                    st.markdown("<h3 style='margin-top:15px; color:#c0392b;'>Motivo da Interrupção</h3>", unsafe_allow_html=True)
                    
                    if not df_codigos_parado.empty:
                        valid_codes = {str(row['codigo']).strip(): str(row['descricao']).strip() for _, row in df_codigos_parado.iterrows()}
                        valid_codes_json = json.dumps(valid_codes)
                        
                        tab_tcl_int, tab_lst_int = st.tabs(["🔢 Teclado Numérico", "📄 Selecionar na Lista"])
                        
                        with tab_tcl_int:
                            codigo_js_int = st.text_input("input_codigo_js_int", label_visibility="collapsed")
                            
                            html_teclado_int = f"""
                            <style>
                                body {{ font-family: sans-serif; margin: 0; padding: 10px; }}
                                .lcd {{ background: #ffffff; padding: 15px; border-radius: 12px; text-align: center; border: 2px solid #dcdde1; box-shadow: inset 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 20px; }}
                                .lcd-val {{ margin: 0; font-family: monospace; font-size: 45px; letter-spacing: 5px; color: #2c3e50; min-height: 55px; }}
                                .lcd-desc {{ margin: 5px 0 0 0; font-size: 18px; font-weight: bold; min-height: 25px; transition: color 0.2s; }}
                                .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 25px; }}
                                .btn-key {{ background: #ffffff; border: 1px solid #dcdde1; border-radius: 12px; font-size: 28px; font-weight: 900; color: #2c3e50; padding: 20px 0; cursor: pointer; transition: all 0.1s; box-shadow: 0 4px 6px rgba(0,0,0,0.05); -webkit-tap-highlight-color: transparent; }}
                                .btn-key:active {{ transform: scale(0.95); background: #f1f2f6; }}
                                .btn-c {{ color: #e74c3c; }}
                                .btn-del {{ color: #e67e22; }}
                                .btn-start {{ width: 100%; background: #e74c3c; color: white; border: none; border-radius: 12px; font-size: 22px; font-weight: 900; text-transform: uppercase; padding: 25px 0; cursor: pointer; opacity: 0.5; -webkit-tap-highlight-color: transparent; }}
                                .btn-start.ready {{ opacity: 1; background: #c0392b; animation: pulse 2s infinite; }}
                                @keyframes pulse {{ 0% {{ box-shadow: 0 0 0 0 rgba(231, 76, 60, 0.7); }} 70% {{ box-shadow: 0 0 0 15px rgba(231, 76, 60, 0); }} 100% {{ box-shadow: 0 0 0 0 rgba(231, 76, 60, 0); }} }}
                            </style>
                            <div class="lcd"><h2 id="lcd-val" class="lcd-val">---</h2><p id="lcd-desc" class="lcd-desc" style="color: #7f8c8d;">Aguardando código...</p></div>
                            <div class="grid">
                                <button type="button" class="btn-key" onclick="pressKey('1')">1</button>
                                <button type="button" class="btn-key" onclick="pressKey('2')">2</button>
                                <button type="button" class="btn-key" onclick="pressKey('3')">3</button>
                                <button type="button" class="btn-key" onclick="pressKey('4')">4</button>
                                <button type="button" class="btn-key" onclick="pressKey('5')">5</button>
                                <button type="button" class="btn-key" onclick="pressKey('6')">6</button>
                                <button type="button" class="btn-key" onclick="pressKey('7')">7</button>
                                <button type="button" class="btn-key" onclick="pressKey('8')">8</button>
                                <button type="button" class="btn-key" onclick="pressKey('9')">9</button>
                                <button type="button" class="btn-key btn-c" onclick="pressKey('C')">C</button>
                                <button type="button" class="btn-key" onclick="pressKey('0')">0</button>
                                <button type="button" class="btn-key btn-del" onclick="pressKey('<')">⌫</button>
                            </div>
                            <button id="btn-start" class="btn-start" onclick="sendCode()" disabled>🔴 CONFIRMAR INTERRUPÇÃO</button>
                            <script>
                                const validCodes = {valid_codes_json};
                                let currentCode = "";
                                function updateLCD() {{
                                    const lcdVal = document.getElementById("lcd-val"); const lcdDesc = document.getElementById("lcd-desc"); const btnStart = document.getElementById("btn-start");
                                    lcdVal.innerText = currentCode === "" ? "---" : currentCode;
                                    if (currentCode === "") {{ lcdDesc.innerText = "Aguardando código..."; lcdDesc.style.color = "#7f8c8d"; btnStart.disabled = true; btnStart.classList.remove("ready"); }} 
                                    else if (validCodes[currentCode]) {{ lcdDesc.innerText = "✅ " + validCodes[currentCode]; lcdDesc.style.color = "#27ae60"; btnStart.disabled = false; btnStart.classList.add("ready"); }} 
                                    else {{ lcdDesc.innerText = "❌ Código não encontrado"; lcdDesc.style.color = "#e74c3c"; btnStart.disabled = true; btnStart.classList.remove("ready"); }}
                                }}
                                function pressKey(k) {{ if (k === 'C') currentCode = ""; else if (k === '<') currentCode = currentCode.slice(0, -1); else currentCode += k; updateLCD(); }}
                                function sendCode() {{
                                    if (!validCodes[currentCode]) return;
                                    document.getElementById("btn-start").innerText = "Processando...";
                                    const inputs = window.parent.document.querySelectorAll('input[aria-label="input_codigo_js_int"]');
                                    if (inputs.length > 0) {{
                                        const input = inputs[0]; let nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                                        nativeSetter.call(input, currentCode); input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                        setTimeout(() => {{ input.focus(); input.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', keyCode: 13, bubbles: true }})); input.blur(); }}, 50);
                                    }}
                                }}
                            </script>
                            """
                            components.html(html_teclado_int, height=650)

                        with tab_lst_int:
                            opcoes_prob = [f"{str(row['descricao']).strip()} ({str(row['codigo']).strip()})" for _, row in df_codigos_parado.iterrows()]
                            problema_selecionado = st.selectbox("Selecione o problema:", [""] + opcoes_prob)
                            st.markdown("<br>", unsafe_allow_html=True)
                            btn_submit_lista_int = st.form_submit_button("🔴 CONFIRMAR INTERRUPÇÃO", use_container_width=True)
                            
                    st.markdown("<br>", unsafe_allow_html=True)
                    btn_cancelar_int = st.form_submit_button("❌ Cancelar Operação", use_container_width=True)
                    
                    if btn_cancelar_int:
                        st.session_state[chave_estado_fin] = None
                        st.rerun()
                    elif btn_submit_lista_int or (codigo_js_int and codigo_js_int in valid_codes):
                        cod_final = codigo_js_int if (codigo_js_int and codigo_js_int in valid_codes) else problema_selecionado.split("(")[-1].replace(")", "").strip() if problema_selecionado else None
                        if cod_final:
                            try: qtd_val_int = int(qtd_str_int)
                            except: qtd_val_int = 0
                            salvar_producao_atual(codigo_parada_novo=cod_final, qtd_informada=qtd_val_int, modalidade_escolhida=modalidade_escolhida)

    # ==========================================
    # ESTADO 3: MÁQUINA PARADA (PROBLEMA)
    # ==========================================
    elif status_db == 'Parado':
        desc_problema = "Desconhecido"
        tipo_problema = "PARADA" 
        
        if cod_ocorrencia and not df_codigos.empty:
            filtro_desc = df_codigos[df_codigos['codigo'].astype(str) == str(cod_ocorrencia)]
            if not filtro_desc.empty:
                desc_problema = str(filtro_desc.iloc[0]['descricao']).strip()
                if 'tipo' in filtro_desc.columns: tipo_problema = str(filtro_desc.iloc[0]['tipo']).strip().upper()

        hora_inicio_iso = hora_inicio_str.replace(" ", "T")
        is_pausa = (tipo_problema == 'NÃO CONTA' or 'DESCONSIDERAR' in tipo_problema)
        
        cor_fundo = "#f39c12" if is_pausa else "#c0392b"
        cor_sombra = "rgba(243, 156, 18, 0.4)" if is_pausa else "rgba(192, 57, 43, 0.4)"
        titulo_card = "☕ PAUSA PROGRAMADA" if is_pausa else "🔴 MÁQUINA PARADA"
        sub_texto = "Pausa em andamento:" if is_pausa else "Problema em andamento:"
        texto_botao = "✅ FINALIZAR INTERVALO" if is_pausa else "✅ PROBLEMA RESOLVIDO (FINALIZAR)"

        js_cronometro = f"""
        <style>
            body {{ margin: 0; padding: 0; font-family: sans-serif; }}
            .caixa-vermelha {{ background-color: {cor_fundo}; color: white; padding: 25px 20px; border-radius: 12px; text-align: center; box-shadow: 0 4px 15px {cor_sombra}; box-sizing: border-box; margin: 0; transition: background-color 0.3s; }}
            .titulo-vermelho {{ margin: 0; font-size: 34px; text-transform: uppercase; font-weight: 900; }}
            .sub-vermelho {{ margin: 10px 0 15px 0; font-size: 18px; opacity: 0.95; }}
            .cronometro {{ font-size: 60px; font-weight: 900; font-family: monospace; letter-spacing: 2px; }}
            @media (max-width: 768px) {{ .caixa-vermelha {{ padding: 20px 10px; }} .titulo-vermelho {{ font-size: 24px; }} .sub-vermelho {{ font-size: 15px; margin: 10px 0 10px 0; }} .cronometro {{ font-size: 40px; letter-spacing: 0px; }} }}
        </style>
        <div class="caixa-vermelha">
            <h1 class="titulo-vermelho">{titulo_card}</h1><p class="sub-vermelho">{sub_texto} <br><b>{desc_problema} ({cod_ocorrencia})</b></p>
            <div id="stopwatch" class="cronometro">00:00:00</div>
        </div>
        <script>
            const startTime = new Date("{hora_inicio_iso}").getTime();
            setInterval(function() {{
                const now = new Date().getTime(); const distance = now - startTime;
                if (distance > 0) {{
                    const h = Math.floor(distance / (1000 * 60 * 60)); const m = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60)); const s = Math.floor((distance % (1000 * 60)) / 1000);
                    document.getElementById("stopwatch").innerHTML = (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
                }}
                
                const isLess1Min = distance < 60000;
                const btns = window.parent.document.querySelectorAll('button');
                btns.forEach(btn => {{
                    const txt = btn.innerText ? btn.innerText.toUpperCase() : "";
                    if(txt.includes('CANCELAR PARADA (ERRO DE SELEÇÃO)')) {{
                        btn.closest('div[data-testid="stButton"]').style.display = isLess1Min ? 'block' : 'none';
                    }}
                    if(txt === '{texto_botao.upper()}') {{
                        btn.closest('div[data-testid="stButton"]').style.display = isLess1Min ? 'none' : 'block';
                    }}
                }});
            }}, 500);
        </script>
        """
        components.html(js_cronometro, height=250)
        
        st.markdown("<br>", unsafe_allow_html=True)
        btn_canc_parada = st.button("❌ CANCELAR PARADA (Erro de Seleção)", use_container_width=True)
        btn_fin_parada = st.button(texto_botao, use_container_width=True, type="primary")
        
        if btn_canc_parada or btn_fin_parada:
            hora_fim = obter_hora_atual()
            hora_inicio_obj = datetime.strptime(hora_inicio_str, "%Y-%m-%d %H:%M:%S")
            duracao_segundos = (hora_fim - hora_inicio_obj).total_seconds()
            
            if duracao_segundos >= 60 and btn_fin_parada:
                dados_nuvem = {
                    "data_registro": hora_inicio_obj.strftime("%Y-%m-%d"),
                    "setor": setor_selecionado, "maquina": maquina_selecionada, 
                    "tipo": tipo_problema,
                    "cod_ocorrencia": cod_ocorrencia, "operador": nomes_operadores,
                    "das": hora_inicio_obj.strftime("%H:%M"), "as_hora": hora_fim.strftime("%H:%M"), "origem": "Chão de Fábrica"
                }
                supa.table("producao_diaria").insert(dados_nuvem).execute()
            
            supa.table("status_maquinas").update({
                "status": "Livre", "hora_inicio": None, "cod_ocorrencia": None, "cod_peca_atual": None
            }).eq("maquina", maquina_selecionada).execute()
            st.rerun()

    # ==========================================
    # 4. HISTÓRICO EXCLUSIVO DO TABLET
    # ==========================================
    st.markdown("<hr style='opacity: 0.2; margin-top: 20px; margin-bottom: 20px;'>", unsafe_allow_html=True)
    st.markdown(f"### 📋 Últimos Registros de Hoje")
    
    hoje_str = obter_hora_atual().strftime("%Y-%m-%d")
    
    if df_nuvem.empty or 'maquina' not in df_nuvem.columns: df_hist = pd.DataFrame()
    else:
        if 'origem' not in df_nuvem.columns: df_nuvem['origem'] = 'Importação'
        if 'tipo' not in df_nuvem.columns: df_nuvem['tipo'] = 'PARADA'
        df_hist = df_nuvem[(df_nuvem['maquina'] == maquina_selecionada) & (df_nuvem['data_registro'] == hoje_str) & (df_nuvem['origem'] == 'Chão de Fábrica')].copy()
    
    if df_hist.empty: st.info("Nenhum apontamento nesta máquina hoje.")
    else:
        df_hist = df_hist.sort_values(by=['data_registro', 'as_hora'], ascending=[False, False]).head(20)
        linhas_html = ""
        for i, row in df_hist.iterrows():
            fundo = "#f9f9f9" if i % 2 != 0 else "#ffffff"
            tipo_bd = str(row.get('tipo', '')).strip().upper()
            codigo_bd = str(row.get('cod_ocorrencia', '')).strip().upper()
            nome_operador_hist = row.get('operador', 'Não registrado')
            
            if codigo_bd == 'P':
                cod_peca = row.get('cod_peca', 'S/N')
                qtd_peca = row.get('quantidade', 0)
                nome_peca_hist = row.get('nome_peca', 'Peça Desconhecida')
                modalidade = row.get('modalidade_processo', 'Simples')
                tag_mod = f" <span style='background:#ecf0f1; color:#7f8c8d; padding:2px 6px; border-radius:4px; font-size:11px; margin-left:5px; border:1px solid #bdc3c7;'>{modalidade}</span>"
                texto_exibicao = f"🟢 <b>Produção:</b> {nome_peca_hist}{tag_mod} <br><span style='font-size: 13px; color: #7f8c8d;'>Cód: {cod_peca} | Qtde Produzida: {qtd_peca} | Operador: {nome_operador_hist}</span>"
            else:
                desc_oco = "Sem Descrição"
                if not df_codigos.empty:
                    f_cod = df_codigos[df_codigos['codigo'].astype(str).str.upper() == codigo_bd]
                    if not f_cod.empty: desc_oco = str(f_cod.iloc[0]['descricao']).strip()
                if tipo_bd == "NÃO CONTA" or "DESCONSIDERAR" in tipo_bd:
                    texto_exibicao = f"🟠 <b>Pausa:</b> {desc_oco} <b>({codigo_bd})</b> <br><span style='font-size: 13px; color: #7f8c8d;'>Operador: {nome_operador_hist}</span>"
                else:
                    texto_exibicao = f"🔴 <b>Parada:</b> {desc_oco} <b>({codigo_bd})</b> <br><span style='font-size: 13px; color: #7f8c8d;'>Operador: {nome_operador_hist}</span>"

            linhas_html += f"<tr style='background-color: {fundo};'><td style='padding: 10px; border-bottom: 1px solid #eee; text-align: center; font-weight: bold; color: #2c3e50;'>{row['das']}</td><td style='padding: 10px; border-bottom: 1px solid #eee; text-align: center; font-weight: bold; color: #2c3e50;'>{row['as_hora']}</td><td style='padding: 10px; border-bottom: 1px solid #eee;'>{texto_exibicao}</td></tr>"
            
        tabela_html = f"<div style='border: 1px solid #eaeaea; border-radius: 8px; overflow: hidden;'><table style='width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 14px;'><thead><tr style='color: white; text-align: left;'><th style='padding: 10px; text-align: center; background-color: #34495e;'>Início</th><th style='padding: 10px; text-align: center; background-color: #34495e;'>Fim</th><th style='padding: 10px; background-color: #34495e;'>Apontamento Registrado</th></tr></thead><tbody>{linhas_html}</tbody></table></div>"
        st.markdown(tabela_html, unsafe_allow_html=True)

    # ==========================================
    # 5. RODAPÉ DO TERMINAL
    # ==========================================
    st.markdown("<hr style='opacity: 0.2; margin-top: 30px;'>", unsafe_allow_html=True)
    texto_rodape = f"{setor_selecionado} &nbsp;|&nbsp; {maquina_selecionada} &nbsp;|&nbsp; {nomes_operadores}"
    st.markdown(f"<div style='text-align: center; color: #7f8c8d; font-size: 16px; margin-bottom: 25px; font-weight: 700; text-transform: uppercase;'>{texto_rodape}</div>", unsafe_allow_html=True)

    if not is_travado:
        st.info("💡 Modo de Gestão: Altere a máquina abaixo para visualizar seu status.")
        cr1, cr2 = st.columns(2)
        with cr1: st.selectbox("🏭 Setor", lista_setores_nuvem, key="cf_setor")
        with cr2: st.selectbox("⚙️ Máquina", lista_maquinas_nuvem, key="cf_maquina")

    cfg = banco.obter_configuracoes()
    titulo_app = cfg.get('titulo_programa', 'PCP Avelan')
    logo_b64 = cfg.get('logo_base64', None)
    
    c1, c2 = st.columns([7, 3])
    with c1:
        if logo_b64: st.markdown(f'<div style="display: flex; align-items: center; gap: 15px;"><img src="data:image/png;base64,{logo_b64}" style="max-height: 40px;"><h3 style="margin:0; color: #2c3e50;">{titulo_app}</h3></div>', unsafe_allow_html=True)
        else: st.markdown(f'<h3 style="margin:0; color: #2c3e50;">🏭 {titulo_app}</h3>', unsafe_allow_html=True)
    with c2:
        if st.button("🚪 Sair do Sistema", use_container_width=True, key="btn_sair_cf"):
            st.session_state['usuario_logado'] = None
            try: st.query_params.clear()
            except: st.experimental_set_query_params()
            st.rerun()

    # ==========================================
    # SCRIPT PARA INFLAR OS BOTÕES DE AÇÃO 
    # ==========================================
    js_cores = """
    <script>
        setInterval(() => {
            const btns = window.parent.document.querySelectorAll('button');
            btns.forEach(btn => {
                const texto = btn.innerText ? btn.innerText.toUpperCase() : "";
                
                if(texto === '▶️ CONFIRMAR E INICIAR' || texto === '💾 CONFIRMAR E SALVAR' || texto === '✅ FINALIZAR (CONCLUÍDO)' || texto === '✅ PROBLEMA RESOLVIDO (FINALIZAR)' || texto === '✅ FINALIZAR INTERVALO') {
                    btn.style.setProperty('height', '90px', 'important');
                    btn.style.setProperty('font-size', '22px', 'important');
                    btn.style.setProperty('font-weight', '900', 'important');
                    btn.style.setProperty('border-radius', '12px', 'important');
                    if (!btn.disabled) {
                        btn.style.setProperty('background-color', '#27ae60', 'important');
                        btn.style.setProperty('border-color', '#27ae60', 'important');
                        btn.style.setProperty('color', 'white', 'important');
                    } else {
                        btn.style.setProperty('background-color', '#ecf0f1', 'important');
                        btn.style.setProperty('border-color', '#bdc3c7', 'important');
                        btn.style.setProperty('color', '#95a5a6', 'important');
                    }
                }
                else if(texto === '🔴 CONFIRMAR PARADA' || texto === '🔴 INTERROMPER (POR FALHA)' || texto === '🔴 CONFIRMAR INTERRUPÇÃO') {
                    btn.style.setProperty('height', '90px', 'important');
                    btn.style.setProperty('font-size', '22px', 'important');
                    btn.style.setProperty('font-weight', '900', 'important');
                    btn.style.setProperty('border-radius', '12px', 'important');
                    if (!btn.disabled) {
                        btn.style.setProperty('background-color', '#c0392b', 'important');
                        btn.style.setProperty('border-color', '#c0392b', 'important');
                        btn.style.setProperty('color', 'white', 'important');
                    } else {
                        btn.style.setProperty('background-color', '#ecf0f1', 'important');
                        btn.style.setProperty('border-color', '#bdc3c7', 'important');
                        btn.style.setProperty('color', '#95a5a6', 'important');
                    }
                }
                else if(texto.includes('CANCELAR PRODUÇÃO (ERRO') || texto.includes('CANCELAR PARADA (ERRO')) {
                    btn.style.setProperty('height', '90px', 'important');
                    btn.style.setProperty('font-size', '22px', 'important');
                    btn.style.setProperty('font-weight', '900', 'important');
                    btn.style.setProperty('border-radius', '12px', 'important');
                    if (!btn.disabled) {
                        btn.style.setProperty('background-color', '#e67e22', 'important');
                        btn.style.setProperty('border-color', '#e67e22', 'important');
                        btn.style.setProperty('color', 'white', 'important');
                    }
                }
            });
            
            // BLOQUEIO DO TECLADO NATIVO NOS MENUS DROP-DOWN
            const selects = window.parent.document.querySelectorAll('div[data-baseweb="select"] input');
            selects.forEach(sel => {
                sel.setAttribute('inputmode', 'none');
                sel.readOnly = true;
            });

        }, 300);
    </script>
    """
    components.html(js_cores, height=0)