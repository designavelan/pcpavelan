import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import altair as alt
import banco
import textwrap

def calcular_minutos_str(hora_str):
    try: return int(hora_str.split(':')[0]) * 60 + int(hora_str.split(':')[1])
    except: return 0

def formatar_minutos(minutos):
    h = int(minutos // 60)
    m = int(minutos % 60)
    if h > 0: return f"{h}:{m:02d}m"
    return f"{m}m"

def processar_dados_periodo(df_nuvem, df_codigos, data_de, data_ate, setor_filtro, maq_filtro):
    df = df_nuvem.copy()
    if df.empty or 'data_registro' not in df.columns: return pd.DataFrame()
    
    df['data_registro_dt'] = pd.to_datetime(df['data_registro'], errors='coerce')
    df = df[(df['data_registro_dt'] >= pd.to_datetime(data_de)) & (df['data_registro_dt'] <= pd.to_datetime(data_ate))]
    
    if setor_filtro != "[ Todos ]": df = df[df['setor'] == setor_filtro]
    if maq_filtro != "[ Todas ]": df = df[df['maquina'] == maq_filtro]
    
    if df.empty: return df
    
    cfg = banco.obter_configuracoes()
    m_das_min = calcular_minutos_str(cfg.get('manha_das', '07:30'))
    m_as_min = calcular_minutos_str(cfg.get('manha_as', '11:50'))
    t_das_min = calcular_minutos_str(cfg.get('tarde_das', '13:30'))
    t_as_min = calcular_minutos_str(cfg.get('tarde_as', '17:30'))
    
    lm_das_min = calcular_minutos_str(cfg.get('lanche_m_das', '')) if cfg.get('lanche_m_das') else -1
    lm_as_min = calcular_minutos_str(cfg.get('lanche_m_as', '')) if cfg.get('lanche_m_as') else -1
    lt_das_min = calcular_minutos_str(cfg.get('lanche_t_das', '')) if cfg.get('lanche_t_das') else -1
    lt_as_min = calcular_minutos_str(cfg.get('lanche_t_as', '')) if cfg.get('lanche_t_as') else -1

    def calcular_minutos_uteis_no_turno(das_min, as_min):
        if as_min < das_min: as_min += 1440
        total = 0
        for m in range(int(das_min), int(as_min)):
            is_turno = (m_das_min <= m < m_as_min) or (t_das_min <= m < t_as_min)
            is_lanche = (lm_das_min <= m < lm_as_min) or (lt_das_min <= m < lt_as_min)
            if is_turno and not is_lanche:
                total += 1
        return total
    
    if 'tipo' not in df.columns: df['tipo'] = 'PARADA'
    
    mask_exclude = df['tipo'].astype(str).str.strip().str.upper().isin(['PRODUÇÃO', 'LIVRE', 'A REALIZAR'])
    df_paradas = df[~mask_exclude].copy()
    
    if not df_paradas.empty:
        df_paradas['das_min'] = df_paradas['das'].astype(str).apply(calcular_minutos_str)
        df_paradas['as_min'] = df_paradas['as_hora'].astype(str).apply(calcular_minutos_str)
        
        df_paradas['duracao'] = df_paradas.apply(lambda row: calcular_minutos_uteis_no_turno(row['das_min'], row['as_min']), axis=1)
        
        if not df_codigos.empty:
            df_cod = df_codigos[['codigo', 'descricao', 'tipo']].copy()
            df_cod['codigo'] = df_cod['codigo'].astype(str).str.strip()
            df_cod = df_cod.rename(columns={'descricao': 'desc_mestre', 'tipo': 'tipo_mestre'})
            
            df_paradas['cod_ocorrencia'] = df_paradas['cod_ocorrencia'].astype(str).str.strip()
            df_paradas = df_paradas.merge(df_cod, left_on='cod_ocorrencia', right_on='codigo', how='left')
            
            df_paradas['classificacao'] = df_paradas['tipo_mestre'].combine_first(df_paradas['tipo']).astype(str).str.strip().str.upper()
            df_paradas['descricao_falha'] = df_paradas['desc_mestre'].fillna('Desconhecido')
        else:
            df_paradas['classificacao'] = df_paradas['tipo'].astype(str).str.strip().str.upper()
            df_paradas['descricao_falha'] = 'Desconhecido'
            
        df_paradas = df_paradas[~df_paradas['classificacao'].str.contains('NÃO CONTA|DESCONSIDERAR')]
            
    return df_paradas

def calcular_kpis(df_paradas):
    if df_paradas.empty:
        return 0, 0, 0, 0, "Nenhum (0m)", "Nenhuma (0m)", pd.DataFrame(), pd.DataFrame()
        
    df_problema = df_paradas[df_paradas['classificacao'].isin(['PARADA', 'RETRABALHO'])]
    df_rotina = df_paradas[df_paradas['classificacao'] == 'ROTINA']
    
    min_problema = df_problema['duracao'].sum() if not df_problema.empty else 0
    min_rotina = df_rotina['duracao'].sum() if not df_rotina.empty else 0
    min_total = min_problema + min_rotina
    
    mttr = min_problema / len(df_problema) if not df_problema.empty and len(df_problema) > 0 else 0
    
    ofensor_prob = "Nenhum (0m)"
    if not df_problema.empty and min_problema > 0:
        agrup_prob = df_problema.groupby('descricao_falha')['duracao'].sum().sort_values(ascending=False)
        ofensor_prob = f"{agrup_prob.index[0]} ({formatar_minutos(agrup_prob.iloc[0])})"
        
    ofensor_rot = "Nenhuma (0m)"
    if not df_rotina.empty and min_rotina > 0:
        agrup_rot = df_rotina.groupby('descricao_falha')['duracao'].sum().sort_values(ascending=False)
        ofensor_rot = f"{agrup_rot.index[0]} ({formatar_minutos(agrup_rot.iloc[0])})"
        
    return min_total, min_problema, min_rotina, mttr, ofensor_prob, ofensor_rot, df_problema, df_rotina


def renderizar(df_nuvem, df_codigos, filtros_selecionados):
    st.markdown("""
        <style>
        .kpi-card { background:#fff; padding:20px; border-radius:12px; border:1px solid #e0e0e0; box-shadow:0 4px 6px rgba(0,0,0,0.05); text-align:center; height: 100%; display: flex; flex-direction: column; justify-content: center; }
        .kpi-title { color:#7f8c8d; font-size:14px; font-weight:700; text-transform:uppercase; margin-bottom:10px; letter-spacing:0.5px; }
        .kpi-value { font-size:38px; font-weight:900; line-height:1.1; margin-bottom:5px; }
        .kpi-sub { font-size:13px; color:#95a5a6; font-weight:600; }
        .val-red { color:#c0392b; } .val-blue { color:#2980b9; } .val-orange { color:#e67e22; } .val-dark { color:#2c3e50; }
        
        .box-resumo { background:#fdfefe; border-left:4px solid #f1c40f; padding:18px; border-radius:8px; border-top:1px solid #eee; border-right:1px solid #eee; border-bottom:1px solid #eee; box-shadow:0 2px 4px rgba(0,0,0,0.02); margin-bottom: 20px;}
        .box-resumo p { margin:0; color:#555; font-size:14px; line-height:1.6; }
        .box-resumo b { color:#2c3e50; }
        
        ::-webkit-scrollbar { display: none; }
        </style>
    """, unsafe_allow_html=True)

    data_de = filtros_selecionados.get('de')
    data_ate = filtros_selecionados.get('ate')
    setor = filtros_selecionados.get('setor')
    maquina = filtros_selecionados.get('maquina')
    
    if data_de == "[ Todas ]" or not data_de: 
        st.warning("Selecione um período válido no filtro superior.")
        return

    is_single_day = (data_de == data_ate)
    qtd_dias = (pd.to_datetime(data_ate) - pd.to_datetime(data_de)).days + 1

    cfg = banco.obter_configuracoes()
    m_das = cfg.get('manha_das', '07:30')
    m_as = cfg.get('manha_as', '11:50')
    t_das = cfg.get('tarde_das', '13:30')
    t_as = cfg.get('tarde_as', '17:30')
    
    m_das_min = calcular_minutos_str(m_das)
    m_as_min = calcular_minutos_str(m_as)
    t_das_min = calcular_minutos_str(t_das)
    t_as_min = calcular_minutos_str(t_as)

    # Coleta de Parâmetros de UI no Banco
    altura_graficos = int(banco.obter_memoria_sistema('Análise', 'Geral', 'altura_graficos', 500))
    tamanho_valores = int(banco.obter_memoria_sistema('Análise', 'Geral', 'tamanho_valores', 16))
    tamanho_labels = int(banco.obter_memoria_sistema('Análise', 'Geral', 'tamanho_labels', 14))
    tamanho_titulos = int(banco.obter_memoria_sistema('Análise', 'Geral', 'tamanho_titulos', 15))

    total_timeline_min = max(1, t_as_min - m_das_min)
    total_disp_min = total_timeline_min * qtd_dias

    expr_horas = "floor(datum.value / 60) > 0 ? floor(datum.value / 60) + ':' + (datum.value % 60 < 10 ? '0' : '') + (datum.value % 60) + 'm' : (datum.value % 60) + 'm'"

    aba_geral, aba_comp = st.tabs(["📊 Visão Geral do Período", "⚖️ Comparativo de Dias"])

    # ==========================================
    # 📊 SUB-ABA 1: VISÃO GERAL
    # ==========================================
    with aba_geral:
        df_paradas = processar_dados_periodo(df_nuvem, df_codigos, data_de, data_ate, setor, maquina)
        min_total, min_prob, min_rot, mttr, ofensor_prob, ofensor_rot, df_prob, df_rot = calcular_kpis(df_paradas)
        
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"<div class='kpi-card'><div class='kpi-title'>🩸 Tempo Útil Perdido</div><div class='kpi-value val-red'>{formatar_minutos(min_total)}</div><div class='kpi-sub'>({formatar_minutos(min_prob)} Prob. | {formatar_minutos(min_rot)} Rotina)</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='kpi-card'><div class='kpi-title'>⏱️ MTTR (Problemas)</div><div class='kpi-value val-blue'>{int(mttr)}m</div><div class='kpi-sub'>Tempo médio de solução</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='kpi-card'><div class='kpi-title'>🔴 Pior Ofensor (Parada)</div><div class='kpi-value val-red' style='font-size:24px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>{ofensor_prob.split(' (')[0]}</div><div class='kpi-sub'>Tempo: {ofensor_prob.split('(')[-1].replace(')','')}</div></div>", unsafe_allow_html=True)
        c4.markdown(f"<div class='kpi-card'><div class='kpi-title'>🟠 Maior Rotina</div><div class='kpi-value val-orange' style='font-size:24px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>{ofensor_rot.split(' (')[0]}</div><div class='kpi-sub'>Tempo: {ofensor_rot.split('(')[-1].replace(')','')}</div></div>", unsafe_allow_html=True)
        
        st.markdown("<hr style='opacity:0.2;'>", unsafe_allow_html=True)

        # ==========================================
        # 🏆 BLOCO 3: RANKINGS E PARETOS HORIZONTAIS
        # ==========================================
        df_est = banco.obter_estrutura()
        if setor != "[ Todos ]": df_est = df_est[df_est['setor'] == setor]
        if maquina != "[ Todas ]": df_est = df_est[df_est['maquina'] == maquina]
        todas_maquinas = df_est['maquina'].dropna().unique().tolist()
        
        agrup_maq = pd.DataFrame()
        if not df_prob.empty and min_prob > 0:
            agrup_maq = df_prob.groupby('maquina')['duracao'].sum().reset_index()
            agrup_maq = agrup_maq[agrup_maq['duracao'] > 0]
            agrup_maq['tempo_str'] = agrup_maq['duracao'].apply(formatar_minutos)
            agrup_maq['pct'] = (agrup_maq['duracao'] / min_prob * 100).fillna(0)
            agrup_maq['label'] = agrup_maq.apply(lambda x: f"{x['tempo_str']} ({x['pct']:.1f}%)", axis=1)
            
        disp_data = []
        for maq in todas_maquinas:
            min_prob_maq = df_prob[df_prob['maquina'] == maq]['duracao'].sum() if not df_prob.empty else 0
            disp_pct = max(0, 100 - (min_prob_maq / total_disp_min * 100))
            disp_data.append({'maquina': maq, 'disponibilidade': disp_pct, 'perdido_str': formatar_minutos(min_prob_maq)})
        
        df_disp = pd.DataFrame(disp_data)
        if not df_disp.empty:
            df_disp['label'] = df_disp['disponibilidade'].apply(lambda x: f"{x:.1f}%")

        agrup_prob = pd.DataFrame()
        if not df_prob.empty and min_prob > 0:
            agrup_prob = df_prob.groupby('descricao_falha')['duracao'].sum().reset_index()
            agrup_prob = agrup_prob[agrup_prob['duracao'] > 0]
            agrup_prob['tempo_str'] = agrup_prob['duracao'].apply(formatar_minutos)
            agrup_prob['pct'] = (agrup_prob['duracao'] / min_prob * 100).fillna(0)
            agrup_prob['label'] = agrup_prob.apply(lambda x: f"{x['tempo_str']} ({x['pct']:.1f}%)", axis=1)
            agrup_prob['descricao_quebrada'] = agrup_prob['descricao_falha'].apply(lambda x: ' | '.join(textwrap.wrap(str(x), width=30)))

        agrup_rot = pd.DataFrame()
        if not df_rot.empty and min_rot > 0:
            agrup_rot = df_rot.groupby('descricao_falha')['duracao'].sum().reset_index()
            agrup_rot = agrup_rot[agrup_rot['duracao'] > 0]
            agrup_rot['tempo_str'] = agrup_rot['duracao'].apply(formatar_minutos)
            agrup_rot['pct'] = (agrup_rot['duracao'] / min_rot * 100).fillna(0)
            agrup_rot['label'] = agrup_rot.apply(lambda x: f"{x['tempo_str']} ({x['pct']:.1f}%)", axis=1)
            agrup_rot['descricao_quebrada'] = agrup_rot['descricao_falha'].apply(lambda x: ' | '.join(textwrap.wrap(str(x), width=30)))

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.markdown("### 🏆 Piores Máquinas (Paradas/Problemas)")
            if not agrup_maq.empty:
                max_dur_maq = agrup_maq['duracao'].max()
                thresh_maq = max_dur_maq * 0.15 if max_dur_maq > 0 else 1
                
                base_maq = alt.Chart(agrup_maq).encode(
                    x=alt.X('duracao:Q', title='Tempo Perdido', axis=alt.Axis(labelExpr=expr_horas)),
                    y=alt.Y('maquina:N', sort=alt.EncodingSortField(field="duracao", order="descending"), title=None, axis=alt.Axis(labelOverlap=False)), 
                    tooltip=[alt.Tooltip('maquina:N', title='Máquina'), alt.Tooltip('tempo_str:N', title='Tempo Perdido')]
                )
                bars_maq = base_maq.mark_bar(color='#e74c3c')
                text_maq_in = base_maq.transform_filter(alt.datum.duracao > thresh_maq).mark_text(
                    align='right', dx=-5, color='white', baseline='middle', size=tamanho_valores
                ).encode(text='label:N')
                text_maq_out = base_maq.transform_filter(alt.datum.duracao <= thresh_maq).mark_text(
                    align='left', dx=5, color='#2c3e50', baseline='middle', size=tamanho_valores
                ).encode(text='label:N')
                
                chart_maq = (bars_maq + text_maq_in + text_maq_out).properties(height=altura_graficos).configure_axis(
                    labelFontSize=tamanho_labels, titleFontSize=tamanho_titulos
                )
                st.altair_chart(chart_maq, use_container_width=True)
            else:
                st.write("Sem problemas registrados no período.")

        with col_m2:
            st.markdown("### 📈 Ranking de Disponibilidade (%)")
            if not df_disp.empty:
                base_disp = alt.Chart(df_disp).encode(
                    x=alt.X('disponibilidade:Q', title='Disponibilidade (%)', scale=alt.Scale(domain=[0, 100])),
                    y=alt.Y('maquina:N', sort=alt.EncodingSortField(field="disponibilidade", order="ascending"), title=None, axis=alt.Axis(labelOverlap=False)), 
                    tooltip=[alt.Tooltip('maquina:N', title='Máquina'), alt.Tooltip('disponibilidade:Q', title='Disponibilidade (%)', format='.1f'), alt.Tooltip('perdido_str:N', title='Tempo Perdido (Problema)')]
                )
                bars_disp = base_disp.mark_bar(color='#2ecc71')
                text_disp_in = base_disp.transform_filter(alt.datum.disponibilidade > 15).mark_text(
                    align='right', dx=-5, color='#2c3e50', baseline='middle', size=tamanho_valores
                ).encode(text='label:N')
                text_disp_out = base_disp.transform_filter(alt.datum.disponibilidade <= 15).mark_text(
                    align='left', dx=5, color='#2c3e50', baseline='middle', size=tamanho_valores
                ).encode(text='label:N')
                
                chart_disp = (bars_disp + text_disp_in + text_disp_out).properties(height=altura_graficos).configure_axis(
                    labelFontSize=tamanho_labels, titleFontSize=tamanho_titulos
                )
                st.altair_chart(chart_disp, use_container_width=True)
            else:
                st.write("Nenhuma máquina encontrada na estrutura.")

        st.markdown("<hr style='opacity:0.2;'>", unsafe_allow_html=True)
        col_p1, col_p2 = st.columns(2)
        
        with col_p1:
            st.markdown("### 🔴 Pareto: Top 10 Paradas (Problemas)")
            if not agrup_prob.empty:
                max_dur_prob = agrup_prob['duracao'].max()
                thresh_prob = max_dur_prob * 0.15 if max_dur_prob > 0 else 1
                
                base_prob = alt.Chart(agrup_prob.head(10)).encode(
                    x=alt.X('duracao:Q', title='Tempo Consumido', axis=alt.Axis(labelExpr=expr_horas)),
                    y=alt.Y('descricao_quebrada:N', sort=alt.EncodingSortField(field="duracao", order="descending"), title=None, axis=alt.Axis(labelAngle=0, labelOverlap=False, labelExpr="split(datum.value, ' | ')")),
                    tooltip=[alt.Tooltip('descricao_falha:N', title='Motivo'), alt.Tooltip('tempo_str:N', title='Tempo Consumido')]
                )
                bars_prob = base_prob.mark_bar(color='#c0392b')
                text_prob_in = base_prob.transform_filter(alt.datum.duracao > thresh_prob).mark_text(
                    align='right', dx=-5, color='white', baseline='middle', size=tamanho_valores
                ).encode(text='label:N')
                text_prob_out = base_prob.transform_filter(alt.datum.duracao <= thresh_prob).mark_text(
                    align='left', dx=5, color='#2c3e50', baseline='middle', size=tamanho_valores
                ).encode(text='label:N')
                
                chart_prob = (bars_prob + text_prob_in + text_prob_out).properties(height=altura_graficos).configure_axis(
                    labelFontSize=tamanho_labels, titleFontSize=tamanho_titulos
                )
                st.altair_chart(chart_prob, use_container_width=True)
            else:
                st.write("Nenhum problema registrado no período.")

        with col_p2:
            st.markdown("### 🟠 Pareto: Top 10 Rotinas (Processos)")
            if not agrup_rot.empty:
                max_dur_rot = agrup_rot['duracao'].max()
                thresh_rot = max_dur_rot * 0.15 if max_dur_rot > 0 else 1
                
                base_rot = alt.Chart(agrup_rot.head(10)).encode(
                    x=alt.X('duracao:Q', title='Tempo Consumido', axis=alt.Axis(labelExpr=expr_horas)),
                    y=alt.Y('descricao_quebrada:N', sort=alt.EncodingSortField(field="duracao", order="descending"), title=None, axis=alt.Axis(labelAngle=0, labelOverlap=False, labelExpr="split(datum.value, ' | ')")),
                    tooltip=[alt.Tooltip('descricao_falha:N', title='Processo'), alt.Tooltip('tempo_str:N', title='Tempo Consumido')]
                )
                bars_rot = base_rot.mark_bar(color='#f39c12')
                text_rot_in = base_rot.transform_filter(alt.datum.duracao > thresh_rot).mark_text(
                    align='right', dx=-5, color='#2c3e50', baseline='middle', size=tamanho_valores
                ).encode(text='label:N')
                text_rot_out = base_rot.transform_filter(alt.datum.duracao <= thresh_rot).mark_text(
                    align='left', dx=5, color='#2c3e50', baseline='middle', size=tamanho_valores
                ).encode(text='label:N')
                
                chart_rot = (bars_rot + text_rot_in + text_rot_out).properties(height=altura_graficos).configure_axis(
                    labelFontSize=tamanho_labels, titleFontSize=tamanho_titulos
                )
                st.altair_chart(chart_rot, use_container_width=True)
            else:
                st.write("Nenhuma rotina registrada no período.")

        # ==========================================
        # 🔎 BLOCO 4: ANÁLISE DE IMPACTO POR OCORRÊNCIA
        # ==========================================
        st.markdown("<hr style='opacity:0.2;'>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: #2c3e50; margin-bottom: 25px;'>🔎 Análise de Impacto por Ocorrência</h3>", unsafe_allow_html=True)

        if not df_paradas.empty and df_paradas['duracao'].sum() > 0:
            total_tempo_geral = df_paradas['duracao'].sum()
            
            agrup_oco = df_paradas.groupby(['cod_ocorrencia', 'descricao_falha', 'classificacao'])['duracao'].sum().reset_index()
            agrup_oco = agrup_oco[agrup_oco['duracao'] > 0].sort_values('duracao', ascending=False)
            
            opcoes_dropdown = []
            for _, row in agrup_oco.iterrows():
                pct_oco = (row['duracao'] / total_tempo_geral) * 100
                tag = "🔴 PARADA" if row['classificacao'] == "PARADA" else "🟠 ROTINA"
                opcoes_dropdown.append(f"{row['cod_ocorrencia']} - {row['descricao_falha']} ({pct_oco:.1f}%) [{tag}]")
                
            col_vazia1, col_menu, col_vazia2 = st.columns([1, 4, 1])
            with col_menu:
                selecao = st.selectbox("Selecione a ocorrência para detalhar:", opcoes_dropdown, label_visibility="collapsed")
                
            if selecao:
                cod_selecionado = selecao.split(" - ")[0].strip()
                df_sel = df_paradas[df_paradas['cod_ocorrencia'] == cod_selecionado].copy()
                
                tot_min_sel = df_sel['duracao'].sum()
                qtd_sel = len(df_sel)
                media_sel = tot_min_sel / qtd_sel if qtd_sel > 0 else 0
                maq_ofensor_sel = df_sel.groupby('maquina')['duracao'].sum().idxmax() if not df_sel.empty else "Nenhuma"
                pct_sel = (tot_min_sel / total_tempo_geral) * 100
                
                nome_limpo = selecao.split(' (')[0]
                texto_dia = "no período filtrado" if not is_single_day else f"no dia {data_de}"
                
                st.markdown(f"""
                <div class='box-resumo'>
                    <p style='margin-bottom: 8px;'><b>💡 Resumo da Ocorrência</b></p>
                    <p>O apontamento <b>{nome_limpo}</b> gerou um total de <b>{formatar_minutos(tot_min_sel)}</b> de tempo perdido {texto_dia}, o que representa <b>{pct_sel:.1f}%</b> de todas as interrupções do setor.</p>
                    <p>Foram registrados <b>{qtd_sel} apontamentos</b> dessa classificação, com uma média de <b>{int(media_sel)} min</b> por parada. A máquina mais impactada foi a <b>{maq_ofensor_sel}</b>.</p>
                </div>
                """, unsafe_allow_html=True)
                
                ck1, ck2, ck3, ck4 = st.columns(4)
                ck1.markdown(f"<div class='kpi-card'><div class='kpi-title'>TOTAL TEMPO PERDIDO</div><div class='kpi-value val-dark'>{formatar_minutos(tot_min_sel)}</div></div>", unsafe_allow_html=True)
                ck2.markdown(f"<div class='kpi-card'><div class='kpi-title'>QTD. OCORRÊNCIAS</div><div class='kpi-value val-dark'>{qtd_sel}</div></div>", unsafe_allow_html=True)
                ck3.markdown(f"<div class='kpi-card'><div class='kpi-title'>MÉDIA POR OCORRÊNCIA</div><div class='kpi-value val-dark'>{int(media_sel)} min</div></div>", unsafe_allow_html=True)
                ck4.markdown(f"<div class='kpi-card'><div class='kpi-title'>MÁQUINA MAIS AFETADA</div><div class='kpi-value val-dark' style='font-size:26px;'>{maq_ofensor_sel}</div></div>", unsafe_allow_html=True)
                
                st.markdown("<br>", unsafe_allow_html=True)
                cg1, cg2 = st.columns(2)
                
                with cg1:
                    st.markdown(f"<div style='text-align: center; color: #2c3e50; font-weight: bold; margin-bottom: 10px;'>Distribuição do Tempo Perdido</div>", unsafe_allow_html=True)
                    agrup_pizza = df_sel.groupby('maquina')['duracao'].sum().reset_index()
                    agrup_pizza['pct'] = (agrup_pizza['duracao'] / tot_min_sel * 100).fillna(0)
                    agrup_pizza['label'] = agrup_pizza.apply(lambda x: f"{formatar_minutos(x['duracao'])} ({x['pct']:.1f}%)", axis=1)
                    
                    base_pizza = alt.Chart(agrup_pizza).encode(
                        theta=alt.Theta(field="duracao", type="quantitative"),
                        color=alt.Color(field="maquina", type="nominal", legend=alt.Legend(title="Máquina")),
                        tooltip=['maquina', 'duracao']
                    )
                    pie = base_pizza.mark_arc(innerRadius=40)
                    text_pizza = base_pizza.mark_text(radiusOffset=20, color='#2c3e50', size=tamanho_valores).encode(text='label:N')
                    
                    chart_p = (pie + text_pizza).properties(height=350).configure_legend(
                        labelFontSize=tamanho_labels, titleFontSize=tamanho_titulos
                    )
                    st.altair_chart(chart_p, use_container_width=True)
                    
                with cg2:
                    st.markdown(f"<div style='text-align: center; color: #2c3e50; font-weight: bold; margin-bottom: 10px;'>Evolução Diária</div>", unsafe_allow_html=True)
                    df_sel['data_curta'] = df_sel['data_registro_dt'].dt.strftime('%d/%m')
                    agrup_linha = df_sel.groupby(['data_curta', 'maquina'])['duracao'].sum().reset_index()
                    agrup_linha['label'] = agrup_linha['duracao'].apply(formatar_minutos)
                    
                    base_linha = alt.Chart(agrup_linha).encode(
                        x=alt.X('data_curta:N', title='Data'),
                        y=alt.Y('duracao:Q', title='Tempo Perdido', axis=alt.Axis(labelExpr=expr_horas)),
                        color=alt.Color('maquina:N', title='Máquina'),
                        tooltip=['data_curta', 'maquina', 'duracao']
                    )
                    lines = base_linha.mark_line(point=True, size=3)
                    text_linha = base_linha.mark_text(align='center', baseline='bottom', dy=-8, color='#2c3e50', size=tamanho_valores).encode(text='label:N')
                    
                    chart_l = (lines + text_linha).properties(height=350).configure_axis(
                        labelFontSize=tamanho_labels, titleFontSize=tamanho_titulos
                    ).configure_legend(labelFontSize=tamanho_labels, titleFontSize=tamanho_titulos)
                    st.altair_chart(chart_l, use_container_width=True)
        else:
            st.info("Nenhuma ocorrência com tempo contabilizado neste período.")

    # ==========================================
    # ⚖️ SUB-ABA 2: COMPARATIVO DE DIAS
    # ==========================================
    with aba_comp:
        st.markdown("### ⚖️ Batalha de Dias")
        st.write("Selecione dois dias específicos para comparar o desempenho lado a lado.")
        
        cd1, cd2 = st.columns(2)
        with cd1: dia_a = st.date_input("📅 Selecione o Dia A", value=datetime.utcnow().date() - timedelta(days=2))
        with cd2: dia_b = st.date_input("📅 Selecione o Dia B", value=datetime.utcnow().date() - timedelta(days=1))
        
        str_a = dia_a.strftime('%Y-%m-%d')
        str_b = dia_b.strftime('%Y-%m-%d')
        
        df_a = processar_dados_periodo(df_nuvem, df_codigos, str_a, str_a, setor, maquina)
        df_b = processar_dados_periodo(df_nuvem, df_codigos, str_b, str_b, setor, maquina)
        
        min_tot_a, min_prob_a, _, mttr_a, _, _, _, _ = calcular_kpis(df_a)
        min_tot_b, min_prob_b, _, mttr_b, _, _, _, _ = calcular_kpis(df_b)
        
        st.markdown("#### 📊 Confronto de Indicadores")
        col_k1, col_k2, col_k3 = st.columns(3)
        
        delta_tot = min_tot_b - min_tot_a
        delta_mttr = mttr_b - mttr_a
        
        col_k1.metric(label="Tempo Total Perdido (Dia B vs Dia A)", 
                      value=formatar_minutos(min_tot_b), 
                      delta=f"{int(delta_tot)} min", delta_color="inverse")
                      
        col_k2.metric(label="MTTR (Dia B vs Dia A)", 
                      value=f"{int(mttr_b)}m", 
                      delta=f"{int(delta_mttr)}m", delta_color="inverse")
                      
        st.markdown("#### 🏭 Comparativo por Máquina (Minutos de Problema)")
        if not df_a.empty or not df_b.empty:
            agrup_a = df_a[df_a['classificacao']=='PARADA'].groupby('maquina')['duracao'].sum().reset_index() if not df_a.empty else pd.DataFrame(columns=['maquina','duracao'])
            agrup_b = df_b[df_b['classificacao']=='PARADA'].groupby('maquina')['duracao'].sum().reset_index() if not df_b.empty else pd.DataFrame(columns=['maquina','duracao'])
            
            agrup_a['Dia'] = 'Dia A'
            agrup_b['Dia'] = 'Dia B'
            df_comp = pd.concat([agrup_a, agrup_b])
            
            if not df_comp.empty:
                df_comp['label'] = df_comp['duracao'].apply(formatar_minutos)
                base_comp = alt.Chart().encode(
                    x=alt.X('Dia:N', title='', axis=alt.Axis(labels=False, ticks=False)),
                    y=alt.Y('duracao:Q', title='Tempo Perdido (Parada)', axis=alt.Axis(labelExpr=expr_horas)),
                    color=alt.Color('Dia:N', scale=alt.Scale(range=['#3498db', '#9b59b6']))
                )
                bars_comp = base_comp.mark_bar()
                text_comp = base_comp.mark_text(align='center', baseline='bottom', dy=-5, color='#2c3e50', size=tamanho_valores).encode(text='label:N')
                
                chart_comp_final = alt.layer(bars_comp, text_comp, data=df_comp).properties(width=60, height=altura_graficos).facet(
                    column=alt.Column('maquina:N', title='Máquinas')
                ).configure_axis(labelFontSize=tamanho_labels, titleFontSize=tamanho_titulos).configure_header(labelFontSize=tamanho_labels, titleFontSize=tamanho_titulos)
                
                st.altair_chart(chart_comp_final)
            else:
                st.write("Sem falhas (Paradas) registradas nestes dias.")

    # ==========================================
    # ⚙️ PAINEL DE CONTROLE DE FONTES E AJUSTES VISUAIS
    # ==========================================
    st.markdown("<hr style='opacity:0.2;'>", unsafe_allow_html=True)
    with st.expander("⚙️ Ajustes Visuais dos Gráficos (Aplicar e Salvar)"):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            alt_graf = st.number_input("Altura dos Gráficos (px)", value=altura_graficos, step=10)
        with c2:
            font_val = st.number_input("Tamanho: Valores (px)", value=tamanho_valores, step=1)
        with c3:
            font_lab = st.number_input("Tamanho: Legendas (px)", value=tamanho_labels, step=1)
        with c4:
            font_tit = st.number_input("Tamanho: Títulos (px)", value=tamanho_titulos, step=1)
            
        if st.button("💾 Salvar Ajustes Visuais", type="primary", use_container_width=True):
            banco.salvar_memoria_sistema('Análise', 'Geral', 'altura_graficos', alt_graf)
            banco.salvar_memoria_sistema('Análise', 'Geral', 'tamanho_valores', font_val)
            banco.salvar_memoria_sistema('Análise', 'Geral', 'tamanho_labels', font_lab)
            banco.salvar_memoria_sistema('Análise', 'Geral', 'tamanho_titulos', font_tit)
            st.success("✅ Ajustes visuais salvos com sucesso! Recarregue a página (F5) para ver.")