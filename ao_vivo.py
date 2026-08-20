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
    m_das = cfg.get('manha_das', '07:30')
    m_as = cfg.get('manha_as', '11:50')
    t_das = cfg.get('tarde_das', '13:30')
    t_as = cfg.get('tarde_as', '17:30')

    agora = obter_hora_atual()
    hoje_str = agora.strftime("%Y-%m-%d")

    # ==========================================
    # BARRA DE PROGRESSO DO TURNO (VISÃO GERAL RESTAURADA)
    # ==========================================
    inicio_turno = datetime.strptime(f"{hoje_str} {m_das}", "%Y-%m-%d %H:%M")
    fim_turno = datetime.strptime(f"{hoje_str} {t_as}", "%Y-%m-%d %H:%M")
    
    total_min_turno = (fim_turno - inicio_turno).total_seconds() / 60
    min_passados = (agora - inicio_turno).total_seconds() / 60
    
    if min_passados < 0: perc_turno = 0
    elif min_passados > total_min_turno: perc_turno = 100
    else: perc_turno = (min_passados / total_min_turno) * 100

    st.markdown(f"""
    <div style="text-align: center; margin-bottom: 25px;">
        <h2 style="color: #2c3e50; font-weight: 900; margin-bottom: 5px; font-size: 36px; text-transform: uppercase;">🔴 Jornada de Trabalho</h2>
        <div style="width: 100%; background-color: #e0e0e0; border-radius: 10px; height: 12px; overflow: hidden; margin: 15px 0 5px 0; box-shadow: inset 0 1px 3px rgba(0,0,0,0.2);">
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
    qtd_rodando = 0
    minutos_ativos_perdidos = 0
    
    # Agrupamento para a timeline no rodapé
    setores_dict = {}

    for maq in todas_maquinas:
        setor = mapa_setores.get(maq, "Sem Setor")
        if setor not in setores_dict:
            setores_dict[setor] = []
        setores_dict[setor].append(maq)
        
        info = status_dict.get(maq)
        if info and info.get('status') == 'Parado':
            cod = info.get('cod_ocorrencia')
            desc = "Desconhecido"
            if cod and not df_codigos.empty:
                filtro = df_codigos[df_codigos['codigo'].astype(str) == str(cod)]
                if not filtro.empty: desc = str(filtro.iloc[0]['descricao'])
            
            info['descricao_completa'] = f"{desc} ({cod})"
            info['setor'] = setor
            maquinas_paradas.append(info)
            
            try:
                h_ini = datetime.strptime(info['hora_inicio'], "%Y-%m-%d %H:%M:%S")
                minutos_ativos_perdidos += (agora - h_ini).total_seconds() / 60
            except: pass
        else:
            qtd_rodando += 1

    qtd_total = len(todas_maquinas)
    qtd_paradas = len(maquinas_paradas)
    perc_rodando = (qtd_rodando / qtd_total) * 100 if qtd_total > 0 else 0
    perc_paradas = (qtd_paradas / qtd_total) * 100 if qtd_total > 0 else 0

    df_hoje = df_nuvem[(df_nuvem['data_registro'] == hoje_str) & (df_nuvem['maquina'].isin(todas_maquinas))].copy()
    minutos_finalizados = 0
    top_ofensor = "Nenhum (0)"
    mttr_str = "0m"
    noticias = []
    
    if not df_hoje.empty:
        for _, row in df_hoje.iterrows():
            m_das_calc = calcular_minutos_str(row['das'])
            m_as_calc = calcular_minutos_str(row['as_hora'])
            minutos_finalizados += (m_as_calc - m_das_calc)
            
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
    # RENDERIZAÇÃO DA HIERARQUIA SUPERIOR
    # ==========================================
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div style='background:#f8f9fa; padding:15px; border-radius:10px; text-align:center; border:1px solid #ddd;'><h4 style='margin:0; color:#555;'>Máquinas do Setor</h4><h2 style='margin:0; font-size:38px; color:#2c3e50;'>{qtd_total}</h2></div>", unsafe_allow_html=True)
    c2.markdown(f"<div style='background:#e8f8f5; padding:15px; border-radius:10px; text-align:center; border:1px solid #c8e6c9;'><h4 style='margin:0; color:#27ae60;'>Produzindo</h4><h2 style='margin:0; font-size:38px; color:#2ecc71;'>{qtd_rodando} <span style='font-size:18px;'>({perc_rodando:.0f}%)</span></h2></div>", unsafe_allow_html=True)
    c3.markdown(f"<div style='background:#fdedec; padding:15px; border-radius:10px; text-align:center; border:1px solid #f5b7b1;'><h4 style='margin:0; color:#c0392b;'>Paradas</h4><h2 style='margin:0; font-size:38px; color:#e74c3c;'>{qtd_paradas} <span style='font-size:18px;'>({perc_paradas:.0f}%)</span></h2></div>", unsafe_allow_html=True)

    m1, m2, m3 = st.columns(3)
    m1.markdown(f"<div style='background:#fff; padding:15px; border-radius:10px; text-align:center; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-top: 10px;'><h5 style='margin:0; color:#7f8c8d; text-transform: uppercase;'>🩸 Tempo Perdido Hoje</h5><h3 style='margin:0; font-size:28px; color:#c0392b;'>{h_perdido:02d}h:{m_perdido:02d}m</h3></div>", unsafe_allow_html=True)
    m2.markdown(f"<div style='background:#fff; padding:15px; border-radius:10px; text-align:center; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-top: 10px;'><h5 style='margin:0; color:#7f8c8d; text-transform: uppercase;'>⏱️ Tempo Médio de Solução</h5><h3 style='margin:0; font-size:28px; color:#2980b9;'>{mttr_str}</h3></div>", unsafe_allow_html=True)
    m3.markdown(f"<div style='background:#fff; padding:15px; border-radius:10px; text-align:center; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-top: 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'><h5 style='margin:0; color:#7f8c8d; text-transform: uppercase;'>🏆 Principal Ofensor</h5><h3 style='margin:0; font-size:20px; color:#e67e22; margin-top: 8px;'>{top_ofensor}</h3></div>", unsafe_allow_html=True)

    st.markdown("<hr style='opacity:0.2; margin: 25px 0;'>", unsafe_allow_html=True)

    # ==========================================
    # PAINEL DE PARADAS ATIVAS (ALERTAS)
    # ==========================================
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
            try: hora_formatada = datetime.strptime(p['hora_inicio'], "%Y-%m-%d %H:%M:%S").strftime("%H:%M")
            except: hora_formatada = "--:--"
                
            p_id = p['maquina'].replace(" ", "_")
            lista_js_paradas.append({"id": p_id, "inicio_iso": hora_iso})
            
            html_cards += f"<div id='card_{p_id}' class='card-ao-vivo card-normal'>"
            html_cards += f"<div class='maq-setor'>{p['setor']}</div>"
            html_cards += f"<div class='maq-nome'><span class='alerta-icone'>⚠️</span>{p['maquina']}</div>"
            html_cards += f"<div class='maq-prob'>{p['descricao_completa']}</div>"
            html_cards += f"<div class='maq-inicio'>Início da parada: {hora_formatada}</div>"
            html_cards += f"<div id='timer_{p_id}' class='maq-timer'>00:00:00</div>"
            html_cards += "</div>"
        html_cards += "</div>"
        
        st.markdown(html_cards, unsafe_allow_html=True)

    json_paradas = json.dumps(lista_js_paradas)

    # ==========================================
    # HISTÓRICO INDIVIDUAL POR MÁQUINA (GRÁFICO DE FITA AGRUPADO)
    # ==========================================
    st.markdown("<hr style='opacity:0.2; margin: 30px 0 20px 0;'>", unsafe_allow_html=True)
    
    m_das_min = calcular_minutos_str(m_das)
    m_as_min = calcular_minutos_str(m_as)
    t_das_min = calcular_minutos_str(t_das)
    t_as_min = calcular_minutos_str(t_as)
    agora_min = agora.hour * 60 + agora.minute

    total_timeline_min = t_as_min - m_das_min
    if total_timeline_min <= 0: total_timeline_min = 600 
    
    pct_as_m = ((m_as_min - m_das_min) / total_timeline_min) * 100
    pct_das_t = ((t_das_min - m_das_min) / total_timeline_min) * 100

    html_timelines = "<div style='max-width: 1200px; margin: 0 auto;'>"
    html_timelines += "<h3 style='text-align: center; color: #2c3e50; text-transform: uppercase; font-weight: 900; margin-bottom: 30px;'>📊 Histórico Individual das Máquinas</h3>"
    
    color_map = {0: "#95a5a6", 1: "#27ae60", 2: "#e74c3c", 3: "#ecf0f1"}

    for setor in sorted(setores_dict.keys()):
        html_timelines += "<div style='margin-bottom: 30px; background: #fff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); border: 1px solid #eaeaea;'>"
        html_timelines += f"<h4 style='color: #7f8c8d; text-transform: uppercase; font-weight: 900; margin-top: 0; margin-bottom: 20px; border-bottom: 2px solid #ecf0f1; padding-bottom: 8px;'>🏭 {setor}</h4>"
        
        html_timelines += "<div style='position: relative; height: 20px; font-size: 13px; color: #7f8c8d; font-weight: bold; margin-bottom: 10px; border-bottom: 1px solid #eee;'>"
        html_timelines += f"<div style='position: absolute; left: 0%; transform: translateX(0%);'>{m_das}</div>"
        html_timelines += f"<div style='position: absolute; left: {pct_as_m}%; transform: translateX(-50%);'>{m_as}</div>"
        html_timelines += f"<div style='position: absolute; left: {pct_das_t}%; transform: translateX(-50%);'>{t_das}</div>"
        html_timelines += f"<div style='position: absolute; left: 100%; transform: translateX(-100%);'>{t_as}</div>"
        html_timelines += "</div>"
        
        for maq in sorted(setores_dict[setor]):
            timeline = [0] * total_timeline_min
            
            for i in range(total_timeline_min):
                curr = m_das_min + i
                if (curr >= m_das_min and curr < m_as_min) or (curr >= t_das_min and curr < t_as_min):
                    if curr <= agora_min: timeline[i] = 1 
                    else: timeline[i] = 3 
                else:
                    timeline[i] = 0 
                    
            maq_stops = df_hoje[df_hoje['maquina'] == maq]
            for _, row in maq_stops.iterrows():
                inicio = calcular_minutos_str(row['das'])
                fim = calcular_minutos_str(row['as_hora'])
                for m in range(inicio, fim):
                    idx = m - m_das_min
                    if 0 <= idx < total_timeline_min:
                        timeline[idx] = 2 
                        
            for p in maquinas_paradas:
                if p['maquina'] == maq:
                    try:
                        h_ini_obj = datetime.strptime(p['hora_inicio'], "%Y-%m-%d %H:%M:%S")
                        if h_ini_obj.date() == agora.date():
                            inicio = h_ini_obj.hour * 60 + h_ini_obj.minute
                            fim = agora_min
                            for m in range(inicio, fim):
                                idx = m - m_das_min
                                if 0 <= idx < total_timeline_min:
                                    timeline[idx] = 2 
                    except: pass

            segments = []
            if total_timeline_min > 0:
                curr_type = timeline[0]
                curr_len = 1
                for i in range(1, total_timeline_min):
                    if timeline[i] == curr_type: curr_len += 1
                    else:
                        segments.append((curr_type, curr_len))
                        curr_type = timeline[i]
                        curr_len = 1
                segments.append((curr_type, curr_len))
                
            html_timelines += "<div style='margin-bottom: 12px; display: flex; flex-direction: column;'>"
            html_timelines += f"<div style='font-size: 14px; font-weight: bold; color: #34495e; margin-bottom: 4px; text-transform: uppercase;'>{maq}</div>"
            html_timelines += "<div style='display: flex; width: 100%; height: 18px; border-radius: 4px; overflow: hidden; box-shadow: inset 0 1px 3px rgba(0,0,0,0.15);'>"
            
            for stype, slen in segments:
                pct = (slen / total_timeline_min) * 100
                color = color_map.get(stype, "#000")
                html_timelines += f"<div style='width: {pct}%; background-color: {color};'></div>"
            
            html_timelines += "</div></div>"
            
        html_timelines += "</div>"
        
    html_timelines += "<div style='display: flex; justify-content: center; flex-wrap: wrap; gap: 20px; margin-top: 10px; font-size: 13px; font-weight: bold; color: #555;'>"
    html_timelines += "<div style='display: flex; align-items: center; gap: 6px;'><div style='width:14px; height:14px; background:#27ae60; border-radius:3px;'></div> Trabalhando</div>"
    html_timelines += "<div style='display: flex; align-items: center; gap: 6px;'><div style='width:14px; height:14px; background:#e74c3c; border-radius:3px;'></div> Parada</div>"
    html_timelines += "<div style='display: flex; align-items: center; gap: 6px;'><div style='width:14px; height:14px; background:#95a5a6; border-radius:3px;'></div> Intervalo / Almoço</div>"
    html_timelines += "<div style='display: flex; align-items: center; gap: 6px;'><div style='width:14px; height:14px; background:#ecf0f1; border-radius:3px; border: 1px solid #ccc;'></div> A Realizar</div>"
    html_timelines += "</div></div>"

    st.markdown(html_timelines, unsafe_allow_html=True)

    # ==========================================
    # LETREIRO DE NOTÍCIAS (RODAPÉ)
    # ==========================================
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
            }} catch(e) {{ console.log("Áudio bloqueado."); }}
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