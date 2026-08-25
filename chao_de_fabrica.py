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
def cache_obter_caixas():
    supa = banco.conectar()
    try:
        resp = supa.table("caixas_matriz").select("*").execute()
        return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    except:
        return pd.DataFrame()

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

def atualizar_status_maquina(supa, setor, maquina, dados):
    resp = supa.table("status_maquinas").select("maquina").eq("setor", setor).eq("maquina", maquina).execute()
    if not resp.data:
        dados_in = dados.copy()
        dados_in['setor'] = setor
        dados_in['maquina'] = maquina
        return supa.table("status_maquinas").insert(dados_in).execute()
    else:
        return supa.table("status_maquinas").update(dados).eq("setor", setor).eq("maquina", maquina).execute()

def registrar_telemetria(supa, setor, maquina, acao):
    try:
        agora_str = obter_hora_atual().strftime("%Y-%m-%d %H:%M:%S")
        df_est = cache_obter_estrutura()
        if not df_est.empty:
            df_limpo = df_est[['setor', 'maquina']].dropna().drop_duplicates()
            maquinas_validas = set(df_limpo['setor'].astype(str).str.strip() + "||" + df_limpo['maquina'].astype(str).str.strip())
            total_maquinas = len(maquinas_validas)
        else:
            maquinas_validas = set()
            total_maquinas = 1
            
        ativas = 0
        if maquinas_validas:
            resp = supa.table("status_maquinas").select("status, setor, maquina").eq("status", "Produzindo").execute()
            if resp.data:
                for m in resp.data:
                    chave_m = str(m.get("setor")).strip() + "||" + str(m.get("maquina")).strip()
                    if chave_m in maquinas_validas:
                        ativas += 1
        
        percentual = round((ativas / total_maquinas) * 100.0, 2) if total_maquinas > 0 else 0.0
        texto_acao = f"[{setor}] {maquina}: {acao}"
        
        dados_telemetria = {"data_hora": agora_str, "percentual": float(percentual), "acao": str(texto_acao), "maquinas_ativas": int(ativas), "maquinas_totais": int(total_maquinas)}
        supa.table("historico_operacao").insert([dados_telemetria]).execute()
        return True, ""
    except Exception as e:
        return False, str(e)

# ==========================================
# COMPONENTES HTML BLINDADOS (SEM F-STRINGS)
# ==========================================
@st.dialog("📦 Catálogo de Produtos")
def modal_selecionar_produto(lista_exibicao, separador, chave_memoria):
    st.markdown("Toque no botão correspondente ao produto:")
    for p in lista_exibicao:
        if p == separador:
            st.markdown("<hr style='margin: 15px 0; border: 1px dashed #ccc;'>", unsafe_allow_html=True)
        else:
            if st.button(p, use_container_width=True, key=f"btn_modal_{p}"):
                st.session_state[chave_memoria] = p
                st.rerun()

def obter_html_teclado_qtd(label_input_js, titulo="Quantidade"):
    """Teclado HTML exclusivo para quantidades (limpa zeros à esquerda)"""
    html_content = """
    <style>
        body { font-family: sans-serif; margin: 0; padding: 10px; }
        .lcd { background: #ffffff; padding: 15px; border-radius: 12px; text-align: center; border: 2px solid #dcdde1; box-shadow: inset 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 20px; }
        .lcd-val { margin: 0; font-family: monospace; font-size: 50px; letter-spacing: 5px; color: #27ae60; min-height: 60px; font-weight: 900; }
        .lcd-desc { margin: 5px 0 0 0; font-size: 16px; font-weight: bold; color: #7f8c8d; text-transform: uppercase; letter-spacing: 1px; }
        .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; }
        .btn-key { background: #ffffff; border: 1px solid #dcdde1; border-radius: 12px; font-size: 28px; font-weight: 900; color: #2c3e50; padding: 20px 0; cursor: pointer; transition: all 0.1s; box-shadow: 0 4px 6px rgba(0,0,0,0.05); -webkit-tap-highlight-color: transparent; }
        .btn-key:active { transform: scale(0.95); background: #f1f2f6; }
        .btn-c { color: #e74c3c; }
        .btn-del { color: #e67e22; }
    </style>
    <div class="lcd">
        <h2 id="lcd-val" class="lcd-val">0</h2>
        <p class="lcd-desc">TITULO_PLACEHOLDER</p>
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
        function updateLCD() {
            const lcdVal = document.getElementById("lcd-val");
            lcdVal.innerText = currentQty === "" ? "0" : currentQty;
            const inputs = window.parent.document.querySelectorAll('input');
            inputs.forEach(inp => {
                if(inp.getAttribute('aria-label') === 'LABEL_PLACEHOLDER') {
                    let nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                    nativeSetter.call(inp, currentQty === "" ? "0" : currentQty); 
                    inp.dispatchEvent(new Event('input', { bubbles: true }));
                }
            });
        }
        function pressKey(k) { 
            if (k === 'C') currentQty = ""; 
            else if (k === '<') currentQty = currentQty.slice(0, -1); 
            else currentQty += k; 
            
            if (currentQty.length > 1 && currentQty.startsWith("0")) currentQty = currentQty.substring(1);
            if (currentQty.length > 6) currentQty = currentQty.slice(0, 6);
            
            updateLCD(); 
        }
        setTimeout(updateLCD, 500);
    </script>
    """
    return html_content.replace('LABEL_PLACEHOLDER', label_input_js).replace('TITULO_PLACEHOLDER', titulo)

