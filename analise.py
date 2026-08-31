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
    if h > 0: return f"{h}:{m:02d}h"
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
    
    mask_exclude = df['tipo'].astype(str).str.strip().str.upper().isin(['LIVRE', 'A REALIZAR'])
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
        
    df_problema = df_paradas[df_paradas['classificacao'] == 'PARADA']
    df_rotina = df_paradas[df_paradas['classificacao'].isin(['ROTINA', 'RETRABALHO'])]
    
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

    lm_das_min = calcular_minutos_str(cfg.get('lanche_m_das', '')) if cfg.get('lanche_m_das') else -1
    lm_as_min = calcular_minutos_str(cfg.get('lanche_m_as', '')) if cfg.get('lanche_m_as') else -1
    lt_das_min = calcular_minutos_str(cfg.get('lanche_t_das', '')) if cfg.get('lanche_t_das') else -1
    lt_as_min = calcular_minutos_str(cfg.get('lanche_t_as', '')) if cfg.get('lanche_t_as') else -1

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
        
        # 1. CARDS (KPIS)
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"<div class='kpi-card'><div class='kpi-title'>🩸 Tempo Útil Perdido</div><div class='kpi-value val-red'>{formatar_minutos(min_total)}</div><div class='kpi-sub'>({formatar_minutos(min_prob)} Prob. | {formatar_minutos(min_rot)} Rotina)</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='kpi-card'><div class='kpi-title'>⏱️ MTTR (Problemas)</div><div class='kpi-value val-blue'>{int(mttr)}m</div><div class='kpi-sub'>Tempo médio de solução</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='kpi-card'><div class='kpi-title'>🔴 Pior Ofensor (Parada)</div><div class='kpi-value val-red' style='font-size:24px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>{ofensor_prob.split(' (')[0]}</div><div class='kpi-sub'>Tempo: {ofensor_prob.split('(')[-1].replace(')','')}</div></div>", unsafe_allow_html=True)
        c4.markdown(f"<div class='kpi-card'><div class='kpi-title'>🟠 Maior Rotina</div><div class='kpi-value val-orange' style='font-size:24px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>{ofensor_rot.split(' (')[0]}</div><div class='kpi-sub'>Tempo: {ofensor_rot.split('(')[-1].replace(')','')}</div></div>", unsafe_allow_html=True)
        
        st.markdown("<hr style='opacity:0.2;'>", unsafe_allow_html=True)

        # 2. EVOLUÇÃO DA OPERAÇÃO
        if is_single_day:
            st.info(f"📅 **Modo Diário Ativo:** Exibindo dados detalhados para o dia **{data_de}**.")
            
            supa = banco.conectar()
            agora = datetime.utcnow() - timedelta(hours=3)
            is_hoje = (data_de == agora.strftime("%Y-%m-%d"))
            agora_min = agora.hour * 60 + agora.minute if is_hoje else 1440
            
            df_est_total = banco.obter_estrutura()
            total_maq_atual = len(df_est_total[['setor', 'maquina']].dropna().drop_duplicates()) if not df_est_total.empty else 0

            resp_hist = supa.table("historico_operacao").select("data_hora, percentual, maquinas_ativas, maquinas_totais").gte("data_hora", f"{data_de} 00:00:00").lte("data_hora", f"{data_de} 23:59:59").order("data_hora").execute()
            hora_inicio_turno = datetime.strptime(f"{data_de} {m_das}", "%Y-%m-%d %H:%M")
            hora_fim_turno = datetime.strptime(f"{data_de} {t_as}", "%Y-%m-%d %H:%M")
            
            df_h = pd.DataFrame(resp_hist.data) if resp_hist.data else pd.DataFrame()
            if not df_h.empty:
                df_h['data_hora'] = pd.to_datetime(df_h['data_hora']).dt.tz_localize(None)
                df_h['minuto_exato'] = df_h['data_hora'].dt.floor('min')
                df_agrupado = df_h.groupby('minuto_exato')[['percentual', 'maquinas_ativas', 'maquinas_totais']].last().reset_index()
                df_agrupado.set_index('minuto_exato', inplace=True)
            else:
                df_agrupado = pd.DataFrame(columns=['percentual', 'maquinas_ativas', 'maquinas_totais'])
                
            idx_todos_minutos = pd.date_range(start=hora_inicio_turno, end=hora_fim_turno, freq='min')
            df_completo = pd.DataFrame(index=idx_todos_minutos)
            
            if not df_agrupado.empty: df_completo = df_completo.join(df_agrupado)
            else:
                df_completo['percentual'] = pd.NA
                df_completo['maquinas_ativas'] = pd.NA
                df_completo['maquinas_totais'] = pd.NA
                
            df_completo['percentual'] = df_completo['percentual'].ffill().fillna(0.0)
            df_completo['maquinas_ativas'] = df_completo['maquinas_ativas'].ffill().fillna(0)
            df_completo['maquinas_totais'] = df_completo['maquinas_totais'].ffill().fillna(total_maq_atual)
            
            if is_hoje:
                agora_minuto = agora.replace(second=0, microsecond=0)
                df_completo.loc[df_completo.index > agora_minuto, 'percentual'] = pd.NA
            
            df_completo.reset_index(inplace=True)
            df_completo.rename(columns={'index': 'Hora', 'percentual': 'Em Operação (%)'}, inplace=True)
            df_plot = df_completo.dropna(subset=['Em Operação (%)']).copy()
            
            df_plot['Ativas_Str'] = df_plot['maquinas_ativas'].astype(int).astype(str)
            df_plot['Totais_Str'] = df_plot['maquinas_totais'].astype(int).astype(str)
            df_plot['Detalhe_Maquinas'] = df_plot['Ativas_Str'] + " de " + df_plot['Totais_Str'] + " ativas"
            
            st.markdown(f"<div style='margin-top: 5px; margin-bottom: 5px; color: #34495e; font-weight: 800; font-size: {tamanho_titulos}px; text-transform: uppercase; text-align: center; letter-spacing: 1px;'>📈 Evolução da Operação ({data_de})</div>", unsafe_allow_html=True)
            
            chart_evo = alt.Chart(df_plot).mark_area(
                line={'color': '#2980b9', 'strokeWidth': 2}, color='#2980b9', opacity=0.4
            ).encode(
                x=alt.X('Hora:T', title='', axis=alt.Axis(format='%H:%M', tickCount=15, grid=True), scale=alt.Scale(domain=[hora_inicio_turno.isoformat(), hora_fim_turno.isoformat()])),
                y=alt.Y('Em Operação (%):Q', title='', axis=alt.Axis(values=[0, 25, 50, 75, 100], format='.0f', grid=True), scale=alt.Scale(domain=[0, 100])),
                tooltip=[
                    alt.Tooltip('Hora:T', format='%H:%M', title='Horário'), 
                    alt.Tooltip('Em Operação (%):Q', format='.1f', title='Operação (%)'),
                    alt.Tooltip('Detalhe_Maquinas:N', title='Máquinas')
                ]
            ).properties(height=230).configure_axis(labelFontSize=tamanho_labels, titleFontSize=tamanho_titulos)
            
            st.altair_chart(chart_evo, use_container_width=True)
            st.markdown("<hr style='opacity:0.2; margin: 30px 0 20px 0;'>", unsafe_allow_html=True)
        else:
            st.warning("⚠️ **Múltiplos Dias Selecionados:** A visualização em Linha do Tempo e Evolução foi ocultada. Consulte o consolidado abaixo.")
            st.markdown("<hr style='opacity:0.2;'>", unsafe_allow_html=True)

        # 3. VISÃO MACRO DA FÁBRICA (OEE) - BARRA ÚNICA EMPILHADA
        st.markdown("### 📊 Visão Macro da Fábrica (Distribuição do Tempo Útil)")
        
        if not df_paradas.empty:
            df_macro = df_paradas[df_paradas['classificacao'].isin(['PRODUÇÃO', 'PARADA', 'ROTINA', 'RETRABALHO'])].groupby('classificacao')['duracao'].sum().reset_index()
            df_macro = df_macro[df_macro['duracao'] > 0]
            total_macro = df_macro['duracao'].sum()
            
            if total_macro > 0:
                df_macro['pct'] = (df_macro['duracao'] / total_macro * 100).fillna(0)
                df_macro['tempo_str'] = df_macro['duracao'].apply(formatar_minutos)
                
                # Regra Lógica de Texto: % Arredondada
                def get_label_macro(row):
                    if row['pct'] >= 8: return f"{row['tempo_str']} ({row['pct']:.1f}%)"
                    elif row['pct'] >= 4: return f"{int(round(row['pct']))}%"
                    return ""
                
                df_macro['label_exibicao'] = df_macro.apply(get_label_macro, axis=1)
                
                df_macro['dummy'] = 'Fábrica'
                ordem_dict = {'PRODUÇÃO': 1, 'RETRABALHO': 2, 'ROTINA': 3, 'PARADA': 4}
                df_macro['ordem'] = df_macro['classificacao'].map(ordem_dict)
                df_macro = df_macro.sort_values('ordem')
                df_macro['cum_duracao'] = df_macro['duracao'].cumsum()
                df_macro['midpos'] = df_macro['cum_duracao'] - (df_macro['duracao'] / 2)
                
                bars_macro = alt.Chart(df_macro).mark_bar(size=70).encode(
                    x=alt.X('duracao:Q', title='', axis=alt.Axis(labelExpr=expr_horas, grid=False), stack='zero'),
                    y=alt.Y('dummy:N', title=None, axis=alt.Axis(labels=False, ticks=False, domain=False)),
                    color=alt.Color('classificacao:N', scale=alt.Scale(
                        domain=['PRODUÇÃO', 'RETRABALHO', 'ROTINA', 'PARADA'],
                        range=['#27ae60', '#2ecc71', '#f39c12', '#c0392b'] 
                    ), legend=alt.Legend(title="", orient="top", labelFontSize=14, symbolSize=200, padding=10)),
                    order=alt.Order('ordem:Q'),
                    tooltip=[alt.Tooltip('classificacao:N', title='Categoria'), alt.Tooltip('tempo_str:N', title='Tempo'), alt.Tooltip('pct:Q', title='%', format='.1f')]
                )
                
                text_macro = alt.Chart(df_macro).mark_text(
                    align='center', baseline='middle', size=tamanho_valores
                ).encode(
                    x=alt.X('midpos:Q', axis=None),
                    y=alt.Y('dummy:N', axis=None),
                    text='label_exibicao:N',
                    color=alt.condition(alt.datum.classificacao == 'ROTINA', alt.value('#2c3e50'), alt.value('white')),
                    tooltip=[alt.Tooltip('classificacao:N', title='Categoria'), alt.Tooltip('tempo_str:N', title='Tempo'), alt.Tooltip('pct:Q', title='%', format='.1f')]
                )
                
                chart_macro = (bars_macro + text_macro).properties(height=120).configure_axis(
                    labelFontSize=tamanho_labels, titleFontSize=tamanho_titulos
                ).configure_legend(
                    labelFontSize=tamanho_labels, titleFontSize=tamanho_titulos
                ).configure_view(strokeWidth=0)
                
                st.altair_chart(chart_macro, use_container_width=True)
                
                # LEGENDA DISCRETA PARA FATIAS PEQUENAS
                df_macro_small = df_macro[df_macro['pct'] < 4]
                if not df_macro_small.empty:
                    text_items = [f"<b>{row['classificacao']}</b>: {row['tempo_str']} ({row['pct']:.1f}%)" for _, row in df_macro_small.iterrows()]
                    st.markdown(f"<div style='text-align:center; font-size:12px; color:#7f8c8d; margin-top:-10px; margin-bottom:20px;'>*Ocultos no gráfico por falta de espaço: {', '.join(text_items)}*</div>", unsafe_allow_html=True)
            else:
                st.info("Nenhum dado macro registrado no período.")
        else:
            st.info("Nenhum dado registrado no período.")

        # Criação do Filtro Exclusivo para Ocorrências (Retirando a Produção Limpa dos Paretos de Falhas)
        df_ocorrencias = df_paradas[df_paradas['classificacao'].isin(['PARADA', 'ROTINA', 'RETRABALHO'])]

        # 4. GRÁFICO DE PARETO GERAL
        st.markdown("<hr style='opacity:0.2;'>", unsafe_allow_html=True)
        st.markdown("### 📊 Pareto Geral: Top 15 Ocorrências (Tempo Consumido)")
        
        agrup_geral = pd.DataFrame()
        if not df_ocorrencias.empty and min_total > 0:
            agrup_geral = df_ocorrencias.groupby(['descricao_falha', 'classificacao'])['duracao'].sum().reset_index().sort_values('duracao', ascending=False).head(15)
            agrup_geral = agrup_geral[agrup_geral['duracao'] > 0]
            agrup_geral['tempo_str'] = agrup_geral['duracao'].apply(formatar_minutos)
            agrup_geral['pct'] = (agrup_geral['duracao'] / min_total * 100).fillna(0)
            agrup_geral['label'] = agrup_geral.apply(lambda x: f"{x['tempo_str']} ({x['pct']:.1f}%)", axis=1)
            agrup_geral['descricao_quebrada'] = agrup_geral['descricao_falha'].apply(lambda x: ' | '.join(textwrap.wrap(str(x), width=60)))

        ordem_geral = agrup_geral['descricao_quebrada'].tolist() if not agrup_geral.empty else []

        if not agrup_geral.empty:
            max_dur_geral = agrup_geral['duracao'].max()
            thresh_geral = max_dur_geral * 0.15 if max_dur_geral > 0 else 1
            
            base_geral = alt.Chart(agrup_geral).encode(
                x=alt.X('duracao:Q', title='Tempo Consumido', axis=alt.Axis(labelExpr=expr_horas)),
                y=alt.Y('descricao_quebrada:N', sort=ordem_geral, title=None, axis=alt.Axis(labelAngle=0, labelOverlap=False, labelLimit=0, labelExpr="split(datum.value, ' | ')")),
                tooltip=[alt.Tooltip('descricao_falha:N', title='Ocorrência'), alt.Tooltip('classificacao:N', title='Tipo'), alt.Tooltip('tempo_str:N', title='Tempo Consumido')]
            )
            
            bars_geral = base_geral.mark_bar().encode(
                color=alt.Color('classificacao:N', scale=alt.Scale(
                    domain=['PARADA', 'RETRABALHO', 'ROTINA'],
                    range=['#c0392b', '#27ae60', '#f39c12']
                ), legend=None)
            )
            
            text_geral_in = base_geral.transform_filter(alt.datum.duracao > thresh_geral).mark_text(
                align='right', dx=-5, baseline='middle', size=tamanho_valores
            ).encode(
                text='label:N',
                color=alt.condition(alt.datum.classificacao == 'ROTINA', alt.value('#2c3e50'), alt.value('white'))
            )
            
            text_geral_out = base_geral.transform_filter(alt.datum.duracao <= thresh_geral).mark_text(
                align='left', dx=5, color='#2c3e50', baseline='middle', size=tamanho_valores
            ).encode(text='label:N')
            
            chart_geral = (bars_geral + text_geral_in + text_geral_out).properties(height=altura_graficos).configure_axis(
                labelFontSize=tamanho_labels, titleFontSize=tamanho_titulos
            )
            st.altair_chart(chart_geral, use_container_width=True)
        else:
            st.write("Nenhuma ocorrência registrada no período.")

        # 5. DESEMPENHO POR MÁQUINA (ESCALA ABSOLUTA COM TEXTO FLUTUANTE)
        st.markdown("<hr style='opacity:0.2;'>", unsafe_allow_html=True)
        st.markdown("### 🏭 Desempenho por Máquina")
        
        if not df_paradas.empty:
            df_desemp = df_paradas[df_paradas['classificacao'].isin(['PRODUÇÃO', 'PARADA', 'ROTINA', 'RETRABALHO'])].groupby(['maquina', 'classificacao'])['duracao'].sum().reset_index()
            df_desemp = df_desemp[df_desemp['duracao'] > 0]
            
            df_desemp['total_maq'] = df_desemp.groupby('maquina')['duracao'].transform('sum')
            df_desemp['pct'] = (df_desemp['duracao'] / df_desemp['total_maq'] * 100).fillna(0)
            df_desemp['tempo_str'] = df_desemp['duracao'].apply(formatar_minutos)
            
            # Regra Lógica de Texto: % Arredondada no meio
            def get_label_maq(row):
                if row['pct'] >= 8: return f"{row['tempo_str']} ({row['pct']:.1f}%)"
                elif row['pct'] >= 4: return f"{int(round(row['pct']))}%" 
                return ""
            
            df_desemp['label_exibicao'] = df_desemp.apply(get_label_maq, axis=1)
            
            ordem_dict = {'PRODUÇÃO': 1, 'RETRABALHO': 2, 'ROTINA': 3, 'PARADA': 4}
            df_desemp['ordem'] = df_desemp['classificacao'].map(ordem_dict)
            
            # Ordenar pela máquina com maior tempo total
            df_desemp = df_desemp.sort_values(by=['total_maq', 'maquina', 'ordem'], ascending=[False, True, True])
            ordem_maquinas_chart = df_desemp[['maquina', 'total_maq']].drop_duplicates().sort_values('total_maq', ascending=False)['maquina'].tolist()
            
            df_desemp['cum_duracao'] = df_desemp.groupby('maquina')['duracao'].cumsum()
            df_desemp['midpos'] = df_desemp['cum_duracao'] - (df_desemp['duracao'] / 2)
            
            # Altura Dinâmica para manter o respiro perfeito (Cresce conforme novas máquinas são adicionadas)
            qtd_maquinas_grafico = len(ordem_maquinas_chart)
            altura_dinamica = max(150, qtd_maquinas_grafico * 90) 
            
            # Barras finas com eixo X absoluto (Minutos)
            bars_desemp = alt.Chart(df_desemp).mark_bar(size=35).encode(
                x=alt.X('duracao:Q', stack='zero', title='Tempo Total Utilizado', axis=alt.Axis(grid=True, labelExpr=expr_horas)),
                y=alt.Y('maquina:N', sort=ordem_maquinas_chart, title=None, axis=alt.Axis(labels=False, ticks=False, domain=False)),
                color=alt.Color('classificacao:N', scale=alt.Scale(
                    domain=['PRODUÇÃO', 'RETRABALHO', 'ROTINA', 'PARADA'],
                    range=['#27ae60', '#2ecc71', '#f39c12', '#c0392b']
                ), legend=alt.Legend(title="", orient="top", labelFontSize=14, padding=10)),
                order=alt.Order('ordem:Q'),
                tooltip=[alt.Tooltip('maquina:N', title='Máquina'), alt.Tooltip('classificacao:N', title='Categoria'), alt.Tooltip('tempo_str:N', title='Tempo'), alt.Tooltip('pct:Q', title='%', format='.1f')]
            )
            
            # Texto da Porcentagem dentro da Barra
            text_desemp = alt.Chart(df_desemp).mark_text(
                align='center', baseline='middle', size=tamanho_valores
            ).encode(
                x=alt.X('midpos:Q', axis=None),
                y=alt.Y('maquina:N', sort=ordem_maquinas_chart, axis=None),
                text='label_exibicao:N',
                color=alt.condition(alt.datum.classificacao == 'ROTINA', alt.value('#2c3e50'), alt.value('white')),
                tooltip=[alt.Tooltip('maquina:N', title='Máquina'), alt.Tooltip('classificacao:N', title='Categoria'), alt.Tooltip('tempo_str:N', title='Tempo'), alt.Tooltip('pct:Q', title='%', format='.1f')]
            )
            
            # Nova Camada: O Nome da Máquina Flutuando Acima da Barra
            df_nomes = df_desemp[['maquina', 'total_maq']].drop_duplicates()
            names_desemp = alt.Chart(df_nomes).mark_text(
                align='left', baseline='bottom', dy=-22, size=tamanho_titulos, fontWeight='bold', color='#34495e'
            ).encode(
                x=alt.value(0), # Trava o nome sempre no canto esquerdo da tela
                y=alt.Y('maquina:N', sort=ordem_maquinas_chart, axis=None),
                text='maquina:N'
            )
            
            chart_desemp = alt.layer(bars_desemp, text_desemp, names_desemp).properties(height=altura_dinamica).configure_axis(
                labelFontSize=tamanho_labels, titleFontSize=tamanho_titulos
            ).configure_legend(
                labelFontSize=tamanho_labels, titleFontSize=tamanho_titulos
            ).configure_view(strokeWidth=0)
            
            st.altair_chart(chart_desemp, use_container_width=True)
            
            df_desemp_small = df_desemp[df_desemp['pct'] < 4]
            if not df_desemp_small.empty:
                st.markdown("<div style='text-align:center; font-size:11px; color:#95a5a6; margin-top:-10px; margin-bottom:20px;'>*Passe o mouse sobre as barras para ver os detalhes das fatias ocultas (menores que 4%).*</div>", unsafe_allow_html=True)
                
        else:
            st.write("Sem dados de desempenho para o período.")

        # 6. HISTÓRICO INDIVIDUAL (LINHA DO TEMPO) COM CORTES E DETALHES
        if is_single_day:
            st.markdown("<hr style='opacity:0.2;'>", unsafe_allow_html=True)
            mapa_cores = banco.obter_mapa_cores()
            def get_color(tipo):
                t = str(tipo).strip().upper()
                if t in mapa_cores: return mapa_cores[t]
                if t == 'PRODUÇÃO': return '#27ae60'
                if t == 'PARADA': return '#e74c3c'
                if t == 'ROTINA': return '#e67e22'
                if t == 'NÃO CONTA': return '#f39c12'
                if t == 'LIVRE': return '#3498db'
                if t == 'A REALIZAR': return '#ecf0f1'
                if t == 'INTERVALO PREVISTO': return '#bdc3c7'
                if t == 'RETRABALHO': return '#27ae60'
                return '#95a5a6'

            def get_friendly_name(tipo):
                t = str(tipo).strip().upper()
                if t == 'NÃO CONTA': return 'Pausa Registrada'
                if t == 'PRODUÇÃO': return 'Produzindo'
                if t == 'PARADA': return 'Indisponível (Parada)'
                if t == 'ROTINA': return 'Rotina'
                if t == 'LIVRE': return 'Disponível (Livre)'
                if t == 'A REALIZAR': return 'A Realizar (Futuro)'
                if t == 'INTERVALO PREVISTO': return 'Intervalo Previsto'
                return t.title()

            df_dia_completo = df_nuvem[(df_nuvem['data_registro'] == data_de)].copy()
            
            # Carregando códigos para buscar as descrições em tempo real
            if not df_codigos.empty:
                df_codigos_temp = df_codigos.copy()
                df_codigos_temp['codigo'] = df_codigos_temp['codigo'].astype(str).str.strip()
            else:
                df_codigos_temp = pd.DataFrame()
            
            df_est_total = banco.obter_estrutura()
            if setor != "[ Todos ]": df_est_total = df_est_total[df_est_total['setor'] == setor]
            if maquina != "[ Todas ]": df_est_total = df_est_total[df_est_total['maquina'] == maquina]
            pares_maquinas = df_est_total[['setor', 'maquina']].dropna().drop_duplicates().values.tolist()
            
            status_dict = {}
            if is_hoje:
                resp_status = supa.table("status_maquinas").select("*").execute()
                if resp_status.data:
                    status_dict = {(str(d.get('setor', '')).strip(), str(d.get('maquina', '')).strip()): d for d in resp_status.data}

            setores_dict_timeline = {}
            for s, m in pares_maquinas:
                if s not in setores_dict_timeline: setores_dict_timeline[s] = []
                setores_dict_timeline[s].append(m)

            ordem_setores = {}
            if 'ordem_fluxo' in df_est_total.columns:
                for _, row in df_est_total[['setor', 'ordem_fluxo']].dropna().drop_duplicates().iterrows():
                    try: ordem_setores[str(row['setor']).strip()] = float(row['ordem_fluxo'])
                    except: pass

            if not df_dia_completo.empty or is_hoje:
                html_timelines = "<div style='max-width: 1200px; margin: 0 auto;'>"
                st.markdown(f"<h3 style='text-align: center; color: #2c3e50; text-transform: uppercase; font-weight: 900; margin-bottom: 30px;'>📊 Histórico Individual das Máquinas</h3>", unsafe_allow_html=True)

                pct_as_m = ((m_as_min - m_das_min) / total_timeline_min) * 100
                pct_das_t = ((t_das_min - m_das_min) / total_timeline_min) * 100

                for s in sorted(setores_dict_timeline.keys(), key=lambda x: (ordem_setores.get(x, 999), x)):
                    html_timelines += "<div style='margin-bottom: 30px; background: #fff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); border: 1px solid #eaeaea;'>"
                    html_timelines += f"<h4 style='color: #7f8c8d; text-transform: uppercase; font-weight: 900; margin-top: 0; margin-bottom: 20px; border-bottom: 2px solid #ecf0f1; padding-bottom: 8px; font-size: {tamanho_titulos + 2}px;'>🏭 {s}</h4>"
                    
                    html_timelines += "<div style='position: relative; height: 25px; color: #7f8c8d; font-weight: bold; margin-bottom: 8px; border-bottom: 1px solid #eee;'>"
                    html_timelines += f"<div style='position: absolute; left: 0%; transform: translateX(0%); top: 0px; font-size: {tamanho_labels}px;'>{m_das}</div>"
                    
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
                            html_timelines += f"<div style='position: absolute; left: {pct}%; transform: translateX(-50%); font-weight: 500; color: #95a5a6; top: 2px; font-size: {tamanho_labels - 2}px;'>{h}h</div>"
                        elif curr % 60 == 30:
                            html_timelines += f"<div style='position: absolute; left: {pct}%; top: 6px; width: 1px; height: 6px; background-color: #bdc3c7;'></div>"
                    
                    html_timelines += f"<div style='position: absolute; left: {pct_as_m}%; transform: translateX(-50%); top: 0px; font-size: {tamanho_labels}px;'>{m_as}</div>"
                    html_timelines += f"<div style='position: absolute; left: {pct_das_t}%; transform: translateX(-50%); top: 0px; font-size: {tamanho_labels}px;'>{t_das}</div>"
                    html_timelines += f"<div style='position: absolute; left: 100%; transform: translateX(-100%); top: 0px; font-size: {tamanho_labels}px;'>{t_as}</div>"
                    html_timelines += "</div>"

                    for maq in sorted(setores_dict_timeline[s]):
                        # A nova timeline salva DUAS informações: Macro Categoria e Descrição Específica
                        timeline = [('LIVRE', 'Disponível (Livre)')] * total_timeline_min
                        
                        for i in range(total_timeline_min):
                            curr = m_das_min + i
                            if curr >= m_as_min and curr < t_das_min: timeline[i] = ('INTERVALO PREVISTO', 'Intervalo Previsto')
                            elif lm_das_min != -1 and curr >= lm_das_min and curr < lm_as_min: timeline[i] = ('INTERVALO PREVISTO', 'Intervalo Previsto')
                            elif lt_das_min != -1 and curr >= lt_das_min and curr < lt_as_min: timeline[i] = ('INTERVALO PREVISTO', 'Intervalo Previsto')
                            elif is_hoje and curr > agora_min: timeline[i] = ('A REALIZAR', 'A Realizar (Futuro)')
                            elif not ((curr >= m_das_min and curr < m_as_min) or (curr >= t_das_min and curr < t_as_min)):
                                timeline[i] = ('INTERVALO PREVISTO', 'Intervalo Previsto')
                            
                        if not df_dia_completo.empty:
                            maq_records = df_dia_completo[(df_dia_completo['maquina'] == maq) & (df_dia_completo['setor'] == s)]
                            for _, row in maq_records.iterrows():
                                if pd.notna(row.get('das')) and pd.notna(row.get('as_hora')):
                                    inicio = calcular_minutos_str(row['das'])
                                    fim = calcular_minutos_str(row['as_hora'])
                                    tipo_reg = str(row.get('tipo', 'PARADA')).strip().upper()
                                    desc_reg = "Sem Descrição"
                                    
                                    if tipo_reg == 'PARADA':
                                        cod = str(row.get('cod_ocorrencia')).strip()
                                        if cod and not df_codigos_temp.empty:
                                            f_cod = df_codigos_temp[df_codigos_temp['codigo'] == cod]
                                            if not f_cod.empty:
                                                if 'tipo' in f_cod.columns: tipo_reg = str(f_cod.iloc[0]['tipo']).strip().upper()
                                                if 'descricao' in f_cod.columns: desc_reg = str(f_cod.iloc[0]['descricao']).strip()
                                                
                                    if 'DESCONSIDERAR' in tipo_reg: tipo_reg = 'NÃO CONTA'
                                    
                                    if tipo_reg == 'PRODUÇÃO': desc_reg = 'Produzindo'
                                    elif tipo_reg == 'LIVRE': desc_reg = 'Disponível (Livre)'
                                    elif tipo_reg == 'NÃO CONTA': desc_reg = 'Pausa Registrada'
                                    elif desc_reg == "Sem Descrição": desc_reg = tipo_reg.title()
                                    
                                    for m in range(inicio, fim):
                                        idx = m - m_das_min
                                        if 0 <= idx < total_timeline_min: timeline[idx] = (tipo_reg, desc_reg)

                        if is_hoje:
                            info_maq = status_dict.get((s, maq), {})
                            status_atual = info_maq.get('status', 'Livre')
                            
                            if status_atual in ['Produzindo', 'Parado']:
                                try:
                                    h_ini_obj = datetime.strptime(info_maq['hora_inicio'], "%Y-%m-%d %H:%M:%S")
                                    if h_ini_obj.date() == agora.date():
                                        inicio = h_ini_obj.hour * 60 + h_ini_obj.minute
                                        fim = agora_min + 1 
                                        
                                        if status_atual == 'Produzindo': 
                                            tipo_linha = 'PRODUÇÃO'
                                            desc_linha = 'Produzindo'
                                        else:
                                            c_oco = str(info_maq.get('cod_ocorrencia')).strip()
                                            tipo_linha = 'PARADA'
                                            desc_linha = 'Sem Descrição'
                                            if c_oco and not df_codigos_temp.empty:
                                                f_cod = df_codigos_temp[df_codigos_temp['codigo'] == c_oco]
                                                if not f_cod.empty:
                                                    if 'tipo' in f_cod.columns: tipo_linha = str(f_cod.iloc[0]['tipo']).strip().upper()
                                                    if 'descricao' in f_cod.columns: desc_linha = str(f_cod.iloc[0]['descricao']).strip()
                                            if 'DESCONSIDERAR' in tipo_linha: tipo_linha = 'NÃO CONTA'
                                            if desc_linha == 'Sem Descrição': desc_linha = tipo_linha.title()
                                            
                                        for m in range(inicio, fim):
                                            idx = m - m_das_min
                                            if 0 <= idx < total_timeline_min: timeline[idx] = (tipo_linha, desc_linha)
                                except: pass

                        segments = []
                        if total_timeline_min > 0:
                            curr_type, curr_desc = timeline[0]
                            curr_len = 1
                            for i in range(1, total_timeline_min):
                                if timeline[i] == (curr_type, curr_desc): curr_len += 1
                                else:
                                    segments.append((curr_type, curr_desc, curr_len))
                                    curr_type, curr_desc = timeline[i]
                                    curr_len = 1
                            segments.append((curr_type, curr_desc, curr_len))
                            
                        html_timelines += "<div style='margin-bottom: 25px; display: flex; flex-direction: column;'>"
                        html_timelines += f"<div style='font-size: {tamanho_titulos}px; font-weight: bold; color: #34495e; margin-bottom: 4px; text-transform: uppercase;'>{maq}</div>"
                        html_timelines += "<div style='display: flex; width: 100%; height: 18px; border-radius: 4px; overflow: hidden; box-shadow: inset 0 1px 3px rgba(0,0,0,0.15); margin-bottom: 6px;'>"
                        
                        counts_minutos = {}
                        minutos_nao_conta = 0
                        for stype, sdesc, slen in segments:
                            counts_minutos[stype] = counts_minutos.get(stype, 0) + slen
                            if stype == 'INTERVALO PREVISTO' or 'NÃO CONTA' in stype or 'DESCONSIDERAR' in stype:
                                minutos_nao_conta += slen
                                
                        base_100_util = total_timeline_min - minutos_nao_conta
                        if base_100_util <= 0: base_100_util = 1 
                        
                        for i, (stype, sdesc, slen) in enumerate(segments):
                            pct = (slen / total_timeline_min) * 100
                            color = get_color(stype)
                            
                            # Formatação exata do Tooltip solicitada com cálculos inteligentes
                            if stype == 'INTERVALO PREVISTO' or 'NÃO CONTA' in stype or 'A REALIZAR' in stype:
                                tooltip_text = f"{sdesc} / {formatar_minutos(slen)}"
                            else:
                                pct_util = (slen / base_100_util) * 100
                                tooltip_text = f"{sdesc} / {formatar_minutos(slen)} ({pct_util:.1f}%)"
                            
                            # Corte visível e elegante usando borda branca de alta transparência
                            border_css = "border-right: 1px solid rgba(255,255,255,0.6); box-sizing: border-box;" if i < len(segments)-1 else ""
                            html_timelines += f"<div style='width: {pct}%; background-color: {color}; {border_css}' title='{tooltip_text}'></div>"
                            
                        html_timelines += "</div>"
                        
                        itens_conta = []
                        itens_nao_conta = []
                        
                        for stype, slen in counts_minutos.items():
                            if slen > 0:
                                tempo_str = formatar_minutos(slen)
                                color = get_color(stype)
                                fname = get_friendly_name(stype)
                                border = "border: 1px solid #ccc;" if color.upper() in ["#ECF0F1", "#FFFFFF", "#BDC3C7"] else ""
                                is_nao_conta = (stype == 'INTERVALO PREVISTO' or 'NÃO CONTA' in stype or 'DESCONSIDERAR' in stype)
                                
                                if is_nao_conta:
                                    itens_nao_conta.append(f"<div style='display: flex; align-items: center; gap: 4px;'><div style='width:10px; height:10px; background:{color}; border-radius:2px; {border}'></div> <b style='color: #7f8c8d; font-size: {tamanho_labels}px;'>{fname}:</b> <span style='color: #7f8c8d; font-size: {tamanho_valores}px;'>{tempo_str}</span></div>")
                                else:
                                    pct_val = (slen / base_100_util) * 100
                                    itens_conta.append((slen, f"<div style='display: flex; align-items: center; gap: 4px;'><div style='width:10px; height:10px; background:{color}; border-radius:2px; {border}'></div> <b style='font-size: {tamanho_labels}px;'>{fname}:</b> <span style='font-size: {tamanho_valores}px;'>{tempo_str} ({pct_val:.1f}%)</span></div>"))
                                    
                        itens_conta.sort(key=lambda x: x[0], reverse=True)
                        html_timelines += f"<div style='display: flex; flex-wrap: wrap; gap: 15px; color: #2c3e50;'>"
                        
                        for _, html_item in itens_conta: html_timelines += html_item
                        if itens_nao_conta:
                            html_timelines += "<div style='border-left: 2px solid #bdc3c7; margin: 0 5px;'></div>"
                            for html_item in itens_nao_conta: html_timelines += html_item
                                
                        html_timelines += "</div></div>" 
                    html_timelines += "</div>" 
                
                tipos_exibicao_legenda = set(['LIVRE', 'PRODUÇÃO', 'PARADA', 'ROTINA', 'RETRABALHO', 'NÃO CONTA', 'INTERVALO PREVISTO', 'A REALIZAR'])
                for k in mapa_cores.keys(): tipos_exibicao_legenda.add(k)
                
                html_timelines += f"<div style='display: flex; justify-content: center; flex-wrap: wrap; gap: 20px; font-weight: bold; color: #555; padding-top: 10px; margin-bottom: 20px; font-size: {tamanho_labels}px;'>"
                for stype in sorted(tipos_exibicao_legenda):
                    c_hex = get_color(stype)
                    f_name = get_friendly_name(stype)
                    border = "border: 1px solid #ccc;" if c_hex.upper() in ["#ECF0F1", "#FFFFFF", "#BDC3C7"] else ""
                    html_timelines += f"<div style='display: flex; align-items: center; gap: 6px;'><div style='width:14px; height:14px; background:{c_hex}; border-radius:3px; {border}'></div> {f_name}</div>"
                html_timelines += "</div></div>"

                st.markdown(html_timelines, unsafe_allow_html=True)

        # 7. ANÁLISE DE IMPACTO POR OCORRÊNCIA
        st.markdown("<hr style='opacity:0.2;'>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: #2c3e50; margin-bottom: 25px;'>🔎 Análise de Impacto por Ocorrência</h3>", unsafe_allow_html=True)

        if not df_ocorrencias.empty and df_ocorrencias['duracao'].sum() > 0:
            total_tempo_geral = df_ocorrencias['duracao'].sum()
            
            agrup_oco = df_ocorrencias.groupby(['cod_ocorrencia', 'descricao_falha', 'classificacao'])['duracao'].sum().reset_index()
            agrup_oco = agrup_oco[agrup_oco['duracao'] > 0].sort_values('duracao', ascending=False)
            
            opcoes_dropdown = []
            for _, row in agrup_oco.iterrows():
                pct_oco = (row['duracao'] / total_tempo_geral) * 100
                tag = "🔴 PARADA" if row['classificacao'] == "PARADA" else ("🟢 RETRABALHO" if row['classificacao'] == "RETRABALHO" else "🟠 ROTINA")
                opcoes_dropdown.append(f"{row['cod_ocorrencia']} - {row['descricao_falha']} ({pct_oco:.1f}%) [{tag}]")
                
            col_vazia1, col_menu, col_vazia2 = st.columns([1, 4, 1])
            with col_menu:
                selecao = st.selectbox("Selecione a ocorrência para detalhar:", opcoes_dropdown, label_visibility="collapsed")
                
            if selecao:
                cod_selecionado = selecao.split(" - ")[0].strip()
                df_sel = df_ocorrencias[df_ocorrencias['cod_ocorrencia'] == cod_selecionado].copy()
                
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
                    <p>O apontamento <b>{nome_limpo}</b> gerou um total de <b>{formatar_minutos(tot_min_sel)}</b> de tempo consumido {texto_dia}, o que representa <b>{pct_sel:.1f}%</b> de todos os registros do setor.</p>
                    <p>Foram registrados <b>{qtd_sel} apontamentos</b> dessa classificação, com uma média de <b>{int(media_sel)} min</b> de duração. A máquina mais impactada foi a <b>{maq_ofensor_sel}</b>.</p>
                </div>
                """, unsafe_allow_html=True)
                
                ck1, ck2, ck3, ck4 = st.columns(4)
                ck1.markdown(f"<div class='kpi-card'><div class='kpi-title'>TOTAL TEMPO CONSUMIDO</div><div class='kpi-value val-dark'>{formatar_minutos(tot_min_sel)}</div></div>", unsafe_allow_html=True)
                ck2.markdown(f"<div class='kpi-card'><div class='kpi-title'>QTD. OCORRÊNCIAS</div><div class='kpi-value val-dark'>{qtd_sel}</div></div>", unsafe_allow_html=True)
                ck3.markdown(f"<div class='kpi-card'><div class='kpi-title'>MÉDIA POR OCORRÊNCIA</div><div class='kpi-value val-dark'>{int(media_sel)} min</div></div>", unsafe_allow_html=True)
                ck4.markdown(f"<div class='kpi-card'><div class='kpi-title'>MÁQUINA MAIS AFETADA</div><div class='kpi-value val-dark' style='font-size:26px;'>{maq_ofensor_sel}</div></div>", unsafe_allow_html=True)
                
                st.markdown("<br>", unsafe_allow_html=True)
                cg1, cg2 = st.columns(2)
                
                with cg1:
                    st.markdown(f"<div style='text-align: center; color: #2c3e50; font-weight: bold; margin-bottom: 10px;'>Distribuição do Tempo</div>", unsafe_allow_html=True)
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
                        y=alt.Y('duracao:Q', title='Tempo Gasto', axis=alt.Axis(labelExpr=expr_horas)),
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