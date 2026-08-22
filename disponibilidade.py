import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import banco
import filtros
import streamlit.components.v1 as components 

def calcular_minutos_str(hora_str):
    try: return int(hora_str.split(':')[0]) * 60 + int(hora_str.split(':')[1])
    except: return 0

def criar_cartao(titulo, valor_principal, valor_secundario="", cor_secundaria="#666666", cor_titulo="#777777"):
    val_sec = valor_secundario if valor_secundario else "&nbsp;"
    html = f"""
    <div class="cartao-kpi-disp kpis-container" style="background-color: #ffffff; padding: 20px 10px; border-radius: 8px; border: 1px solid #eaeaea; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05); display: flex; flex-direction: column; justify-content: center; height: 100%;">
        <p style="margin: 0 0 5px 0; color: {cor_titulo}; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; font-weight: 700; line-height: 1.2;">{titulo}</p>
        <h2 style="margin: 0; color: #222222; font-size: 38px; font-weight: 800; line-height: 1.2;">{valor_principal}</h2>
        <p style="margin: 5px 0 0 0; color: {cor_secundaria}; font-size: 16px; font-weight: bold; line-height: 1.2;">{val_sec}</p>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def renderizar(df_nuvem, df_codigos, filtros_selecionados, jornada_max_minutos, meta_disp):
    filtros.renderizar_cabecalho_global("Disponibilidade")

    df_filt = filtros.aplicar_filtros_analiticos(df_nuvem, df_codigos, filtros_selecionados)

    if df_filt.empty:
        st.warning("⚠️ Nenhum apontamento registrado para esta combinação de filtros.")
        return

    lista_alfabetica_maq = sorted(df_filt['maquina'].unique())
    paleta_cores = px.colors.qualitative.Plotly * 10
    mapa_cores_mestre = {maq: paleta_cores[i] for i, maq in enumerate(lista_alfabetica_maq)}

    dias_reais = df_filt['data_registro'].nunique()
    if dias_reais == 0: dias_reais = 1
    jornada_total_periodo = jornada_max_minutos * dias_reais

    # ==========================================================
    # CÁLCULO VISÃO GLOBAL (TEEP)
    # A base é sempre o Turno Total de Relógio.
    # ==========================================================
    df_parado = df_filt[df_filt['tipo'] == 'PARADA'].groupby('maquina')['minutos'].sum().reset_index()
    df_parado.rename(columns={'minutos': 'Parado'}, inplace=True)
    
    df_nao_conta = df_filt[(df_filt['tipo'] == 'NÃO CONTA') | (df_filt['tipo'] == 'DESCONSIDERAR')].groupby('maquina')['minutos'].sum().reset_index()
    df_nao_conta.rename(columns={'minutos': 'Nao_Conta'}, inplace=True)

    todas_maquinas = pd.DataFrame({'maquina': df_filt['maquina'].unique()})
    df_maq = pd.merge(todas_maquinas, df_parado, on='maquina', how='left').fillna(0)
    df_maq = pd.merge(df_maq, df_nao_conta, on='maquina', how='left').fillna(0)

    # 1. BASE DE CÁLCULO (Jornada Total Pura)
    df_maq['Total'] = jornada_total_periodo
    
    # 2. TEMPO DISPONÍVEL = Total - Paradas por Problema - Pausas (Lanche/Almoço)
    df_maq['Disponivel_min'] = df_maq['Total'] - df_maq['Parado'] - df_maq['Nao_Conta']
    df_maq.loc[df_maq['Disponivel_min'] < 0, 'Disponivel_min'] = 0 

    # 3. RESULTADOS PERCENTUAIS (Tudo sobre o Total da Jornada)
    df_maq['Disponibilidade'] = (df_maq['Disponivel_min'] / df_maq['Total']) * 100
    df_maq['Perc_Parado'] = (df_maq['Parado'] / df_maq['Total']) * 100
    df_maq['Perc_Pausa'] = (df_maq['Nao_Conta'] / df_maq['Total']) * 100
    
    df_maq = df_maq.sort_values('Disponibilidade', ascending=False)
    ordem_maquinas_pior_melhor = df_maq.sort_values('Disponibilidade', ascending=True)['maquina'].tolist()

    tot_trab_base = df_maq['Disponivel_min'].sum()
    tot_total_base = df_maq['Total'].sum()
    tot_par_base = df_maq['Parado'].sum()
    
    media_setor = (tot_trab_base / tot_total_base) * 100 if tot_total_base > 0 else 0
    
    melhor_maq = df_maq.iloc[0]['maquina'] if not df_maq.empty else "-"
    melhor_val = df_maq.iloc[0]['Disponibilidade'] if not df_maq.empty else 0
    pior_maq = df_maq.iloc[-1]['maquina'] if not df_maq.empty else "-"
    pior_val = df_maq.iloc[-1]['Disponibilidade'] if not df_maq.empty else 0

    cor_melhor_maq = mapa_cores_mestre.get(melhor_maq, "#555")
    cor_pior_maq = mapa_cores_mestre.get(pior_maq, "#555")
    texto_dias_rodape = f"No Período de {dias_reais} Dia{'s' if dias_reais > 1 else ''}"

    k1, k2, k3, k4 = st.columns(4)
    with k1: criar_cartao("Média do Setor", f"{media_setor:.1f}%", "Geral", "#555", "#777777")
    with k2: criar_cartao("Maior Disponibilidade", f"{melhor_val:.1f}%", f"🏆 {melhor_maq}", cor_melhor_maq, "#2ecc71")
    with k3: criar_cartao("Menor Disponibilidade", f"{pior_val:.1f}%", f"⚠️ {pior_maq}", cor_pior_maq, "#e74c3c")
    with k4: criar_cartao("Total Horas Perdidas", banco.minutos_para_string(tot_par_base), texto_dias_rodape, "#555", "#777777")

    js_equalizer = """
    <script>
        setInterval(() => {
            const cards = window.parent.document.querySelectorAll('.cartao-kpi-disp');
            if(cards.length > 0) {
                let maxH = 0; cards.forEach(c => c.style.minHeight = 'auto');
                cards.forEach(c => { if(c.offsetHeight > maxH) maxH = c.offsetHeight; });
                cards.forEach(c => { c.style.minHeight = maxH + 'px'; });
            }
        }, 500);
    </script>
    """
    components.html(js_equalizer, height=0)

    st.markdown("<br>", unsafe_allow_html=True)

    g1, g2 = st.columns(2)
    with g1:
        st.markdown("<div class='graficos-container'></div>", unsafe_allow_html=True)
        texto_dias = f"{dias_reais} Dia{'s' if dias_reais > 1 else ''}"
        st.markdown(f"#### Ranking de Disponibilidade por Máquina — {texto_dias}")
        
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=df_maq['Disponibilidade'], y=df_maq['maquina'], orientation='h',
            marker_color=[mapa_cores_mestre[m] for m in df_maq['maquina']],
            text=df_maq['Disponibilidade'].apply(lambda x: f"<b>{x:.1f}%</b>"),
            textposition='outside', textfont=dict(size=18, color='black'), cliponaxis=False, hoverinfo='none'
        ))
        
        for i, row in df_maq.iterrows():
            perc_trab = row['Disponibilidade']
            perc_parado = row['Perc_Parado']
            perc_pausa = row['Perc_Pausa']
            
            str_trab = f"Dispon: {banco.minutos_para_string(row['Disponivel_min'])} ({perc_trab:.1f}%)"
            str_parado = f"Parado: {banco.minutos_para_string(row['Parado'])} ({perc_parado:.1f}%)"
            
            texto_interno = f"{str_trab}<br>{str_parado}"
            if row['Nao_Conta'] > 0:
                str_pausa = f"Pausa: {banco.minutos_para_string(row['Nao_Conta'])} ({perc_pausa:.1f}%)"
                texto_interno += f"<br>{str_pausa}"
            
            fig_bar.add_annotation(
                x=2, y=row['maquina'], text=f"<b>{texto_interno}</b>",
                showarrow=False, font=dict(color="white", size=13), xanchor="left", yanchor="middle"
            )
            
        fig_bar.update_layout(
            dragmode=False, showlegend=False, xaxis_title="", yaxis_title="", 
            xaxis=dict(range=[0, 115], showgrid=True, zeroline=False, fixedrange=True, ticksuffix="%"), 
            yaxis=dict(fixedrange=True), margin=dict(l=0, r=0, t=10, b=0), height=400, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
        )
        
        try:
            evento = st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False}, on_select="rerun", selection_mode="points")
            st.markdown("<p style='text-align: center; font-size: 13px; color: #7f8c8d; margin-top: -15px;'><i>(👆 Clique em uma barra para ver os apontamentos detalhados)</i></p>", unsafe_allow_html=True)
            if evento and hasattr(evento, 'selection') and evento.selection.points:
                maquina_clicada = str(evento.selection.points[0]["y"])
                if st.session_state.get('maquina_global') != maquina_clicada or st.session_state.get('aba_atual') != "📋 Apontamentos":
                    st.session_state['maquina_global'] = maquina_clicada
                    st.session_state['aba_atual'] = "📋 Apontamentos"
                    st.rerun()
        except TypeError:
            st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})
            st.markdown("<p style='text-align: center; font-size: 13px; color: #7f8c8d; margin-top: -15px;'><i>(Atualize a versão do Streamlit para ativar cliques nas barras)</i></p>", unsafe_allow_html=True)

    with g2:
        st.markdown("#### Evolução Diária da Disponibilidade")
        df_parado_dia = df_filt[df_filt['tipo'] == 'PARADA'].groupby(['data_registro', 'maquina'])['minutos'].sum().reset_index()
        df_parado_dia.rename(columns={'minutos': 'Parado'}, inplace=True)
        
        df_nao_conta_dia = df_filt[(df_filt['tipo'] == 'NÃO CONTA') | (df_filt['tipo'] == 'DESCONSIDERAR')].groupby(['data_registro', 'maquina'])['minutos'].sum().reset_index()
        df_nao_conta_dia.rename(columns={'minutos': 'Nao_Conta'}, inplace=True)
        
        df_dia = df_filt[['data_registro', 'maquina']].drop_duplicates()
        df_dia = pd.merge(df_dia, df_parado_dia, on=['data_registro', 'maquina'], how='left').fillna(0)
        df_dia = pd.merge(df_dia, df_nao_conta_dia, on=['data_registro', 'maquina'], how='left').fillna(0)
        
        # A Base de Cálculo Diária também é a Jornada Total Integral
        df_dia['Total'] = jornada_max_minutos
        
        df_dia['Disponivel_min'] = df_dia['Total'] - df_dia['Parado'] - df_dia['Nao_Conta']
        df_dia.loc[df_dia['Disponivel_min'] < 0, 'Disponivel_min'] = 0
        df_dia['Disponibilidade'] = (df_dia['Disponivel_min'] / df_dia['Total']) * 100
        
        dias_pt = {0: 'SEG', 1: 'TER', 2: 'QUA', 3: 'QUI', 4: 'SEX', 5: 'SAB', 6: 'DOM'}
        df_dia = df_dia.sort_values('data_registro')
        df_dia['data_formatada'] = pd.to_datetime(df_dia['data_registro']).apply(lambda x: f"{dias_pt[x.weekday()]} {x.strftime('%d/%m')}")
        ordem_datas = df_dia['data_formatada'].unique().tolist()
        
        fig_line = px.line(
            df_dia, x='data_formatada', y='Disponibilidade', color='maquina', markers=True,
            category_orders={"data_formatada": ordem_datas, "maquina": ordem_maquinas_pior_melhor}, color_discrete_map=mapa_cores_mestre 
        )
        fig_line.add_hline(y=meta_disp, line_dash="dash", line_color="red", annotation_text=f"Meta: {meta_disp}%", annotation_position="bottom right", annotation_font_color="red")
        fig_line.update_layout(
            dragmode=False, xaxis_type='category', xaxis_title="", yaxis_title="%", xaxis=dict(fixedrange=True, tickfont=dict(size=14)), 
            yaxis=dict(range=[0, 105], fixedrange=True), 
            legend=dict(font=dict(size=15), title_font=dict(size=15), yanchor="bottom", y=0.03, xanchor="left", x=0.01, bgcolor="rgba(255, 255, 255, 0.85)", bordercolor="rgba(0,0,0,0.1)", borderwidth=1),
            legend_title="Máquinas", margin=dict(l=0, r=0, t=10, b=0), height=400, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_line, use_container_width=True, config={'displayModeBar': False})

    # ==========================================
    # ELETROCARDIOGRAMA DIÁRIO AUTOMATIZADO
    # ==========================================
    st.markdown("<hr style='opacity: 0.2; margin: 40px 0 30px 0;'>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #2c3e50; text-transform: uppercase; font-weight: 900; margin-bottom: 5px;'>📊 Eletrocardiograma Diário</h3>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #7f8c8d; margin-bottom: 25px;'>Linha do tempo detalhada das máquinas (Paradas Registradas).</p>", unsafe_allow_html=True)
    
    datas_disponiveis = sorted(df_filt['data_registro'].dropna().unique().tolist(), reverse=True)
    if not datas_disponiveis: return
        
    cfg = banco.obter_configuracoes()
    m_das, m_as = cfg.get('manha_das', '07:30'), cfg.get('manha_as', '11:50')
    t_das, t_as = cfg.get('tarde_das', '13:30'), cfg.get('tarde_as', '17:30')
    
    lm_das, lm_as = cfg.get('lanche_m_das', ''), cfg.get('lanche_m_as', '')
    lt_das, lt_as = cfg.get('lanche_t_das', ''), cfg.get('lanche_t_as', '')

    m_das_min, m_as_min = calcular_minutos_str(m_das), calcular_minutos_str(m_as)
    t_das_min, t_as_min = calcular_minutos_str(t_das), calcular_minutos_str(t_as)
    
    lm_das_min = calcular_minutos_str(lm_das) if lm_das else -1
    lm_as_min = calcular_minutos_str(lm_as) if lm_as else -1
    lt_das_min = calcular_minutos_str(lt_das) if lt_das else -1
    lt_as_min = calcular_minutos_str(lt_as) if lt_as else -1
    
    total_timeline_min = t_as_min - m_das_min
    if total_timeline_min <= 0: total_timeline_min = 600 

    pct_as_m = ((m_as_min - m_das_min) / total_timeline_min) * 100
    pct_das_t = ((t_das_min - m_das_min) / total_timeline_min) * 100

    setores_dict = {}
    mapa_setores = df_nuvem[['maquina', 'setor']].dropna().drop_duplicates().set_index('maquina')['setor'].to_dict()
    
    todas_maquinas_cadastradas = sorted(df_filt['maquina'].unique())
    for maq in todas_maquinas_cadastradas:
        setor = mapa_setores.get(maq, "Sem Setor")
        if setor not in setores_dict: setores_dict[setor] = []
        setores_dict[setor].append(maq)

    html_timelines = "<div style='max-width: 1200px; margin: 0 auto; margin-top: 20px;'>"
    color_map = {0: "#ecf0f1", 1: "#27ae60", 2: "#e74c3c", 3: "#3498db", 4: "#f39c12", 5: "#bdc3c7"}

    for data_fita in datas_disponiveis:
        
        df_nuvem_dia = pd.DataFrame()
        if not df_nuvem.empty and 'data_registro' in df_nuvem.columns:
            if 'tipo' not in df_nuvem.columns: df_nuvem['tipo'] = 'PARADA'
            df_nuvem_dia = df_nuvem[df_nuvem['data_registro'].astype(str).str.startswith(data_fita)].copy()

        df_fita = df_filt[df_filt['data_registro'] == data_fita]
        data_formatada = pd.to_datetime(data_fita).strftime('%d/%m/%Y')
        html_timelines += f"<h3 style='text-align: center; color: #2980b9; margin-top: 30px; margin-bottom: 20px; font-weight: bold;'>📅 Referência: {data_formatada}</h3>"

        for setor in sorted(setores_dict.keys()):
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
            
            for maq in sorted(setores_dict[setor]):
                timeline = [0] * total_timeline_min
                
                # 1. Base Padrão: Azul (Disponível) ou Cinza (Previsão de Intervalo)
                for i in range(total_timeline_min):
                    curr = m_das_min + i
                    if curr >= m_as_min and curr < t_das_min: timeline[i] = 5
                    elif lm_das_min != -1 and curr >= lm_das_min and curr < lm_as_min: timeline[i] = 5
                    elif lt_das_min != -1 and curr >= lt_das_min and curr < lt_as_min: timeline[i] = 5
                    elif (curr >= m_das_min and curr < m_as_min) or (curr >= t_das_min and curr < t_as_min): timeline[i] = 3
                        
                # 2. Sobrepõe Registros Reais (Puxando agora estritamente pelo novo Tipo!)
                maq_records = df_fita[df_fita['maquina'] == maq]
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

    html_timelines += "<div style='display: flex; justify-content: center; flex-wrap: wrap; gap: 20px; margin-top: 10px; font-size: 13px; font-weight: bold; color: #555;'>"
    html_timelines += "<div style='display: flex; align-items: center; gap: 6px;'><div style='width:14px; height:14px; background:#3498db; border-radius:3px;'></div> Disponível (Livre)</div>"
    html_timelines += "<div style='display: flex; align-items: center; gap: 6px;'><div style='width:14px; height:14px; background:#27ae60; border-radius:3px;'></div> Produzindo</div>"
    html_timelines += "<div style='display: flex; align-items: center; gap: 6px;'><div style='width:14px; height:14px; background:#e74c3c; border-radius:3px;'></div> Indisponível (Parada)</div>"
    html_timelines += "<div style='display: flex; align-items: center; gap: 6px;'><div style='width:14px; height:14px; background:#f39c12; border-radius:3px;'></div> Pausa Registrada</div>"
    html_timelines += "<div style='display: flex; align-items: center; gap: 6px;'><div style='width:14px; height:14px; background:#bdc3c7; border-radius:3px;'></div> Intervalo Previsto</div>"
    html_timelines += "</div></div>"

    st.markdown(html_timelines, unsafe_allow_html=True)