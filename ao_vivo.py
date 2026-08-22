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
    
    lm_das = cfg.get('lanche_m_das', '')
    lm_as = cfg.get('lanche_m_as', '')
    lt_das = cfg.get('lanche_t_das', '')
    lt_as = cfg.get('lanche_t_as', '')
    
    m_das_min = calcular_minutos_str(m_das)
    m_as_min = calcular_minutos_str(m_as)
    t_das_min = calcular_minutos_str(t_das)
    t_as_min = calcular_minutos_str(t_as)
    
    lm_das_min = calcular_minutos_str(lm_das) if lm_das else -1
    lm_as_min = calcular_minutos_str(lm_as) if lm_as else -1
    lt_das_min = calcular_minutos_str(lt_das) if lt_das else -1
    lt_as_min = calcular_minutos_str(lt_as) if lt_as else -1

    agora = obter_hora_atual()
    hoje_str = agora.strftime("%Y-%m-%d")
    agora_min = agora.hour * 60 + agora.minute

    codigos_pausa = []
    if not df_codigos.empty and 'tipo' in df_codigos.columns:
        mask_pausa = df_codigos['tipo'].astype(str).str.strip().str.upper().isin(['NÃO CONTA', 'DESNCONSIDERAR', 'DESCONSIDERAR'])
        codigos_pausa = df_codigos[mask_pausa]['codigo'].astype(str).str.strip().tolist()

    total_min_turno = max(0, m_as_min - m_das_min) + max(0, t_as_min - t_das_min)
    if total_min_turno <= 0: total_min_turno = 1
    
    min_passados = 0
    for m in range(m_das_min, agora_min):
        if (m >= m_das_min and m < m_as_min) or (m >= t_das_min and m < t_as_min):
            min_passados += 1
            
    perc_turno = (min_passados / total_min_turno) * 100
    if perc_turno > 100: perc_turno = 100

    st.markdown(f"""
    <div style="text-align: center; margin-bottom: 25px;">
        <h2 style="color: #2c3e50; font-weight: 900; margin-bottom: 5px; font-size: 36px; text-transform: uppercase;">🔴 Jornada de Trabalho</h2>
        <div style="width: 100%; background-color: #e0e0e0; border-radius: 10px; height: 12px; overflow: hidden; margin: 15px 0 5px 0; box-shadow: inset 0 1px 3px rgba(0,0,0,0.2);">
            <div style="width: {perc_turno:.1f}%; background-color: #2980b9; height: 100%; transition: width 1s;"></div>
        </div>
        <div style="font-size: 13px; color: #7f8c8d; font-weight: bold; text-align: right;">PROGRESSO DA JORNADA: {perc_turno:.1f}%</div>
    </div>
    """, unsafe_allow_html=True)

    # O botão de atualização agora é visível, mas será transformado em flutuante pelo JS no final do arquivo
    if st.button("🔄 Atualizar", key="btn_refresh_aovivo"): pass

    supa = banco.conectar()
    df_est = banco.obter_estrutura()
    df_produtos = banco.obter_produtos_matriz() 
    
    if df_est.empty:
        st.info("⚠️ Nenhuma estrutura de fábrica cadastrada. Vá em Configurações > Estrutura.")
        return

    if filtros_selecionados['setor'] != "[ Todos ]":
        todas_maquinas = sorted(df_est[df_est['setor'] == filtros_selecionados['setor']]['maquina'].dropna().unique().tolist())
    else:
        todas_maquinas = sorted(df_est['maquina'].dropna().unique().tolist())

    if not todas_maquinas:
        st.info("Nenhuma máquina encontrada neste setor.")
        return

    mapa_setores = df_est[['maquina', 'setor']].dropna().drop_duplicates().set_index('maquina')['setor'].to_dict()

    resp_status = supa.table("status_maquinas").select("*").in_("maquina", todas_maquinas).execute()
    status_dict = {d['maquina']: d for d in resp_status.data} if resp_status.data else {}

    maquinas_paradas_criticas = []
    maquinas_pausas = []
    maquinas_produzindo = []
    
    qtd_rodando = 0
    qtd_livres = 0
    minutos_ativos_perdidos = 0
    setores_dict = {}

    for maq in todas_maquinas:
        setor = mapa_setores.get(maq, "Sem Setor")
        if setor not in setores_dict: setores_dict[setor] = []
        setores_dict[setor].append(maq)
        
        info = status_dict.get(maq, {})
        status_maq = info.get('status', 'Livre')
        
        if status_maq == 'Parado':
            cod = info.get('cod_ocorrencia')
            desc = "Desconhecido"
            if cod and not df_codigos.empty:
                filtro = df_codigos[df_codigos['codigo'].astype(str) == str(cod)]
                if not filtro.empty: desc = str(filtro.iloc[0]['descricao'])
            
            info['descricao_completa'] = f"{desc} ({cod})"
            info['setor'] = setor
            info['is_pausa'] = str(cod).strip() in codigos_pausa
            
            if info['is_pausa']:
                maquinas_pausas.append(info)
            else:
                maquinas_paradas_criticas.append(info)
                try:
                    h_ini = datetime.strptime(info['hora_inicio'], "%Y-%m-%d %H:%M:%S")
                    if h_ini.date() == agora.date():
                        inicio_m = h_ini.hour * 60 + h_ini.minute
                        fim_m = agora_min + 1
                        for m in range(inicio_m, fim_m):
                            if (m >= m_das_min and m < m_as_min) or (m >= t_das_min and m < t_as_min):
                                minutos_ativos_perdidos += 1
                except: pass
                
        elif status_maq == 'Produzindo':
            qtd_rodando += 1
            info['setor'] = setor
            
            cod_peca = info.get('cod_peca_atual')
            nome_peca_completo = "Peça Desconhecida"
            if cod_peca and not df_produtos.empty:
                f_peca = df_produtos[df_produtos['cod'].astype(str) == str(cod_peca)]
                if not f_peca.empty:
                    prod_form = f_peca.iloc[0]['produto_formula']
                    desc_peca = f_peca.iloc[0]['descricao']
                    nome_peca_completo = f"{prod_form} ➔ {desc_peca} (Cód: {cod_peca})"
                    
            info['descricao_completa'] = nome_peca_completo
            maquinas_produzindo.append(info)
        else:
            qtd_livres += 1

    cards_exibicao = maquinas_paradas_criticas + maquinas_pausas + maquinas_produzindo

    qtd_total = len(todas_maquinas)
    qtd_paradas = len(maquinas_paradas_criticas) + len(maquinas_pausas)
    perc_rodando = (qtd_rodando / qtd_total) * 100 if qtd_total > 0 else 0
    perc_paradas = (qtd_paradas / qtd_total) * 100 if qtd_total > 0 else 0

    df_hoje = pd.DataFrame()
    if not df_nuvem.empty and 'maquina' in df_nuvem.columns:
        if 'tipo' not in df_nuvem.columns: df_nuvem['tipo'] = 'PARADA'
        df_hoje = df_nuvem[(df_nuvem['data_registro'] == hoje_str) & (df_nuvem['maquina'].isin(todas_maquinas))].copy()
    
    minutos_finalizados = 0
    top_ofensor = "Nenhum (0)"
    mttr_str = "0m"
    noticias = []
    
    df_paradas_hoje = pd.DataFrame()
    if not df_hoje.empty:
        df_paradas_hoje = df_hoje[df_hoje['tipo'].astype(str).str.strip().str.upper() == 'PARADA']
        
    if not df_paradas_hoje.empty:
        for _, row in df_paradas_hoje.iterrows():
            c_oco = str(row['cod_ocorrencia']).strip()
            if c_oco not in codigos_pausa:
                m_das_calc = calcular_minutos_str(row['das'])
                m_as_calc = calcular_minutos_str(row['as_hora'])
                for m in range(m_das_calc, m_as_calc):
                    if (m >= m_das_min and m < m_as_min) or (m >= t_das_min and m < t_as_min):
                        minutos_finalizados += 1
            
        df_problemas = df_paradas_hoje[~df_paradas_hoje['cod_ocorrencia'].astype(str).str.strip().isin(codigos_pausa)]
        if not df_problemas.empty:
            mttr = minutos_finalizados / len(df_problemas)
            mttr_str = f"{int(mttr)}m"
            
            vilao_cod = df_problemas['cod_ocorrencia'].value_counts().idxmax()
            qtd_vilao = df_problemas['cod_ocorrencia'].value_counts().max()
            desc_vilao = "Problema"
            if not df_codigos.empty:
                filtro = df_codigos[df_codigos['codigo'].astype(str) == str(vilao_cod)]
                if not filtro.empty: desc_vilao = str(filtro.iloc[0]['descricao'])
            top_ofensor = f"{desc_vilao} ({qtd_vilao}x)"
        
        df_noticias = df_paradas_hoje.sort_values(by='as_hora', ascending=False).head(5)
        for _, rr in df_noticias.iterrows():
            noticias.append(f"🟢 {rr['maquina']} solucionou problema às {rr['as_hora']}")

    total_perdido_hoje = minutos_finalizados + minutos_ativos_perdidos
    h_perdido = int(total_perdido_hoje // 60)
    m_perdido = int(total_perdido_hoje % 60)
    
    for p in maquinas_paradas_criticas: noticias.append(f"🔴 {p['maquina']} parada: {p['descricao_completa']}")
    for p in maquinas_pausas: noticias.append(f"☕ {p['maquina']} em intervalo: {p['descricao_completa']}")
    for p in maquinas_produzindo: noticias.append(f"🟢 {p['maquina']} produzindo: {str(p.get('cod_peca_atual',''))}")
        
    texto_letreiro = " &nbsp;&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;&nbsp; ".join(noticias) if noticias else "🟢 FÁBRICA OPERANDO COM 100% DE CAPACIDADE NESTE MOMENTO"

    # ==========================================
    # NOVO LAYOUT GIGANTE (HERO CARD PARA TV)
    # ==========================================
    html_hero = f"""
    <div style="background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%); color: white; border-radius: 15px; padding: 40px 20px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.2); margin-bottom: 25px;">
        <div style="font-size: 22px; text-transform: uppercase; letter-spacing: 3px; color: #bdc3c7; font-weight: 700; margin-bottom: 15px;">Status da Produção</div>
        <div style="font-size: 100px; font-weight: 900; line-height: 1; margin-bottom: 10px; text-shadow: 3px 3px 6px rgba(0,0,0,0.4); color: #2ecc71;">
            {perc_rodando:.0f}% <span style="font-size: 45px; color: #ffffff;">EM OPERAÇÃO</span>
        </div>
        <div style="font-size: 26px; font-weight: 600; color: #ecf0f1; margin-bottom: 35px;">
            {qtd_rodando} de {qtd_total} máquinas ativas neste momento
        </div>
        <div style="display: flex; justify-content: center; gap: 30px; background: rgba(0,0,0,0.3); padding: 20px; border-radius: 12px; font-size: 20px; font-weight: bold; flex-wrap: wrap;">
            <div style="display: flex; align-items: center; gap: 8px;"><span style="font-size: 24px;">🟢</span> <span style="color: #2ecc71; font-size: 28px;">{qtd_rodando}</span> Produzindo</div>
            <div style="display: flex; align-items: center; gap: 8px;"><span style="font-size: 24px;">🔴</span> <span style="color: #e74c3c; font-size: 28px;">{len(maquinas_paradas_criticas)}</span> Paradas</div>
            <div style="display: flex; align-items: center; gap: 8px;"><span style="font-size: 24px;">🟠</span> <span style="color: #f39c12; font-size: 28px;">{len(maquinas_pausas)}</span> Pausas</div>
            <div style="display: flex; align-items: center; gap: 8px;"><span style="font-size: 24px;">🔵</span> <span style="color: #3498db; font-size: 28px;">{qtd_livres}</span> Aguardando</div>
        </div>
    </div>
    """
    st.markdown(html_hero, unsafe_allow_html=True)

    # ==========================================
    # CARDS SECUNDÁRIOS OTIMIZADOS E AMPLIADOS
    # ==========================================
    m1, m2, m3 = st.columns(3)
    
    m1.markdown(f"""
    <div style='background:#fff; padding:25px 15px; border-radius:12px; text-align:center; border: 1px solid #e0e0e0; box-shadow: 0 6px 12px rgba(0,0,0,0.05); margin-bottom: 25px; display: flex; flex-direction: column; justify-content: center; height: 160px;'>
        <div style='color:#7f8c8d; text-transform: uppercase; font-size: 18px; font-weight: 700; letter-spacing: 1px; margin-bottom: 10px;'>🩸 Tempo Útil Perdido Hoje</div>
        <div style='font-size:50px; font-weight:900; color:#c0392b; line-height:1;'>{h_perdido:02d}h:{m_perdido:02d}m</div>
    </div>
    """, unsafe_allow_html=True)
    
    m2.markdown(f"""
    <div style='background:#fff; padding:25px 15px; border-radius:12px; text-align:center; border: 1px solid #e0e0e0; box-shadow: 0 6px 12px rgba(0,0,0,0.05); margin-bottom: 25px; display: flex; flex-direction: column; justify-content: center; height: 160px;'>
        <div style='color:#7f8c8d; text-transform: uppercase; font-size: 18px; font-weight: 700; letter-spacing: 1px; margin-bottom: 10px;'>⏱️ Tempo Médio de Solução</div>
        <div style='font-size:50px; font-weight:900; color:#2980b9; line-height:1;'>{mttr_str}</div>
    </div>
    """, unsafe_allow_html=True)
    
    m3.markdown(f"""
    <div style='background:#fff; padding:25px 15px; border-radius:12px; text-align:center; border: 1px solid #e0e0e0; box-shadow: 0 6px 12px rgba(0,0,0,0.05); margin-bottom: 25px; display: flex; flex-direction: column; justify-content: center; height: 160px;'>
        <div style='color:#7f8c8d; text-transform: uppercase; font-size: 18px; font-weight: 700; letter-spacing: 1px; margin-bottom: 10px;'>🏆 Principal Ofensor</div>
        <div style='font-size:32px; font-weight:900; color:#e67e22; line-height:1.1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{top_ofensor}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)

    # ==========================================
    # PAINEL DE PARADAS E PRODUÇÃO ATIVAS
    # ==========================================
    lista_js_timers = []
    
    if not cards_exibicao:
        pass 
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
            .card-pausa { background-color: #f39c12; }
            .card-producao { background-color: #27ae60; }
            .card-critico { background-color: #8b0000; animation: pulse-critico 1s infinite alternate; }
            
            @keyframes pulse-critico {
                0% { box-shadow: 0 0 0 0 rgba(139, 0, 0, 0.7); transform: scale(1); }
                100% { box-shadow: 0 0 0 20px rgba(139, 0, 0, 0); transform: scale(1.02); }
            }
            .maq-setor { font-size: 16px; text-transform: uppercase; letter-spacing: 2px; opacity: 0.9; margin-bottom: 8px; font-weight: bold; color: #ffffff; }
            .maq-nome { font-size: 34px; font-weight: 900; margin: 0 0 10px 0; text-transform: uppercase; }
            .maq-prob { font-size: 18px; margin: 0 0 15px 0; opacity: 0.95; min-height: 45px; }
            .maq-inicio { font-size: 15px; font-weight: bold; opacity: 0.85; margin-bottom: 5px; }
            .maq-timer { font-size: 60px; font-family: monospace; font-weight: bold; letter-spacing: 2px; background: rgba(0,0,0,0.2); border-radius: 10px; padding: 10px; }
            .alerta-icone { font-size: 30px; vertical-align: middle; margin-right: 10px; display: none; }
            .card-critico .alerta-icone, .card-pausa .alerta-icone, .card-producao .alerta-icone { display: inline-block; }
        </style>
        """, unsafe_allow_html=True)

        html_cards = "<div class='grid-ao-vivo'>"
        for p in cards_exibicao:
            hora_iso = str(p['hora_inicio']).replace(" ", "T")
            try: hora_formatada = datetime.strptime(p['hora_inicio'], "%Y-%m-%d %H:%M:%S").strftime("%H:%M")
            except: hora_formatada = "--:--"
                
            p_id = p['maquina'].replace(" ", "_")
            lista_js_timers.append({"id": p_id, "inicio_iso": hora_iso})
            
            status_maq = p.get('status', 'Livre')
            
            if status_maq == 'Produzindo':
                classe_card = "card-producao"
                icone = "🟢"
                texto_inicio = "Início da produção"
            else:
                is_pausa = p.get('is_pausa', False)
                classe_card = "card-pausa" if is_pausa else "card-normal"
                icone = "☕" if is_pausa else "⚠️"
                texto_inicio = "Início do intervalo" if is_pausa else "Início da parada"
            
            html_cards += f"<div id='card_{p_id}' class='card-ao-vivo {classe_card}'>"
            html_cards += f"<div class='maq-setor'>{p['setor']}</div>"
            html_cards += f"<div class='maq-nome'><span class='alerta-icone'>{icone}</span>{p['maquina']}</div>"
            html_cards += f"<div class='maq-prob'>{p['descricao_completa']}</div>"
            html_cards += f"<div class='maq-inicio'>{texto_inicio}: {hora_formatada}</div>"
            html_cards += f"<div id='timer_{p_id}' class='maq-timer'>00:00:00</div>"
            html_cards += "</div>"
        html_cards += "</div>"
        
        st.markdown(html_cards, unsafe_allow_html=True)

    json_timers = json.dumps(lista_js_timers)

    # ==========================================
    # HISTÓRICO INDIVIDUAL (OCULTA OCIOSAS NO DIA)
    # ==========================================
    st.markdown("<hr style='opacity:0.2; margin: 30px 0 20px 0;'>", unsafe_allow_html=True)

    total_timeline_min = t_as_min - m_das_min
    if total_timeline_min <= 0: total_timeline_min = 600 
    
    pct_as_m = ((m_as_min - m_das_min) / total_timeline_min) * 100
    pct_das_t = ((t_das_min - m_das_min) / total_timeline_min) * 100

    maquinas_ativas_hoje = set()
    if not df_hoje.empty:
        maquinas_ativas_hoje.update(df_hoje['maquina'].dropna().unique().tolist())
        
    for maq, info_maq in status_dict.items():
        if info_maq.get('status') in ['Produzindo', 'Parado']:
            try:
                h_ini_obj = datetime.strptime(info_maq['hora_inicio'], "%Y-%m-%d %H:%M:%S")
                if h_ini_obj.date() == agora.date():
                    maquinas_ativas_hoje.add(maq)
            except:
                maquinas_ativas_hoje.add(maq)

    setores_dict_timeline = {}
    for setor, maquinas_do_setor in setores_dict.items():
        maquinas_filtradas = [m for m in maquinas_do_setor if m in maquinas_ativas_hoje]
        if maquinas_filtradas:
            setores_dict_timeline[setor] = sorted(maquinas_filtradas)

    if not setores_dict_timeline:
        st.markdown("<div style='background:#f8f9fa; padding:30px; border-radius:10px; text-align:center; border:1px dashed #ccc;'><h4 style='color:#7f8c8d; margin:0;'>Nenhum apontamento registrado no dia de hoje até o momento.</h4></div>", unsafe_allow_html=True)
    else:
        html_timelines = "<div style='max-width: 1200px; margin: 0 auto;'>"
        st.markdown("<h3 style='text-align: center; color: #2c3e50; text-transform: uppercase; font-weight: 900; margin-bottom: 30px;'>📊 Histórico Individual das Máquinas</h3>", unsafe_allow_html=True)
        
        color_map = {0: "#ecf0f1", 1: "#27ae60", 2: "#e74c3c", 3: "#3498db", 4: "#f39c12", 5: "#bdc3c7"}

        for setor in sorted(setores_dict_timeline.keys()):
            html_timelines += "<div style='margin-bottom: 30px; background: #fff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); border: 1px solid #eaeaea;'>"
            html_timelines += f"<h4 style='color: #7f8c8d; text-transform: uppercase; font-weight: 900; margin-top: 0; margin-bottom: 20px; border-bottom: 2px solid #ecf0f1; padding-bottom: 8px;'>🏭 {setor}</h4>"
            
            html_timelines += "<div style='position: relative; height: 25px; font-size: 13px; color: #7f8c8d; font-weight: bold; margin-bottom: 8px; border-bottom: 1px solid #eee;'>"
            html_timelines += f"<div style='position: absolute; left: 0%; transform: translateX(0%); top: 0px;'>{m_das}</div>"
            
            for m in range(total_timeline_min):
                curr = m_das_min + m
                pct = (m / total_timeline_min) * 100
                dist_inicio_m = abs(curr - m_das_min)
                dist_fim_m = abs(curr - m_as_min)
                dist_inicio_t = abs(curr - t_das_min)
                dist_fim_t = abs(curr - t_as_min)
                if dist_inicio_m < 15 or dist_fim_m < 15 or dist_inicio_t < 15 or dist_fim_t < 15: continue
                    
                if curr % 60 == 0:
                    h = curr // 60
                    html_timelines += f"<div style='position: absolute; left: {pct}%; transform: translateX(-50%); font-size: 11px; font-weight: 500; color: #95a5a6; top: 2px;'>{h}</div>"
                elif curr % 60 == 30:
                    html_timelines += f"<div style='position: absolute; left: {pct}%; top: 6px; width: 1px; height: 6px; background-color: #bdc3c7;'></div>"
            
            html_timelines += f"<div style='position: absolute; left: {pct_as_m}%; transform: translateX(-50%); top: 0px;'>{m_as}</div>"
            html_timelines += f"<div style='position: absolute; left: {pct_das_t}%; transform: translateX(-50%); top: 0px;'>{t_das}</div>"
            html_timelines += f"<div style='position: absolute; left: 100%; transform: translateX(-100%); top: 0px;'>{t_as}</div>"
            html_timelines += "</div>"
            
            for maq in setores_dict_timeline[setor]:
                timeline = [0] * total_timeline_min
                
                # 1. Base Padrão: Azul, Cinza ou Branco(Futuro)
                for i in range(total_timeline_min):
                    curr = m_das_min + i
                    if curr >= m_as_min and curr < t_das_min: timeline[i] = 5
                    elif lm_das_min != -1 and curr >= lm_das_min and curr < lm_as_min: timeline[i] = 5
                    elif lt_das_min != -1 and curr >= lt_das_min and curr < lt_as_min: timeline[i] = 5
                    elif curr > agora_min: timeline[i] = 0 
                    elif (curr >= m_das_min and curr < m_as_min) or (curr >= t_das_min and curr < t_as_min): timeline[i] = 3
                        
                # 2. Registros Reais
                if not df_hoje.empty:
                    maq_records = df_hoje[df_hoje['maquina'] == maq]
                    for _, row in maq_records.iterrows():
                        if pd.notna(row.get('das')) and pd.notna(row.get('as_hora')):
                            inicio = calcular_minutos_str(row['das'])
                            fim = calcular_minutos_str(row['as_hora'])
                            tipo_reg = str(row.get('tipo')).strip().upper()
                            
                            if tipo_reg == 'PRODUÇÃO': cor_linha = 1
                            elif tipo_reg == 'NÃO CONTA' or 'DESCONSIDERAR' in tipo_reg: cor_linha = 4
                            else: cor_linha = 2 
                            
                            for m in range(inicio, fim):
                                idx = m - m_das_min
                                if 0 <= idx < total_timeline_min: timeline[idx] = cor_linha
                                
                # 3. Estado Atual da Máquina 
                info_maq = status_dict.get(maq, {})
                status_atual = info_maq.get('status', 'Livre')
                
                if status_atual in ['Produzindo', 'Parado']:
                    try:
                        h_ini_obj = datetime.strptime(info_maq['hora_inicio'], "%Y-%m-%d %H:%M:%S")
                        if h_ini_obj.date() == agora.date():
                            inicio = h_ini_obj.hour * 60 + h_ini_obj.minute
                            fim = agora_min + 1 
                            
                            if status_atual == 'Produzindo': cor_linha = 1
                            else:
                                c_oco = str(info_maq.get('cod_ocorrencia')).strip()
                                cor_linha = 4 if c_oco in codigos_pausa else 2
                                
                            for m in range(inicio, fim):
                                idx = m - m_das_min
                                if 0 <= idx < total_timeline_min: timeline[idx] = cor_linha
                    except: pass

                segments = []
                if total_timeline_min > 0:
                    curr_type, curr_len = timeline[0], 1
                    for i in range(1, total_timeline_min):
                        if timeline[i] == curr_type: curr_len += 1
                        else:
                            segments.append((curr_type, curr_len))
                            curr_type, curr_len = timeline[i], 1
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
        
        html_timelines += "</div>" 
        
        html_timelines += "<div style='display: flex; justify-content: center; flex-wrap: wrap; gap: 20px; margin-top: 10px; font-size: 13px; font-weight: bold; color: #555;'>"
        html_timelines += "<div style='display: flex; align-items: center; gap: 6px;'><div style='width:14px; height:14px; background:#3498db; border-radius:3px;'></div> Disponível (Livre)</div>"
        html_timelines += "<div style='display: flex; align-items: center; gap: 6px;'><div style='width:14px; height:14px; background:#27ae60; border-radius:3px;'></div> Produzindo</div>"
        html_timelines += "<div style='display: flex; align-items: center; gap: 6px;'><div style='width:14px; height:14px; background:#e74c3c; border-radius:3px;'></div> Indisponível (Parada)</div>"
        html_timelines += "<div style='display: flex; align-items: center; gap: 6px;'><div style='width:14px; height:14px; background:#f39c12; border-radius:3px;'></div> Pausa Registrada</div>"
        html_timelines += "<div style='display: flex; align-items: center; gap: 6px;'><div style='width:14px; height:14px; background:#bdc3c7; border-radius:3px;'></div> Intervalo Previsto</div>"
        html_timelines += "<div style='display: flex; align-items: center; gap: 6px;'><div style='width:14px; height:14px; background:#ecf0f1; border-radius:3px; border: 1px solid #ccc;'></div> A Realizar (Futuro)</div>"
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

    # ==========================================
    # LÓGICA DO BOTÃO FLUTUANTE (INVISÍVEL NA TELA PRINCIPAL)
    # ==========================================
    js_engine = f"""
    <script>
        // Transforma o botão Atualizar em um ícone flutuante discreto no canto inferior direito
        const allBtns = window.parent.document.querySelectorAll('button');
        allBtns.forEach(b => {{
            if(b.innerText.includes('Atualizar')) {{
                let container = b.closest('div[data-testid="stElementContainer"]');
                if(container) {{
                    container.style.position = 'fixed';
                    container.style.bottom = '20px';
                    container.style.right = '20px';
                    container.style.zIndex = '9999';
                    container.style.width = 'auto';
                    
                    b.style.borderRadius = '30px';
                    b.style.padding = '8px 15px';
                    b.style.boxShadow = '0 4px 10px rgba(0,0,0,0.2)';
                    b.style.backgroundColor = '#ffffff';
                    b.style.color = '#7f8c8d';
                    b.style.border = '1px solid #bdc3c7';
                    b.style.opacity = '0.3';
                    b.style.transition = 'all 0.3s ease';
                    
                    b.onmouseenter = () => {{ b.style.opacity = '1'; b.style.transform = 'scale(1.05)'; }};
                    b.onmouseleave = () => {{ b.style.opacity = '0.3'; b.style.transform = 'scale(1)'; }};
                }}
            }}
        }});

        setTimeout(function() {{
            const btns = window.parent.document.querySelectorAll('button');
            for (let i = 0; i < btns.length; i++) {{
                if (btns[i].innerText.includes('Atualizar')) {{ btns[i].click(); break; }}
            }}
        }}, {refresh_segundos * 1000});

        function playBeep() {{
            try {{
                const AudioContext = window.AudioContext || window.webkitAudioContext;
                if (!AudioContext) return;
                const ctx = new AudioContext(); const osc = ctx.createOscillator(); const gain = ctx.createGain();
                osc.connect(gain); gain.connect(ctx.destination);
                osc.type = 'sine'; osc.frequency.value = 750; 
                gain.gain.setValueAtTime(0, ctx.currentTime); gain.gain.linearRampToValueAtTime(0.3, ctx.currentTime + 0.1); gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.6);
                osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.6);
            }} catch(e) {{ console.log("Áudio bloqueado."); }}
        }}

        const timers = {json_timers};
        const tempoCriticoMs = {tempo_critico} * 60 * 1000;
        
        if (timers.length > 0) {{
            setInterval(() => {{
                const now = new Date().getTime();
                timers.forEach(p => {{
                    const startTime = new Date(p.inicio_iso).getTime();
                    const distance = now - startTime;
                    
                    if (distance > 0) {{
                        const h = Math.floor(distance / (1000 * 60 * 60)); const m = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60)); const s = Math.floor((distance % (1000 * 60)) / 1000);
                        
                        const timerEl = window.parent.document.getElementById("timer_" + p.id);
                        if (timerEl) {{
                            timerEl.innerHTML = (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
                        }}
                            
                        const cardEl = window.parent.document.getElementById("card_" + p.id);
                        if (cardEl && distance >= tempoCriticoMs) {{
                            if (!cardEl.classList.contains("card-critico") && !cardEl.classList.contains("card-pausa") && !cardEl.classList.contains("card-producao")) {{
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