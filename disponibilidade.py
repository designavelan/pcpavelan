import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import banco
import filtros
import streamlit.components.v1 as components 

def classificar_status(row):
    cod = str(row['cod_ocorrencia']).strip().lower()
    if cod in ['none', 'nan', '']: return 'Trabalhando'
    tipo = str(row['tipo']).strip().upper()
    if 'DESNCONSIDERAR' in tipo or 'DESCONSIDERAR' in tipo: return 'Desconsiderar'
    if tipo == 'PARADO': return 'Parado'
    return 'Trabalhando'

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

    df_nuvem['data_registro'] = pd.to_datetime(df_nuvem['data_registro']).dt.strftime('%Y-%m-%d')
    df_nuvem['das_dt'] = pd.to_datetime(df_nuvem['das'], format='%H:%M', errors='coerce')
    df_nuvem['as_dt'] = pd.to_datetime(df_nuvem['as_hora'], format='%H:%M', errors='coerce')
    df_nuvem['minutos'] = (df_nuvem['as_dt'] - df_nuvem['das_dt']).dt.total_seconds() / 60.0
    df_nuvem.loc[df_nuvem['minutos'] < 0, 'minutos'] += 24 * 60 

    if not df_codigos.empty:
        df_codigos['codigo'] = df_codigos['codigo'].astype(str).str.strip()
        df_nuvem['cod_ocorrencia'] = df_nuvem['cod_ocorrencia'].astype(str).str.strip()
        df_nuvem = df_nuvem.merge(df_codigos[['codigo', 'tipo']], left_on='cod_ocorrencia', right_on='codigo', how='left')
    else:
        df_nuvem['tipo'] = None

    df_nuvem['status_real'] = df_nuvem.apply(classificar_status, axis=1)

    df_filt = df_nuvem.copy()
    if filtros_selecionados['de'] != "[ Todas ]": df_filt = df_filt[df_filt['data_registro'] >= filtros_selecionados['de']]
    if filtros_selecionados['ate'] != "[ Todas ]": df_filt = df_filt[df_filt['data_registro'] <= filtros_selecionados['ate']]
    if filtros_selecionados['setor'] != "[ Todos ]": df_filt = df_filt[df_filt['setor'] == filtros_selecionados['setor']]
    if filtros_selecionados['maquina'] != "[ Todas ]": df_filt = df_filt[df_filt['maquina'] == filtros_selecionados['maquina']]

    if df_filt.empty:
        st.warning("⚠️ Nenhum dado encontrado para esta combinação de filtros.")
        return

    lista_alfabetica_maq = sorted(df_filt['maquina'].unique())
    paleta_cores = px.colors.qualitative.Plotly * 10
    mapa_cores_mestre = {maq: paleta_cores[i] for i, maq in enumerate(lista_alfabetica_maq)}

    dias_reais = df_filt['data_registro'].nunique()
    if dias_reais == 0: dias_reais = 1
    jornada_total_periodo = jornada_max_minutos * dias_reais

    df_parado = df_filt[df_filt['status_real'] == 'Parado'].groupby('maquina')['minutos'].sum().reset_index()
    df_parado.rename(columns={'minutos': 'Parado'}, inplace=True)

    todas_maquinas = pd.DataFrame({'maquina': df_filt['maquina'].unique()})
    df_maq = pd.merge(todas_maquinas, df_parado, on='maquina', how='left').fillna(0)

    df_maq['Total'] = jornada_total_periodo
    df_maq['Trabalhando'] = df_maq['Total'] - df_maq['Parado']
    df_maq.loc[df_maq['Trabalhando'] < 0, 'Trabalhando'] = 0 

    df_maq['Disponibilidade'] = (df_maq['Trabalhando'] / df_maq['Total']) * 100
    df_maq = df_maq.sort_values('Disponibilidade', ascending=False)
    
    ordem_maquinas_pior_melhor = df_maq.sort_values('Disponibilidade', ascending=True)['maquina'].tolist()

    sel_tipo = filtros_selecionados['tipo']
    if sel_tipo == "Parado":
        df_maq['Trabalhando_View'], df_maq['Parado_View'] = 0, df_maq['Parado']
    elif sel_tipo == "Trabalhando":
        df_maq['Trabalhando_View'], df_maq['Parado_View'] = df_maq['Trabalhando'], 0
    else:
        df_maq['Trabalhando_View'], df_maq['Parado_View'] = df_maq['Trabalhando'], df_maq['Parado']

    tot_trab_base = df_maq['Trabalhando'].sum()
    tot_par_base = df_maq['Parado'].sum()
    media_setor = (tot_trab_base / (tot_trab_base + tot_par_base)) * 100 if (tot_trab_base + tot_par_base) > 0 else 0
    
    melhor_maq = df_maq.iloc[0]['maquina'] if not df_maq.empty else "-"
    melhor_val = df_maq.iloc[0]['Disponibilidade'] if not df_maq.empty else 0
    pior_maq = df_maq.iloc[-1]['maquina'] if not df_maq.empty else "-"
    pior_val = df_maq.iloc[-1]['Disponibilidade'] if not df_maq.empty else 0

    tot_view_kpi = df_maq['Parado_View'].sum() if sel_tipo == "Parado" else (df_maq['Trabalhando_View'].sum() if sel_tipo == "Trabalhando" else df_maq['Parado'].sum())
    titulo_kpi = "Total Horas Perdidas" if sel_tipo != "Trabalhando" else "Total Horas Trabalhadas"

    cor_melhor_maq = mapa_cores_mestre.get(melhor_maq, "#555")
    cor_pior_maq = mapa_cores_mestre.get(pior_maq, "#555")
    
    texto_dias_rodape = f"No Período de {dias_reais} Dia{'s' if dias_reais > 1 else ''}"

    k1, k2, k3, k4 = st.columns(4)
    with k1: 
        criar_cartao("Média do Setor", f"{media_setor:.1f}%", "Geral", "#555", "#777777")
    with k2: 
        criar_cartao("Maior Disponibilidade", f"{melhor_val:.1f}%", f"🏆 {melhor_maq}", cor_melhor_maq, "#2ecc71")
    with k3: 
        criar_cartao("Menor Disponibilidade", f"{pior_val:.1f}%", f"⚠️ {pior_maq}", cor_pior_maq, "#e74c3c")
    with k4: 
        criar_cartao(titulo_kpi, banco.minutos_para_string(tot_view_kpi), texto_dias_rodape, "#555", "#777777")

    js_equalizer = """
    <script>
        setInterval(() => {
            const cards = window.parent.document.querySelectorAll('.cartao-kpi-disp');
            if(cards.length > 0) {
                let maxH = 0;
                cards.forEach(c => c.style.minHeight = 'auto');
                cards.forEach(c => {
                    if(c.offsetHeight > maxH) maxH = c.offsetHeight;
                });
                cards.forEach(c => {
                    c.style.minHeight = maxH + 'px';
                });
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
            textposition='outside', textfont=dict(size=18, color='black'), cliponaxis=False,
            hoverinfo='none'
        ))
        
        for i, row in df_maq.iterrows():
            perc_trab = row['Disponibilidade']
            perc_parado = 100.0 - perc_trab
            
            str_trab = f"Trab: {banco.minutos_para_string(row['Trabalhando'])} ({perc_trab:.1f}%)"
            str_parado = f"Parado: {banco.minutos_para_string(row['Parado'])} ({perc_parado:.1f}%)"
            
            texto_interno = f"{str_trab}<br>{str_parado}"
            
            fig_bar.add_annotation(
                x=2, y=row['maquina'], text=f"<b>{texto_interno}</b>",
                showarrow=False, font=dict(color="white", size=14), xanchor="left", yanchor="middle"
            )
            
        fig_bar.update_layout(
            dragmode=False, showlegend=False, xaxis_title="", yaxis_title="", 
            xaxis=dict(range=[0, 115], showgrid=True, zeroline=False, fixedrange=True, ticksuffix="%"), 
            yaxis=dict(fixedrange=True), 
            margin=dict(l=0, r=0, t=10, b=0), height=400, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
        )
        
        try:
            evento = st.plotly_chart(
                fig_bar, 
                use_container_width=True, 
                config={'displayModeBar': False}, 
                on_select="rerun", 
                selection_mode="points"
            )
            
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
        df_parado_dia = df_filt[df_filt['status_real'] == 'Parado'].groupby(['data_registro', 'maquina'])['minutos'].sum().reset_index()
        df_parado_dia.rename(columns={'minutos': 'Parado'}, inplace=True)
        
        df_dia = df_filt[['data_registro', 'maquina']].drop_duplicates()
        df_dia = pd.merge(df_dia, df_parado_dia, on=['data_registro', 'maquina'], how='left').fillna(0)
        
        df_dia['Total'] = jornada_max_minutos
        df_dia['Trabalhando'] = df_dia['Total'] - df_dia['Parado']
        df_dia.loc[df_dia['Trabalhando'] < 0, 'Trabalhando'] = 0
        df_dia['Disponibilidade'] = (df_dia['Trabalhando'] / df_dia['Total']) * 100
        
        dias_pt = {0: 'SEG', 1: 'TER', 2: 'QUA', 3: 'QUI', 4: 'SEX', 5: 'SAB', 6: 'DOM'}
        
        df_dia = df_dia.sort_values('data_registro')
        df_dia['data_formatada'] = pd.to_datetime(df_dia['data_registro']).apply(
            lambda x: f"{dias_pt[x.weekday()]} {x.strftime('%d/%m')}"
        )
        ordem_datas = df_dia['data_formatada'].unique().tolist()
        
        fig_line = px.line(
            df_dia, x='data_formatada', y='Disponibilidade', color='maquina', markers=True,
            category_orders={"data_formatada": ordem_datas, "maquina": ordem_maquinas_pior_melhor},
            color_discrete_map=mapa_cores_mestre 
        )
        
        fig_line.add_hline(y=meta_disp, line_dash="dash", line_color="red", annotation_text=f"Meta: {meta_disp}%", annotation_position="bottom right", annotation_font_color="red")
        
        fig_line.update_layout(
            dragmode=False, xaxis_type='category', xaxis_title="", yaxis_title="%", 
            xaxis=dict(fixedrange=True, tickfont=dict(size=14)), 
            yaxis=dict(range=[0, 105], fixedrange=True), 
            legend=dict(
                font=dict(size=15), 
                title_font=dict(size=15),
                yanchor="bottom", y=0.03, 
                xanchor="left", x=0.01, 
                bgcolor="rgba(255, 255, 255, 0.85)", 
                bordercolor="rgba(0,0,0,0.1)", borderwidth=1
            ),
            legend_title="Máquinas", margin=dict(l=0, r=0, t=10, b=0), height=400,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_line, use_container_width=True, config={'displayModeBar': False})

    # ==========================================
    # 6. ADIÇÃO DA NOVA FUNÇÃO: ELETROCARDIOGRAMA DIÁRIO AUTOMATIZADO
    # ==========================================
    st.markdown("<hr style='opacity: 0.2; margin: 40px 0 30px 0;'>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #2c3e50; text-transform: uppercase; font-weight: 900; margin-bottom: 5px;'>📊 Eletrocardiograma Diário</h3>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #7f8c8d; margin-bottom: 25px;'>Linha do tempo detalhada das máquinas conforme o período filtrado.</p>", unsafe_allow_html=True)
    
    # Extrai todas as datas presentes nos filtros globais
    datas_disponiveis = sorted(df_filt['data_registro'].dropna().unique().tolist(), reverse=True)
    
    if not datas_disponiveis:
        st.info("Nenhuma data disponível no filtro selecionado para exibir o Eletrocardiograma.")
        return
        
    cfg = banco.obter_configuracoes()
    m_das = cfg.get('manha_das', '07:30')
    m_as = cfg.get('manha_as', '11:50')
    t_das = cfg.get('tarde_das', '13:30')
    t_as = cfg.get('tarde_as', '17:30')

    m_das_min = calcular_minutos_str(m_das)
    m_as_min = calcular_minutos_str(m_as)
    t_das_min = calcular_minutos_str(t_das)
    t_as_min = calcular_minutos_str(t_as)
    
    total_timeline_min = t_as_min - m_das_min
    if total_timeline_min <= 0: total_timeline_min = 600 

    pct_as_m = ((m_as_min - m_das_min) / total_timeline_min) * 100
    pct_das_t = ((t_das_min - m_das_min) / total_timeline_min) * 100

    agora = datetime.utcnow() - timedelta(hours=3)
    hoje_str = agora.strftime("%Y-%m-%d")
    
    setores_dict = {}
    mapa_setores = df_nuvem[['maquina', 'setor']].dropna().drop_duplicates().set_index('maquina')['setor'].to_dict()
    
    todas_maquinas_cadastradas = sorted(df_filt['maquina'].unique())
    for maq in todas_maquinas_cadastradas:
        setor = mapa_setores.get(maq, "Sem Setor")
        if setor not in setores_dict:
            setores_dict[setor] = []
        setores_dict[setor].append(maq)

    html_timelines = "<div style='max-width: 1200px; margin: 0 auto; margin-top: 20px;'>"
    color_map = {0: "#95a5a6", 1: "#27ae60", 2: "#e74c3c", 3: "#ecf0f1"}

    teve_hoje = False

    # LAÇO DE REPETIÇÃO: Renderiza um bloco inteiro para CADA dia filtrado
    for data_fita in datas_disponiveis:
        is_hoje = (data_fita == hoje_str)
        if is_hoje: teve_hoje = True
        agora_min = agora.hour * 60 + agora.minute if is_hoje else 24 * 60

        df_fita = df_filt[df_filt['data_registro'] == data_fita]
        
        # Cabeçalho da Data atual
        data_formatada = pd.to_datetime(data_fita).strftime('%d/%m/%Y')
        html_timelines += f"<h3 style='text-align: center; color: #2980b9; margin-top: 30px; margin-bottom: 20px; font-weight: bold;'>📅 Referência: {data_formatada}</h3>"

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
                        
                maq_stops = df_fita[(df_fita['maquina'] == maq) & (df_fita['status_real'] == 'Parado')]
                for _, row in maq_stops.iterrows():
                    if pd.notna(row['das']) and pd.notna(row['as_hora']):
                        inicio = calcular_minutos_str(row['das'])
                        fim = calcular_minutos_str(row['as_hora'])
                        for m in range(inicio, fim):
                            idx = m - m_das_min
                            if 0 <= idx < total_timeline_min:
                                timeline[idx] = 2 
                                
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
                
            html_timelines += "</div>" # Fecha a box do Setor

    # Legenda Global de Cores
    html_timelines += "<div style='display: flex; justify-content: center; flex-wrap: wrap; gap: 20px; margin-top: 10px; font-size: 13px; font-weight: bold; color: #555;'>"
    html_timelines += "<div style='display: flex; align-items: center; gap: 6px;'><div style='width:14px; height:14px; background:#27ae60; border-radius:3px;'></div> Trabalhando</div>"
    html_timelines += "<div style='display: flex; align-items: center; gap: 6px;'><div style='width:14px; height:14px; background:#e74c3c; border-radius:3px;'></div> Parada Registrada</div>"
    html_timelines += "<div style='display: flex; align-items: center; gap: 6px;'><div style='width:14px; height:14px; background:#95a5a6; border-radius:3px;'></div> Intervalo / Almoço</div>"
    if teve_hoje:
        html_timelines += "<div style='display: flex; align-items: center; gap: 6px;'><div style='width:14px; height:14px; background:#ecf0f1; border-radius:3px; border: 1px solid #ccc;'></div> A Realizar</div>"
    html_timelines += "</div></div>"

    st.markdown(html_timelines, unsafe_allow_html=True)