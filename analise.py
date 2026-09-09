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

# Motor de processamento aceitando as flags de unificação global
def processar_dados_periodo(df_nuvem, df_codigos, data_de, data_ate, setor_filtro, maq_filtro, unif_prod=False, unif_par=False):
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
            
        # LÓGICA DE UNIFICAÇÃO GLOBAL (Visual)
        if unif_prod:
            df_paradas['classificacao'] = df_paradas['classificacao'].replace({'RETRABALHO': 'PRODUÇÃO'})
        if unif_par:
            df_paradas['classificacao'] = df_paradas['classificacao'].replace({'ROTINA': 'PARADA'})
            
        df_paradas = df_paradas[~df_paradas['classificacao'].str.contains('NÃO CONTA|DESCONSIDERAR')]

        # ==========================================
        # LÓGICA DE INJEÇÃO DO "NÃO APONTADO"
        # ==========================================
        agora = datetime.utcnow() - timedelta(hours=3)
        hoje_date = agora.date()
        agora_min = agora.hour * 60 + agora.minute

        min_dia_cheio = 0
        for m in range(1440):
            is_t = (m_das_min <= m < m_as_min) or (t_das_min <= m < t_as_min)
            is_l = (lm_das_min <= m < lm_as_min) or (lt_das_min <= m < lt_as_min)
            if is_t and not is_l: min_dia_cheio += 1

        min_hoje_ate_agora = 0
        for m in range(1440):
            if m >= agora_min: break
            is_t = (m_das_min <= m < m_as_min) or (t_das_min <= m < t_as_min)
            is_l = (lm_das_min <= m < lm_as_min) or (lt_das_min <= m < lt_as_min)
            if is_t and not is_l: min_hoje_ate_agora += 1

        # Agrupa dia a dia por máquina para achar o buraco de apontamento
        df_totais_dia_maq = df_paradas.groupby(['data_registro', 'data_registro_dt', 'setor', 'maquina'])['duracao'].sum().reset_index()
        novas_linhas = []

        for _, r in df_totais_dia_maq.iterrows():
            data_reg = r['data_registro_dt'].date()
            if data_reg < hoje_date:
                teto_dia = min_dia_cheio
            elif data_reg == hoje_date:
                teto_dia = min_hoje_ate_agora
            else:
                teto_dia = 0

            falta = teto_dia - r['duracao']
            if falta > 0:
                novas_linhas.append({
                    'data_registro': r['data_registro'],
                    'data_registro_dt': r['data_registro_dt'],
                    'setor': r['setor'],
                    'maquina': r['maquina'],
                    'classificacao': 'NÃO APONTADO',
                    'duracao': falta,
                    'tipo': 'NÃO APONTADO',
                    'descricao_falha': 'Tempo sem apontamento no sistema',
                    'cod_ocorrencia': 'N'
                })

        if novas_linhas:
            df_paradas = pd.concat([df_paradas, pd.DataFrame(novas_linhas)], ignore_index=True)

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

    # --- MAPEAMENTO DE CORES DO SISTEMA ---
    mapa_cores = banco.obter_mapa_cores()
    cor_prod = mapa_cores.get('PRODUÇÃO', '#27ae60')
    cor_ret = mapa_cores.get('RETRABALHO', '#2ecc71')
    cor_rot = mapa_cores.get('ROTINA', '#f39c12')
    cor_par = mapa_cores.get('PARADA', '#c0392b')
    cor_nao = mapa_cores.get('NÃO APONTADO', '#7f8c8d')
    
    domain_graficos = ['PRODUÇÃO', 'RETRABALHO', 'ROTINA', 'PARADA', 'NÃO APONTADO']
    range_graficos = [cor_prod, cor_ret, cor_rot, cor_par, cor_nao]

    # --- NOVOS FILTROS GLOBAIS DE UNIFICAÇÃO ---
    st.markdown("##### 🔍 Nível de Detalhamento da Análise")
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        unif_prod_ret = st.checkbox("🟢 Unificar Produção + Retrabalho (Visão: Máquina Trabalhando)", value=False)
    with col_opt2:
        unif_par_rot = st.checkbox("🔴 Unificar Rotina + Parada (Visão: Máquina Parada)", value=False)
    st.markdown("<br>", unsafe_allow_html=True)

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

    altura_graficos = int(banco.obter_memoria_sistema('Análise', 'Geral', 'altura_graficos', 500))
    tamanho_valores = int(banco.obter_memoria_sistema('Análise', 'Geral', 'tamanho_valores', 16))
    tamanho_labels = int(banco.obter_memoria_sistema('Análise', 'Geral', 'tamanho_labels', 14))
    tamanho_titulos = int(banco.obter_memoria_sistema('Análise', 'Geral', 'tamanho_titulos', 15))

    expr_horas = "floor(datum.value / 60) > 0 ? floor(datum.value / 60) + ':' + (datum.value % 60 < 10 ? '0' : '') + (datum.value % 60) + 'm' : (datum.value % 60) + 'm'"

    aba_geral, aba_evo, aba_comp = st.tabs(["📊 Visão Geral do Período", "📈 Evolução do Período", "⚖️ Comparativo de Dias"])

    # ==========================================
    # 📊 SUB-ABA 1: VISÃO GERAL
    # ==========================================
    with aba_geral:
        df_paradas = processar_dados_periodo(df_nuvem, df_codigos, data_de, data_ate, setor, maquina, unif_prod_ret, unif_par_rot)
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

        # 3. VISÃO MACRO DA FÁBRICA (OEE)
        st.markdown("### 📊 Visão Macro da Fábrica (Distribuição do Tempo Útil)")
        
        if not df_paradas.empty:
            df_macro = df_paradas[df_paradas['classificacao'].isin(['PRODUÇÃO', 'PARADA', 'ROTINA', 'RETRABALHO', 'NÃO APONTADO'])].groupby('classificacao')['duracao'].sum().reset_index()
            df_macro = df_macro[df_macro['duracao'] > 0]
            total_macro = df_macro['duracao'].sum()
            
            if total_macro > 0:
                df_macro['pct'] = (df_macro['duracao'] / total_macro * 100).fillna(0)
                df_macro['tempo_str'] = df_macro['duracao'].apply(formatar_minutos)
                
                def get_label_macro(row):
                    if row['pct'] >= 8: return f"{row['tempo_str']} ({row['pct']:.1f}%)"
                    elif row['pct'] >= 4: return f"{int(round(row['pct']))}%"
                    return ""
                
                df_macro['label_exibicao'] = df_macro.apply(get_label_macro, axis=1)
                
                df_macro['dummy'] = 'Fábrica'
                ordem_dict = {'PRODUÇÃO': 1, 'RETRABALHO': 2, 'ROTINA': 3, 'PARADA': 4, 'NÃO APONTADO': 5}
                df_macro['ordem'] = df_macro['classificacao'].map(ordem_dict)
                df_macro = df_macro.sort_values('ordem')
                df_macro['cum_duracao'] = df_macro['duracao'].cumsum()
                df_macro['midpos'] = df_macro['cum_duracao'] - (df_macro['duracao'] / 2)
                
                bars_macro = alt.Chart(df_macro).mark_bar(size=70).encode(
                    x=alt.X('duracao:Q', title='', axis=alt.Axis(labelExpr=expr_horas, grid=False), stack='zero'),
                    y=alt.Y('dummy:N', title=None, axis=alt.Axis(labels=False, ticks=False, domain=False)),
                    color=alt.Color('classificacao:N', scale=alt.Scale(
                        domain=domain_graficos,
                        range=range_graficos 
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
                
                df_macro_small = df_macro[df_macro['pct'] < 4]
                if not df_macro_small.empty:
                    text_items = [f"<b>{row['classificacao']}</b>: {row['tempo_str']} ({row['pct']:.1f}%)" for _, row in df_macro_small.iterrows()]
                    st.markdown(f"<div style='text-align:center; font-size:12px; color:#7f8c8d; margin-top:-10px; margin-bottom:20px;'>*Ocultos no gráfico por falta de espaço: {', '.join(text_items)}*</div>", unsafe_allow_html=True)
            else:
                st.info("Nenhum dado macro registrado no período.")
        else:
            st.info("Nenhum dado registrado no período.")

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
                    range=[cor_par, cor_ret, cor_rot]
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

        # 5. DESEMPENHO POR MÁQUINA
        st.markdown("<hr style='opacity:0.2;'>", unsafe_allow_html=True)
        st.markdown("### 🏭 Desempenho por Máquina")
        
        if not df_paradas.empty:
            df_desemp = df_paradas[df_paradas['classificacao'].isin(['PRODUÇÃO', 'PARADA', 'ROTINA', 'RETRABALHO', 'NÃO APONTADO'])].groupby(['maquina', 'classificacao'])['duracao'].sum().reset_index()
            df_desemp = df_desemp[df_desemp['duracao'] > 0]
            
            df_desemp['total_maq'] = df_desemp.groupby('maquina')['duracao'].transform('sum')
            df_desemp['pct'] = (df_desemp['duracao'] / df_desemp['total_maq'] * 100).fillna(0)
            df_desemp['tempo_str'] = df_desemp['duracao'].apply(formatar_minutos)
            
            def get_label_maq(row):
                if row['pct'] >= 8: return f"{row['tempo_str']} ({row['pct']:.1f}%)"
                elif row['pct'] >= 4: return f"{int(round(row['pct']))}%" 
                return ""
            
            df_desemp['label_exibicao'] = df_desemp.apply(get_label_maq, axis=1)
            
            ordem_dict = {'PRODUÇÃO': 1, 'RETRABALHO': 2, 'ROTINA': 3, 'PARADA': 4, 'NÃO APONTADO': 5}
            df_desemp['ordem'] = df_desemp['classificacao'].map(ordem_dict)
            
            df_desemp = df_desemp.sort_values(by=['total_maq', 'maquina', 'ordem'], ascending=[False, True, True])
            ordem_maquinas_chart = df_desemp[['maquina', 'total_maq']].drop_duplicates().sort_values('total_maq', ascending=False)['maquina'].tolist()
            
            df_desemp['cum_duracao'] = df_desemp.groupby('maquina')['duracao'].cumsum()
            df_desemp['midpos'] = df_desemp['cum_duracao'] - (df_desemp['duracao'] / 2)
            
            qtd_maquinas_grafico = len(ordem_maquinas_chart)
            altura_dinamica = max(150, qtd_maquinas_grafico * 90) 
            
            bars_desemp = alt.Chart(df_desemp).mark_bar(size=35).encode(
                x=alt.X('duracao:Q', stack='zero', title='Tempo Total Utilizado', axis=alt.Axis(grid=True, labelExpr=expr_horas)),
                y=alt.Y('maquina:N', sort=ordem_maquinas_chart, title=None, axis=alt.Axis(labels=False, ticks=False, domain=False)),
                color=alt.Color('classificacao:N', scale=alt.Scale(
                    domain=domain_graficos,
                    range=range_graficos
                ), legend=alt.Legend(title="", orient="top", labelFontSize=14, padding=10)),
                order=alt.Order('ordem:Q'),
                tooltip=[alt.Tooltip('maquina:N', title='Máquina'), alt.Tooltip('classificacao:N', title='Categoria'), alt.Tooltip('tempo_str:N', title='Tempo'), alt.Tooltip('pct:Q', title='%', format='.1f')]
            )
            
            text_desemp = alt.Chart(df_desemp).mark_text(
                align='center', baseline='middle', size=tamanho_valores
            ).encode(
                x=alt.X('midpos:Q', axis=None),
                y=alt.Y('maquina:N', sort=ordem_maquinas_chart, axis=None),
                text='label_exibicao:N',
                color=alt.condition(alt.datum.classificacao == 'ROTINA', alt.value('#2c3e50'), alt.value('white')),
                tooltip=[alt.Tooltip('maquina:N', title='Máquina'), alt.Tooltip('classificacao:N', title='Categoria'), alt.Tooltip('tempo_str:N', title='Tempo'), alt.Tooltip('pct:Q', title='%', format='.1f')]
            )
            
            df_nomes = df_desemp[['maquina', 'total_maq']].drop_duplicates()
            names_desemp = alt.Chart(df_nomes).mark_text(
                align='left', baseline='bottom', dy=-22, size=tamanho_titulos, fontWeight='bold', color='#34495e'
            ).encode(
                x=alt.value(0), 
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

        # 6. HISTÓRICO INDIVIDUAL (LINHA DO TEMPO) E DRILL DOWN DE PARETO
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
                    
                    dias_pt = {0: 'SEG', 1: 'TER', 2: 'QUA', 3: 'QUI', 4: 'SEX', 5: 'SÁB', 6: 'DOM'}
                    df_sel['dia_semana'] = df_sel['data_registro_dt'].dt.dayofweek.map(dias_pt)
                    df_sel['data_curta'] = df_sel['dia_semana'] + " • " + df_sel['data_registro_dt'].dt.strftime('%d/%m')
                    df_sel['data_pura'] = df_sel['data_registro_dt'].dt.strftime('%Y-%m-%d')
                    
                    agrup_linha = df_sel.groupby(['data_pura', 'data_curta', 'maquina'])['duracao'].sum().reset_index()
                    agrup_linha['label'] = agrup_linha['duracao'].apply(formatar_minutos)
                    
                    base_linha = alt.Chart(agrup_linha).encode(
                        x=alt.X('data_curta:O', title='Data', sort=alt.EncodingSortField(field='data_pura'), axis=alt.Axis(labelAngle=0, labelFontWeight='bold', labelPadding=10)),
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
    # 📈 SUB-ABA 2: EVOLUÇÃO DO PERÍODO
    # ==========================================
    with aba_evo:
        c_tit, c_fil = st.columns([6, 4])
        with c_tit:
            st.markdown("### 📈 Evolução do Desempenho por Tipo")
            st.markdown("Acompanhe a tendência do tempo gasto em Produção, Retrabalho, Rotina e Parada ao longo dos dias.")
        with c_fil:
            setor_str = "TODOS" if setor == "[ Todos ]" else str(setor).upper()
            maq_str = "TODAS" if maquina == "[ Todas ]" else str(maquina).upper()
            st.markdown(f"<div style='text-align: right; color: #2980b9; font-size: 26px; font-weight: 900; margin-top: 10px; letter-spacing: 1px;'>{setor_str} / {maq_str}</div>", unsafe_allow_html=True)
        
        df_paradas_evo = processar_dados_periodo(df_nuvem, df_codigos, data_de, data_ate, setor, maquina, unif_prod_ret, unif_par_rot)
        
        if not df_paradas_evo.empty:
            df_evo = df_paradas_evo[df_paradas_evo['classificacao'].isin(['PRODUÇÃO', 'PARADA', 'ROTINA', 'RETRABALHO', 'NÃO APONTADO'])].copy()
            
            if not df_evo.empty:
                dias_pt = {0: 'SEG', 1: 'TER', 2: 'QUA', 3: 'QUI', 4: 'SEX', 5: 'SÁB', 6: 'DOM'}
                df_evo['dia_semana'] = df_evo['data_registro_dt'].dt.dayofweek.map(dias_pt)
                df_evo['data_exibicao'] = df_evo['dia_semana'] + " • " + df_evo['data_registro_dt'].dt.strftime('%d/%m')
                
                agrup_evo = df_evo.groupby(['data_registro', 'data_exibicao', 'classificacao'])['duracao'].sum().reset_index()
                agrup_evo = agrup_evo[agrup_evo['duracao'] > 0] 
                agrup_evo['tempo_str'] = agrup_evo['duracao'].apply(formatar_minutos)
                
                base_evo = alt.Chart(agrup_evo).encode(
                    x=alt.X('data_exibicao:O', title='Dias Selecionados', sort=alt.EncodingSortField(field='data_registro'), axis=alt.Axis(labelAngle=0, labelFontWeight='bold', labelPadding=10)),
                    y=alt.Y('duracao:Q', title='Tempo Absoluto Consumido', axis=alt.Axis(labelExpr=expr_horas, grid=True)),
                    color=alt.Color('classificacao:N', scale=alt.Scale(
                        domain=domain_graficos,
                        range=range_graficos
                    ), legend=alt.Legend(title="", orient="top", labelFontSize=14, padding=10)),
                    tooltip=[
                        alt.Tooltip('data_exibicao:N', title='Data'),
                        alt.Tooltip('classificacao:N', title='Categoria'),
                        alt.Tooltip('tempo_str:N', title='Tempo Total')
                    ]
                )
                
                lines_evo = base_evo.mark_line(point=True, size=4)
                
                text_evo = base_evo.mark_text(
                    align='center', baseline='bottom', dy=-10, size=tamanho_valores, fontWeight='bold'
                ).encode(
                    text='tempo_str:N',
                    color=alt.condition(alt.datum.classificacao == 'ROTINA', alt.value('#2c3e50'), alt.value('#34495e'))
                )
                
                chart_evo = (lines_evo + text_evo).properties(height=max(450, altura_graficos)).configure_axis(
                    labelFontSize=tamanho_labels, titleFontSize=tamanho_titulos
                ).configure_legend(
                    labelFontSize=tamanho_labels, titleFontSize=tamanho_titulos
                ).configure_view(strokeWidth=0)
                
                st.altair_chart(chart_evo, use_container_width=True)
                
                if maquina == "[ Todas ]":
                    st.info("💡 **Atenção:** Como o filtro superior está em '[ Todas ]', os tempos exibidos neste gráfico representam a **SOMA TOTAL** das horas de todas as máquinas do setor. Para avaliar a evolução de um equipamento individual, selecione-o no filtro de Máquina.")
            else:
                st.info("Sem dados das categorias principais para gerar a evolução neste período.")
        else:
            st.info("Nenhum dado registrado no período.")

    # ==========================================
    # ⚖️ SUB-ABA 3: COMPARATIVO DE DIAS
    # ==========================================
    with aba_comp:
        st.markdown("### ⚖️ Batalha de Dias")
        st.write("Selecione dois dias específicos para comparar o desempenho lado a lado.")
        
        cd1, cd2 = st.columns(2)
        with cd1: dia_a = st.date_input("📅 Selecione o Dia A", value=datetime.utcnow().date() - timedelta(days=2))
        with cd2: dia_b = st.date_input("📅 Selecione o Dia B", value=datetime.utcnow().date() - timedelta(days=1))
        
        str_a = dia_a.strftime('%Y-%m-%d')
        str_b = dia_b.strftime('%Y-%m-%d')
        
        df_a = processar_dados_periodo(df_nuvem, df_codigos, str_a, str_a, setor, maquina, unif_prod_ret, unif_par_rot)
        df_b = processar_dados_periodo(df_nuvem, df_codigos, str_b, str_b, setor, maquina, unif_prod_ret, unif_par_rot)
        
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