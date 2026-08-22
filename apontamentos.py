import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import banco
import filtros
import streamlit.components.v1 as components 

def renderizar(df_nuvem, df_codigos, filtros_selecionados):
    filtros.renderizar_cabecalho_global("Apontamentos")

    cfg = banco.obter_configuracoes()
    mostrar_cronico = cfg.get('mostrar_cronico', True)
    mostrar_especifico = cfg.get('mostrar_especifico', True)

    df = filtros.aplicar_filtros_analiticos(df_nuvem, df_codigos, filtros_selecionados)
    if df.empty:
        st.warning("⚠️ Sem dados suficientes para análise.")
        return

    df = df[df['status_real'] == 'Parado']
    if df.empty:
        st.info("Nenhuma ocorrência (Parada) registrada neste período com os filtros atuais.")
        return

    total_minutos_geral = df['minutos'].sum()

    lista_alfabetica_maq = sorted(df['maquina'].unique())
    paleta_cores = px.colors.qualitative.Plotly * 10
    mapa_cores_mestre = {maq: paleta_cores[i] for i, maq in enumerate(lista_alfabetica_maq)}

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
        rank_posicao = i + 1
        cod = row['cod_ocorrencia']
        desc_original = str(row['descricao'])
        desc_com_rank = f"{rank_posicao}º — {desc_original}" 
        
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
        icone_lupa = f"""
        <a href="?codigo_alvo={cod}" target="_parent" style="text-decoration: none;">
            <div style="cursor: pointer; background-color: #ecf0f1; border-radius: 5px; padding: 6px; font-size: 16px; text-align: center; transition: 0.2s; color: #2c3e50;" 
                 onmouseover="this.style.backgroundColor='#bdc3c7'" onmouseout="this.style.backgroundColor='#ecf0f1'" title="Analisar Ocorrência em Detalhes">🔎</div>
        </a>
        """
        
        linhas_html += f"<tr style='background-color: {fundo}; {estilo_linha}'><td style='padding: 8px; border-bottom: 1px solid #eee; text-align: center; width: 45px;'>{icone_lupa}</td><td style='padding: 10px; border-bottom: 1px solid #eee;'>{desc_com_rank} <b>({cod})</b>{tags}</td><td style='padding: 10px; border-bottom: 1px solid #eee; text-align: center;'>{row['Ocor']}</td><td style='padding: 10px; border-bottom: 1px solid #eee; text-align: center;'>{banco.minutos_para_string(row['Tempo'])}</td><td style='padding: 10px; border-bottom: 1px solid #eee; text-align: center; font-weight: bold;'>{row['Perc']:.0f}%</td></tr>"

    qtd_linhas_tabela = len(df_agrupado)
    altura_calculada = 50 + (qtd_linhas_tabela * 48) + 50
    altura_final = max(420, min(altura_calculada, 650))

    tabela_html = f"<div style='max-height: {altura_final}px; overflow-y: auto; padding-right: 5px;'><table style='width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 14px;'><thead><tr style='color: white; text-align: left;'><th style='padding: 12px; text-align: center; width: 45px; position: sticky; top: 0; background-color: #2980b9; z-index: 1;'>Ação</th><th style='padding: 12px; position: sticky; top: 0; background-color: #2980b9; z-index: 1;'>Descrição do Problema</th><th style='padding: 12px; text-align: center; position: sticky; top: 0; background-color: #2980b9; z-index: 1;'>Ocor.</th><th style='padding: 12px; text-align: center; position: sticky; top: 0; background-color: #2980b9; z-index: 1;'>Tempo</th><th style='padding: 12px; text-align: center; position: sticky; top: 0; background-color: #2980b9; z-index: 1;'>%</th></tr></thead><tbody>{linhas_html}</tbody></table></div>"

    legenda_html = "<div style='margin-top: 15px; font-size: 12px; color: #7f8c8d;'>"
    if mostrar_cronico and mostrar_especifico: legenda_html += "<span style='color: #d35400;'>⚠️ [CRÔNICO]:</span> Falhas recorrentes em múltiplos dias | <span style='color: #8e44ad;'>⚠️ [ESPECÍFICO]:</span> Falhas com alta ocorrência (3+), concentradas em uma máquina (80%+)."
    elif mostrar_cronico: legenda_html += "<span style='color: #d35400;'>⚠️ [CRÔNICO]:</span> Falhas recorrentes em múltiplos dias."
    elif mostrar_especifico: legenda_html += "<span style='color: #8e44ad;'>⚠️ [ESPECÍFICO]:</span> Falhas com alta ocorrência (3+), concentradas em uma máquina (80%+)."
    legenda_html += "</div>"
    tabela_html += legenda_html

    df_top10 = df_agrupado.head(10).copy()
    max_minutos = df_top10['Tempo'].max() if not df_top10.empty else 0
    
    if max_minutos > 1200: step = 240       
    elif max_minutos > 600: step = 120      
    elif max_minutos > 300: step = 60       
    elif max_minutos > 120: step = 30       
    elif max_minutos > 60: step = 15        
    else: step = 10                         

    tickvals_y1 = list(range(0, int(max_minutos) + step, step))
    ticktext_y1 = [f"{int(v // 60)}:{int(v % 60):02d}" for v in tickvals_y1]
    
    fig = go.Figure()
    custom_data_pareto = list(zip([f"{i+1}º — {desc}" for i, desc in enumerate(df_top10['descricao'])], [banco.minutos_para_string(m) for m in df_top10['Tempo']]))

    fig.add_trace(go.Bar(
        x=df_top10['cod_ocorrencia'], y=df_top10['Tempo'], name='Tempo Perdido', marker_color='#2c3e50', customdata=custom_data_pareto,
        hovertemplate="<b>Descrição:</b> %{customdata[0]}<br><b>Código:</b> %{x}<br><b>Tempo:</b> %{customdata[1]}<extra></extra>"
    ))

    fig.add_trace(go.Scatter(
        x=df_top10['cod_ocorrencia'], y=df_top10['Acumulado'], name='Impacto Acumulado (%)', mode='lines+markers+text',
        marker=dict(color='#f39c12', size=8), line=dict(color='#f39c12', width=3), text=[f"<b>{x:.0f}%</b>" for x in df_top10['Acumulado']],
        textposition="top center", textfont=dict(color='#d35400', size=13), yaxis='y2', hovertemplate="<b>Acumulado:</b> %{text}<extra></extra>"
    ))

    fig.update_layout(
        title=dict(text="Principais Causadores de Paradas (Top 10)", font=dict(size=16, color='#2c3e50')),
        xaxis=dict(type='category', title="", tickfont=dict(size=13), fixedrange=True),
        yaxis=dict(title="Tempo Perdido (Horas)", showgrid=True, gridcolor='#ecf0f1', tickfont=dict(size=13), tickvals=tickvals_y1, ticktext=ticktext_y1, fixedrange=True),
        yaxis2=dict(title="Impacto Acumulado (%)", overlaying='y', side='right', range=[0, 110], showgrid=False, tickfont=dict(size=13), ticksuffix="%", fixedrange=True),
        showlegend=False, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=40, b=0), height=altura_final, dragmode=False
    )

    col1, col2 = st.columns([5, 5])
    with col1:
        st.markdown("#### Ranking de Ocorrências")
        st.markdown(tabela_html, unsafe_allow_html=True)
    with col2: st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    st.markdown("<hr style='opacity: 0.2; margin-top: 30px; margin-bottom: 20px;'>", unsafe_allow_html=True)
    top_codigos = df_top10['cod_ocorrencia'].tolist()
    df_maq_cod = df[df['cod_ocorrencia'].isin(top_codigos)].groupby(['cod_ocorrencia', 'descricao', 'maquina'])['minutos'].sum().reset_index()

    if not df_maq_cod.empty:
        fig_maq = px.bar(
            df_maq_cod, x='cod_ocorrencia', y='minutos', color='maquina', barmode='group', 
            category_orders={'cod_ocorrencia': top_codigos}, color_discrete_map=mapa_cores_mestre,
            text=df_maq_cod['minutos'].apply(banco.minutos_para_string), custom_data=['descricao'] 
        )
        fig_maq.update_traces(textposition='outside', textfont=dict(size=11), cliponaxis=False, hovertemplate="<b>Descrição:</b> %{customdata[0]}<br><b>Código:</b> %{x}<br><b>Tempo:</b> %{text}<extra></extra>")
        fig_maq.update_layout(
            title=dict(text="Detalhamento das Ocorrências por Máquina (Top 10)", font=dict(size=16, color='#2c3e50')), xaxis_title="", yaxis_title="Tempo Perdido (Horas)",
            yaxis=dict(showgrid=True, gridcolor='#ecf0f1', tickvals=tickvals_y1, ticktext=ticktext_y1, fixedrange=True), xaxis=dict(fixedrange=True, type='category'),
            legend=dict(title="", orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5, bgcolor="rgba(0,0,0,0)", font=dict(size=13)),
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=40, b=80), height=500, dragmode=False
        )
        st.plotly_chart(fig_maq, use_container_width=True, config={'displayModeBar': False})