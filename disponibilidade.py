import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import banco
import filtros # Importando o módulo global que contém a função do cabeçalho

def classificar_status(row):
    cod = str(row['cod_ocorrencia']).strip().lower()
    if cod in ['none', 'nan', '']: return 'Trabalhando'
    tipo = str(row['tipo']).strip().upper()
    if 'DESNCONSIDERAR' in tipo or 'DESCONSIDERAR' in tipo: return 'Desconsiderar'
    if tipo == 'PARADO': return 'Parado'
    return 'Trabalhando'

def criar_cartao(titulo, valor_principal, valor_secundario="", cor_secundaria="#666666"):
    html = f"""
    <div style="background-color: #ffffff; padding: 20px 10px; border-radius: 8px; border: 1px solid #eaeaea; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05); height: 100%;">
        <p style="margin: 0 0 5px 0; color: #777777; font-size: 13px; text-transform: uppercase; letter-spacing: 1px;">{titulo}</p>
        <h2 style="margin: 0; color: #222222; font-size: 38px; font-weight: 800;">{valor_principal}</h2>
        <p style="margin: 5px 0 0 0; color: {cor_secundaria}; font-size: 16px; font-weight: bold;">{valor_secundario}</p>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# O parâmetro de filtros foi renomeado para filtros_selecionados para não dar conflito com o "import filtros"
def renderizar(df_nuvem, df_codigos, filtros_selecionados, jornada_max_minutos, meta_disp):
    
    # CHAMA O CABEÇALHO GLOBAL NO TOPO DA ABA
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

    # ==========================================
    # DICIONÁRIO MESTRE DE CORES (Sincronizador)
    lista_alfabetica_maq = sorted(df_filt['maquina'].unique())
    paleta_cores = px.colors.qualitative.Plotly * 10
    mapa_cores_mestre = {maq: paleta_cores[i] for i, maq in enumerate(lista_alfabetica_maq)}
    # ==========================================

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

    k1, k2, k3, k4 = st.columns(4)
    with k1: criar_cartao("Média do Setor", f"{media_setor:.1f}%", "Geral", "#555")
    with k2: criar_cartao("Maior Disponibilidade", f"{melhor_val:.1f}%", f"🏆 {melhor_maq}", "#2ecc71")
    with k3: criar_cartao("Menor Disponibilidade", f"{pior_val:.1f}%", f"⚠️ {pior_maq}", "#e74c3c")
    with k4: criar_cartao(titulo_kpi, banco.minutos_para_string(tot_view_kpi), "No Período", "#555")

    st.markdown("<br>", unsafe_allow_html=True)

    g1, g2 = st.columns(2)
    with g1:
        st.markdown("#### Ranking de Disponibilidade por Máquina")
        fig_bar = go.Figure()
        
        fig_bar.add_trace(go.Bar(
            x=df_maq['Disponibilidade'], y=df_maq['maquina'], orientation='h',
            marker_color=[mapa_cores_mestre[m] for m in df_maq['maquina']],
            text=df_maq['Disponibilidade'].apply(lambda x: f"<b>{x:.1f}%</b>"),
            textposition='outside', textfont=dict(size=18, color='black'), cliponaxis=False
        ))
        
        for i, row in df_maq.iterrows():
            texto_interno = f"Trab: {banco.minutos_para_string(row['Trabalhando'])}<br>Parado: {banco.minutos_para_string(row['Parado'])}"
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
        st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})

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