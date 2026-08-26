import streamlit as st
import streamlit.components.v1 as components

def injetar_css_global():
    """CSS que oculta elementos nativos e estrutura o layout base."""
    st.markdown("""
        <style>
        .block-container { padding-top: 0.5rem !important; padding-bottom: 0rem !important; margin-bottom: 0rem !important; }
        div[data-testid="stTabs"] { margin-top: -15px; }
        footer { display: none !important; }
        #MainMenu { visibility: hidden; }
        /* Oculta os inputs do JavaScript para não piscarem na tela */
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

def injetar_css_kanban():
    """CSS específico para a lista de peças em 3 andares."""
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

def injetar_js_botoes():
    """Formata e infla os botões de ação e bloqueia o teclado nos selects."""
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

def obter_html_teclado_parada(valid_codes_json, label_input, texto_botao):
    return f"""
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
    <button id="btn-start" class="btn-start" onclick="sendCode()" disabled>{texto_botao}</button>
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
            const inputs = window.parent.document.querySelectorAll('input[aria-label="{label_input}"]');
            if (inputs.length > 0) {{
                const input = inputs[0]; let nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                nativeSetter.call(input, currentCode); input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                setTimeout(() => {{ input.focus(); input.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', keyCode: 13, bubbles: true }})); input.blur(); }}, 50);
            }}
        }}
    </script>
    """

def obter_html_cronometro_produzindo(nome_peca, cod_peca_atual, hora_inicio_iso):
    return f"""
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

def obter_html_cronometro_parado(titulo_card, sub_texto, desc_problema, cod_ocorrencia, hora_inicio_iso, cor_fundo, cor_sombra, texto_botao):
    return f"""
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