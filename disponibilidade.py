import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import banco

def classificar_status(row):
    """Conta como parada se o TIPO na tabela de códigos for EXATAMENTE Parado"""
    cod = str(row['cod_ocorrencia']).strip().lower()
    if cod in ['none', 'nan', '']: 
        return 'Trabalhando'
        
    tipo = str(row['tipo']).strip().upper()
    if 'DESNCONSIDERAR' in tipo or 'DESCONSIDERAR' in tipo: 
        return 'Desconsiderar'
    if tipo == 'PARADO': 
        return 'Parado'
        
    return 'Trabalhando'

def renderizar(df_nuvem, df_codigos, filtros, jornada_max_minutos, meta_disp):
    # Preparação de Datas
    df_nuvem['data_registro'] = pd.to_datetime(df_nuvem['data_registro']).dt.strftime('%Y-%m-%d')
    df_nuvem['das_dt'] = pd.to_datetime(df_nuvem['das'], format='%H:%M', errors='coerce')
    df_nuvem['as_dt'] = pd.to_datetime(df_nuvem['as_hora'], format='%H:%M', errors='coerce')
    df_nuvem['minutos'] = (df_nuvem['as_dt'] - df_nuvem['das_dt']).dt.total_seconds() / 60.0
    df_nuvem.loc[df_nuvem['minutos'] < 0, 'minutos'] += 24 * 60 

    # Cruza os códigos do Banco
    if not df_codigos.empty:
        df_codigos['codigo'] = df_codigos['codigo'].astype(str).str.strip()
        df_nuvem['cod_ocorrencia'] = df_nuvem['cod_ocorrencia'].astype(str).str.strip()
        df_nuvem = df_nuvem.merge(df_codigos[['codigo', 'tipo']], left_on='cod_ocorrencia', right_on='codigo', how='left')
    else:
        df_nuvem['tipo'] = None

    df_nuvem['status_real'] = df_nuvem.apply(classificar_status, axis=1)

    # 1. APLICAÇÃO DOS FILTROS GLOBAIS
    df_filt = df_nuvem.copy()
    if filtros['de'] != "[ Todas ]": df_filt = df_filt[df_filt['data_registro'] >= filtros['de']]
    if filtros['ate'] != "[ Todas ]": df_filt = df_filt[df_filt['data_registro'] <= filtros['ate']]
    if filtros['setor'] != "[ Todos ]": df_filt = df_filt[df_filt['setor'] == filtros['setor']]
    if filtros['maquina'] != "[ Todas ]": df_filt = df_filt[df_filt['maquina'] == filtros['maquina']]

    if df_filt.empty:
        st.warning("⚠️ Nenhum dado encontrado para esta combinação de filtros.")
        return

    # 2. MATEMÁTICA EXATA DA DISPONIBILIDADE (Total - Parado)
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
    df_maq = df_maq.sort_values('Disponibilidade', ascending=True)

    # 3. INTERPRETAÇÃO DO FILTRO TIPO (Apenas para os KPIs Numéricos)
    sel_tipo = filtros['tipo']
    if sel_tipo == "Parado":
        df_maq['Trabalhando_View'], df_maq['Parado_View'] = 0, df_maq['Parado']
    elif sel_tipo == "Trabalhando":
        df_maq['Trabalhando_View'], df_maq['Parado_View'] = df_maq['Trabalhando'], 0
    else:
        df_maq['Trabalhando_View'], df_maq['Parado_View'] = df_maq['Trabalhando'], df_maq['Parado']

    # --- KPIS ---
    tot_trab_base = df_maq['Trabalhando'].sum()
    tot_par_base = df_maq['Parado'].sum()
    media_setor = (tot_trab_base / (tot_trab_base + tot_par_base)) * 100 if (tot_trab_base + tot_par_base) > 0 else 0
    
    maior_maq = df_maq.iloc[-1]['maquina'] if not df_maq.empty else "-"
    maior_val = df_maq.iloc[-1]['Disponibilidade'] if not df_maq.empty else 0
    menor_maq = df_maq.iloc[0]['maquina'] if not df_maq.empty else "-"
    menor_val = df_maq.iloc[0]['Disponibilidade'] if not df_maq.empty else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Média do Setor", f"{media_setor:.1f}%")
    st.markdown("""<style>div[data-testid="metric-container"]:nth-of-type(2) label { color: #2ecc71; font-weight: bold; } div[data-testid="metric-container"]:nth-of-type(3) label { color: #e74c3c; font-weight: bold; } div[data-testid="metric-container"]:nth-of-type(4) label { color: #e74c3c; font-weight: bold; }</style>""", unsafe_allow_html=True)
    k2.metric("Maior Disponibilidade", f"{maior_maq}", f"{maior_val:.1f}%")
    k3.metric("Menor Disponibilidade", f"{menor_maq}", f"{menor_val:.1f}%", delta_color="inverse")
    
    tot_view_kpi = df_maq['Parado_View'].sum() if sel_tipo == "Parado" else (df_maq['Trabalhando_View'].sum() if sel_tipo == "Trabalhando" else df_maq['Parado'].sum())
    titulo_kpi = "Total Horas Perdidas" if sel_tipo != "Trabalhando" else "Total Horas Trabalhadas"
    k4.metric(titulo_kpi, banco.minutos_para_string(tot_view_kpi))

    st.markdown("<br>", unsafe_allow_html=True)

    g1, g2 = st.columns(2)
    with g1:
        st.markdown("#### Ranking de Disponibilidade por Máquina")
        
        fig_bar = go.Figure()
        
        # Cores vibrantes padrão do Plotly
        cores = px.colors.qualitative.Plotly * 10
        mapa_cores = {maq: cores[i] for i, maq in enumerate(df_maq['maquina'].unique())}
        
        # 1. Desenha a barra e coloca a Porcentagem fora (à direita)
        fig_bar.add_trace(go.Bar(
            x=df_maq['Disponibilidade'],
            y=df_maq['maquina'],
            orientation='h',
            marker_color=[mapa_cores[m] for m in df_maq['maquina']],
            text=df_maq['Disponibilidade'].apply(lambda x: f"<b>{x:.1f}%</b>"),
            textposition='outside',
            textfont=dict(size=18, color='black'),
            cliponaxis=False
        ))
        
        # 2. Cola os textos "Trab / Parado" dentro da barra (à esquerda)
        for i, row in df_maq.iterrows():
            texto_interno = f"Trab: {banco.minutos_para_string(row['Trabalhando'])} | Parado: {banco.minutos_para_string(row['Parado'])}"
            fig_bar.add_annotation(
                x=2, # Pequeno recuo da borda esquerda (2%)
                y=row['maquina'],
                text=f"<b>{texto_interno}</b>",
                showarrow=False,
                font=dict(color="white", size=14),
                xanchor="left",
                yanchor="middle"
            )
            
        fig_bar.update_layout(
            showlegend=False, 
            xaxis_title="", 
            yaxis_title="", 
            xaxis=dict(range=[0, 115], showgrid=True, zeroline=False), # Espaço extra (115) para a porcentagem caber fora da barra 
            margin=dict(l=0, r=0, t=10, b=0), 
            height=400,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_bar, use_container_width=True)

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
        
        fig_line = px.line(df_dia, x='data_registro', y='Disponibilidade', color='maquina', markers=True)
        fig_line.add_hline(y=meta_disp, line_dash="dash", line_color="red", annotation_text=f"Meta: {meta_disp}%", annotation_position="bottom right", annotation_font_color="red")
        
        fig_line.update_layout(
            yaxis_range=[0, 105], 
            xaxis_type='category', 
            xaxis_title="", 
            yaxis_title="%", 
            legend_title="Máquinas", 
            margin=dict(l=0, r=0, t=10, b=0), 
            height=400,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_line, use_container_width=True)