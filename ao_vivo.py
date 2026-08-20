import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import banco
import streamlit.components.v1 as components
import json
import time

def obter_hora_atual():
    return datetime.utcnow() - timedelta(hours=3)

def calcular_minutos_str(hora_str):
    try: return int(hora_str.split(':')[0]) * 60 + int(hora_str.split(':')[1])
    except: return 0

def renderizar(df_nuvem, df_codigos, filtros_selecionados):
    st.markdown("""
        <style>
        ::-webkit-scrollbar { display: none; }
        .block-container { max-width: 98% !important; padding-top: 1rem !important; }
        </style>
    """, unsafe_allow_html=True)

    cfg = banco.obter_configuracoes()
    refresh_segundos = int(cfg.get('ao_vivo_refresh', 60))
    tempo_critico = int(cfg.get('ao_vivo_critico', 15))
    vel_barra = int(cfg.get('ao_vivo_vel_barra', 8))

    agora = obter_hora_atual()
    hoje_str = agora.strftime("%Y-%m-%d")

    # ==========================================
    # BARRA DE PROGRESSO DO TURNO
    # ==========================================
    m_das = cfg.get('manha_das', '07:00')
    t_as = cfg.get('tarde_as', '17:00')
    
    inicio_turno = datetime.strptime(f"{hoje_str} {m_das}", "%Y-%m-%d %H:%M")
    fim_turno = datetime.strptime(f"{hoje_str} {t_as}", "%Y-%m-%d %H:%M")
    
    total_min_turno = (fim_turno - inicio_turno).total_seconds() / 60
    min_passados = (agora - inicio_turno).total_seconds() / 60
    
    if min_passados < 0: perc_turno = 0
    elif min_passados > total_min_turno: perc_turno = 100
    else: perc_turno = (min_passados / total_min_turno) * 100

    st.markdown(f"""
    <div style="text-align: center; margin-bottom: 10px;">
        <h2 style="color: #2c3e50; font-weight: 900; margin-bottom: 5px; font-size: 36px; text-transform: uppercase;">🔴 Painel Andon — Tempo Real</h2>
        <div style="width: 100%; background-color: #e0e0e0; border-radius: 10px; height: 12px; overflow: hidden; margin: 15px 0 5px 0;">
            <div style="width: {perc_turno:.1f}%; background-color: #2980b9; height: 100%; transition: width 1s;"></div>
        </div>
        <div style="font-size: 13px; color: #7f8c8d; font-weight: bold; text-align: right;">PROGRESSO DO TURNO: {perc_turno:.1f}%</div>
    </div>
    """, unsafe_allow_html=True)

    # BOTÃO INVISÍVEL
    st.markdown("<div style='display:none;'>", unsafe_allow_html=True)
    if st.button("RefreshAoVivo", key="btn_refresh_aovivo"): pass
    st.markdown("</div>", unsafe_allow_html=True)

    supa = banco.conectar()
    
    if filtros_selecionados['setor'] != "[ Todos ]":
        todas_maquinas = sorted(df_nuvem[df_nuvem['setor'] == filtros_selecionados['setor']]['maquina'].dropna().unique().tolist())
    else:
        todas_maquinas = sorted(df_nuvem['maquina'].dropna().unique().tolist())

    if not todas_maquinas:
        st.info("Nenhuma máquina encontrada neste setor.")
        return

    mapa_setores = df_nuvem[['maquina', 'setor']].dropna().drop_duplicates().set_index('maquina')['setor'].to_dict()

    resp_status = supa.table("status_maquinas").select("*").in_("maquina", todas_maquinas).execute()
    status_dict = {d['maquina']: d for d in resp_status.data} if resp_status.data else {}

    maquinas_paradas = []
    maquinas_rodando_por_setor = {}
    qtd_rodando = 0
    minutos_ativos_perdidos = 0

    for maq in todas_maquinas:
        info = status_dict.get(maq)
        if info and info.get('status') == 'Parado':
            cod = info.get('cod_ocorrencia')
            desc = "Desconhecido"
            if cod and not df_codigos.empty:
                filtro = df_codigos[df_codigos['codigo'].astype(str) == str(cod)]
                if not filtro.empty: desc = str(filtro.iloc[0]['descricao'])
            
            info['descricao_completa'] = f"{desc} ({cod})"
            info['setor'] = mapa_setores.get(maq, "Desconhecido")
            maquinas_paradas.append(info)
            
            try:
                h_ini = datetime.strptime(info['hora_inicio'], "%Y-%m-%d %H:%M:%S")
                minutos_ativos_perdidos += (agora - h_ini).total_seconds() / 60
            except: pass
        else:
            setor_maq = mapa_setores.get(maq, "Sem Setor")
            if setor_maq not in maquinas_rodando_por_setor:
                maquinas_rodando_por_setor[setor_maq] = []
            maquinas_rodando_por_setor[setor_maq].append(maq)
            qtd_rodando += 1

    qtd_total = len(todas_maquinas)
    qtd_paradas = len(maquinas_paradas)
    perc_rodando = (qtd_rodando / qtd_total) * 100 if qtd_total > 0 else 0
    perc_paradas = (qtd_paradas / qtd_total) * 100 if qtd_total > 0 else 0

    # ==========================================
    # CÁLCULO DAS MÉTRICAS DO DIA
    # ==========================================
    df_hoje = df_nuvem[(df_nuvem['data_registro'] == hoje_str) & (df_nuvem['maquina'].isin(todas_maquinas))].copy()
    minutos_finalizados = 0
    top_ofensor = "Nenhum (0)"
    mttr_str = "0m"
    noticias = []
    
    if not df_hoje.empty:
        for _, row in df_hoje.iterrows():
            m_das = calcular_minutos_str(row['das'])
            m_as = calcular_minutos_str(row['as_hora'])
            minutos_finalizados += (m_as - m_das)
            
        mttr = minutos_finalizados / len(df_hoje)
        mttr_str = f"{int(mttr)}m"
        
        vilao_cod = df_hoje['cod_ocorrencia'].value_counts().idxmax()
        qtd_vilao = df_hoje['cod_ocorrencia'].value_counts().max()
        desc_vilao = "Problema"
        if not df_codigos.empty:
            filtro = df_codigos[df_codigos['codigo'].astype(str) == str(vilao_cod)]
            if not filtro.empty: desc_vilao = str(filtro.iloc[0]['descricao'])
        top_ofensor = f"{desc_vilao} ({qtd_vilao}x)"
        
        df_noticias = df_hoje.sort_values(by='as_hora', ascending=False).head(5)
        for _, rr in df_noticias.iterrows():
            noticias.append(f"🟢 {rr['maquina']} voltou a operar às {rr['as_hora']}")

    total_perdido_hoje = minutos_finalizados + minutos_ativos_perdidos
    h_perdido = int(total_perdido_hoje // 60)
    m_perdido = int(total_perdido_hoje % 60)
    
    for p in maquinas_paradas:
        noticias.append(f"🔴 {p['maquina']} parada: {p['descricao_completa']}")
        
    texto_letreiro = " &nbsp;&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;&nbsp; ".join(noticias) if noticias else "🟢 FÁBRICA OPERANDO COM 100% DE CAPACIDADE NESTE MOMENTO"

    # ==========================================
    # RENDERIZAÇÃO DA HIERARQUIA 
    # ==========================================
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div style='background:#f8f9fa; padding:15px; border-radius:10px; text-align:center; border:1px solid #ddd;'><h4 style='margin:0; color:#555;'>Máquinas do Setor</h4><h2 style='margin:0; font-size:38px; color:#2c3e50;'>{qtd_total}</h2></div>", unsafe_allow_html=True)
    c2.markdown(f"<div style='background:#e8f8f5; padding:15px; border-radius:10px; text-align:center; border:1px solid #c8e6c9;'><h4 style='margin:0; color:#27ae60;'>Produzindo</h4><h2 style='margin:0; font-size:38px; color:#2ecc71;'>{qtd_rodando} <span style='font-size:18px;'>({perc_rodando:.0f}%)</span></h2></div>", unsafe_allow_html=True)
    c3.markdown(f"<div style='background:#fdedec; padding:15px; border-radius:10px; text-align:center; border:1px solid #f5b7b1;'><h4 style='margin:0; color:#c0392b;'>Paradas</h4><h2 style='margin:0; font-size:38px; color:#e74c3c;'>{qtd_paradas} <span style='font-size:18px;'>({perc_paradas:.0f}%)</span></h2></div>", unsafe_allow_html=True)

    m1, m2, m3 = st.columns(3)
    m1.markdown(f"<div style='background:#fff; padding:15px; border-radius:10px; text-align:center; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-top: 10px;'><h5 style='margin:0; color:#7f8c8d; text-transform: uppercase;'>🩸 Tempo Perdido Hoje</h5><h3 style='margin:0; font-size:28px; color:#c0392b;'>{h_perdido:02d}h:{m_perdido:02d}m</h3></div>", unsafe_allow_html=True)
    # --- NOVO NOME: TEMPO MÉDIO DE SOLUÇÃO ---
    m2.markdown(f"<div style='background:#fff; padding:15px; border-radius:10px; text-align:center; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-top: 10px;'><h5 style='margin:0; color:#7f8c8d; text-transform: uppercase;'>⏱️ Tempo Médio de Solução</h5><h3 style='margin:0; font-size:28px; color:#2980b9;'>{mttr_str}</h3></div>", unsafe_allow_html=True)
    m3.markdown(f"<div style='background:#fff; padding:15px; border-radius:10px; text-align:center; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-top: 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'><h5 style='margin:0; color:#7f8c8d; text-transform: uppercase;'>🏆 Principal Ofensor</h5><h3 style='margin:0; font-size:20px; color:#e67e22; margin-top: 8px;'>{top_ofensor}</h3></div>", unsafe_allow_html=True)

    st.markdown("<hr style='opacity:0.2; margin: 25px 0;'>", unsafe_allow_html=True)

    st.markdown("<h3 style='text-align: center; color: #c0392b; text-transform: uppercase; font-weight: 900; margin-bottom: 20px;'>🚨 Atenção Requerida (Paradas Ativas)</h3>", unsafe_allow_html=True)
    
    lista_js_paradas = []
    
    if not maquinas_paradas:
        st.markdown("<div style='background:#e8f8f5; padding:20px; border-radius:8px; color:#27ae60; text-align:center; font-size:20px; font-weight: bold;'>Tudo operando dentro da normalidade!</div>", unsafe_allow_html=True)
    else:
        st.markdown("""
        <style>
            .grid-ao-vivo { display: flex; flex-wrap: wrap; gap: 25px; padding: 10px; justify-content: center; }
            .card-ao-vivo {
                flex: 1 1 320px; max-width: 450px;
                padding: 30px 20px; border-radius: 15px; color: white; text-align: center;
                box-shadow: 0 8px 20px rgba(0,0,0,0.2); transition: background-color 0.5s ease;
            }
            .card-normal { background-color: #e74c3c; }
            .card-critico { background-color: #8b0000; animation: pulse-critico 1s infinite alternate; }
            @keyframes pulse-critico {
                0% { box-shadow: 0 0 0 0 rgba(139, 0, 0, 0.7); transform: scale(1); }
                100% { box-shadow: 0 0 0 20px rgba(139, 0, 0, 0); transform: scale(1.02); }
            }
            .maq-setor { font-size: 16px; text-transform: uppercase; letter-spacing: 2px; opacity: 0.9; margin-bottom: 8px; font-weight: bold; color: #f1c40f; }
            .maq-nome { font-size: 34px; font-weight: 900; margin: 0 0 10px 0; text-transform: uppercase; }
            .maq-prob { font-size: 18px; margin: 0 0 15px 0; opacity: 0.95; min-height: 45px; }
            .maq-inicio { font-size: 15px; font-weight: bold; opacity: 0.85; margin-bottom: 5px; }
            .maq-timer { font-size: 60px; font-family: monospace; font-weight: bold; letter-spacing: 2px; background: rgba(0,0,0,0.2); border-radius: 10px; padding: 10px; }
            .alerta-icone { font-size: 30px; vertical-align: middle; margin-right: 10px; display: none; }
            .card-critico .alerta-icone { display: inline-block; }
        </style>
        """, unsafe_allow_html=True)

        html_cards = "<div class='grid-ao-vivo'>"
        for p in maquinas_paradas:
            hora_iso = str(p['hora_inicio']).replace(" ", "T")
            
            # --- FORMATAÇÃO DO HORÁRIO DE INÍCIO ---
            try:
                hora_formatada = datetime.strptime(p['hora_inicio'], "%Y-%m-%d %H:%M:%S").strftime("%H:%M")
            except:
                hora_formatada = "--:--"
                
            p_id = p['maquina'].replace(" ", "_")
            
            lista_js_paradas.append({"id": p_id, "inicio_iso": hora_iso})
            
            html_cards += f"<div id='card_{p_id}' class='card-ao-vivo card-normal'>"
            html_cards += f"<div class='maq-setor'>{p['setor']}</div>"
            html_cards += f"<div class='maq-nome'><span class='alerta-icone'>⚠️</span>{p['maquina']}</div>"
            html_cards += f"<div class='maq-prob'>{p['descricao_completa']}</div>"
            # --- INSERÇÃO DA LABEL DE INÍCIO ---
            html_cards += f"<div class='maq-inicio'>Início da parada: {hora_formatada}</div>"
            html_cards += f"<div id='timer_{p_id}' class='maq-timer'>00:00:00</div>"
            html_cards += "</div>"
        html_cards += "</div>"
        
        st.markdown(html_cards, unsafe_allow_html=True)

    json_paradas = json.dumps(lista_js_paradas)

    st.markdown("<hr style='opacity:0.2; margin: 30px 0 15px 0;'>", unsafe_allow_html=True)
    if maquinas_rodando_por_setor:
        html_rodando = "<div style='text-align: center;'>"
        for setor_nome in sorted(maquinas_rodando_por_setor.keys()):
            html_rodando += f"<div style='margin-bottom: 15px;'>"
            html_rodando += f"<div style='font-size: 14px; color: #7f8c8d; font-weight: bold; text-transform: uppercase; margin-bottom: 5px;'>🏢 {setor_nome}</div>"
            for mr in sorted(maquinas_rodando_por_setor[setor_nome]):
                html_rodando += f"<div style='display:inline-block; background-color:#e8f8f5; border: 2px solid #27ae60; color:#27ae60; padding:8px 16px; border-radius:25px; font-weight:900; font-size:15px; margin:0 8px 8px 0;'>{mr}</div>"
            html_rodando += "</div>"
        html_rodando += "</div>"
        st.markdown(html_rodando, unsafe_allow_html=True)

    # --- LETREIRO COM VELOCIDADE DINÂMICA ---
    st.markdown(f"""
    <div style="width: 100%; overflow: hidden; background-color: #34495e; color: white; padding: 12px 0; margin-top: 30px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <marquee scrollamount="{vel_barra}" style="font-size: 18px; font-weight: 600; letter-spacing: 1px;">
            {texto_letreiro}
        </marquee>
    </div>
    """, unsafe_allow_html=True)

    hash_unico = time.time() 
    
    js_engine = f"""
    <script>
        setTimeout(function() {{
            const btns = window.parent.document.querySelectorAll('button');
            for (let i = 0; i < btns.length; i++) {{
                if (btns[i].innerText === 'RefreshAoVivo') {{ btns[i].click(); break; }}
            }}
        }}, {refresh_segundos * 1000});

        function playBeep() {{
            try {{
                const AudioContext = window.AudioContext || window.webkitAudioContext;
                if (!AudioContext) return;
                const ctx = new AudioContext();
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.type = 'sine';
                osc.frequency.value = 750; 
                gain.gain.setValueAtTime(0, ctx.currentTime);
                gain.gain.linearRampToValueAtTime(0.3, ctx.currentTime + 0.1);
                gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.6);
                osc.start(ctx.currentTime);
                osc.stop(ctx.currentTime + 0.6);
            }} catch(e) {{ console.log("Áudio bloqueado pelo navegador."); }}
        }}

        const paradas = {json_paradas};
        const tempoCriticoMs = {tempo_critico} * 60 * 1000;
        
        if (paradas.length > 0) {{
            setInterval(() => {{
                const now = new Date().getTime();
                paradas.forEach(p => {{
                    const startTime = new Date(p.inicio_iso).getTime();
                    const distance = now - startTime;
                    
                    if (distance > 0) {{
                        const h = Math.floor(distance / (1000 * 60 * 60));
                        const m = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
                        const s = Math.floor((distance % (1000 * 60)) / 1000);
                        
                        const timerEl = window.parent.document.getElementById("timer_" + p.id);
                        if (timerEl) {{
                            timerEl.innerHTML = 
                                (h < 10 ? "0" : "") + h + ":" + 
                                (m < 10 ? "0" : "") + m + ":" + 
                                (s < 10 ? "0" : "") + s;
                        }}
                            
                        const cardEl = window.parent.document.getElementById("card_" + p.id);
                        if (cardEl && distance >= tempoCriticoMs) {{
                            if (!cardEl.classList.contains("card-critico")) {{
                                cardEl.classList.remove("card-normal");
                                cardEl.classList.add("card-critico");
                                playBeep();
                            }}
                        }}
                    }}
                }});
            }}, 1000);
        }}
    </script>
    """
    components.html(js_engine, height=0)