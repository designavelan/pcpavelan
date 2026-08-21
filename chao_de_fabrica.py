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

    st.markdown("""
        <style>
        .titulo-pagina { font-size: 35px !important; }
        div[data-baseweb="select"] input { pointer-events: none !important; caret-color: transparent !important; }
        div[data-testid="stElementContainer"]:has(input[aria-label="input_codigo_js"]) {
            position: absolute !important; left: -9999px !important; width: 0px !important; height: 0px !important; overflow: hidden !important;
        }
        @media (max-width: 768px) {
            .titulo-pagina { font-size: 26px !important; }
            .titulo-verde { font-size: 26px !important; }
            .sub-verde { font-size: 16px !important; }
            .caixa-verde { padding: 25px 15px !important; margin-bottom: 20px !important; }
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<h2 class='titulo-pagina' style='text-align: center; color: #2c3e50; margin-bottom: 0;'>📱 Terminal Chão de Fábrica</h2>", unsafe_allow_html=True)

    supa = banco.conectar()

    if df_nuvem.empty:
        st.warning("Banco de dados vazio. Não há setores cadastrados.")
        return

    # ==========================================
    # 1. IDENTIFICAÇÃO DO EQUIPAMENTO (POKA-YOKE)
    # ==========================================
    usuario = st.session_state.get('usuario_logado', {})
    user_setor = usuario.get('setor', '[ Todos ]')
    user_maq = usuario.get('maquina', '[ Todas ]')

    # Verifica se o usuário está travado em uma máquina e setor específicos
    is_travado = (user_setor != "[ Todos ]" and user_maq != "[ Todas ]" and user_setor != "" and user_maq != "")

    if is_travado:
        setor_selecionado = user_setor
        maquina_selecionada = user_maq
        
        # Cabeçalho Fixo e Seguro (Sem Menus)
        st.markdown(f"""
        <div style="display: flex; justify-content: center; gap: 20px; margin-top: 15px; margin-bottom: 20px; flex-wrap: wrap;">
            <div style="background-color: #f8f9fa; border-left: 5px solid #2980b9; border-radius: 8px; padding: 12px 25px; text-align: left; box-shadow: 0 2px 4px rgba(0,0,0,0.05); flex: 1; min-width: 200px; max-width: 300px;">
                <span style="color: #7f8c8d; font-size: 13px; text-transform: uppercase; font-weight: 800; letter-spacing: 1px;">🏢 Setor Vinculado</span><br>
                <span style="color: #2c3e50; font-size: 24px; font-weight: 900;">{setor_selecionado}</span>
            </div>
            <div style="background-color: #f8f9fa; border-left: 5px solid #e67e22; border-radius: 8px; padding: 12px 25px; text-align: left; box-shadow: 0 2px 4px rgba(0,0,0,0.05); flex: 1; min-width: 200px; max-width: 300px;">
                <span style="color: #7f8c8d; font-size: 13px; text-transform: uppercase; font-weight: 800; letter-spacing: 1px;">⚙️ Máquina Vinculada</span><br>
                <span style="color: #2c3e50; font-size: 24px; font-weight: 900;">{maquina_selecionada}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<hr style='opacity: 0.2; margin-top: 5px;'>", unsafe_allow_html=True)
        
    else:
        # Se for um gestor/admin (que vê tudo), os menus aparecem para ele poder navegar
        lista_setores_nuvem = sorted(df_nuvem['setor'].dropna().unique().tolist())
        st.markdown("<p style='text-align: center; color: #7f8c8d; font-size: 16px; margin-top: 10px;'>Selecione o equipamento manualmente</p>", unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            setor_selecionado = st.selectbox("🏭 Selecione o Setor", lista_setores_nuvem, key="cf_setor")
        
        lista_maquinas_nuvem = sorted(df_nuvem[df_nuvem['setor'] == setor_selecionado]['maquina'].dropna().unique().tolist())
        
        with c2:
            maquina_selecionada = st.selectbox("⚙️ Selecione a Máquina", lista_maquinas_nuvem, key="cf_maquina")

        st.markdown("<hr style='opacity: 0.2;'>", unsafe_allow_html=True)


    # ==========================================
    # 2. VERIFICA O STATUS DA MÁQUINA
    # ==========================================
    response = supa.table("status_maquinas").select("*").eq("maquina", maquina_selecionada).execute()
    
    status_atual = 'Trabalhando'
    hora_inicio_str = None
    cod_ocorrencia = None
    
    if response.data:
        dados_maq = response.data[0]
        status_atual = dados_maq.get('status', 'Trabalhando')
        hora_inicio_str = dados_maq.get('hora_inicio')
        cod_ocorrencia = dados_maq.get('cod_ocorrencia')

    # ==========================================
    # TELA 1: MÁQUINA PRODUZINDO (TUDO OK)
    # ==========================================
    if status_atual == 'Trabalhando':
        st.markdown("""
        <div class="caixa-verde" style="background-color: #27ae60; color: white; padding: 40px 20px; border-radius: 15px; text-align: center; box-shadow: 0 4px 10px rgba(0,0,0,0.1); margin-bottom: 20px;">
            <h1 class="titulo-verde" style="margin:0; font-size: 40px; text-transform: uppercase;">🟢 Máquina Produzindo</h1>
            <p class="sub-verde" style="margin: 5px 0 0 0; font-size: 20px; opacity: 0.9;">Nenhuma parada registrada no momento.</p>
        </div>
        """, unsafe_allow_html=True)
        
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
                if 'tipo' in df_codigos.columns: df_codigos_parado = df_codigos[df_codigos['tipo'].astype(str).str.strip().str.upper() == 'PARADO']
                else: df_codigos_parado = pd.DataFrame()
                
            if not df_codigos_parado.empty:
                valid_codes = {str(row['codigo']).strip(): str(row['descricao']).strip() for _, row in df_codigos_parado.iterrows()}
                valid_codes_json = json.dumps(valid_codes)
                
                tab_teclado, tab_lista = st.tabs(["🔢 Teclado Numérico", "📄 Selecionar na Lista"])
                
                with tab_teclado:
                    chave_dinamica = f"input_js_{st.session_state['tk_counter']}"
                    codigo_js = st.text_input("input_codigo_js", key=chave_dinamica, label_visibility="collapsed")
                    
                    if codigo_js:
                        if codigo_js in valid_codes:
                            agora = obter_hora_atual().strftime("%Y-%m-%d %H:%M:%S")
                            dados_upsert = {
                                "maquina": maquina_selecionada,
                                "setor": setor_selecionado,
                                "status": "Parado",
                                "cod_ocorrencia": codigo_js,
                                "hora_inicio": agora
                            }
                            supa.table("status_maquinas").upsert(dados_upsert).execute()
                            st.session_state['tk_counter'] += 1 
                            st.rerun()

                    html_teclado = f"""
                    <style>
                        body {{ font-family: sans-serif; margin: 0; padding: 10px; }}
                        .lcd {{ background: #f8f9fa; padding: 15px; border-radius: 12px; text-align: center; border: 2px solid #dcdde1; box-shadow: inset 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 20px; }}
                        .lcd-val {{ margin: 0; font-family: monospace; font-size: 45px; letter-spacing: 5px; color: #2c3e50; min-height: 55px; }}
                        .lcd-desc {{ margin: 5px 0 0 0; font-size: 18px; font-weight: bold; min-height: 25px; transition: color 0.2s; }}
                        .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 25px; }}
                        .btn-key {{ background: #ffffff; border: 1px solid #dcdde1; border-radius: 12px; font-size: 28px; font-weight: 900; color: #2c3e50; padding: 20px 0; cursor: pointer; transition: all 0.1s; box-shadow: 0 4px 6px rgba(0,0,0,0.05); -webkit-tap-highlight-color: transparent; }}
                        .btn-key:active {{ transform: scale(0.95); background: #f1f2f6; }}
                        .btn-c {{ color: #e74c3c; }}
                        .btn-del {{ color: #e67e22; }}
                        .btn-start {{ width: 100%; background: #e74c3c; color: white; border: none; border-radius: 12px; font-size: 22px; font-weight: 900; text-transform: uppercase; padding: 25px 0; cursor: pointer; transition: all 0.2s; box-shadow: 0 4px 6px rgba(231,76,60,0.3); opacity: 0.5; -webkit-tap-highlight-color: transparent; }}
                        .btn-start:active:not(:disabled) {{ transform: scale(0.98); }}
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
                    <button id="btn-start" class="btn-start" onclick="sendCode()" disabled>🔴 Iniciar Parada</button>
                    <script>
                        const validCodes = {valid_codes_json};
                        let currentCode = "";
                        function updateLCD() {{
                            const lcdVal = document.getElementById("lcd-val");
                            const lcdDesc = document.getElementById("lcd-desc");
                            const btnStart = document.getElementById("btn-start");
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
                                const input = inputs[0];
                                let nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                                nativeSetter.call(input, currentCode);
                                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                setTimeout(() => {{ input.focus(); input.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }})); input.blur(); }}, 50);
                            }} else {{ document.getElementById("btn-start").innerText = "Erro no Campo Oculto!"; }}
                        }}
                    </script>
                    """
                    components.html(html_teclado, height=650)

                with tab_lista:
                    st.markdown("""
                        <style>
                        div[data-testid="stTabs"] button[kind="primary"] { height: 90px; font-size: 26px !important; font-weight: 900 !important; border-radius: 12px !important; text-transform: uppercase; white-space: normal !important; }
                        @media (max-width: 768px) { div[data-testid="stTabs"] button[kind="primary"] { height: 70px; font-size: 16px !important; } }
                        </style>
                    """, unsafe_allow_html=True)
                    st.markdown("<br>Ou pesquise e selecione o problema ocorrido:", unsafe_allow_html=True)
                    opcoes_prob = [f"{str(row['descricao']).strip()} ({str(row['codigo']).strip()})" for _, row in df_codigos_parado.iterrows()]
                    problema_selecionado = st.selectbox("", opcoes_prob, label_visibility="collapsed", key="sel_lista_parada")
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    if st.button("🔴 Iniciar Parada", key="btn_start_lista", use_container_width=True, type="primary"):
                        cod_selecionado = problema_selecionado.split("(")[-1].replace(")", "").strip()
                        agora = obter_hora_atual().strftime("%Y-%m-%d %H:%M:%S")
                        dados_upsert = {"maquina": maquina_selecionada, "setor": setor_selecionado, "status": "Parado", "cod_ocorrencia": cod_selecionado, "hora_inicio": agora}
                        supa.table("status_maquinas").upsert(dados_upsert).execute()
                        st.rerun()
            else:
                st.warning(f"⚠️ Não há nenhum código configurado para ser exibido no setor '{setor_selecionado}'.")

    # ==========================================
    # TELA 2: MÁQUINA PARADA (FINALIZAÇÃO)
    # ==========================================
    else:
        desc_problema = "Desconhecido"
        tipo_problema = "PARADO"
        
        if cod_ocorrencia and not df_codigos.empty:
            filtro_desc = df_codigos[df_codigos['codigo'].astype(str) == str(cod_ocorrencia)]
            if not filtro_desc.empty:
                desc_problema = str(filtro_desc.iloc[0]['descricao']).strip()
                if 'tipo' in filtro_desc.columns: tipo_problema = str(filtro_desc.iloc[0]['tipo']).strip().upper()

        hora_inicio_iso = hora_inicio_str.replace(" ", "T")
        is_pausa = (tipo_problema == 'DESNCONSIDERAR' or tipo_problema == 'DESCONSIDERAR')
        
        cor_fundo = "#f39c12" if is_pausa else "#c0392b"
        cor_sombra = "rgba(243, 156, 18, 0.4)" if is_pausa else "rgba(192, 57, 43, 0.4)"
        titulo_card = "☕ PAUSA PROGRAMADA" if is_pausa else "🔴 MÁQUINA PARADA"
        sub_texto = "Pausa em andamento:" if is_pausa else "Problema em andamento:"
        texto_botao = "✅ FINALIZAR INTERVALO" if is_pausa else "✅ PROBLEMA RESOLVIDO (FINALIZAR)"
        css_cor_botao = f"background-color: {cor_fundo} !important; border-color: {cor_fundo} !important; color: white !important;" if is_pausa else ""

        st.markdown(f"""
            <style>
            div[data-testid="stButton"] > button[kind="primary"] {{ height: 90px; font-size: 26px !important; font-weight: 900 !important; border-radius: 12px !important; text-transform: uppercase; white-space: normal !important; {css_cor_botao} }}
            @media (max-width: 768px) {{ div[data-testid="stButton"] > button[kind="primary"] {{ height: 70px; font-size: 16px !important; }} }}
            </style>
        """, unsafe_allow_html=True)

        js_cronometro = f"""
        <style>
            body {{ margin: 0; padding: 0; font-family: sans-serif; }}
            .caixa-vermelha {{ background-color: {cor_fundo}; color: white; padding: 40px 20px; border-radius: 15px; text-align: center; box-shadow: 0 4px 15px {cor_sombra}; box-sizing: border-box; margin: 0; transition: background-color 0.3s; }}
            .titulo-vermelho {{ margin: 0; font-size: 40px; text-transform: uppercase; }}
            .sub-vermelho {{ margin: 10px 0 20px 0; font-size: 22px; opacity: 0.9; }}
            .cronometro {{ font-size: 80px; font-weight: 900; font-family: monospace; letter-spacing: 2px; }}
            @media (max-width: 768px) {{ .caixa-vermelha {{ padding: 25px 10px; }} .titulo-vermelho {{ font-size: 26px; }} .sub-vermelho {{ font-size: 16px; margin: 10px 0 15px 0; }} .cronometro {{ font-size: 48px; letter-spacing: 0px; }} }}
        </style>
        <div class="caixa-vermelha">
            <h1 class="titulo-vermelho">{titulo_card}</h1><p class="sub-vermelho">{sub_texto} <br><b>{desc_problema} ({cod_ocorrencia})</b></p>
            <div id="stopwatch" class="cronometro">00:00:00</div>
        </div>
        <script>
            const startTime = new Date("{hora_inicio_iso}").getTime();
            setInterval(function() {{
                const now = new Date().getTime();
                const distance = now - startTime;
                if (distance > 0) {{
                    const h = Math.floor(distance / (1000 * 60 * 60)); const m = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60)); const s = Math.floor((distance % (1000 * 60)) / 1000);
                    document.getElementById("stopwatch").innerHTML = (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
                }}
            }}, 1000);
        </script>
        """
        components.html(js_cronometro, height=280)
        
        if st.button(texto_botao, use_container_width=True, type="primary"):
            hora_fim = obter_hora_atual()
            hora_inicio_obj = datetime.strptime(hora_inicio_str, "%Y-%m-%d %H:%M:%S")
            duracao_segundos = (hora_fim - hora_inicio_obj).total_seconds()
            
            if duracao_segundos >= 60:
                dados_nuvem = {
                    "data_registro": hora_inicio_obj.strftime("%Y-%m-%d"),
                    "setor": setor_selecionado,
                    "maquina": maquina_selecionada,
                    "cod_ocorrencia": cod_ocorrencia,
                    "das": hora_inicio_obj.strftime("%H:%M"),
                    "as_hora": hora_fim.strftime("%H:%M"),
                    "origem": "Chão de Fábrica"
                }
                supa.table("producao_diaria").insert(dados_nuvem).execute()
                
            supa.table("status_maquinas").update({"status": "Trabalhando", "hora_inicio": None, "cod_ocorrencia": None}).eq("maquina", maquina_selecionada).execute()
            st.rerun()

    # ==========================================
    # 3. HISTÓRICO EXCLUSIVO DO TABLET (HOJE)
    # ==========================================
    st.markdown("<hr style='opacity: 0.2; margin-top: 10px; margin-bottom: 20px;'>", unsafe_allow_html=True)
    st.markdown(f"### 📋 Últimos Registros de Hoje — {maquina_selecionada}")
    
    if 'origem' not in df_nuvem.columns: df_nuvem['origem'] = 'Importação'
    hoje_str = obter_hora_atual().strftime("%Y-%m-%d")
    
    df_hist = df_nuvem[(df_nuvem['maquina'] == maquina_selecionada) & (df_nuvem['data_registro'] == hoje_str) & (df_nuvem['origem'] == 'Chão de Fábrica')].copy()
    
    if df_hist.empty: st.info("Você ainda não registrou nenhuma parada nesta máquina hoje.")
    else:
        df_hist = df_hist.sort_values(by=['data_registro', 'as_hora'], ascending=[False, False]).head(20)
        if not df_codigos.empty:
            df_codigos_clean = df_codigos[['codigo', 'descricao']].copy()
            df_codigos_clean['codigo'] = df_codigos_clean['codigo'].astype(str).str.strip()
            df_hist['cod_ocorrencia'] = df_hist['cod_ocorrencia'].astype(str).str.strip()
            df_hist = df_hist.merge(df_codigos_clean, left_on='cod_ocorrencia', right_on='codigo', how='left')
            df_hist['descricao'] = df_hist['descricao'].fillna("Sem Descrição")
        else: df_hist['descricao'] = "Sem Descrição"
            
        linhas_html = ""
        for i, row in df_hist.iterrows():
            fundo = "#f9f9f9" if i % 2 != 0 else "#ffffff"
            linhas_html += f"<tr style='background-color: {fundo};'><td style='padding: 10px; border-bottom: 1px solid #eee; text-align: center; font-weight: bold; color: #e74c3c;'>{row['das']}</td><td style='padding: 10px; border-bottom: 1px solid #eee; text-align: center; font-weight: bold; color: #27ae60;'>{row['as_hora']}</td><td style='padding: 10px; border-bottom: 1px solid #eee;'>{row['descricao']} <b>({row['cod_ocorrencia']})</b></td></tr>"
            
        tabela_html = f"<div style='max-height: 400px; overflow-y: auto; border: 1px solid #eaeaea; border-radius: 8px;'><table style='width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 15px;'><thead><tr style='color: white; text-align: left;'><th style='padding: 12px; text-align: center; position: sticky; top: 0; background-color: #34495e; z-index: 1;'>Início</th><th style='padding: 12px; text-align: center; position: sticky; top: 0; background-color: #34495e; z-index: 1;'>Fim</th><th style='padding: 12px; position: sticky; top: 0; background-color: #34495e; z-index: 1;'>Problema Registrado</th></tr></thead><tbody>{linhas_html}</tbody></table></div>"
        st.markdown(tabela_html, unsafe_allow_html=True)