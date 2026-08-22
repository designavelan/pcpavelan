import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import banco
import streamlit.components.v1 as components
import json

def obter_hora_atual():
    return datetime.utcnow() - timedelta(hours=3)

def renderizar(df_nuvem, df_codigos):
    
    if 'tk_counter' not in st.session_state: st.session_state['tk_counter'] = 0
    if 'modo_cf' not in st.session_state: st.session_state['modo_cf'] = None

    st.markdown("""
        <style>
        div[data-baseweb="select"] input { pointer-events: none !important; caret-color: transparent !important; }
        div[data-testid="stElementContainer"]:has(input[aria-label="input_codigo_js"]) {
            position: absolute !important; left: -9999px !important; width: 0px !important; height: 0px !important; overflow: hidden !important;
        }
        </style>
    """, unsafe_allow_html=True)

    supa = banco.conectar()
    
    df_est = banco.obter_estrutura()
    if df_est.empty:
        st.warning("⚠️ Nenhuma estrutura de fábrica cadastrada. Vá na aba Configurações > Estrutura.")
        return

    # ==========================================
    # 1. LÓGICA DE IDENTIFICAÇÃO DO USUÁRIO E MÁQUINA
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
        if setor_selecionado not in lista_setores_nuvem and lista_setores_nuvem: 
            setor_selecionado = lista_setores_nuvem[0]
            
        lista_maquinas_nuvem = sorted(df_est[df_est['setor'] == setor_selecionado]['maquina'].dropna().unique().tolist())
        maquina_selecionada = st.session_state.get("cf_maquina", lista_maquinas_nuvem[0] if lista_maquinas_nuvem else "")
        if maquina_selecionada not in lista_maquinas_nuvem and lista_maquinas_nuvem: 
            maquina_selecionada = lista_maquinas_nuvem[0]

        usuarios_cadastrados = banco.obter_usuarios_completo()
        operadores_vinculados = [
            u['nome'] for u in usuarios_cadastrados 
            if str(u.get('setor')) == str(setor_selecionado) and str(u.get('maquina')) == str(maquina_selecionada) and u.get('ativo') == True
        ]
        nomes_operadores = " / ".join(operadores_vinculados) if operadores_vinculados else "Sem Operador"

    df_produtos = banco.obter_produtos_matriz()

    # ==========================================
    # 2. STATUS DA MÁQUINA E FILTRO DE CÓDIGOS
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
            mascara = df_codigos['exibir_na_lista'].apply(filtrar_por_setor)
            df_codigos_parado = df_codigos[mascara]
        else:
            if 'tipo' in df_codigos.columns: 
                # Oculta o código "P" e tudo que for tipo "PRODUÇÃO" para não poluir a tela de paradas
                df_codigos_parado = df_codigos[(df_codigos['tipo'].astype(str).str.strip().str.upper() != 'PRODUÇÃO') & (df_codigos['codigo'].astype(str).str.strip().str.upper() != 'P')]
            else: df_codigos_parado = pd.DataFrame()
    else: df_codigos_parado = pd.DataFrame()

    # ==========================================
    # ESTADO 1: MÁQUINA LIVRE
    # ==========================================
    if status_db == 'Livre':
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🟢 INICIAR NOVA PRODUÇÃO", use_container_width=True, type="primary"):
                st.session_state['modo_cf'] = 'PRODUCAO'
                st.rerun()
        with c2:
            if st.button("🔴 REGISTRAR NOVA PARADA", use_container_width=True, type="primary"):
                st.session_state['modo_cf'] = 'PARADA'
                st.rerun()

        modo_ativo = st.session_state.get('modo_cf')
        
        if modo_ativo == 'PRODUCAO':
            st.markdown("<div style='background-color: #f1f8ff; padding: 20px; border-radius: 12px; border: 2px solid #27ae60; margin-top: 15px;'>", unsafe_allow_html=True)
            st.markdown("#### 📦 Dados de Fabricação")
            if not df_produtos.empty:
                lista_produtos = sorted(df_produtos['produto_formula'].dropna().unique().tolist())
                sel_prod = st.selectbox("1. Selecione o Produto:", [""] + lista_produtos, key=f"sel_prod_{maquina_selecionada}")
                
                if sel_prod:
                    df_pecas = df_produtos[df_produtos['produto_formula'] == sel_prod]
                    lista_pecas = [f"{row['descricao']} (Cód: {row['cod']})" for _, row in df_pecas.iterrows()]
                    sel_peca = st.selectbox("2. Selecione a Peça:", [""] + lista_pecas, key=f"sel_peca_{maquina_selecionada}")
                    
                    if sel_peca:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("▶️ CONFIRMAR E INICIAR", type="primary", use_container_width=True):
                            codigo_peca = sel_peca.split("(Cód: ")[-1].replace(")", "").strip()
                            agora = obter_hora_atual().strftime("%Y-%m-%d %H:%M:%S")
                            
                            supa.table("status_maquinas").upsert({
                                "maquina": maquina_selecionada, "setor": setor_selecionado, 
                                "status": "Produzindo", "cod_peca_atual": codigo_peca, 
                                "hora_inicio": agora, "cod_ocorrencia": "P" # INSERE O CÓDIGO 'P' OFICIALMENTE NO STATUS
                            }).execute()
                            st.session_state['modo_cf'] = None
                            st.rerun()
            else:
                st.info("Nenhum produto cadastrado na Matriz.")
            st.markdown("</div>", unsafe_allow_html=True)

        elif modo_ativo == 'PARADA':
            st.markdown("<div style='background-color: #fff5f5; padding: 20px; border-radius: 12px; border: 2px solid #c0392b; margin-top: 15px;'>", unsafe_allow_html=True)
            if not df_codigos_parado.empty:
                valid_codes = {str(row['codigo']).strip(): str(row['descricao']).strip() for _, row in df_codigos_parado.iterrows()}
                valid_codes_json = json.dumps(valid_codes)
                
                tab_tcl, tab_lst = st.tabs(["🔢 Teclado Numérico", "📄 Selecionar na Lista"])
                
                with tab_tcl:
                    chave_dinamica = f"input_js_{st.session_state['tk_counter']}"
                    codigo_js = st.text_input("input_codigo_js", key=chave_dinamica, label_visibility="collapsed")
                    
                    if codigo_js:
                        if codigo_js in valid_codes:
                            agora = obter_hora_atual().strftime("%Y-%m-%d %H:%M:%S")
                            supa.table("status_maquinas").upsert({
                                "maquina": maquina_selecionada, "setor": setor_selecionado, 
                                "status": "Parado", "cod_peca_atual": None,
                                "cod_ocorrencia": codigo_js, "hora_inicio": agora
                            }).execute()
                            st.session_state['tk_counter'] += 1 
                            st.session_state['modo_cf'] = None
                            st.rerun()

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
                        <button class="btn-key" onclick="pressKey('1')">1</button><button class="btn-key" onclick="pressKey('2')">2</button><button class="btn-key" onclick="pressKey('3')">3</button>
                        <button class="btn-key" onclick="pressKey('4')">4</button><button class="btn-key" onclick="pressKey('5')">5</button><button class="btn-key" onclick="pressKey('6')">6</button>
                        <button class="btn-key" onclick="pressKey('7')">7</button><button class="btn-key" onclick="pressKey('8')">8</button><button class="btn-key" onclick="pressKey('9')">9</button>
                        <button class="btn-key btn-c" onclick="pressKey('C')">C</button><button class="btn-key" onclick="pressKey('0')">0</button><button class="btn-key btn-del" onclick="pressKey('<')">⌫</button>
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
                    problema_selecionado = st.selectbox("Ou selecione o problema na lista:", [""] + opcoes_prob, key="sel_lista_parada")
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    if st.button("🔴 CONFIRMAR PARADA", key="btn_start_lista", use_container_width=True, type="primary"):
                        if problema_selecionado:
                            cod_selecionado = problema_selecionado.split("(")[-1].replace(")", "").strip()
                            agora = obter_hora_atual().strftime("%Y-%m-%d %H:%M:%S")
                            supa.table("status_maquinas").upsert({
                                "maquina": maquina_selecionada, "setor": setor_selecionado, 
                                "status": "Parado", "cod_peca_atual": None,
                                "cod_ocorrencia": cod_selecionado, "hora_inicio": agora
                            }).execute()
                            st.session_state['modo_cf'] = None
                            st.rerun()
            else: st.warning(f"⚠️ Não há nenhum código configurado para este setor.")
            st.markdown("</div>", unsafe_allow_html=True)

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
            }}, 1000);
        </script>
        """
        components.html(js_cronometro, height=250)
        
        chave_estado_fin = f"fin_estado_{maquina_selecionada}"
        estado_fin = st.session_state.get(chave_estado_fin, None)
        
        if not estado_fin:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ FINALIZAR LOTE (Concluído)", use_container_width=True, type="primary"):
                    st.session_state[chave_estado_fin] = "CONCLUIDO"
                    st.rerun()
            with c2:
                if st.button("🔴 INTERROMPER (Por Falha)", use_container_width=True, type="primary"):
                    st.session_state[chave_estado_fin] = "INTERROMPIDO"
                    st.rerun()
        else:
            st.markdown("<div style='background-color: #f1f8ff; padding: 20px; border-radius: 10px; border: 2px solid #c8e1ff;'>", unsafe_allow_html=True)
            st.markdown("### 📊 Fechamento do Lote")
            qtd_informada = st.number_input("Quantas peças foram produzidas?", min_value=0, step=1, key=f"qtd_{maquina_selecionada}")
            
            cod_parada_escolhido = None
            if estado_fin == "INTERROMPIDO":
                st.markdown("### 🚨 Motivo da Interrupção")
                opcoes_prob = [f"{str(row['descricao']).strip()} ({str(row['codigo']).strip()})" for _, row in df_codigos_parado.iterrows()]
                sel_prob = st.selectbox("Selecione o problema:", [""] + opcoes_prob, key=f"prob_{maquina_selecionada}")
                if sel_prob: cod_parada_escolhido = sel_prob.split("(")[-1].replace(")", "").strip()
            
            st.markdown("<br>", unsafe_allow_html=True)
            cb1, cb2 = st.columns(2)
            with cb1:
                pode_salvar = True
                if estado_fin == "INTERROMPIDO" and not cod_parada_escolhido: pode_salvar = False
                    
                if st.button("💾 CONFIRMAR E SALVAR", type="primary", use_container_width=True, disabled=not pode_salvar):
                    hora_fim = obter_hora_atual()
                    hora_inicio_obj = datetime.strptime(hora_inicio_str, "%Y-%m-%d %H:%M:%S")
                    duracao_segundos = (hora_fim - hora_inicio_obj).total_seconds()
                    
                    if duracao_segundos >= 60:
                        # --- BUSCA O TIPO NA TABELA DE CÓDIGOS PARA O CÓDIGO 'P' ---
                        tipo_producao = "PRODUÇÃO" # Fallback de segurança
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
                            "das": hora_inicio_obj.strftime("%H:%M"), "as_hora": hora_fim.strftime("%H:%M"), "origem": "Chão de Fábrica"
                        }
                        supa.table("producao_diaria").insert(dados_nuvem).execute()
                    
                    if estado_fin == "INTERROMPIDO" and cod_parada_escolhido:
                        supa.table("status_maquinas").update({
                            "status": "Parado", "hora_inicio": hora_fim.strftime("%Y-%m-%d %H:%M:%S"),
                            "cod_ocorrencia": cod_parada_escolhido, "cod_peca_atual": None
                        }).eq("maquina", maquina_selecionada).execute()
                    else:
                        supa.table("status_maquinas").update({
                            "status": "Livre", "hora_inicio": None, "cod_ocorrencia": None, "cod_peca_atual": None
                        }).eq("maquina", maquina_selecionada).execute()
                        
                    st.session_state[chave_estado_fin] = None
                    st.rerun()
            with cb2:
                if st.button("❌ Cancelar Operação", use_container_width=True):
                    st.session_state[chave_estado_fin] = None
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    # ==========================================
    # ESTADO 3: MÁQUINA PARADA (PROBLEMA)
    # ==========================================
    elif status_db == 'Parado':
        desc_problema = "Desconhecido"
        tipo_problema = "PARADA" # Fallback
        
        # --- BUSCA O TIPO NA TABELA DE CÓDIGOS ---
        if cod_ocorrencia and not df_codigos.empty:
            filtro_desc = df_codigos[df_codigos['codigo'].astype(str) == str(cod_ocorrencia)]
            if not filtro_desc.empty:
                desc_problema = str(filtro_desc.iloc[0]['descricao']).strip()
                if 'tipo' in filtro_desc.columns: 
                    tipo_problema = str(filtro_desc.iloc[0]['tipo']).strip().upper()

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
            }}, 1000);
        </script>
        """
        components.html(js_cronometro, height=250)
        
        if st.button(texto_botao, use_container_width=True, type="primary"):
            hora_fim = obter_hora_atual()
            hora_inicio_obj = datetime.strptime(hora_inicio_str, "%Y-%m-%d %H:%M:%S")
            duracao_segundos = (hora_fim - hora_inicio_obj).total_seconds()
            
            if duracao_segundos >= 60:
                dados_nuvem = {
                    "data_registro": hora_inicio_obj.strftime("%Y-%m-%d"),
                    "setor": setor_selecionado, "maquina": maquina_selecionada, 
                    "tipo": tipo_problema, # <--- SALVA O TIPO OFICIAL EXTRAÍDO DA TABELA
                    "cod_ocorrencia": cod_ocorrencia, "operador": nomes_operadores,
                    "das": hora_inicio_obj.strftime("%H:%M"), "as_hora": hora_fim.strftime("%H:%M"), "origem": "Chão de Fábrica"
                }
                supa.table("producao_diaria").insert(dados_nuvem).execute()
                
            supa.table("status_maquinas").update({
                "status": "Livre", "hora_inicio": None, "cod_ocorrencia": None, "cod_peca_atual": None
            }).eq("maquina", maquina_selecionada).execute()
            st.rerun()

    # ==========================================
    # 4. HISTÓRICO EXCLUSIVO DO TABLET (HOJE)
    # ==========================================
    st.markdown("<hr style='opacity: 0.2; margin-top: 20px; margin-bottom: 20px;'>", unsafe_allow_html=True)
    st.markdown(f"### 📋 Últimos Registros de Hoje")
    
    hoje_str = obter_hora_atual().strftime("%Y-%m-%d")
    
    if df_nuvem.empty or 'maquina' not in df_nuvem.columns:
        df_hist = pd.DataFrame()
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
            
            # --- AGORA A LISTA DO TABLET IDENTIFICA PRODUÇÃO ESTRITAMENTE PELO CÓDIGO 'P' ---
            if codigo_bd == 'P':
                cod_peca = row.get('cod_peca', 'S/N')
                qtd_peca = row.get('quantidade', 0)
                nome_peca_hist = row.get('nome_peca', 'Peça Desconhecida')
                texto_exibicao = f"🟢 <b>Produção:</b> {nome_peca_hist} <br><span style='font-size: 13px; color: #7f8c8d;'>Cód: {cod_peca} | Qtde Produzida: {qtd_peca} | Operador: {nome_operador_hist}</span>"
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
            
        tabela_html = f"<div style='max-height: 250px; overflow-y: auto; border: 1px solid #eaeaea; border-radius: 8px;'><table style='width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 14px;'><thead><tr style='color: white; text-align: left;'><th style='padding: 10px; text-align: center; position: sticky; top: 0; background-color: #34495e; z-index: 1;'>Início</th><th style='padding: 10px; text-align: center; position: sticky; top: 0; background-color: #34495e; z-index: 1;'>Fim</th><th style='padding: 10px; position: sticky; top: 0; background-color: #34495e; z-index: 1;'>Apontamento Registrado</th></tr></thead><tbody>{linhas_html}</tbody></table></div>"
        st.markdown(tabela_html, unsafe_allow_html=True)

    # ==========================================
    # 5. RODAPÉ DO TERMINAL (INFO SECUNDÁRIAS)
    # ==========================================
    st.markdown("<hr style='opacity: 0.2; margin-top: 30px;'>", unsafe_allow_html=True)
    st.markdown("##### ℹ️ Informações do Terminal")

    if is_travado:
        st.markdown(f"""
        <div style="display: flex; gap: 15px; margin-bottom: 15px; flex-wrap: wrap;">
            <div style="background-color: #f8f9fa; border-left: 4px solid #2980b9; padding: 10px 15px; border-radius: 6px; flex: 1; min-width: 150px;">
                <span style="font-size: 11px; color: #7f8c8d; text-transform: uppercase; font-weight: bold;">Setor Vinculado</span><br><span style="font-size: 16px; font-weight: bold; color: #2c3e50;">{setor_selecionado}</span>
            </div>
            <div style="background-color: #f8f9fa; border-left: 4px solid #e67e22; padding: 10px 15px; border-radius: 6px; flex: 1; min-width: 150px;">
                <span style="font-size: 11px; color: #7f8c8d; text-transform: uppercase; font-weight: bold;">Máquina Vinculada</span><br><span style="font-size: 16px; font-weight: bold; color: #2c3e50;">{maquina_selecionada}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("💡 Modo de Gestão: Altere a máquina abaixo para visualizar seu status.")
        cr1, cr2 = st.columns(2)
        with cr1: st.selectbox("🏭 Setor", lista_setores_nuvem, key="cf_setor")
        with cr2: st.selectbox("⚙️ Máquina", lista_maquinas_nuvem, key="cf_maquina")

    if operadores_vinculados:
        st.markdown(f"<div style='background-color: #f1f8ff; border: 1px solid #c8e1ff; border-radius: 6px; padding: 10px; margin-bottom: 20px; text-align: center;'><span style='color: #555; font-size: 14px;'>👷 <b>Operador Vinculado:</b></span> <span style='color: #0366d6; font-size: 15px; font-weight: 700;'>{nomes_operadores}</span></div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='background-color: #fff8f2; border: 1px solid #ffd8b5; border-radius: 6px; padding: 10px; margin-bottom: 20px; text-align: center;'><span style='color: #d35400; font-size: 14px;'>⚠️ <b>Nenhum operador vinculado a esta máquina no momento.</b></span></div>", unsafe_allow_html=True)

    cfg = banco.obter_configuracoes()
    titulo_app = cfg.get('titulo_programa', 'PCP Avelan')
    logo_b64 = cfg.get('logo_base64', None)
    
    c1, c2 = st.columns([7, 3])
    with c1:
        if logo_b64: st.markdown(f'<div style="display: flex; align-items: center; gap: 15px;"><img src="data:image/png;base64,{logo_b64}" style="max-height: 40px;"><h3 style="margin:0; color: #2c3e50;">{titulo_app}</h3></div>', unsafe_allow_html=True)
        else: st.markdown(f'<h3 style="margin:0; color: #2c3e50;">🏭 {titulo_app}</h3>', unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div style='text-align: right; color: #7f8c8d; font-size: 14px; margin-bottom: 5px;'>👤 Olá, <b>{usuario.get('nome', 'Usuário')}</b></div>", unsafe_allow_html=True)
        if st.button("🚪 Sair do Sistema", use_container_width=True, key="btn_sair_cf"):
            st.session_state['usuario_logado'] = None
            try: st.query_params.clear()
            except: st.experimental_set_query_params()
            st.rerun()

    # ==========================================
    # SCRIPT PARA INFLAR OS BOTÕES E INJETAR CORES MÁGICAS
    # ==========================================
    js_cores = """
    <script>
        setInterval(() => {
            const btns = window.parent.document.querySelectorAll('button');
            btns.forEach(btn => {
                const texto = btn.innerText ? btn.innerText.toUpperCase() : "";
                
                if(texto.includes('INICIAR NOVA PRODUÇÃO') || texto.includes('CONFIRMAR E INICIAR') || texto.includes('CONFIRMAR E SALVAR')) {
                    btn.style.setProperty('background-color', '#27ae60', 'important');
                    btn.style.setProperty('border-color', '#27ae60', 'important');
                    btn.style.setProperty('color', 'white', 'important');
                }
                else if(texto.includes('REGISTRAR NOVA PARADA') || texto.includes('CONFIRMAR PARADA') || texto.includes('PROBLEMA RESOLVIDO') || texto.includes('FINALIZAR INTERVALO') || texto.includes('INTERROMPER')) {
                    btn.style.setProperty('background-color', '#c0392b', 'important');
                    btn.style.setProperty('border-color', '#c0392b', 'important');
                    btn.style.setProperty('color', 'white', 'important');
                }
                
                // Infla os botões principais do topo para ficarem gigantes e responsivos
                if(texto.includes('INICIAR NOVA PRODUÇÃO') || texto.includes('REGISTRAR NOVA PARADA') || texto.includes('FINALIZAR LOTE') || texto.includes('INTERROMPER') || texto.includes('PROBLEMA RESOLVIDO') || texto.includes('FINALIZAR INTERVALO')) {
                    btn.style.setProperty('height', '90px', 'important');
                    btn.style.setProperty('font-size', '22px', 'important');
                    btn.style.setProperty('font-weight', '900', 'important');
                    btn.style.setProperty('border-radius', '12px', 'important');
                    btn.style.setProperty('white-space', 'normal', 'important');
                }
            });
        }, 300);
    </script>
    """
    components.html(js_cores, height=0)