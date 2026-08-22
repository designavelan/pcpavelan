import streamlit as st
import pandas as pd
import banco
import filtros
import streamlit.components.v1 as components 

def criar_cartao(titulo, valor_principal, valor_secundario="", cor_secundaria="#666666", cor_titulo="#777777", cor_principal="#222222"):
    val_sec = valor_secundario if valor_secundario else "&nbsp;"
    html = f"""
    <div class="cartao-kpi-acao kpis-container" style="background-color: #ffffff; padding: 20px 10px; border-radius: 8px; border: 1px solid #eaeaea; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05); display: flex; flex-direction: column; justify-content: center; height: 100%;">
        <p style="margin: 0 0 5px 0; color: {cor_titulo}; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; font-weight: 700; line-height: 1.2;">{titulo}</p>
        <h2 style="margin: 0; color: {cor_principal}; font-size: 28px; font-weight: 800; line-height: 1.2;">{valor_principal}</h2>
        <p style="margin: 5px 0 0 0; color: {cor_secundaria}; font-size: 14px; font-weight: bold; line-height: 1.2;">{val_sec}</p>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def renderizar(df_nuvem, df_codigos, filtros_selecionados, jornada_max_minutos):
    filtros.renderizar_cabecalho_global("Plano de Ação")

    cfg = banco.obter_configuracoes()
    LIMITE_GERAL = int(cfg.get('top_gerais', 3))
    LIMITE_INDIVIDUAL = int(cfg.get('top_individuais', 3))
    LIMITE_CONCENTRACAO = float(cfg.get('perc_individual', 70.0)) / 100.0

    df_filt = filtros.aplicar_filtros_analiticos(df_nuvem, df_codigos, filtros_selecionados)
    if df_filt.empty:
        st.warning("⚠️ Nenhum tempo de parada registrado para esta combinação de filtros.")
        return

    df_parado_puro = df_filt[df_filt['status_real'] == 'Parado'].copy()

    dias_reais = df_filt['data_registro'].nunique()
    if dias_reais == 0: dias_reais = 1
    
    df_parado_calc = df_parado_puro.groupby('maquina')['minutos'].sum().reset_index()
    df_parado_calc.rename(columns={'minutos': 'Parado'}, inplace=True)
    
    todas_maquinas = pd.DataFrame({'maquina': df_filt['maquina'].unique()})
    df_maq = pd.merge(todas_maquinas, df_parado_calc, on='maquina', how='left').fillna(0)
    df_maq['Total'] = jornada_max_minutos * dias_reais
    df_maq['Trabalhando'] = df_maq['Total'] - df_maq['Parado']
    df_maq.loc[df_maq['Trabalhando'] < 0, 'Trabalhando'] = 0 
    
    tot_trab = df_maq['Trabalhando'].sum()
    tot_par = df_maq['Parado'].sum()
    disp_media = (tot_trab / (tot_trab + tot_par)) * 100 if (tot_trab + tot_par) > 0 else 0
    
    maq_critica = df_maq.loc[df_maq['Parado'].idxmax()] if not df_maq.empty and df_maq['Parado'].max() > 0 else None
    nome_maq_critica = maq_critica['maquina'] if maq_critica is not None else "N/A"
    tempo_maq_critica = banco.minutos_para_string(maq_critica['Parado']) if maq_critica is not None else "00:00h"

    ofensor_critico = "N/A"
    if not df_parado_puro.empty:
        df_ofensor = df_parado_puro.groupby(['cod_ocorrencia', 'descricao'])['minutos'].sum().reset_index()
        top_ofensor = df_ofensor.loc[df_ofensor['minutos'].idxmax()]
        ofensor_critico = f"[{top_ofensor['cod_ocorrencia']}] {top_ofensor['descricao']}"
    
    k1, k2, k3, k4 = st.columns(4)
    with k1: criar_cartao("Disponibilidade Média", f"{disp_media:.1f}%", cor_titulo="#777", cor_principal="#e74c3c" if disp_media < 85 else "#2ecc71")
    with k2: criar_cartao("Total Perdido", banco.minutos_para_string(tot_par), cor_titulo="#777", cor_principal="#e74c3c")
    with k3: criar_cartao("Máquina Gargalo", nome_maq_critica, f"({tempo_maq_critica})", cor_titulo="#777", cor_principal="#f39c12", cor_secundaria="#f39c12")
    with k4: criar_cartao("Ofensor Principal", ofensor_critico, cor_titulo="#777", cor_principal="#f39c12")

    js_equalizer = """
    <script>
        setInterval(() => {
            const cards = window.parent.document.querySelectorAll('.cartao-kpi-acao');
            if(cards.length > 0) {
                let maxH = 0; cards.forEach(c => c.style.minHeight = 'auto');
                cards.forEach(c => { if(c.offsetHeight > maxH) maxH = c.offsetHeight; });
                cards.forEach(c => { c.style.minHeight = maxH + 'px'; });
            }
        }, 500);
    </script>
    """
    components.html(js_equalizer, height=0)
        
    st.markdown("<br>", unsafe_allow_html=True)

    lista_gerais, lista_individuais = [], []

    if not df_parado_puro.empty:
        df_problemas = df_parado_puro.groupby(['cod_ocorrencia', 'descricao'])['minutos'].sum().reset_index()
        
        for _, row in df_problemas.iterrows():
            cod, desc, tempo_total_falha = row['cod_ocorrencia'], row['descricao'], row['minutos']
            perc_do_setor = (tempo_total_falha / tot_par) * 100 if tot_par > 0 else 0
            
            df_este_prob = df_parado_puro[df_parado_puro['cod_ocorrencia'] == cod]
            df_maq_prob = df_este_prob.groupby('maquina')['minutos'].sum().reset_index()
            maq_ofensora = df_maq_prob.loc[df_maq_prob['minutos'].idxmax()]
            
            concentracao = maq_ofensora['minutos'] / tempo_total_falha if tempo_total_falha > 0 else 0
            
            item_obj = {'cod': cod, 'desc': desc, 'tempo': tempo_total_falha, 'perc_setor': perc_do_setor, 'maq_foco': maq_ofensora['maquina'], 'concentracao': concentracao * 100}
            
            if concentracao >= LIMITE_CONCENTRACAO: lista_individuais.append(item_obj)
            else: lista_gerais.append(item_obj)

    lista_gerais = sorted(lista_gerais, key=lambda k: k['tempo'], reverse=True)[:LIMITE_GERAL]
    lista_individuais = sorted(lista_individuais, key=lambda k: k['tempo'], reverse=True)[:LIMITE_INDIVIDUAL]

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"""<div style="background-color: #f8f9fa; padding: 25px; border-radius: 8px; border: 1px solid #eaeaea; height: 100%;"><h3 style="color: #2980b9; margin-top: 0; font-size: 20px;">🌎 Problemas Gerais (Afetam o Setor)</h3>""", unsafe_allow_html=True)
        if not lista_gerais: st.markdown("<p style='color: #7f8c8d; font-style: italic;'>Nenhuma falha distribuída identificada no período.</p>", unsafe_allow_html=True)
        else:
            for idx, prob in enumerate(lista_gerais):
                st.markdown(f"""<p style="font-size: 16px; color: #333; margin-bottom: 15px; font-weight: 500; line-height: 1.5;">{idx + 1}. Analisar o desvio <b>[{prob['cod']}] - {prob['desc']}</b>. Representa <b>{prob['perc_setor']:.1f}%</b> das perdas do período e afeta a produção de forma distribuída.</p>""", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown(f"""<div style="background-color: #f8f9fa; padding: 25px; border-radius: 8px; border: 1px solid #eaeaea; height: 100%;"><h3 style="color: #f39c12; margin-top: 0; font-size: 20px;">⚙️ Problemas Individuais (Foco por Máquina)</h3>""", unsafe_allow_html=True)
        if not lista_individuais: st.markdown("<p style='color: #7f8c8d; font-style: italic;'>Nenhuma falha altamente concentrada identificada no período.</p>", unsafe_allow_html=True)
        else:
            for idx, prob in enumerate(lista_individuais):
                st.markdown(f"""<p style="font-size: 16px; color: #333; margin-bottom: 15px; font-weight: 500; line-height: 1.5;">{idx + 1}. Foco na máquina <b>{prob['maq_foco']}</b>: O desvio <b>[{prob['cod']}] - {prob['desc']}</b> está concentrado nela e representa <b>{prob['perc_setor']:.1f}%</b> de todas as perdas do setor.</p>""", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)