def obter_html_teclado_parada(label_input_js, valid_codes_json, texto_botao="🔴 CONFIRMAR PARADA"):
    """Teclado HTML exclusivo para Códigos de Parada (Aceita '00' livremente)"""
    html_content = """
    <style>
        body { font-family: sans-serif; margin: 0; padding: 10px; }
        .lcd { background: #ffffff; padding: 15px; border-radius: 12px; text-align: center; border: 2px solid #dcdde1; box-shadow: inset 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 20px; }
        .lcd-val { margin: 0; font-family: monospace; font-size: 45px; letter-spacing: 5px; color: #2c3e50; min-height: 55px; font-weight: 900; }
        .lcd-desc { margin: 5px 0 0 0; font-size: 18px; font-weight: bold; min-height: 25px; transition: color 0.2s; }
        .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 25px; }
        .btn-key { background: #ffffff; border: 1px solid #dcdde1; border-radius: 12px; font-size: 28px; font-weight: 900; color: #2c3e50; padding: 20px 0; cursor: pointer; transition: all 0.1s; box-shadow: 0 4px 6px rgba(0,0,0,0.05); -webkit-tap-highlight-color: transparent; }
        .btn-key:active { transform: scale(0.95); background: #f1f2f6; }
        .btn-c { color: #e74c3c; }
        .btn-del { color: #e67e22; }
    </style>
    <div class="lcd">
        <h2 id="lcd-val" class="lcd-val">---</h2>
        <p id="lcd-desc" class="lcd-desc" style="color: #7f8c8d;">CÓDIGO DE PARADA</p>
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
    <div id="status-container" style="background: #e8f8f5; padding: 15px; border-radius: 8px; margin-bottom: 20px; font-weight: bold; color: #27ae60; font-size: 16px; display: none;">
        ✅ Identificado: <span id="status-text"></span>
    </div>

    <script>
        const validCodes = VALID_CODES_PLACEHOLDER;
        let currentCode = "";
        
        function updateLCD() {
            const lcdVal = document.getElementById("lcd-val");
            const lcdDesc = document.getElementById("lcd-desc");
            const statusContainer = document.getElementById("status-container");
            const statusText = document.getElementById("status-text");
            
            lcdVal.innerText = currentCode === "" ? "---" : currentCode;

            if (currentCode === "") {
                lcdDesc.innerText = "CÓDIGO DE PARADA";
                lcdDesc.style.color = "#7f8c8d";
                statusContainer.style.display = "none";
            } else if (validCodes[currentCode]) {
                lcdDesc.innerText = "CÓDIGO DE PARADA";
                statusText.innerText = validCodes[currentCode];
                statusContainer.style.display = "block";
                statusContainer.style.backgroundColor = "#e8f8f5";
                statusContainer.style.color = "#27ae60";
            } else {
                lcdDesc.innerText = "CÓDIGO DE PARADA";
                statusText.innerText = "Código não encontrado";
                statusContainer.style.display = "block";
                statusContainer.style.backgroundColor = "#fdedec";
                statusContainer.style.color = "#c0392b";
            }
            
            const inputs = window.parent.document.querySelectorAll('input');
            inputs.forEach(inp => {
                if(inp.getAttribute('aria-label') === 'LABEL_PLACEHOLDER') {
                    let nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                    nativeSetter.call(inp, currentCode);
                    inp.dispatchEvent(new Event('input', { bubbles: true }));
                }
            });
        }
        
        function pressKey(k) {
            if (k === 'C') currentCode = "";
            else if (k === '<') currentCode = currentCode.slice(0, -1);
            else currentCode += k;
            
            if (currentCode.length > 6) currentCode = currentCode.slice(0, 6);
            updateLCD();
        }
    </script>
    """
    return html_content.replace('VALID_CODES_PLACEHOLDER', valid_codes_json).replace('LABEL_PLACEHOLDER', label_input_js).replace('TEXTO_BOTAO_PLACEHOLDER', texto_botao)

