import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import banco
import filtros
import streamlit.components.v1 as components 

def criar_cartao(titulo, valor_principal, valor_secundario="", cor_secundaria="#666666", cor_titulo="#777777"):
    html = f"""
    <div style="background-color: #ffffff; padding: 20px 10px; border-radius: 8px; border: 1px solid #eaeaea; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05); height: 100%;">
        <p style="margin: 0 0 5px 0; color: {cor_titulo}; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; font-weight: 700;">{titulo}</p>
        <h2 style="margin: 0; color: #222222; font-size: 36px; font-weight: 800;">{valor_principal}</h2>
        <p style="margin: 5px 0 0 0; color: {cor_secundaria}; font-size: 16px; font-weight: bold;">{valor_secundario}</p>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def renderizar(df_nuvem, df_codigos, filtros_selecionados):
    filtros.renderizar_cabecalho_global("Ocorrências")
    st.markdown("<br>", unsafe_allow_html=True)
    
    df_filt = filtros.aplicar_filtros_analiticos(df_nuvem, df_codigos, filtros_selecionados)
    if df_filt.empty:
        st.warning("⚠️ Nenhum tempo de parada registrado para esta combinação de filtros.")
        return

    df_parado = df_filt[df_filt['status_real'] == 'Parado'].copy()
    if df_parado.empty:
        st.warning("⚠️ Nenhum tempo de parada registrado para esta combinação de filtros.")
        return

    lista_alfabetica_maq = sorted(df_filt['maquina'].unique())
    paleta_cores = px.colors.qualitative.Plotly * 10
    mapa_cores_mestre = {maq: paleta_cores[i] for i, maq in enumerate(lista_alfabetica_maq)}

    total_parado_geral = df_parado['minutos'].sum()
    df_agrup_ocor = df_parado.groupby(['cod_ocorrencia', 'descricao'])['minutos'].sum().reset_index()
    df_agrup_ocor = df_agrup_ocor.sort_values(by='minutos', ascending=False)
    
    opcoes_dropdown = ["[ Selecione um Problema ]"]
    mapa_ocorrencias = {} 
    codigos_lista = []
    
    for i, row in df_agrup_ocor.iterrows():
        perc = (row['minutos'] / total_parado_geral) * 100 if total_parado_geral > 0 else 0
        texto_opcao = f"{row['cod_ocorrencia']} - {row['descricao']} ({perc:.1f}%)"
        opcoes_dropdown.append(texto_opcao)
        mapa_ocorrencias[texto_opcao] = str(row['cod_ocorrencia'])
        codigos_lista.append(str(row['cod_ocorrencia']))
        
    codigo_alvo = st.session_state.get('codigo_alvo')
    codigo_salvo = st.session_state.get('ocorrencia_selecionada', "")
    codigo_final = None
    
    if codigo_alvo and str(codigo_alvo) in codigos_lista:
        codigo_final = str(codigo_alvo)
        st.session_state['codigo_alvo'] = None 
        st.session_state['ocorrencia_selecionada'] = codigo_final 
    elif codigo_salvo == "NENHUM": codigo_final = None
    elif codigo_salvo and str(codigo_salvo) in codigos_lista: codigo_final = str(codigo_salvo)
    elif len(codigos_lista) > 0:
        codigo_final = codigos_lista[0]
        st.session_state['ocorrencia_selecionada'] = codigo_final

    idx_alvo = 0
    if codigo_final:
        for i, opcao in enumerate(opcoes_dropdown):
            if i > 0 and mapa_ocorrencias[opcao] == codigo_final:
                idx_alvo = i
                break 

    def ao_mudar_ocorrencia():
        val = st.session_state.seletor_ocorrencia_ui
        if val != "[ Selecione um Problema ]": st.session_state.ocorrencia_selecionada = val.split(" - ")[0]
        else: st.session_state.ocorrencia_selecionada = "NENHUM"

    col_sel1, col_sel2, col_sel3 = st.columns([2, 6, 2])
    with col_sel2:
        st.markdown("<h4 style='text-align: center;'>Análise de Impacto por Ocorrência</h4>", unsafe_allow_html=True)
        selecao = st.selectbox("", opcoes_dropdown, index=idx_alvo, key="seletor_ocorrencia_ui", on_change=ao_mudar_ocorrencia, label_visibility="collapsed")
        
        js_bloqueio_teclado = """
        <script>
            const inputs = window.parent.document.querySelectorAll('div[data-baseweb="select"] input');
            inputs.forEach(input => { input.setAttribute('readonly', 'true'); input.style.caretColor = 'transparent'; input.style.cursor = 'pointer'; });
        </script>
        """
        components.html(js_bloqueio_teclado, height=0)

    st.markdown("<br>", unsafe_allow_html=True)

    if selecao != "[ Selecione um Problema ]":
        codigo_escolhido = mapa_ocorrencias[selecao]
        df_alvo = df_parado[df_parado['cod_ocorrencia'] == codigo_escolhido]
        
        total_minutos_alvo = df_alvo['minutos'].sum()
        qtd_ocorrencias = len(df_alvo)
        perc_relativo = (total_minutos_alvo / total_parado_geral) * 100 if total_parado_geral > 0 else 0
        
        qtd_dias = df_alvo['data_registro'].nunique()
        texto_dias = f"em {qtd_dias} dia" if qtd_dias == 1 else f"em {qtd_dias} dias"

        media_minutos = total_minutos_alvo / qtd_ocorrencias if qtd_ocorrencias > 0 else 0
        texto_media = f"{int(media_minutos)} min" if media_minutos < 60 else banco.minutos_para_string(media_minutos)
            
        df_maq_alvo = df_alvo.groupby('maquina')['minutos'].sum().reset_index().sort_values(by='minutos', ascending=False)
        maq_mais_afetada = df_maq_alvo.iloc[0]['maquina'] if not df_maq_alvo.empty else "-"
        cor_maq_afetada = mapa_cores_mestre.get(maq_mais_afetada, "#555")
        desc_problema = df_alvo.iloc[0]['descricao'] if not df_alvo.empty else "Desconhecido"

        st.markdown(f"""
        <div style="background-color: #f8f9fa; border-left: 5px solid #2980b9; padding: 20px; border-radius: 8px; margin-bottom: 25px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <h4 style="margin-top: 0; color: #2c3e50; font-size: 18px;">💡 Resumo da Ocorrência</h4>
            <p style="font-size: 15px; color: #444; line-height: 1.6; margin-bottom: 0;">
                O problema <b>{desc_problema} ({codigo_escolhido})</b> gerou um total de <b>{banco.minutos_para_string(total_minutos_alvo)}</b> de tempo perdido {texto_dias}, o que representa <b>{perc_relativo:.1f}%</b> de todas as paradas do setor.<br>
                Foram registrados <b>{qtd_ocorrencias} apontamentos</b> dessa falha, com uma média de <b>{texto_media}</b> por parada. A máquina mais impactada foi a <b>{maq_mais_afetada}</b>.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        k1, k2, k3, k4 = st.columns(4)
        with k1: 
            st.markdown("<div class='kpis-container'></div>", unsafe_allow_html=True)
            criar_cartao("Total Tempo Perdido", banco.minutos_para_string(total_minutos_alvo))
        with k2: criar_cartao("Qtd. Ocorrências", f"{qtd_ocorrencias}")
        with k3: criar_cartao("Média por Ocorrência", texto_media)
        with k4: criar_cartao("Máquina Mais Afetada", f"{maq_mais_afetada}", cor_titulo="#777", cor_secundaria=cor_maq_afetada)

        st.markdown("<br><hr style='opacity: 0.3;'><br>", unsafe_allow_html=True)

        g1, g2 = st.columns(2)
        with g1:
            st.markdown("<div class='graficos-container'></div>", unsafe_allow_html=True)
            st.markdown(f"<h5 style='text-align: center; color: #444;'>Distribuição do Tempo Perdido</h5>", unsafe_allow_html=True)
            
            fig_pie = px.pie(df_maq_alvo, values='minutos', names='maquina', color='maquina', color_discrete_map=mapa_cores_mestre, hole=0)
            fig_pie.update_traces(textinfo='label+percent', textposition='outside', marker=dict(line=dict(color='#fff', width=1)))
            fig_pie.update_layout(showlegend=False, margin=dict(t=30, b=10, l=10, r=10), height=350, paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})

        with g2:
            st.markdown(f"<h5 style='text-align: center; color: #444;'>Evolução Diária ({selecao.split(' (')[0]})</h5>", unsafe_allow_html=True)
            
            df_dia = df_alvo.groupby(['data_registro', 'maquina'])['minutos'].sum().reset_index()
            dias_pt = {0: 'SEG', 1: 'TER', 2: 'QUA', 3: 'QUI', 4: 'SEX', 5: 'SAB', 6: 'DOM'}
            df_dia['data_formatada'] = pd.to_datetime(df_dia['data_registro']).apply(lambda x: f"{dias_pt[x.weekday()]}<br>{x.strftime('%d/%m')}")
            df_dia = df_dia.sort_values('data_registro')
            ordem_datas = df_dia['data_formatada'].unique().tolist()
            
            fig_line = px.line(
                df_dia, x='data_formatada', y='minutos', color='maquina', markers=True,
                category_orders={"data_formatada": ordem_datas}, color_discrete_map=mapa_cores_mestre 
            )
            
            max_val = df_dia['minutos'].max() if not df_dia.empty else 60
            passo = max(15, int(max_val / 5)) 
            tickvals = list(range(0, int(max_val) + passo + 1, passo))
            ticktext = [banco.minutos_para_string(v) for v in tickvals]
            
            fig_line.update_layout(
                dragmode=False, xaxis_title="", yaxis_title="Tempo Perdido (Horas)", xaxis=dict(fixedrange=True),
                yaxis=dict(fixedrange=True, tickmode='array', tickvals=tickvals, ticktext=ticktext, range=[0, max_val * 1.1], gridcolor='rgba(0,0,0,0.05)'),
                legend=dict(title="", orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), margin=dict(t=30, b=10, l=10, r=10), height=350, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0.02)"
            )
            st.plotly_chart(fig_line, use_container_width=True, config={'displayModeBar': False})