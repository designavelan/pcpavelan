import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import banco
import filtros
import streamlit.components.v1 as components # <--- Biblioteca necessária para o truque no celular

def classificar_status(row):
    cod = str(row['cod_ocorrencia']).strip().lower()
    if cod in ['none', 'nan', '']: return 'Trabalhando'
    tipo = str(row['tipo']).strip().upper()
    if 'DESNCONSIDERAR' in tipo or 'DESCONSIDERAR' in tipo: return 'Desconsiderar'
    if tipo == 'PARADO': return 'Parado'
    return 'Trabalhando'

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
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    df_nuvem['data_registro'] = pd.to_datetime(df_nuvem['data_registro']).dt.strftime('%Y-%m-%d')
    df_nuvem['das_dt'] = pd.to_datetime(df_nuvem['das'], format='%H:%M', errors='coerce')
    df_nuvem['as_dt'] = pd.to_datetime(df_nuvem['as_hora'], format='%H:%M', errors='coerce')
    df_nuvem['minutos'] = (df_nuvem['as_dt'] - df_nuvem['das_dt']).dt.total_seconds() / 60.0
    df_nuvem.loc[df_nuvem['minutos'] < 0, 'minutos'] += 24 * 60 

    if not df_codigos.empty:
        df_codigos['codigo'] = df_codigos['codigo'].astype(str).str.strip()
        df_nuvem['cod_ocorrencia'] = df_nuvem['cod_ocorrencia'].astype(str).str.strip()
        df_nuvem = df_nuvem.merge(df_codigos[['codigo', 'descricao', 'tipo']], left_on='cod_ocorrencia', right_on='codigo', how='left')
        df_nuvem['descricao'] = df_nuvem['descricao'].fillna("Sem Descrição")
    else:
        df_nuvem['tipo'] = None
        df_nuvem['descricao'] = "Desconhecido"

    df_nuvem['status_real'] = df_nuvem.apply(classificar_status, axis=1)

    df_filt = df_nuvem.copy()
    if filtros_selecionados['de'] != "[ Todas ]": df_filt = df_filt[df_filt['data_registro'] >= filtros_selecionados['de']]
    if filtros_selecionados['ate'] != "[ Todas ]": df_filt = df_filt[df_filt['data_registro'] <= filtros_selecionados['ate']]
    if filtros_selecionados['setor'] != "[ Todos ]": df_filt = df_filt[df_filt['setor'] == filtros_selecionados['setor']]
    if filtros_selecionados['maquina'] != "[ Todas ]": df_filt = df_filt[df_filt['maquina'] == filtros_selecionados['maquina']]

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
    
    for _, row in df_agrup_ocor.iterrows():
        perc = (row['minutos'] / total_parado_geral) * 100 if total_parado_geral > 0 else 0
        texto_opcao = f"{row['cod_ocorrencia']} - {row['descricao']} ({perc:.1f}%)"
        opcoes_dropdown.append(texto_opcao)
        mapa_ocorrencias[texto_opcao] = row['cod_ocorrencia']

    col_sel1, col_sel2, col_sel3 = st.columns([2, 6, 2])
    with col_sel2:
        st.markdown("<h4 style='text-align: center;'>Análise de Impacto por Ocorrência</h4>", unsafe_allow_html=True)
        selecao = st.selectbox("", opcoes_dropdown, label_visibility="collapsed")
        
        # --- TRUQUE JS: Bloqueia o teclado virtual no celular ---
        js_bloqueio_teclado = """
        <script>
            // Pega o input escondido dentro do selectbox da tela e aplica o bloqueio
            const inputs = window.parent.document.querySelectorAll('div[data-baseweb="select"] input');
            inputs.forEach(input => {
                input.setAttribute('readonly', 'true');
                input.style.caretColor = 'transparent'; 
                input.style.cursor = 'pointer';
            });
        </script>
        """
        components.html(js_bloqueio_teclado, height=0)

    st.markdown("<br>", unsafe_allow_html=True)

    if selecao != "[ Selecione um Problema ]":
        codigo_escolhido = mapa_ocorrencias[selecao]
        df_alvo = df_parado[df_parado['cod_ocorrencia'] == codigo_escolhido]
        
        total_minutos_alvo = df_alvo['minutos'].sum()
        qtd_ocorrencias = len(df_alvo)
        
        media_minutos = total_minutos_alvo / qtd_ocorrencias if qtd_ocorrencias > 0 else 0
        if media_minutos < 60:
            texto_media = f"{int(media_minutos)} min"
        else:
            texto_media = banco.minutos_para_string(media_minutos)
            
        df_maq_alvo = df_alvo.groupby('maquina')['minutos'].sum().reset_index().sort_values(by='minutos', ascending=False)
        maq_mais_afetada = df_maq_alvo.iloc[0]['maquina'] if not df_maq_alvo.empty else "-"
        cor_maq_afetada = mapa_cores_mestre.get(maq_mais_afetada, "#555")
        
        k1, k2, k3, k4 = st.columns(4)
        with k1: criar_cartao("Total Tempo Perdido", banco.minutos_para_string(total_minutos_alvo))
        with k2: criar_cartao("Qtd. Ocorrências", f"{qtd_ocorrencias}")
        with k3: criar_cartao("Média por Ocorrência", texto_media)
        with k4: criar_cartao("Máquina Mais Afetada", f"{maq_mais_afetada}", cor_titulo="#777", cor_secundaria=cor_maq_afetada)

        st.markdown("<br><hr style='opacity: 0.3;'><br>", unsafe_allow_html=True)

        g1, g2 = st.columns(2)
        with g1:
            st.markdown(f"<h5 style='text-align: center; color: #444;'>Distribuição do Tempo Perdido</h5>", unsafe_allow_html=True)
            
            fig_pie = px.pie(
                df_maq_alvo, values='minutos', names='maquina', 
                color='maquina', color_discrete_map=mapa_cores_mestre, hole=0
            )
            fig_pie.update_traces(textinfo='label+percent', textposition='outside', marker=dict(line=dict(color='#fff', width=1)))
            fig_pie.update_layout(showlegend=False, margin=dict(t=30, b=10, l=10, r=10), height=350, paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})

        with g2:
            st.markdown(f"<h5 style='text-align: center; color: #444;'>Evolução Diária ({selecao.split(' (')[0]})</h5>", unsafe_allow_html=True)
            
            df_dia = df_alvo.groupby(['data_registro', 'maquina'])['minutos'].sum().reset_index()
            dias_pt = {0: 'SEG', 1: 'TER', 2: 'QUA', 3: 'QUI', 4: 'SEX', 5: 'SAB', 6: 'DOM'}
            df_dia['data_formatada'] = pd.to_datetime(df_dia['data_registro']).apply(
                lambda x: f"{dias_pt[x.weekday()]}<br>{x.strftime('%d/%m')}"
            )
            df_dia = df_dia.sort_values('data_registro')
            ordem_datas = df_dia['data_formatada'].unique().tolist()
            
            fig_line = px.line(
                df_dia, x='data_formatada', y='minutos', color='maquina', markers=True,
                category_orders={"data_formatada": ordem_datas},
                color_discrete_map=mapa_cores_mestre 
            )
            
            max_val = df_dia['minutos'].max() if not df_dia.empty else 60
            passo = max(15, int(max_val / 5)) 
            tickvals = list(range(0, int(max_val) + passo + 1, passo))
            ticktext = [banco.minutos_para_string(v) for v in tickvals]
            
            fig_line.update_layout(
                dragmode=False, xaxis_title="", yaxis_title="Tempo Perdido (Horas)",
                xaxis=dict(fixedrange=True),
                yaxis=dict(fixedrange=True, tickmode='array', tickvals=tickvals, ticktext=ticktext, range=[0, max_val * 1.1], gridcolor='rgba(0,0,0,0.05)'),
                legend=dict(title="", orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(t=30, b=10, l=10, r=10), height=350, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0.02)"
            )
            st.plotly_chart(fig_line, use_container_width=True, config={'displayModeBar': False})