def renderizar(df_nuvem, df_codigos):
    if 'tk_counter' not in st.session_state: 
        st.session_state['tk_counter'] = 0

    # CSS GLOBAL BLINDADO
    st.markdown("""
        <style>
        .block-container { padding-top: 0.5rem !important; padding-bottom: 0rem !important; margin-bottom: 0rem !important; }
        div[data-testid="stTabs"] { margin-top: -15px; }
        footer { display: none !important; }
        #MainMenu { visibility: hidden; }
        div[data-baseweb="select"] > div { min-height: 65px !important; font-size: 20px !important; border-radius: 8px !important; }
        div[data-baseweb="select"] { font-size: 20px !important; }
        button[data-baseweb="tab"] { font-size: 20px !important; font-weight: 800 !important; padding: 20px 25px !important; }
        div[data-testid="stRadio"] label { padding: 5px 15px; cursor: pointer; font-size: 18px !important; }
        
        /* 🔥 Esconde caixas de texto nativas da UI */
        div[data-testid="stTextInput"] {
            display: none !important;
        }
        
        ::-webkit-scrollbar { display: none; }
        </style>
    """, unsafe_allow_html=True)

    supa = banco.conectar()
    df_est = cache_obter_estrutura()
    if df_est.empty:
        st.warning("⚠️ Nenhuma estrutura de fábrica cadastrada. Vá na aba Configurações > Estrutura.")
        return

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
    is_embalagem = (str(setor_selecionado).strip().upper() == "EMBALAGEM")

    permite_dupla = False
    maq_row = df_est[(df_est['setor'] == setor_selecionado) & (df_est['maquina'] == maquina_selecionada)]
    if not maq_row.empty:
        val_raw = maq_row.iloc[0].get('permite_producao_dupla', False)
        permite_dupla = True if str(val_raw).strip().lower() == 'true' or val_raw is True else False

    hoje_str = obter_hora_atual().strftime("%Y-%m-%d")
    producao_hoje_pecas = {}
    
    if not df_nuvem.empty and 'maquina' in df_nuvem.columns and 'setor' in df_nuvem.columns:
        if 'tipo' not in df_nuvem.columns: df_nuvem['tipo'] = 'PARADA'
        
        df_prod_hoje = df_nuvem[
            (df_nuvem['maquina'] == maquina_selecionada) & 
            (df_nuvem['setor'] == setor_selecionado) & 
            (df_nuvem['data_registro'] == hoje_str) & 
            (df_nuvem['tipo'].astype(str).str.strip().str.upper() == 'PRODUÇÃO')
        ]
        
        for _, row_prod in df_prod_hoje.iterrows():
            c_peca = str(row_prod.get('cod_peca', '')).strip()
            qtd = row_prod.get('quantidade', 0)
            try: qtd = int(qtd)
            except: qtd = 0
            
            if c_peca not in producao_hoje_pecas:
                producao_hoje_pecas[c_peca] = []
            if qtd > 0:
                producao_hoje_pecas[c_peca].append(qtd)

    response = supa.table("status_maquinas").select("*").eq("maquina", maquina_selecionada).eq("setor", setor_selecionado).execute()
    status_db = 'Livre'
    hora_inicio_str = None
    cod_ocorrencia = None
    cod_peca_atual = None
    ultimo_produto_sel = ""
    ultima_peca_sel = ""
    
    if response.data:
        dados_maq = response.data[0]
        status_db = dados_maq.get('status', 'Livre')
        if status_db == 'Trabalhando': status_db = 'Livre'
        hora_inicio_str = dados_maq.get('hora_inicio')
        cod_ocorrencia = dados_maq.get('cod_ocorrencia')
        cod_peca_atual = dados_maq.get('cod_peca_atual')
        ultimo_produto_sel = dados_maq.get('ultimo_produto_sel', "")
        ultima_peca_sel = dados_maq.get('ultima_peca_sel', "")

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
            last_prod = ultimo_produto_sel if ultimo_produto_sel else ""
            last_peca = ultima_peca_sel if ultima_peca_sel else ""
            
            st.markdown("<br>", unsafe_allow_html=True)
            c_header1, c_header2 = st.columns([7, 3])
            with c_header1: st.markdown("<div style='font-size: 20px; font-weight: bold; color: #2c3e50; margin:0;'>📦 Seleção de Material</div>", unsafe_allow_html=True)
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
                
                mapa_ops = {}
                ops_ativas_unicas = []
                try:
                    resp_ops = supa.table("planejamento_ops").select("*").eq("status", "Em Andamento").order("ordem_prioridade", desc=False).order("id", desc=True).execute()
                    for op in (resp_ops.data if resp_ops.data else []):
                        p_name = op['produto_formula']
                        if p_name not in ops_ativas_unicas:
                            ops_ativas_unicas.append(p_name)
                            mapa_ops[p_name] = op
                except:
                    pass
                
                separador = "───────────────────────────────"
                lista_exibicao_final = []
                mapa_prod_real = {}
                ops_presentes = [p for p in ops_ativas_unicas if p in lista_todos]
                
                for idx_op, p in enumerate(ops_presentes):
                    numero_op = idx_op + 1
                    display_name = f"🔥 [OP {numero_op}] {p}"
                    lista_exibicao_final.append(display_name)
                    mapa_prod_real[display_name] = p
                    
                if ops_presentes:
                    lista_exibicao_final.append(separador)
                    mapa_prod_real[separador] = None
                    
                for p in lista_exibicao:
                    if p not in ops_presentes:
                        lista_exibicao_final.append(p)
                        mapa_prod_real[p] = p
                
                chave_mem_prod = f"mem_prod_{setor_selecionado}_{maquina_selecionada}"
                if chave_mem_prod not in st.session_state:
                    initial_val = ""
                    if last_prod:
                        if last_prod in ops_presentes:
                            numero_op = ops_presentes.index(last_prod) + 1
                            initial_val = f"🔥 [OP {numero_op}] {last_prod}"
                        elif last_prod in lista_exibicao and last_prod not in ops_presentes:
                            initial_val = last_prod
                    elif ops_presentes and len(lista_exibicao_final) > 1:
                        initial_val = lista_exibicao_final[0]
                    st.session_state[chave_mem_prod] = initial_val

                sel_prod_display = st.session_state[chave_mem_prod]
                sel_prod = mapa_prod_real.get(sel_prod_display)

                texto_exibicao = sel_prod_display if sel_prod_display else "Selecione..."
                st.markdown(f"""
                <div style='background: #f8f9fa; border: 1px solid #e1e8ed; border-radius: 8px; padding: 15px; margin-bottom: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);'>
                    <div style='font-size:14px; color:#7f8c8d; font-weight:bold; text-transform:uppercase;'>Produto da Linha:</div>
                    <div style='font-size:18px; font-weight:900; color:#2c3e50; margin-top:5px; white-space: normal; word-wrap: break-word;'>{texto_exibicao}</div>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button("🔍 ALTERAR PRODUTO", use_container_width=True):
                    modal_selecionar_produto(lista_exibicao_final, separador, chave_mem_prod)

                if sel_prod:
                    is_in_op = sel_prod in mapa_ops
                    producao_op_pecas = {}
                    
                    if is_in_op:
                        op_info = mapa_ops[sel_prod]
                        data_inicio_op = op_info['data_inicio'].split(" ")[0].split("T")[0]
                        qtd_op = int(op_info['quantidade_planejada'])

                        if not df_nuvem.empty and 'setor' in df_nuvem.columns:
                            df_op_prod = df_nuvem[
                                (df_nuvem['setor'] == setor_selecionado) &
                                (df_nuvem['data_registro'] >= data_inicio_op) &
                                (df_nuvem['tipo'].astype(str).str.strip().str.upper() == 'PRODUÇÃO')
                            ]
                            for _, r in df_op_prod.iterrows():
                                c = str(r.get('cod_peca', '')).strip()
                                q = int(float(r.get('quantidade', 0))) if pd.notna(r.get('quantidade')) else 0
                                producao_op_pecas[c] = producao_op_pecas.get(c, 0) + q

                    if is_embalagem:
                        df_caixas = cache_obter_caixas()
                        if not df_caixas.empty:
                            df_cx_filtro = df_caixas[df_caixas['produto_formula'] == sel_prod]
                            lista_pecas_limpa = [f"Caixa {row['num_caixa']} (Cód: {row['cod_caixa']})" for _, row in df_cx_filtro.iterrows() if pd.notna(row['cod_caixa']) and str(row['cod_caixa']).strip() not in ["", "None", "nan"]]
                        else:
                            lista_pecas_limpa = []
                        df_pecas = pd.DataFrame()
                    else:
                        df_pecas = df_produtos[df_produtos['produto_formula'] == sel_prod]
                        lista_pecas_limpa = [f"{row['descricao']} (Cód: {row['cod']})" for _, row in df_pecas.iterrows()]
                    
                    if sel_prod == last_prod and last_peca and last_peca not in lista_pecas_limpa:
                        lista_pecas_limpa.append(last_peca)
                        
                    lista_pendentes = []
                    lista_concluidas = []
                    mapa_exibicao_limpa = {}
                    
                    for peca_limpa in lista_pecas_limpa:
                        codigo_ext = peca_limpa.split("(Cód: ")[-1].replace(")", "").strip()
                        
                        # --- LINHA 2: PRODUÇÃO DE HOJE ---
                        if codigo_ext in producao_hoje_pecas and producao_hoje_pecas[codigo_ext]:
                            lista_qtds = producao_hoje_pecas[codigo_ext]
                            total_hoje = sum(lista_qtds)
                            if len(lista_qtds) > 1:
                                resumo_hoje = f"📦 Produzido hoje: {' + '.join(map(str, lista_qtds))} = {total_hoje} un."
                            else:
                                resumo_hoje = f"📦 Produzido hoje: {total_hoje} un."
                        else:
                            resumo_hoje = "📦 Produzido hoje: 0 un."
                            
                        if is_in_op:
                            qnt_por_produto = 1
                            if not is_embalagem and not df_pecas.empty:
                                df_peca_info = df_pecas[df_pecas['cod'].astype(str) == codigo_ext]
                                if not df_peca_info.empty:
                                    try: qnt_por_produto = int(float(df_peca_info.iloc[0].get('qnt', 1)))
                                    except: qnt_por_produto = 1

                            meta = qnt_por_produto * qtd_op
                            prod = producao_op_pecas.get(codigo_ext, 0)
                            perc = (prod / meta * 100) if meta > 0 else 0
                            is_concluida = prod >= meta
                            str_perc = str(round(perc, 1)).replace('.', ',')

                            # --- LINHA 3: DADOS DA OP ---
                            linha_op = f"🎯 OP — Necessidade: {meta} | Produzido: {prod} | {str_perc}%"
                            
                            if is_concluida:
                                texto_completo = f"✅ [CONCLUÍDA] {peca_limpa} *{resumo_hoje}* *{linha_op}*"
                                lista_concluidas.append(texto_completo)
                            else:
                                texto_completo = f"{peca_limpa} *{resumo_hoje}* *{linha_op}*"
                                lista_pendentes.append(texto_completo)
                        else:
                            texto_completo = f"{peca_limpa} *{resumo_hoje}*"
                            lista_pendentes.append(texto_completo)
                            
                        mapa_exibicao_limpa[texto_completo] = peca_limpa

                    mostrar_concluidas = False
                    if lista_concluidas:
                        st.markdown("<br>", unsafe_allow_html=True)
                        cb_key = f"cb_conc_{setor_selecionado}_{maquina_selecionada}"
                        mostrar_concluidas = st.checkbox("☑️ Exibir peças já concluídas na OP (Retrabalho/Reposição)", key=cb_key, value=False)
                        st.markdown("<br>", unsafe_allow_html=True)

                    lista_exibicao_pecas = lista_pendentes.copy()
                    if mostrar_concluidas:
                        lista_exibicao_pecas.extend(lista_concluidas)
                        
                    idx_peca = 0
                    if sel_prod == last_prod and last_peca:
                        for i, txt in enumerate(lista_exibicao_pecas):
                            if mapa_exibicao_limpa[txt] == last_peca:
                                idx_peca = i
                                break
                    
                    if not lista_exibicao_pecas:
                        st.success("🎉 Todas as peças deste produto já atingiram a meta da OP! (Use a caixinha acima se precisar relançar alguma).")
                    else:
                        st.markdown("""
                            <style>
                            div[data-testid='stRadio'] { width: 100% !important; }
                            div[data-testid='stRadio'] > div { width: 100% !important; gap: 12px; }
                            div[data-testid='stRadio'] label {
                                background-color: #ffffff; border: 1px solid #bdc3c7; border-radius: 8px; padding: 16px 20px; width: 100%; cursor: pointer; transition: all 0.2s ease-in-out; margin: 0;
                            }
                            div[data-testid='stRadio'] em { 
                                display: block; margin-top: 6px; font-size: 14px; font-weight: 500; color: #7f8c8d; font-style: normal; 
                            }
                            div[data-testid='stRadio'] label[data-checked="true"] { background-color: #f4f6f7; border-color: #d1d8e0; }
                            div[data-testid='stRadio'] label > div:first-child { display: none !important; }
                            div[data-testid='stRadio'] label p { font-size: 16px; font-weight: 600; color: #2c3e50; margin: 0; text-align: left !important; width: 100%; display: block; }
                            div[data-testid='stRadio'] label[data-checked="true"] p { color: #ff4b4b !important; }
                            div[data-testid='stRadio'] label[data-checked="true"] em { color: #fcebeb !important; }
                            div[data-testid='stRadio'] label[data-checked="true"] p::before { content: '✅ '; }
                            </style>
                        """, unsafe_allow_html=True)
                        
                        titulo_peca = "2. Toque na embalagem/volume:" if is_embalagem else "2. Toque na peça para selecionar:"
                        st.markdown(f"<h4 style='color: #2c3e50; font-size: 16px; margin-top: 5px;'>{titulo_peca}</h4>", unsafe_allow_html=True)
                        
                        sel_peca_exibicao = st.radio("Selecione a Peça", lista_exibicao_pecas, index=idx_peca, label_visibility="collapsed")
                        
                        if sel_peca_exibicao and sel_peca_exibicao in mapa_exibicao_limpa:
                            peca_atual_limpa = mapa_exibicao_limpa[sel_peca_exibicao]
                            nome_peca_curto = peca_atual_limpa.split("(Cód:")[0].strip()
                        else:
                            nome_peca_curto = "VOLUME" if is_embalagem else "PEÇA"
                            
                        texto_btn_iniciar = f"▶️ INICIAR: {nome_peca_curto}"
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button(texto_btn_iniciar, type="primary", use_container_width=True):
                            sel_peca_limpa = mapa_exibicao_limpa[sel_peca_exibicao]
                            codigo_peca = sel_peca_limpa.split("(Cód: ")[-1].replace(")", "").strip()
                            agora = obter_hora_atual().strftime("%Y-%m-%d %H:%M:%S")
                            
                            val_cod_peca_db = codigo_peca if not is_embalagem else None
                            
                            dados_update = {
                                "status": "Produzindo", 
                                "cod_peca_atual": val_cod_peca_db, 
                                "hora_inicio": agora, 
                                "cod_ocorrencia": "P",
                                "ultimo_produto_sel": sel_prod,
                                "ultima_peca_sel": sel_peca_limpa
                            }
                            
                            try:
                                atualizar_status_maquina(supa, setor_selecionado, maquina_selecionada, dados_update)
                                sucesso, erro = registrar_telemetria(supa, setor_selecionado, maquina_selecionada, "Iniciou Produção")
                                if not sucesso:
                                    st.error(f"❌ ERRO AO GRAVAR HISTÓRICO: {erro}")
                                    st.stop()
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"Erro ao iniciar produção: {e}")

            else:
                st.info("Nenhum produto cadastrado na Matriz.")

        with tab_parada:
            st.markdown("<br>", unsafe_allow_html=True)
            if not df_codigos_parado.empty:
                valid_codes = {str(row['codigo']).strip(): str(row['descricao']).strip() for _, row in df_codigos_parado.iterrows()}
                valid_codes_json = json.dumps(valid_codes)
                
                tab_tcl, tab_lst = st.tabs(["🔢 Teclado Numérico", "📄 Selecionar na Lista"])
                
                with tab_tcl:
                    tk_val = st.session_state.get('tk_counter', 0)
                    chave_din_cod = f"in_cod_livre_{tk_val}"
                    
                    codigo_digitado = st.text_input("input_cod_livre", key=chave_din_cod, label_visibility="collapsed")
                    components.html(obter_html_teclado_parada("input_cod_livre", valid_codes_json, "🔴 CONFIRMAR PARADA"), height=650)
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    if codigo_digitado in valid_codes:
                        if st.button("🔴 CONFIRMAR PARADA", use_container_width=True, type="primary"):
                            agora = obter_hora_atual().strftime("%Y-%m-%d %H:%M:%S")
                            atualizar_status_maquina(supa, setor_selecionado, maquina_selecionada, {
                                "status": "Parado", "cod_peca_atual": None, "cod_ocorrencia": codigo_digitado, "hora_inicio": agora
                            })
                            registrar_telemetria(supa, setor_selecionado, maquina_selecionada, f"Parada Iniciada ({codigo_digitado})")
                            st.session_state['tk_counter'] = st.session_state.get('tk_counter', 0) + 1 
                            st.rerun()

                with tab_lst:
                    opcoes_prob = [f"{str(row['descricao']).strip()} ({str(row['codigo']).strip()})" for _, row in df_codigos_parado.iterrows()]
                    problema_selecionado = st.selectbox("Selecione o problema:", [""] + opcoes_prob)
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🔴 CONFIRMAR PARADA", use_container_width=True, type="primary", key="btn_p_lista"):
                        cod_final = problema_selecionado.split("(")[-1].replace(")", "").strip() if problema_selecionado else None
                        if cod_final:
                            agora = obter_hora_atual().strftime("%Y-%m-%d %H:%M:%S")
                            atualizar_status_maquina(supa, setor_selecionado, maquina_selecionada, {
                                "status": "Parado", "cod_peca_atual": None, "cod_ocorrencia": cod_final, "hora_inicio": agora
                            })
                            registrar_telemetria(supa, setor_selecionado, maquina_selecionada, f"Parada Iniciada ({cod_final})")
                            st.rerun()
            else: st.warning(f"⚠️ Não há nenhum código configurado para este setor.")

    # ==========================================
    # ESTADO 2: PRODUZINDO LOTE ATUAL
    # ==========================================
    elif status_db == 'Produzindo':
        nome_peca = "Peça Desconhecida"
        
        if not cod_peca_atual and is_embalagem and ultima_peca_sel and "(Cód:" in ultima_peca_sel:
            cod_peca_atual = ultima_peca_sel.split("(Cód: ")[-1].replace(")", "").strip()
            
        if cod_peca_atual:
            if is_embalagem:
                df_caixas = cache_obter_caixas()
                if not df_caixas.empty:
                    df_filtro = df_caixas[df_caixas['cod_caixa'].astype(str) == str(cod_peca_atual)]
                    if not df_filtro.empty:
                        nome_peca = f"{df_filtro.iloc[0]['produto_formula']} ➔ Caixa {df_filtro.iloc[0]['num_caixa']}"
            else:
                if not df_produtos.empty:
                    df_filtro = df_produtos[df_produtos['cod'].astype(str) == str(cod_peca_atual)]
                    if not df_filtro.empty:
                        nome_peca = f"{df_filtro.iloc[0]['produto_formula']} ➔ {df_filtro.iloc[0]['descricao']}"

        hora_inicio_iso = hora_inicio_str.replace(" ", "T") if hora_inicio_str else ""
        desc_fab = "Embalando:" if is_embalagem else "Fabricando:"

        html_cronometro = """
        <style>
            body { margin: 0; padding: 0; font-family: sans-serif; }
            .caixa { background-color: #27ae60; color: white; padding: 25px 20px; border-radius: 12px; text-align: center; box-shadow: 0 4px 15px rgba(39, 174, 96, 0.4); box-sizing: border-box; margin: 0; }
            .titulo { margin: 0; font-size: 34px; text-transform: uppercase; font-weight: 900; }
            .sub { margin: 10px 0 15px 0; font-size: 18px; opacity: 0.95; }
            .cronometro { font-size: 60px; font-weight: 900; font-family: monospace; letter-spacing: 2px; }
            @media (max-width: 768px) { .caixa { padding: 20px 10px; } .titulo { font-size: 24px; } .sub { font-size: 15px; margin: 10px 0 10px 0; } .cronometro { font-size: 40px; letter-spacing: 0px; } }
        </style>
        <div class="caixa">
            <h1 class="titulo">🟢 EM PRODUÇÃO</h1><p class="sub">DESC_FAB_PLACEHOLDER <br><b>NOME_PECA_PLACEHOLDER (Cód: COD_PECA_PLACEHOLDER)</b></p>
            <div id="stopwatch" class="cronometro">00:00:00</div>
        </div>
        <script>
            const startTime = new Date("HORA_INICIO_PLACEHOLDER").getTime();
            setInterval(function() {
                const now = new Date().getTime(); const distance = now - startTime;
                if (distance > 0) {
                    const h = Math.floor(distance / (1000 * 60 * 60)); const m = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60)); const s = Math.floor((distance % (1000 * 60)) / 1000);
                    document.getElementById("stopwatch").innerHTML = (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
                }
            }, 500);
        </script>
        """
        html_cronometro = html_cronometro.replace("DESC_FAB_PLACEHOLDER", desc_fab).replace("NOME_PECA_PLACEHOLDER", nome_peca).replace("COD_PECA_PLACEHOLDER", str(cod_peca_atual)).replace("HORA_INICIO_PLACEHOLDER", hora_inicio_iso)
        components.html(html_cronometro, height=250)
        
        chave_estado_fin = f"fin_estado_{setor_selecionado}_{maquina_selecionada}"
        estado_fin = st.session_state.get(chave_estado_fin, None)
        
        if hora_inicio_str:
            hora_fim_calc = obter_hora_atual()
            hora_inicio_calc = datetime.strptime(hora_inicio_str, "%Y-%m-%d %H:%M:%S")
            duracao_calc = (hora_fim_calc - hora_inicio_calc).total_seconds()
        else:
            duracao_calc = 999
            
        if not estado_fin:
            st.markdown("<br>", unsafe_allow_html=True)
            
            if duracao_calc < 60:
                if st.button("❌ CANCELAR PRODUÇÃO (Erro de Seleção)", use_container_width=True, key="btn_canc_erro_prod"):
                    atualizar_status_maquina(supa, setor_selecionado, maquina_selecionada, {
                        "status": "Livre", "hora_inicio": None, "cod_ocorrencia": None, "cod_peca_atual": None
                    })
                    registrar_telemetria(supa, setor_selecionado, maquina_selecionada, "Produção Cancelada")
                    st.rerun()
            else:
                c1, c2 = st.columns(2)
                with c1: 
                    if st.button("✅ FINALIZAR (Concluído)", use_container_width=True, type="primary", key="btn_fin_conc"):
                        st.session_state[chave_estado_fin] = "CONCLUIDO"
                        st.rerun()
                with c2: 
                    if st.button("🔴 INTERROMPER (Por Falha)", use_container_width=True, type="primary", key="btn_int_falha"):
                        st.session_state[chave_estado_fin] = "INTERROMPIDO"
                        st.rerun()

        else:
            def salvar_producao_atual(codigo_parada_novo, qtd_informada, modalidade_escolhida):
                if not hora_inicio_str: return
                
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
                        if qtd_valida > 0:
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
                
                try:
                    if codigo_parada_novo:
                        atualizar_status_maquina(supa, setor_selecionado, maquina_selecionada, {
                            "status": "Parado", "hora_inicio": hora_fim.strftime("%Y-%m-%d %H:%M:%S"),
                            "cod_ocorrencia": codigo_parada_novo, "cod_peca_atual": None
                        })
                        registrar_telemetria(supa, setor_selecionado, maquina_selecionada, f"Fim Lote -> Parada ({codigo_parada_novo})")
                    else:
                        atualizar_status_maquina(supa, setor_selecionado, maquina_selecionada, {
                            "status": "Livre", "hora_inicio": None, "cod_ocorrencia": None, "cod_peca_atual": None
                        })
                        registrar_telemetria(supa, setor_selecionado, maquina_selecionada, "Fim Lote -> Livre")
                        
                    st.session_state[chave_estado_fin] = None
                    st.session_state['tk_counter'] = st.session_state.get('tk_counter', 0) + 1
                        
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

            if estado_fin == "CONCLUIDO":
                st.markdown("<div style='font-size: 18px; font-weight: 800; color: #2c3e50; margin:0;'>📊 Fechamento da Produção</div>", unsafe_allow_html=True)
                st.markdown("<hr style='opacity: 0.2; margin-top: 5px; margin-bottom: 20px;'>", unsafe_allow_html=True)
                
                tk_val_conc = st.session_state.get('tk_counter', 0)
                chave_din_conc = f"in_qtd_conc_{tk_val_conc}"
                
                qtd_str = st.text_input("input_qtd_conc", key=chave_din_conc, label_visibility="collapsed")
                components.html(obter_html_teclado_qtd("input_qtd_conc", "Qtd Concluída"), height=530)
                
                modalidade_escolhida = "Simples"
                if permite_dupla:
                    st.markdown("<div style='margin-top: 15px; margin-bottom: 5px; color: #2c3e50; font-weight: bold; font-size:18px;'>⚙️ Modalidade de Produção</div>", unsafe_allow_html=True)
                    modalidade_escolhida = st.radio("mod_inv", ["Simples", "Dupla"], horizontal=True, label_visibility="collapsed")
                
                st.markdown("<br>", unsafe_allow_html=True)
                cb1, cb2 = st.columns(2)
                with cb1:
                    if st.button("💾 CONFIRMAR E SALVAR", type="primary", use_container_width=True, key="btn_sv_conc"):
                        try: qtd_final = int(qtd_str)
                        except: qtd_final = 0
                        salvar_producao_atual(codigo_parada_novo=None, qtd_informada=qtd_final, modalidade_escolhida=modalidade_escolhida)
                with cb2:
                    if st.button("❌ Cancelar Operação", use_container_width=True, key="btn_cc_conc"):
                        st.session_state[chave_estado_fin] = None
                        st.session_state['tk_counter'] = st.session_state.get('tk_counter', 0) + 1
                        st.rerun()
                        
            elif estado_fin == "INTERROMPIDO":
                st.markdown("<div style='font-size: 18px; font-weight: 800; color: #2c3e50; margin:0;'>🚨 Interrupção da Produção</div>", unsafe_allow_html=True)
                st.markdown("<hr style='opacity: 0.2; margin-top: 5px; margin-bottom: 20px;'>", unsafe_allow_html=True)
                
                tk_val_int = st.session_state.get('tk_counter', 0)
                chave_din_int_qtd = f"in_qtd_int_{tk_val_int}"
                
                qtd_str = st.text_input("input_qtd_int", key=chave_din_int_qtd, label_visibility="collapsed")
                components.html(obter_html_teclado_qtd("input_qtd_int", "Qtd Feita Antes da Falha"), height=530)
                
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
                        chave_din_int_cod = f"in_cod_int_{tk_val_int}"
                        codigo_digitado_int = st.text_input("input_cod_int", key=chave_din_int_cod, label_visibility="collapsed")
                        components.html(obter_html_teclado_parada("input_cod_int", valid_codes_json, "🔴 CONFIRMAR INTERRUPÇÃO"), height=650)
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        if codigo_digitado_int in valid_codes:
                            if st.button("🔴 CONFIRMAR INTERRUPÇÃO", use_container_width=True, type="primary", key="btn_int_tcl"):
                                try: qtd_val_int = int(qtd_str)
                                except: qtd_val_int = 0
                                salvar_producao_atual(codigo_parada_novo=codigo_digitado_int, qtd_informada=qtd_val_int, modalidade_escolhida=modalidade_escolhida)

                    with tab_lst_int:
                        opcoes_prob = [f"{str(row['descricao']).strip()} ({str(row['codigo']).strip()})" for _, row in df_codigos_parado.iterrows()]
                        problema_selecionado = st.selectbox("Selecione o problema:", [""] + opcoes_prob)
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("🔴 CONFIRMAR INTERRUPÇÃO", use_container_width=True, type="primary", key="btn_int_lst"):
                            cod_final = problema_selecionado.split("(")[-1].replace(")", "").strip() if problema_selecionado else None
                            if cod_final:
                                try: qtd_val_int = int(qtd_str)
                                except: qtd_val_int = 0
                                salvar_producao_atual(codigo_parada_novo=cod_final, qtd_informada=qtd_val_int, modalidade_escolhida=modalidade_escolhida)
                        
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("❌ Cancelar Operação (Voltar)", use_container_width=True, key="btn_canc_int_all"):
                    st.session_state[chave_estado_fin] = None
                    st.session_state['tk_counter'] = st.session_state.get('tk_counter', 0) + 1
                    st.rerun()

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

        hora_inicio_iso = hora_inicio_str.replace(" ", "T") if hora_inicio_str else ""
        is_pausa = (tipo_problema == 'NÃO CONTA' or 'DESCONSIDERAR' in tipo_problema)
        
        cor_fundo = "#f39c12" if is_pausa else "#c0392b"
        cor_sombra = "rgba(243, 156, 18, 0.4)" if is_pausa else "rgba(192, 57, 43, 0.4)"
        titulo_card = "☕ PAUSA PROGRAMADA" if is_pausa else "🔴 MÁQUINA PARADA"
        sub_texto = "Pausa em andamento:" if is_pausa else "Problema em andamento:"
        texto_botao = "✅ FINALIZAR INTERVALO" if is_pausa else "✅ PROBLEMA RESOLVIDO (FINALIZAR)"

        html_cronometro = """
        <style>
            body { margin: 0; padding: 0; font-family: sans-serif; }
            .caixa-vermelha { background-color: COR_FUNDO_PLACEHOLDER; color: white; padding: 25px 20px; border-radius: 12px; text-align: center; box-shadow: 0 4px 15px COR_SOMBRA_PLACEHOLDER; box-sizing: border-box; margin: 0; transition: background-color 0.3s; }
            .titulo-vermelho { margin: 0; font-size: 34px; text-transform: uppercase; font-weight: 900; }
            .sub-vermelho { margin: 10px 0 15px 0; font-size: 18px; opacity: 0.95; }
            .cronometro { font-size: 60px; font-weight: 900; font-family: monospace; letter-spacing: 2px; }
            @media (max-width: 768px) { .caixa-vermelha { padding: 20px 10px; } .titulo-vermelho { font-size: 24px; } .sub-vermelho { font-size: 15px; margin: 10px 0 10px 0; } .cronometro { font-size: 40px; letter-spacing: 0px; } }
        </style>
        <div class="caixa-vermelha">
            <h1 class="titulo-vermelho">TITULO_CARD_PLACEHOLDER</h1><p class="sub-vermelho">SUB_TEXTO_PLACEHOLDER <br><b>DESC_PROBLEMA_PLACEHOLDER (COD_OCORRENCIA_PLACEHOLDER)</b></p>
            <div id="stopwatch" class="cronometro">00:00:00</div>
        </div>
        <script>
            const startTime = new Date("HORA_INICIO_PLACEHOLDER").getTime();
            setInterval(function() {
                const now = new Date().getTime(); const distance = now - startTime;
                if (distance > 0) {
                    const h = Math.floor(distance / (1000 * 60 * 60)); const m = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60)); const s = Math.floor((distance % (1000 * 60)) / 1000);
                    document.getElementById("stopwatch").innerHTML = (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
                }
            }, 500);
        </script>
        """
        html_cronometro = html_cronometro.replace("COR_FUNDO_PLACEHOLDER", cor_fundo).replace("COR_SOMBRA_PLACEHOLDER", cor_sombra).replace("TITULO_CARD_PLACEHOLDER", titulo_card).replace("SUB_TEXTO_PLACEHOLDER", sub_texto).replace("DESC_PROBLEMA_PLACEHOLDER", desc_problema).replace("COD_OCORRENCIA_PLACEHOLDER", str(cod_ocorrencia)).replace("HORA_INICIO_PLACEHOLDER", hora_inicio_iso)
        components.html(html_cronometro, height=250)
        
        if hora_inicio_str:
            hora_fim_calc = obter_hora_atual()
            hora_inicio_calc = datetime.strptime(hora_inicio_str, "%Y-%m-%d %H:%M:%S")
            duracao_calc = (hora_fim_calc - hora_inicio_calc).total_seconds()
        else:
            duracao_calc = 999
            
        st.markdown("<br>", unsafe_allow_html=True)
        if duracao_calc < 60:
            if st.button("❌ CANCELAR PARADA (Erro de Seleção)", use_container_width=True, key="btn_canc_erro_parada"):
                atualizar_status_maquina(supa, setor_selecionado, maquina_selecionada, {
                    "status": "Livre", "hora_inicio": None, "cod_ocorrencia": None, "cod_peca_atual": None
                })
                registrar_telemetria(supa, setor_selecionado, maquina_selecionada, "Parada Cancelada (Erro Seleção)")
                st.rerun()
        else:
            if st.button(texto_botao, use_container_width=True, type="primary", key="btn_fin_parada"):
                try:
                    hora_fim = obter_hora_atual()
                    hora_inicio_obj = datetime.strptime(hora_inicio_str, "%Y-%m-%d %H:%M:%S") if hora_inicio_str else hora_fim
                    dados_nuvem = {
                        "data_registro": hora_inicio_obj.strftime("%Y-%m-%d"),
                        "setor": setor_selecionado, "maquina": maquina_selecionada, 
                        "tipo": tipo_problema,
                        "cod_ocorrencia": cod_ocorrencia, "operador": nomes_operadores,
                        "das": hora_inicio_obj.strftime("%H:%M"), "as_hora": hora_fim.strftime("%H:%M"), "origem": "Chão de Fábrica"
                    }
                    supa.table("producao_diaria").insert(dados_nuvem).execute()
                    
                    atualizar_status_maquina(supa, setor_selecionado, maquina_selecionada, {
                        "status": "Livre", "hora_inicio": None, "cod_ocorrencia": None, "cod_peca_atual": None
                    })
                    registrar_telemetria(supa, setor_selecionado, maquina_selecionada, "Problema Resolvido (Máquina Livre)")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao finalizar parada: {e}")

    # ==========================================
    # 4. HISTÓRICO EXCLUSIVO DO TABLET
    # ==========================================
    st.markdown("<hr style='opacity: 0.2; margin-top: 20px; margin-bottom: 20px;'>", unsafe_allow_html=True)
    st.markdown("<div style='font-size: 20px; font-weight: bold; color: #2c3e50; margin-bottom: 15px;'>📋 Últimos Registros de Hoje</div>", unsafe_allow_html=True)
    
    hoje_str = obter_hora_atual().strftime("%Y-%m-%d")
    
    if df_nuvem.empty or 'maquina' not in df_nuvem.columns: df_hist = pd.DataFrame()
    else:
        if 'origem' not in df_nuvem.columns: df_nuvem['origem'] = 'Importação'
        if 'tipo' not in df_nuvem.columns: df_nuvem['tipo'] = 'PARADA'
        df_hist = df_nuvem[(df_nuvem['maquina'] == maquina_selecionada) & (df_nuvem['setor'] == setor_selecionado) & (df_nuvem['data_registro'] == hoje_str) & (df_nuvem['origem'] == 'Chão de Fábrica')].copy()
    
    if df_hist.empty: st.info("Nenhum apontamento nesta máquina hoje.")
    else:
        df_hist = df_hist.sort_values(by=['data_registro', 'as_hora'], ascending=[False, False]).head(20)
        
        html_cards_hist = "<div style='display: flex; flex-direction: column; gap: 12px; margin-top: 15px;'>"
        for i, row in df_hist.iterrows():
            tipo_bd = str(row.get('tipo', '')).strip().upper()
            codigo_bd = str(row.get('cod_ocorrencia', '')).strip().upper()
            das_h = row['das']
            as_h = row['as_hora']
            
            if codigo_bd == 'P':
                cor_borda = "#27ae60"
                cor_fundo = "#f4fcf7"
                cod_peca = row.get('cod_peca', 'S/N')
                qtd_val = row.get('quantidade', 0)
                try:
                    if float(qtd_val).is_integer(): qtd_peca = str(int(float(qtd_val)))
                    else: qtd_peca = str(float(qtd_val))
                except:
                    qtd_peca = str(qtd_val)
                
                nome_peca_hist = str(row.get('nome_peca', 'Peça Desconhecida'))
                if " ➔ " in nome_peca_hist:
                    partes_nome = nome_peca_hist.split(" ➔ ")
                    produto_nome = partes_nome[0]
                    peca_nome = partes_nome[1]
                else:
                    produto_nome = "Produto"
                    peca_nome = nome_peca_hist
                    
                modalidade = str(row.get('modalidade_processo', 'Simples'))
                titulo = produto_nome
            else:
                desc_oco = "Sem Descrição"
                if not df_codigos.empty:
                    f_cod = df_codigos[df_codigos['codigo'].astype(str).str.upper() == codigo_bd]
                    if not f_cod.empty: desc_oco = str(f_cod.iloc[0]['descricao']).strip()
                
                if tipo_bd == "NÃO CONTA" or "DESCONSIDERAR" in tipo_bd:
                    cor_borda = "#f39c12"
                    cor_fundo = "#fdf8f3"
                    titulo = f"Pausa: {desc_oco} ({codigo_bd})"
                else:
                    cor_borda = "#e74c3c"
                    cor_fundo = "#fdf4f3"
                    titulo = f"Parada: {desc_oco} ({codigo_bd})"
            
            html_cards_hist += "<div style='border-left: 6px solid " + cor_borda + "; background-color: " + cor_fundo + "; padding: 12px 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border-right: 1px solid #eee; border-top: 1px solid #eee; border-bottom: 1px solid #eee;'>"
            html_cards_hist += "<div style='display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;'>"
            html_cards_hist += "<div style='font-size: 16px; font-weight: 800; color: #2c3e50; line-height: 1.2;'>" + titulo + "</div>"
            html_cards_hist += "<div style='font-size: 13px; font-weight: 700; color: #7f8c8d; background: #fff; padding: 2px 8px; border-radius: 4px; border: 1px solid #ddd; white-space: nowrap; margin-left: 10px;'>⏱️ " + str(das_h) + " às " + str(as_h) + "</div>"
            html_cards_hist += "</div>"
            
            if codigo_bd == 'P':
                html_cards_hist += "<div style='font-size: 15px; font-weight: 700; color: #34495e;'>" + peca_nome + " <span style='font-size: 12px; color: #7f8c8d; font-weight: normal;'>(Cód: " + str(cod_peca) + ")</span></div>"
                html_cards_hist += "<div style='margin-top: 8px; font-size: 18px; font-weight: 900; color: #27ae60;'>Qtde: " + qtd_peca + " <span style='font-size: 14px; color: #7f8c8d; font-weight: 600; margin-left: 15px; background: #e8f8f5; padding: 2px 6px; border-radius: 4px;'>Mod: " + modalidade + "</span></div>"
                
            html_cards_hist += "</div>"
            
        html_cards_hist += "</div>"
        st.markdown(html_cards_hist, unsafe_allow_html=True)

    # ==========================================
    # 5. RODAPÉ DO TERMINAL E CAIXA PRETA
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

    with st.expander("🛠️ CAIXA PRETA (Apenas Admin) - Monitoramento de Sessão"):
        st.write("Se ocorrer algum erro, tire um print desta área e envie para análise:")
        estado_atual_limpo = {k: v for k, v in st.session_state.items() if k != "df_nuvem"}
        st.json(estado_atual_limpo)

    st.markdown("""
        <script>
            document.body.style.overflow = 'hidden';
            setTimeout(() => { document.body.style.overflow = 'auto'; }, 1000);
            
            setInterval(() => {
                const btns = window.parent.document.querySelectorAll('button');
                btns.forEach(btn => {
                    const texto = btn.innerText ? btn.innerText.toUpperCase() : "";
                    if(texto.includes('▶️ INICIAR:') || texto === '💾 CONFIRMAR E SALVAR' || texto === '✅ FINALIZAR (CONCLUÍDO)' || texto === '✅ PROBLEMA RESOLVIDO (FINALIZAR)' || texto === '✅ FINALIZAR INTERVALO') {
                        if (!btn.disabled) {
                            btn.style.setProperty('background-color', '#27ae60', 'important');
                            btn.style.setProperty('border-color', '#27ae60', 'important');
                            btn.style.setProperty('color', 'white', 'important');
                        }
                    }
                    else if(texto === '🔴 CONFIRMAR PARADA' || texto === '🔴 INTERROMPER (POR FALHA)' || texto === '🔴 CONFIRMAR INTERRUPÇÃO') {
                        if (!btn.disabled) {
                            btn.style.setProperty('background-color', '#c0392b', 'important');
                            btn.style.setProperty('border-color', '#c0392b', 'important');
                            btn.style.setProperty('color', 'white', 'important');
                        }
                    }
                    else if(texto.includes('CANCELAR PRODUÇÃO (ERRO') || texto.includes('CANCELAR PARADA (ERRO')) {
                        if (!btn.disabled) {
                            btn.style.setProperty('background-color', '#e67e22', 'important');
                            btn.style.setProperty('border-color', '#e67e22', 'important');
                            btn.style.setProperty('color', 'white', 'important');
                        }
                    }
                });
            }, 300);
        </script>
    """, unsafe_allow_html=True)