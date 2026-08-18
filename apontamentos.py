import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import banco
import filtros

def classificar_status(row):
    cod = str(row['cod_ocorrencia']).strip().lower()
    if cod in ['none', 'nan', '']: return 'Trabalhando'
    tipo = str(row['tipo']).strip().upper()
    if 'DESNCONSIDERAR' in tipo or 'DESCONSIDERAR' in tipo: return 'Desconsiderar'
    if tipo == 'PARADO': return 'Parado'
    return 'Trabalhando'

def renderizar(df_nuvem, df_codigos, filtros_selecionados):
    filtros.renderizar_cabecalho_global("Ocorrências")

    # === LÊ AS CONFIGURAÇÕES DE EXIBIÇÃO DA ABA ===
    cfg = banco.obter_configuracoes()
    mostrar_cronico = cfg.get('mostrar_cronico', True)
    mostrar_especifico = cfg.get('mostrar_especifico', True)
    # ===============================================

    if df_nuvem.empty or df_codigos.empty:
        st.warning("Sem dados suficientes para análise.")
        return

    df = df_nuvem.copy()
    df['data_registro'] = pd.to_datetime(df['data_registro']).dt.strftime('%Y-%m-%d')
    df['das_dt'] = pd.to_datetime(df['das'], format='%H:%M', errors='coerce')
    df['as_dt'] = pd.to_datetime(df['as_hora'], format='%H:%M', errors='coerce')
    df['minutos'] = (df['as_dt'] - df['das_dt']).dt.total_seconds() / 60.0
    df.loc[df['minutos'] < 0, 'minutos'] += 24 * 60 

    if filtros_selecionados['de'] != "[ Todas ]": df = df[df['data_registro'] >= filtros_selecionados['de']]
    if filtros_selecionados['ate'] != "[ Todas ]": df = df[df['data_registro'] <= filtros_selecionados['ate']]
    if filtros_selecionados['setor'] != "[ Todos ]": df = df[df['setor'] == filtros_selecionados['setor']]
    if filtros_selecionados['maquina'] != "[ Todas ]": df = df[df['maquina'] == filtros_selecionados['maquina']]

    df_codigos['codigo'] = df_codigos['codigo'].astype(str).str.strip()
    df['cod_ocorrencia'] = df['cod_ocorrencia'].astype(str).str.strip()
    df_codigos['cronico'] = df_codigos['cronico'].fillna('Nao').astype(str)
    df_codigos['descricao'] = df_codigos['descricao'].fillna('Sem Descrição').astype(str)
    
    df = df.merge(df_codigos[['codigo', 'descricao', 'cronico', 'tipo']], left_on='cod_ocorrencia', right_on='codigo', how='left')

    df['status_real'] = df.apply(classificar_status, axis=1)
    df = df[df['status_real'] == 'Parado']
    
    if df.empty:
        st.info("Nenhuma ocorrência (Parada) registrada neste período com os filtros atuais.")
        return

    total_minutos_geral = df['minutos'].sum()

    # MOTOR DE REGRAS INTACTO
    dias_por_codigo = df.groupby('cod_ocorrencia')['data_registro'].nunique().to_dict()

    maquina_especifica = {}
    if filtros_selecionados['maquina'] == "[ Todas ]": 
        for cod in df['cod_ocorrencia'].unique():
            df_cod = df[df['cod_ocorrencia'] == cod]
            total_ocorrencias = len(df_cod)
            if total_ocorrencias >= 3:
                maq_group = df_cod.groupby('maquina')['minutos'].sum()
                tot_tempo = maq_group.sum()
                if tot_tempo > 0:
                    maq_max = maq_group.idxmax()
                    val_max = maq_group.max()
                    if (val_max / tot_tempo) >= 0.80:
                        maquina_especifica[cod] = maq_max

    df_agrupado = df.groupby(['cod_ocorrencia', 'descricao', 'cronico']).agg(
        Ocor=('cod_ocorrencia', 'count'),
        Tempo=('minutos', 'sum')
    ).reset_index()

    df_agrupado = df_agrupado.sort_values(by='Tempo', ascending=False).reset_index(drop=True)
    df_agrupado['Perc'] = (df_agrupado['Tempo'] / total_minutos_geral) * 100
    df_agrupado['Acumulado'] = df_agrupado['Perc'].cumsum()

    linhas_html = ""
    for i, row in df_agrupado.iterrows():
        cod = row['cod_ocorrencia']
        desc = str(row['descricao'])
        status_cronico = str(row['cronico']).strip().lower()
        
        qtd_dias = dias_por_codigo.get(cod, 0)
        eh_elegivel = ('elegivel' in status_cronico or 'elegível' in status_cronico)
        is_cronico = eh_elegivel and (qtd_dias >= 3)
        
        maq_esp = maquina_especifica.get(cod, None)

        tags = ""
        estilo_linha = ""
        
        exibir_cronico = is_cronico and mostrar_cronico
        exibir_especifico = maq_esp and mostrar_especifico

        if exibir_cronico:
            tags += f" <span style='color: #d35400; font-size: 0.85em;'>⚠️ [CRÔNICO]</span>"
            estilo_linha = "color: #d35400; font-weight: 500;"
        if exibir_especifico:
            tags += f" <span style='color: #8e44ad; font-size: 0.85em;'>⚠️ [ESPECÍFICO - {maq_esp}]</span>"
            if not exibir_cronico: estilo_linha = "color: #8e44ad; font-weight: 500;"

        fundo = "#f9f9f9" if i % 2 != 0 else "#ffffff"
        
        linhas_html += f"<tr style='background-color: {fundo}; {estilo_linha}'>"
        linhas_html += f"<td style='padding: 10px; border-bottom: 1px solid #eee; text-align: center;'>{cod}</td>"
        linhas_html += f"<td style='padding: 10px; border-bottom: 1px solid #eee;'>{desc}{tags}</td>"
        linhas_html += f"<td style='padding: 10px; border-bottom: 1px solid #eee; text-align: center;'>{row['Ocor']}</td>"
        linhas_html += f"<td style='padding: 10px; border-bottom: 1px solid #eee; text-align: center;'>{banco.minutos_para_string(row['Tempo'])}</td>"
        linhas_html += f"<td style='padding: 10px; border-bottom: 1px solid #eee; text-align: center; font-weight: bold;'>{row['Perc']:.0f}%</td>"
        linhas_html += "</tr>"

    tabela_html = f"<table style='width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 14px;'>"
    tabela_html += f"<thead><tr style='background-color: #2980b9; color: white; text-align: left;'>"
    tabela_html += f"<th style='padding: 12px; text-align: center;'>Cod</th>"
    tabela_html += f"<th style='padding: 12px;'>Descrição</th>"
    tabela_html += f"<th style='padding: 12px; text-align: center;'>Ocor.</th>"
    tabela_html += f"<th style='padding: 12px; text-align: center;'>Tempo</th>"
    tabela_html += f"<th style='padding: 12px; text-align: center;'>%</th>"
    tabela_html += f"</tr></thead><tbody>{linhas_html}</tbody></table>"
    
    legenda_html = "<div style='margin-top: 15px; font-size: 12px; color: #7f8c8d;'>"
    if mostrar_cronico and mostrar_especifico:
        legenda_html += "<span style='color: #d35400;'>⚠️ [CRÔNICO]:</span> Falhas recorrentes em múltiplos dias | <span style='color: #8e44ad;'>⚠️ [ESPECÍFICO]:</span> Falhas com alta ocorrência (3+), concentradas em uma máquina (80%+)."
    elif mostrar_cronico:
        legenda_html += "<span style='color: #d35400;'>⚠️ [CRÔNICO]:</span> Falhas recorrentes em múltiplos dias."
    elif mostrar_especifico:
        legenda_html += "<span style='color: #8e44ad;'>⚠️ [ESPECÍFICO]:</span> Falhas com alta ocorrência (3+), concentradas em uma máquina (80%+)."
    legenda_html += "</div>"
    
    tabela_html += legenda_html

    # --- LÓGICA DE ESCALA H:MM AUTOMÁTICA ---
    df_top10 = df_agrupado.head(10).copy()
    max_minutos = df_top10['Tempo'].max() if not df_top10.empty else 0
    
    # Define o "degrau" do eixo baseado no volume de horas para não poluir
    if max_minutos > 1200: step = 240       # De 4 em 4 horas
    elif max_minutos > 600: step = 120      # De 2 em 2 horas
    elif max_minutos > 300: step = 60       # De 1 em 1 hora
    elif max_minutos > 120: step = 30       # De 30 em 30 min
    elif max_minutos > 60: step = 15        # De 15 em 15 min
    else: step = 10                         # De 10 em 10 min

    tickvals_y1 = list(range(0, int(max_minutos) + step, step))
    ticktext_y1 = [f"{int(v // 60)}:{int(v % 60):02d}" for v in tickvals_y1]
    # ----------------------------------------
    
    fig = go.Figure()
    
    # ESCURECI A BARRA PARA MELHORAR O CONTRASTE (#2c3e50 - Azul Petróleo Escuro)
    fig.add_trace(go.Bar(
        x=df_top10['cod_ocorrencia'],
        y=df_top10['Tempo'],
        name='Tempo Perdido',
        marker_color='#2c3e50', 
        hovertemplate="Código: %{x}<br>Tempo: %{customdata}<extra></extra>",
        customdata=[banco.minutos_para_string(m) for m in df_top10['Tempo']]
    ))

    fig.add_trace(go.Scatter(
        x=df_top10['cod_ocorrencia'],
        y=df_top10['Acumulado'],
        name='Impacto Acumulado (%)',
        mode='lines+markers+text',
        marker=dict(color='#f39c12', size=8),
        line=dict(color='#f39c12', width=3),
        text=[f"<b>{x:.0f}%</b>" for x in df_top10['Acumulado']],
        textposition="top center",
        textfont=dict(color='#d35400', size=13),
        yaxis='y2'
    ))

    fig.update_layout(
        title=dict(text="Pareto de Ocorrências (Top 10 Códigos)", font=dict(size=16, color='#2c3e50')),
        xaxis=dict(type='category', title="", tickfont=dict(size=13)),
        
        # APLICA A ESCALA DE HORAS PERSONALIZADA NO EIXO ESQUERDO
        yaxis=dict(
            title="Tempo Perdido (Horas)", 
            showgrid=True, 
            gridcolor='#ecf0f1', 
            tickfont=dict(size=13),
            tickvals=tickvals_y1,
            ticktext=ticktext_y1
        ),
        
        # APLICA O SÍMBOLO DE % NO EIXO DIREITO
        yaxis2=dict(
            title="Impacto Acumulado (%)", 
            overlaying='y', 
            side='right', 
            range=[0, 110], 
            showgrid=False, 
            tickfont=dict(size=13),
            ticksuffix="%"
        ),
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, t=40, b=0),
        height=500,
        dragmode=False
    )

    col1, col2 = st.columns([5, 5])
    with col1:
        st.markdown("#### Ranking de Ocorrências")
        st.markdown(tabela_html, unsafe_allow_html=True)
    with col2:
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})