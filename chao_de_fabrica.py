import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import banco
import streamlit.components.v1 as components

# Função para garantir o fuso horário correto do Brasil (Aracaju) independentemente de onde o servidor esteja
def obter_hora_atual():
    return datetime.utcnow() - timedelta(hours=3)

def renderizar(df_nuvem, df_codigos):
    # CSS INTELIGENTE: Botões gigantes no PC, botões adaptados no celular
    st.markdown("""
        <style>
        div.stButton > button {
            height: 90px;
            font-size: 26px !important;
            font-weight: 900 !important;
            border-radius: 12px !important;
            text-transform: uppercase;
            white-space: normal !important;
        }
        
        /* Regras responsivas para a tela de celular */
        @media (max-width: 768px) {
            div.stButton > button {
                height: 70px;
                font-size: 16px !important;
            }
            .titulo-pagina { font-size: 26px !important; }
            .titulo-verde { font-size: 26px !important; }
            .sub-verde { font-size: 16px !important; }
            .caixa-verde { padding: 25px 15px !important; margin-bottom: 20px !important; }
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<h2 class='titulo-pagina' style='text-align: center; color: #2c3e50; font-size: 35px; margin-bottom: 0;'>📱 Terminal Chão de Fábrica</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #7f8c8d; font-size: 16px;'>Modo de Teste: Seleção Manual de Equipamento</p>", unsafe_allow_html=True)

    supa = banco.conectar()

    if df_nuvem.empty:
        st.warning("Banco de dados vazio. Não há setores cadastrados.")
        return

    # ==========================================
    # 1. SELEÇÃO DO EQUIPAMENTO (MODO TESTE)
    # ==========================================
    lista_setores = sorted(df_nuvem['setor'].dropna().unique().tolist())
    
    c1, c2 = st.columns(2)
    with c1:
        setor_selecionado = st.selectbox("🏭 Selecione o Setor", lista_setores, key="cf_setor")
    
    lista_maquinas = sorted(df_nuvem[df_nuvem['setor'] == setor_selecionado]['maquina'].dropna().unique().tolist())
    with c2:
        maquina_selecionada = st.selectbox("⚙️ Selecione a Máquina", lista_maquinas, key="cf_maquina")

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
        <div class="caixa-verde" style="background-color: #27ae60; color: white; padding: 40px 20px; border-radius: 15px; text-align: center; box-shadow: 0 4px 10px rgba(0,0,0,0.1); margin-bottom: 30px;">
            <h1 class="titulo-verde" style="margin:0; font-size: 40px; text-transform: uppercase;">🟢 Máquina Produzindo</h1>
            <p class="sub-verde" style="margin: 5px 0 0 0; font-size: 20px; opacity: 0.9;">Nenhuma parada registrada no momento.</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### ⚠️ Registrar Nova Parada")
        st.markdown("Pesquise e selecione o problema ocorrido:")
        
        if not df_codigos.empty:
            
            # --- NOVO FILTRO: APENAS CÓDIGOS DO TIPO "PARADO" ---
            if 'tipo' in df_codigos.columns:
                df_codigos_parado = df_codigos[df_codigos['tipo'].astype(str).str.strip().str.upper() == 'PARADO']
            else:
                df_codigos_parado = df_codigos
                
            if not df_codigos_parado.empty:
                opcoes_prob = [f"{str(row['descricao']).strip()} ({str(row['codigo']).strip()})" for _, row in df_codigos_parado.iterrows()]
                problema_selecionado = st.selectbox("", opcoes_prob, label_visibility="collapsed")
                st.markdown("<br>", unsafe_allow_html=True)
                
                if st.button("🔴 Iniciar Parada", use_container_width=True, type="primary"):
                    cod_selecionado = problema_selecionado.split("(")[-1].replace(")", "")
                    agora = obter_hora_atual().strftime("%Y-%m-%d %H:%M:%S")
                    
                    dados_upsert = {
                        "maquina": maquina_selecionada,
                        "setor": setor_selecionado,
                        "status": "Parado",
                        "cod_ocorrencia": cod_selecionado,
                        "hora_inicio": agora
                    }
                    supa.table("status_maquinas").upsert(dados_upsert).execute()
                    st.rerun()
            else:
                st.warning("⚠️ Não há nenhum código classificado como 'Parado' cadastrado no sistema.")

    # ==========================================
    # TELA 2: MÁQUINA PARADA (CRONÔMETRO ATIVO)
    # ==========================================
    else:
        desc_problema = "Desconhecido"
        if cod_ocorrencia and not df_codigos.empty:
            filtro_desc = df_codigos[df_codigos['codigo'].astype(str) == str(cod_ocorrencia)]
            if not filtro_desc.empty:
                desc_problema = filtro_desc.iloc[0]['descricao']

        hora_inicio_iso = hora_inicio_str.replace(" ", "T")

        js_cronometro = f"""
        <style>
            body {{ margin: 0; padding: 0; font-family: sans-serif; }}
            .caixa-vermelha {{
                background-color: #c0392b; color: white; padding: 40px 20px; border-radius: 15px; 
                text-align: center; box-shadow: 0 4px 15px rgba(192, 57, 43, 0.4); 
                box-sizing: border-box; margin: 0;
            }}
            .titulo-vermelho {{ margin: 0; font-size: 40px; text-transform: uppercase; }}
            .sub-vermelho {{ margin: 10px 0 20px 0; font-size: 22px; opacity: 0.9; }}
            .cronometro {{ font-size: 80px; font-weight: 900; font-family: monospace; letter-spacing: 2px; }}
            
            @media (max-width: 768px) {{
                .caixa-vermelha {{ padding: 25px 10px; }}
                .titulo-vermelho {{ font-size: 26px; }}
                .sub-vermelho {{ font-size: 16px; margin: 10px 0 15px 0; }}
                .cronometro {{ font-size: 48px; letter-spacing: 0px; }}
            }}
        </style>
        <div class="caixa-vermelha">
            <h1 class="titulo-vermelho">🔴 Máquina Parada</h1>
            <p class="sub-vermelho">Problema em andamento: <br><b>{desc_problema} ({cod_ocorrencia})</b></p>
            <div id="stopwatch" class="cronometro">00:00:00</div>
        </div>
        <script>
            const startTime = new Date("{hora_inicio_iso}").getTime();
            
            setInterval(function() {{
                const now = new Date().getTime();
                const distance = now - startTime;
                
                if (distance > 0) {{
                    const hours = Math.floor(distance / (1000 * 60 * 60));
                    const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
                    const seconds = Math.floor((distance % (1000 * 60)) / 1000);
                    
                    document.getElementById("stopwatch").innerHTML =
                        (hours < 10 ? "0" : "") + hours + ":" +
                        (minutes < 10 ? "0" : "") + minutes + ":" +
                        (seconds < 10 ? "0" : "") + seconds;
                }}
            }}, 1000);
        </script>
        """
        components.html(js_cronometro, height=280)
        
        if st.button("✅ Problema Resolvido (Finalizar)", use_container_width=True, type="primary"):
            hora_fim = obter_hora_atual()
            hora_inicio_obj = datetime.strptime(hora_inicio_str, "%Y-%m-%d %H:%M:%S")
            
            data_reg = hora_inicio_obj.strftime("%Y-%m-%d")
            das_str = hora_inicio_obj.strftime("%H:%M")
            as_str = hora_fim.strftime("%H:%M")
            
            dados_nuvem = {
                "data_registro": data_reg,
                "setor": setor_selecionado,
                "maquina": maquina_selecionada,
                "cod_ocorrencia": cod_ocorrencia,
                "das": das_str,
                "as_hora": as_str,
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
    
    if 'origem' not in df_nuvem.columns:
        df_nuvem['origem'] = 'Importação'
        
    hoje_str = obter_hora_atual().strftime("%Y-%m-%d")
    
    df_hist = df_nuvem[
        (df_nuvem['maquina'] == maquina_selecionada) & 
        (df_nuvem['data_registro'] == hoje_str) & 
        (df_nuvem['origem'] == 'Chão de Fábrica')
    ].copy()
    
    if df_hist.empty:
        st.info("Você ainda não registrou nenhuma parada nesta máquina hoje.")
    else:
        df_hist = df_hist.sort_values(by=['data_registro', 'as_hora'], ascending=[False, False]).head(20)
        
        if not df_codigos.empty:
            df_codigos_clean = df_codigos[['codigo', 'descricao']].copy()
            df_codigos_clean['codigo'] = df_codigos_clean['codigo'].astype(str).str.strip()
            df_hist['cod_ocorrencia'] = df_hist['cod_ocorrencia'].astype(str).str.strip()
            
            df_hist = df_hist.merge(df_codigos_clean, left_on='cod_ocorrencia', right_on='codigo', how='left')
            df_hist['descricao'] = df_hist['descricao'].fillna("Sem Descrição")
        else:
            df_hist['descricao'] = "Sem Descrição"
            
        linhas_html = ""
        for i, row in df_hist.iterrows():
            fundo = "#f9f9f9" if i % 2 != 0 else "#ffffff"
            desc_formatada = f"{row['descricao']} <b>({row['cod_ocorrencia']})</b>"
            
            linhas_html += f"<tr style='background-color: {fundo};'>"
            linhas_html += f"<td style='padding: 10px; border-bottom: 1px solid #eee; text-align: center; font-weight: bold; color: #e74c3c;'>{row['das']}</td>"
            linhas_html += f"<td style='padding: 10px; border-bottom: 1px solid #eee; text-align: center; font-weight: bold; color: #27ae60;'>{row['as_hora']}</td>"
            linhas_html += f"<td style='padding: 10px; border-bottom: 1px solid #eee;'>{desc_formatada}</td>"
            linhas_html += "</tr>"
            
        tabela_html = f"<div style='max-height: 400px; overflow-y: auto; border: 1px solid #eaeaea; border-radius: 8px;'>"
        tabela_html += f"<table style='width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 15px;'>"
        tabela_html += f"<thead><tr style='color: white; text-align: left;'>"
        tabela_html += f"<th style='padding: 12px; text-align: center; position: sticky; top: 0; background-color: #34495e; z-index: 1;'>Início</th>"
        tabela_html += f"<th style='padding: 12px; text-align: center; position: sticky; top: 0; background-color: #34495e; z-index: 1;'>Fim</th>"
        tabela_html += f"<th style='padding: 12px; position: sticky; top: 0; background-color: #34495e; z-index: 1;'>Problema Registrado</th>"
        tabela_html += f"</tr></thead><tbody>{linhas_html}</tbody></table></div>"
        
        st.markdown(tabela_html, unsafe_allow_html=True)