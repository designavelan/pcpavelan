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
    """Garante que a máquina exista no banco antes de atualizar o status"""
    # CORREÇÃO: Procurar pela coluna 'maquina' ao invés de 'id'
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
        
        if total_maquinas > 0:
            percentual = round((ativas / total_maquinas) * 100.0, 2)
        else:
            percentual = 0.0
            
        texto_acao = f"[{setor}] {maquina}: {acao}"
        
        dados_telemetria = {
            "data_hora": agora_str,
            "percentual": float(percentual),
            "acao": str(texto_acao),
            "maquinas_ativas": int(ativas),
            "maquinas_totais": int(total_maquinas)
        }
        
        supa.table("historico_operacao").insert([dados_telemetria]).execute()
        return True, ""
    except Exception as e:
        return False, str(e)

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
        <p class="lcd-desc">Qtd Produzida / Embalada</p>
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
        <button type="button" class="btn-key" onclick="pressKey('C')">C</button>
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
        .block-container { padding-top: 0.5rem !important; padding-bottom: 0rem !important; margin-bottom: 0rem !important; }
        div[data-testid="stTabs"] { margin-top: -15px; }
        footer { display: none !important; }
        #MainMenu { visibility: hidden; }
        div[data-testid="stElementContainer"]:has(input[aria-label="input_codigo_js"]),
        div[data-testid="stElementContainer"]:has(input[aria-label="input_codigo_js_int"]),
        div[data-testid="stElementContainer"]:has(input[aria-label="input_qtd_js"]),
        div[data-testid="stElementContainer"]:has(input[aria-label="input_qtd_js_int"]) {
            position: absolute !important; left: -9999px !important; width: 0px !important; height: 0px !important; overflow: hidden !important; border: none !important; margin: 0 !important; padding: 0 !important;
        }
        div[data-testid="stElementContainer"]:has(iframe[height="0"]) {
            position: absolute !important; left: -9999px !important; width: 0px !important; height: 0px !important; overflow: hidden !important; border: none !important; margin: 0 !important; padding: 0 !important;
        }
        div[data-baseweb="select"] > div { min-height: 65px !important; font-size: 20px !important; border-radius: 8px !important; }
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

    def obter_resumo_peca(codigo):
        if codigo in producao_hoje_pecas and producao_hoje_pecas[codigo]:
            lista_qtds = producao_hoje_pecas[codigo]
            total = sum(lista_qtds)
            if len(lista_qtds) > 1:
                return f"*📦 Hoje: {' + '.join(map(str, lista_qtds))} = {total} un.*"
            return f"*📦 Hoje: {total} un.*"
        return ""

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
                
                chave_wid_prod = f"sel_prod_{setor_selecionado}_{maquina_selecionada}"
                
                idx_prod = None
                if last_prod and last_prod in lista_exibicao:
                    idx_prod = lista_exibicao.index(last_prod)
                
                sel_prod = st.selectbox(
                    "1. Produto:", 
                    options=lista_exibicao, 
                    index=idx_prod, 
                    placeholder="Clique aqui para selecionar o produto...",
                    key=chave_wid_prod
                )
                
                if sel_prod:
                    if is_embalagem:
                        df_caixas = cache_obter_caixas()
                        if not df_caixas.empty:
                            df_cx_filtro = df_caixas[df_caixas['produto_formula'] == sel_prod]
                            lista_pecas_limpa = [f"Caixa {row['num_caixa']} (Cód: {row['cod_caixa']})" for _, row in df_cx_filtro.iterrows() if pd.notna(row['cod_caixa']) and str(row['cod_caixa']).strip() not in ["", "None", "nan"]]
                        else:
                            lista_pecas_limpa = []
                    else:
                        df_pecas = df_produtos[df_produtos['produto_formula'] == sel_prod]
                        lista_pecas_limpa = [f"{row['descricao']} (Cód: {row['cod']})" for _, row in df_pecas.iterrows()]
                    
                    if sel_prod == last_prod and last_peca and last_peca not in lista_pecas_limpa:
                        lista_pecas_limpa.append(last_peca)
                        
                    lista_exibicao_pecas = []
                    mapa_exibicao_limpa = {}
                    
                    for peca_limpa in lista_pecas_limpa:
                        codigo_ext = peca_limpa.split("(Cód: ")[-1].replace(")", "").strip()
                        resumo_texto = obter_resumo_peca(codigo_ext)
                        texto_completo = f"{peca_limpa} {resumo_texto}" if resumo_texto else peca_limpa
                        lista_exibicao_pecas.append(texto_completo)
                        mapa_exibicao_limpa[texto_completo] = peca_limpa
                        
                    idx_peca = 0
                    if sel_prod == last_prod and last_peca:
                        for i, txt in enumerate(lista_exibicao_pecas):
                            if mapa_exibicao_limpa[txt] == last_peca:
                                idx_peca = i
                                break
                    
                    st.markdown("""
                        <style>
                        div[data-testid='stRadio'] { width: 100% !important; }
                        div[data-testid='stRadio'] > div { width: 100% !important; gap: 12px; }
                        div[data-testid='stRadio']:has(div[aria-orientation='vertical']) label {
                            background-color: #ffffff; border: 1px solid #bdc3c7; border-radius: 8px; padding: 16px 20px; width: 100%; cursor: pointer; transition: all 0.2s ease-in-out; margin: 0;
                        }
                        div[data-testid='stRadio']:has(div[aria-orientation='vertical']) label:has(em) { background-color: #f4f6f7; border-color: #d1d8e0; }
                        div[data-testid='stRadio']:has(div[aria-orientation='vertical']) label[data-checked="true"] { background-color: #ff4b4b !important; border-color: #ff4b4b !important; }
                        div[data-testid='stRadio']:has(div[aria-orientation='vertical']) label > div:first-child { display: none !important; }
                        div[data-testid='stRadio']:has(div[aria-orientation='vertical']) label p { font-size: 16px; font-weight: 600; color: #2c3e50; margin: 0; text-align: left !important; width: 100%; display: block; }
                        div[data-testid='stRadio']:has(div[aria-orientation='vertical']) label p em { display: block; margin-top: 6px; font-size: 14px; font-weight: 500; color: #7f8c8d; font-style: normal; }
                        div[data-testid='stRadio']:has(div[aria-orientation='vertical']) label[data-checked="true"] p { color: #ffffff !important; }
                        div[data-testid='stRadio']:has(div[aria-orientation='vertical']) label[data-checked="true"] p em { color: #fcebeb !important; }
                        div[data-testid='stRadio']:has(div[aria-orientation='vertical']) label[data-checked="true"] p::before { content: '✅ '; }
                        </style>
                    """, unsafe_allow_html=True)
                    
                    titulo_peca = "2. Toque na embalagem/volume:" if is_embalagem else "2. Toque na peça para selecionar:"
                    st.markdown(f"<h4 style='color: #2c3e50; font-size: 16px; margin-top: 15px;'>{titulo_peca}</h4>", unsafe_allow_html=True)
                    
                    sel_peca_exibicao = st.radio("Selecione a Peça", lista_exibicao_pecas, index=idx_peca, label_visibility="collapsed")
                    
                    if sel_peca_exibicao and sel_peca_exibicao in mapa_exibicao_limpa:
                        peca_atual_limpa = mapa_exibicao_limpa[sel_peca_exibicao]
                        nome_peca_curto = peca_atual_limpa.split("(Cód:")[0].strip()
                    else:
                        nome_peca_curto = "VOLUME" if is_embalagem else "PEÇA"
                        
                    texto_btn_iniciar = f"▶️ INICIAR: {nome_peca_curto} ({sel_prod})"
                    
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
                            
                            if chave_wid_prod in st.session_state: del st.session_state[chave_wid_prod]
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
                
                with st.form(key=f"form_parada_livre_{setor_selecionado}_{maquina_selecionada}"):
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
                            <button type="button" class="btn-key" onclick="pressKey('C')">C</button>
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
                            
                            dados_parada = {
                                "status": "Parado", 
                                "cod_peca_atual": None, "cod_ocorrencia": cod_final, "hora_inicio": agora
                            }
                            
                            try:
                                atualizar_status_maquina(supa, setor_selecionado, maquina_selecionada, dados_parada)
                                
                                sucesso, erro = registrar_telemetria(supa, setor_selecionado, maquina_selecionada, f"Parada Iniciada ({cod_final})")
                                if not sucesso:
                                    st.error(f"❌ ERRO AO GRAVAR HISTÓRICO: {erro}")
                                    st.stop()
                                
                                st.session_state['tk_counter'] += 1 
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao iniciar parada: {e}")
                                
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

        hora_inicio_iso = hora_inicio_str.replace(" ", "T")
        desc_fab = "Embalando:" if is_embalagem else "Fabricando:"

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
            <h1 class="titulo">🟢 EM PRODUÇÃO</h1><p class="sub">{desc_fab} <br><b>{nome_peca} (Cód: {cod_peca_atual})</b></p>
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
                        if (isLess1Min) {{
                            btn.closest('div[data-testid="stButton"]').style.display = 'block';
                        }} else {{
                            btn.closest('div[data-testid="stButton"]').style.display = 'none';
                        }}
                    }}
                    
                    if(txt === '✅ FINALIZAR (CONCLUÍDO)' || txt === '🔴 INTERROMPER (POR FALHA)') {{
                        if (isLess1Min) {{
                            btn.closest('div[data-testid="stButton"]').style.display = 'none';
                        }} else {{
                            btn.closest('div[data-testid="stButton"]').style.display = 'block';
                        }}
                    }}
                }});
            }}, 500);
        </script>
        """
        components.html(js_cronometro, height=250)
        
        chave_estado_fin = f"fin_estado_{setor_selecionado}_{maquina_selecionada}"
        estado_fin = st.session_state.get(chave_estado_fin, None)
        
        if not estado_fin:
            st.markdown("<br>", unsafe_allow_html=True)
            
            btn_canc_prod = st.button("❌ CANCELAR PRODUÇÃO (Erro de Seleção)", use_container_width=True)
            c1, c2 = st.columns(2)
            with c1: btn_fin_prod = st.button("✅ FINALIZAR (Concluído)", use_container_width=True, type="primary")
            with c2: btn_int_prod = st.button("🔴 INTERROMPER (Por Falha)", use_container_width=True, type="primary")
                
            if btn_canc_prod:
                try:
                    atualizar_status_maquina(supa, setor_selecionado, maquina_selecionada, {
                        "status": "Livre", "hora_inicio": None, "cod_ocorrencia": None, "cod_peca_atual": None
                    })
                    sucesso, erro = registrar_telemetria(supa, setor_selecionado, maquina_selecionada, "Produção Cancelada (Erro Seleção)")
                    if not sucesso:
                        st.error(f"❌ ERRO AO GRAVAR HISTÓRICO: {erro}")
                        st.stop()
                    
                    chave_w_p = f"sel_prod_{setor_selecionado}_{maquina_selecionada}"
                    if chave_w_p in st.session_state: del st.session_state[chave_w_p]
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao cancelar produção: {e}")
                
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
                
                try:
                    if codigo_parada_novo:
                        atualizar_status_maquina(supa, setor_selecionado, maquina_selecionada, {
                            "status": "Parado", "hora_inicio": hora_fim.strftime("%Y-%m-%d %H:%M:%S"),
                            "cod_ocorrencia": codigo_parada_novo, "cod_peca_atual": None
                        })
                        sucesso, erro = registrar_telemetria(supa, setor_selecionado, maquina_selecionada, f"Fim de Lote c/ Parada ({codigo_parada_novo})")
                        if not sucesso: st.error(f"❌ ERRO AO GRAVAR HISTÓRICO: {erro}")
                    else:
                        atualizar_status_maquina(supa, setor_selecionado, maquina_selecionada, {
                            "status": "Livre", "hora_inicio": None, "cod_ocorrencia": None, "cod_peca_atual": None
                        })
                        sucesso, erro = registrar_telemetria(supa, setor_selecionado, maquina_selecionada, "Fim de Lote (Máquina Livre)")
                        if not sucesso: st.error(f"❌ ERRO AO GRAVAR HISTÓRICO: {erro}")
                        
                    st.session_state[chave_estado_fin] = None
                    chave_w_p = f"sel_prod_{setor_selecionado}_{maquina_selecionada}"
                    if chave_w_p in st.session_state: del st.session_state[chave_w_p]
                        
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

            if estado_fin == "CONCLUIDO":
                with st.form(key=f"form_conc_{setor_selecionado}_{maquina_selecionada}"):
                    st.markdown("<div style='font-size: 18px; font-weight: 800; color: #2c3e50; margin:0;'>📊 Fechamento da Produção</div>", unsafe_allow_html=True)
                    st.markdown("<hr style='opacity: 0.2; margin-top: 5px; margin-bottom: 20px;'>", unsafe_allow_html=True)
                    
                    qtd_str = st.text_input("input_qtd_js", value="0", label_visibility="collapsed")
                    components.html(obter_html_teclado_qtd("input_qtd_js"), height=550)
                    
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
                with st.form(key=f"form_int_{setor_selecionado}_{maquina_selecionada}"):
                    st.markdown("<div style='font-size: 18px; font-weight: 800; color: #2c3e50; margin:0;'>🚨 Interrupção da Produção</div>", unsafe_allow_html=True)
                    st.markdown("<hr style='opacity: 0.2; margin-top: 5px; margin-bottom: 20px;'>", unsafe_allow_html=True)
                    
                    qtd_str_int = st.text_input("input_qtd_js_int", value="0", label_visibility="collapsed")
                    components.html(obter_html_teclado_qtd("input_qtd_js_int"), height=550)
                    
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
                                <button type="button" class="btn-key" onclick="pressKey('C')">C</button>
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
                        if (isLess1Min) {{
                            btn.closest('div[data-testid="stButton"]').style.display = 'block';
                        }} else {{
                            btn.closest('div[data-testid="stButton"]').style.display = 'none';
                        }}
                    }}
                    
                    if(txt === '{texto_botao.upper()}') {{
                        if (isLess1Min) {{
                            btn.closest('div[data-testid="stButton"]').style.display = 'none';
                        }} else {{
                            btn.closest('div[data-testid="stButton"]').style.display = 'block';
                        }}
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
            try:
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
                
                atualizar_status_maquina(supa, setor_selecionado, maquina_selecionada, {
                    "status": "Livre", "hora_inicio": None, "cod_ocorrencia": None, "cod_peca_atual": None
                })
                
                texto_acao = "Problema Resolvido (Máquina Livre)" if btn_fin_parada else "Parada Cancelada (Erro Seleção)"
                sucesso, erro = registrar_telemetria(supa, setor_selecionado, maquina_selecionada, texto_acao)
                if not sucesso:
                    st.error(f"❌ ERRO AO GRAVAR HISTÓRICO: {erro}")
                    st.stop()
                
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao cancelar/finalizar parada: {e}")

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
    permite_troca = cfg.get('permitir_troca_maquina', False)
    titulo_app = cfg.get('titulo_programa', 'PCP Avelan')
    logo_b64 = cfg.get('logo_base64', None)
    
    c1, c2 = st.columns([6, 4])
    with c1:
        if logo_b64: st.markdown(f'<div style="display: flex; align-items: center; gap: 15px;"><img src="data:image/png;base64,{logo_b64}" style="max-height: 40px;"><h3 style="margin:0; color: #2c3e50;">{titulo_app}</h3></div>', unsafe_allow_html=True)
        else: st.markdown(f'<h3 style="margin:0; color: #2c3e50;">🏭 {titulo_app}</h3>', unsafe_allow_html=True)
    with c2:
        if is_travado and permite_troca:
            b1, b2 = st.columns(2)
            with b1:
                if st.button("🔄 Trocar Máquina", use_container_width=True, key="btn_trocar_maq"):
                    st.session_state['show_troca_maquina'] = not st.session_state.get('show_troca_maquina', False)
                    st.rerun()
            with b2:
                if st.button("🚪 Sair", use_container_width=True, key="btn_sair_cf"):
                    st.session_state['usuario_logado'] = None
                    try: st.query_params.clear()
                    except: st.experimental_set_query_params()
                    st.rerun()
        else:
            if st.button("🚪 Sair do Sistema", use_container_width=True, key="btn_sair_cf"):
                st.session_state['usuario_logado'] = None
                try: st.query_params.clear()
                except: st.experimental_set_query_params()
                st.rerun()

    # --- JANELA DE TROCA DE MÁQUINA ---
    if st.session_state.get('show_troca_maquina'):
        st.markdown("<div style='background: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #ddd; margin-top: 15px;'>", unsafe_allow_html=True)
        st.markdown("<h4 style='color: #2c3e50; margin-top:0;'>🔄 Selecione o seu novo posto de trabalho:</h4>", unsafe_allow_html=True)
        
        sel_c1, sel_c2 = st.columns(2)
        with sel_c1:
            idx_setor = lista_setores_nuvem.index(setor_selecionado) if setor_selecionado in lista_setores_nuvem else 0
            novo_setor = st.selectbox("Novo Setor:", lista_setores_nuvem, key="novo_sec_troca", index=idx_setor)
        with sel_c2:
            lista_maq_novo = sorted(df_est[df_est['setor'] == novo_setor]['maquina'].dropna().unique().tolist())
            nova_maq = st.selectbox("Nova Máquina:", lista_maq_novo, key="nova_maq_troca")
            
        st.markdown("<br>", unsafe_allow_html=True)
        conf_c1, conf_c2 = st.columns(2)
        with conf_c1:
            if st.button("✅ Confirmar Mudança", type="primary", use_container_width=True):
                supa.table("usuarios").update({
                    "setor": novo_setor,
                    "maquina": nova_maq
                }).eq("username", usuario['username']).execute()
                
                st.session_state['usuario_logado']['setor'] = novo_setor
                st.session_state['usuario_logado']['maquina'] = nova_maq
                st.session_state['show_troca_maquina'] = False
                st.rerun()
        with conf_c2:
            if st.button("❌ Cancelar", use_container_width=True):
                st.session_state['show_troca_maquina'] = False
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # ==========================================
    # SCRIPT PARA INFLAR OS BOTÕES DE AÇÃO 
    # ==========================================
    js_cores = """
    <script>
        setInterval(() => {
            const btns = window.parent.document.querySelectorAll('button');
            btns.forEach(btn => {
                const texto = btn.innerText ? btn.innerText.toUpperCase() : "";
                
                if(texto.includes('▶️ INICIAR:') || texto === '💾 CONFIRMAR E SALVAR' || texto === '✅ FINALIZAR (CONCLUÍDO)' || texto === '✅ PROBLEMA RESOLVIDO (FINALIZAR)' || texto === '✅ FINALIZAR INTERVALO') {
                    btn.style.setProperty('min-height', '90px', 'important');
                    btn.style.setProperty('height', 'auto', 'important');
                    btn.style.setProperty('padding', '15px 10px', 'important');
                    btn.style.setProperty('font-size', '22px', 'important');
                    btn.style.setProperty('font-weight', '900', 'important');
                    btn.style.setProperty('border-radius', '12px', 'important');
                    btn.style.setProperty('white-space', 'normal', 'important');
                    btn.style.setProperty('line-height', '1.3', 'important');
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
                    btn.style.setProperty('min-height', '90px', 'important');
                    btn.style.setProperty('height', 'auto', 'important');
                    btn.style.setProperty('padding', '15px 10px', 'important');
                    btn.style.setProperty('font-size', '22px', 'important');
                    btn.style.setProperty('font-weight', '900', 'important');
                    btn.style.setProperty('border-radius', '12px', 'important');
                    btn.style.setProperty('white-space', 'normal', 'important');
                    btn.style.setProperty('line-height', '1.3', 'important');
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
                    btn.style.setProperty('min-height', '90px', 'important');
                    btn.style.setProperty('height', 'auto', 'important');
                    btn.style.setProperty('padding', '15px 10px', 'important');
                    btn.style.setProperty('font-size', '22px', 'important');
                    btn.style.setProperty('font-weight', '900', 'important');
                    btn.style.setProperty('border-radius', '12px', 'important');
                    btn.style.setProperty('white-space', 'normal', 'important');
                    btn.style.setProperty('line-height', '1.3', 'important');
                    if (!btn.disabled) {
                        btn.style.setProperty('background-color', '#e67e22', 'important');
                        btn.style.setProperty('border-color', '#e67e22', 'important');
                        btn.style.setProperty('color', 'white', 'important');
                    }
                }
            });
            
            const selects = window.parent.document.querySelectorAll('div[data-baseweb="select"] input');
            selects.forEach(sel => {
                sel.setAttribute('inputmode', 'none');
                sel.readOnly = true;
            });

        }, 300);
    </script>
    """
    components.html(js_cores, height=0)