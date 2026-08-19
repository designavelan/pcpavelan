import streamlit as st
import pandas as pd
import banco
import filtros
import streamlit.components.v1 as components 

def classificar_status(row):
    cod = str(row['cod_ocorrencia']).strip().lower()
    if cod in ['none', 'nan', '']: return 'Trabalhando'
    tipo = str(row['tipo']).strip().upper()
    if 'DESNCONSIDERAR' in tipo or 'DESCONSIDERAR' in tipo: return 'Desconsiderar'
    if tipo == 'PARADO': return 'Parado'
    return 'Trabalhando'

def criar_cartao(titulo, valor_principal, valor_secundario="", cor_secundaria="#666666", cor_titulo="#777777", cor_principal="#222222"):
    # Garante que a linha secundária exista fisicamente mesmo vazia, para manter o eixo vertical intacto
    val_sec = valor_secundario if valor_secundario else "&nbsp;"
    
    # Fundimos a classe 'kpis-container' diretamente na div do cartão! Zero elementos extras na coluna.
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

    # ===============================================
    # LÊ AS CONFIGURAÇÕES SALVAS PELO USUÁRIO
    # ===============================================
    cfg = banco.obter_configuracoes()
    LIMITE_GERAL = int(cfg.get('top_gerais', 3))
    LIMITE_INDIVIDUAL = int(cfg.get('top_individuais', 3))
    LIMITE_CONCENTRACAO = float(cfg.get('perc_individual', 70.0)) / 100.0

    # Tratamento e conversão de tempo
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

    # Aplicação dos Filtros
    df_filt = df_nuvem.copy()
    if filtros_selecionados['de'] != "[ Todas ]": df_filt = df_filt[df_filt['data_registro'] >= filtros_selecionados['de']]
    if filtros_selecionados['ate'] != "[ Todas ]": df_filt = df_filt[df_filt['data_registro'] <= filtros_selecionados['ate']]
    if filtros_selecionados['setor'] != "[ Todos ]": df_filt = df_filt[df_filt['setor'] == filtros_selecionados['setor']]
    if filtros_selecionados['maquina'] != "[ Todas ]": df_filt = df_filt[df_filt['maquina'] == filtros_selecionados['maquina']]

    if df_filt.empty:
        st.warning("⚠️ Nenhum dado encontrado para esta combinação de filtros.")
        return

    # ===============================================
    # CÁLCULOS DOS KPIS PRINCIPAIS
    # ===============================================
    dias_reais = df_filt['data_registro'].nunique()
    if dias_reais == 0: dias_reais = 1
    
    # KPIs de Disponibilidade
    df_parado_calc = df_filt[df_filt['status_real'] == 'Parado'].groupby('maquina')['minutos'].sum().reset_index()
    df_parado_calc.rename(columns={'minutos': 'Parado'}, inplace=True)
    
    todas_maquinas = pd.DataFrame({'maquina': df_filt['maquina'].unique()})
    df_maq = pd.merge(todas_maquinas, df_parado_calc, on='maquina', how='left').fillna(0)
    df_maq['Total'] = jornada_max_minutos * dias_reais
    df_maq['Trabalhando'] = df_maq['Total'] - df_maq['Parado']
    df_maq.loc[df_maq['Trabalhando'] < 0, 'Trabalhando'] = 0 
    
    tot_trab = df_maq['Trabalhando'].sum()
    tot_par = df_maq['Parado'].sum()
    disp_media = (tot_trab / (tot_trab + tot_par)) * 100 if (tot_trab + tot_par) > 0 else 0
    
    # Máquina Gargalo (Maior parada total)
    maq_critica = df_maq.loc[df_maq['Parado'].idxmax()] if not df_maq.empty and df_maq['Parado'].max() > 0 else None
    nome_maq_critica = maq_critica['maquina'] if maq_critica is not None else "N/A"
    tempo_maq_critica = banco.minutos_para_string(maq_critica['Parado']) if maq_critica is not None else "00:00h"

    # Ofensor Principal (Maior causa de parada)
    df_parado_puro = df_filt[df_filt['status_real'] == 'Parado'].copy()
    ofensor_critico = "N/A"
    if not df_parado_puro.empty:
        df_ofensor = df_parado_puro.groupby(['cod_ocorrencia', 'descricao'])['minutos'].sum().reset_index()
        top_ofensor = df_ofensor.loc[df_ofensor['minutos'].idxmax()]
        ofensor_critico = f"[{top_ofensor['cod_ocorrencia']}] {top_ofensor['descricao']}"
    
    # ===============================================
    # RENDERIZAÇÃO DOS CARTÕES (Lado a Lado perfeitos)
    # ===============================================
    k1, k2, k3, k4 = st.columns(4)
    with k1: 
        # A tag solta foi removida daqui!
        criar_cartao("Disponibilidade Operacional Média", f"{disp_media:.1f}%", cor_titulo="#777", cor_principal="#e74c3c" if disp_media < 85 else "#2ecc71")
    with k2: 
        criar_cartao("Tempo Total Perdido no Período", banco.minutos_para_string(tot_par), cor_titulo="#777", cor_principal="#e74c3c")
    with k3: 
        criar_cartao("Máquina Crítica (Gargalo)", nome_maq_critica, f"({tempo_maq_critica})", cor_titulo="#777", cor_principal="#f39c12", cor_secundaria="#f39c12")
    with k4: 
        criar_cartao("Ocorrência Principal (Ofensor)", ofensor_critico, cor_titulo="#777", cor_principal="#f39c12")

    # ===============================================
    # O EQUALIZADOR DE ALTURAS (A Mágica do Alinhamento)
    # ===============================================
    js_equalizer = """
    <script>
        setInterval(() => {
            const cards = window.parent.document.querySelectorAll('.cartao-kpi-acao');
            if(cards.length > 0) {
                let maxH = 0;
                // Reseta a altura para permitir recalcular quando a tela muda de tamanho
                cards.forEach(c => c.style.minHeight = 'auto');
                
                // Encontra qual é o cartão mais alto do grupo
                cards.forEach(c => {
                    if(c.offsetHeight > maxH) maxH = c.offsetHeight;
                });
                
                // Força todos a terem exatamente a mesma altura do maior
                cards.forEach(c => {
                    c.style.minHeight = maxH + 'px';
                });
            }
        }, 500);
    </script>
    """
    components.html(js_equalizer, height=0)
    # ===============================================
        
    st.markdown("<br>", unsafe_allow_html=True)

    # ===============================================
    # O CÉREBRO: LÓGICA DE SEPARAÇÃO DOS PROBLEMAS
    # ===============================================
    lista_gerais = []
    lista_individuais = []

    if not df_parado_puro.empty:
        # Agrupa pelo problema
        df_problemas = df_parado_puro.groupby(['cod_ocorrencia', 'descricao'])['minutos'].sum().reset_index()
        
        for _, row in df_problemas.iterrows():
            cod = row['cod_ocorrencia']
            desc = row['descricao']
            tempo_total_falha = row['minutos']
            perc_do_setor = (tempo_total_falha / tot_par) * 100 if tot_par > 0 else 0
            
            # Filtra apenas os apontamentos deste problema
            df_este_prob = df_parado_puro[df_parado_puro['cod_ocorrencia'] == cod]
            
            # Descobre em qual máquina ele mais bateu
            df_maq_prob = df_este_prob.groupby('maquina')['minutos'].sum().reset_index()
            maq_ofensora = df_maq_prob.loc[df_maq_prob['minutos'].idxmax()]
            
            # Calcula a concentração
            concentracao = maq_ofensora['minutos'] / tempo_total_falha if tempo_total_falha > 0 else 0
            
            # Julgamento (Baseado na configuração salva pelo usuário)
            item_obj = {
                'cod': cod,
                'desc': desc,
                'tempo': tempo_total_falha,
                'perc_setor': perc_do_setor,
                'maq_foco': maq_ofensora['maquina'],
                'concentracao': concentracao * 100
            }
            
            if concentracao >= LIMITE_CONCENTRACAO:
                lista_individuais.append(item_obj)
            else:
                lista_gerais.append(item_obj)

    # Ordena as listas do mais grave (maior tempo perdido) para o menos grave
    lista_gerais = sorted(lista_gerais, key=lambda k: k['tempo'], reverse=True)[:LIMITE_GERAL]
    lista_individuais = sorted(lista_individuais, key=lambda k: k['tempo'], reverse=True)[:LIMITE_INDIVIDUAL]

    # ===============================================
    # GERAÇÃO DO RELATÓRIO EXECUTIVO (UI)
    # ===============================================
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown(f"""
        <div style="background-color: #f8f9fa; padding: 25px; border-radius: 8px; border: 1px solid #eaeaea; height: 100%;">
            <h3 style="color: #2980b9; margin-top: 0; font-size: 20px;">🌎 Problemas Gerais (Afetam o Setor)</h3>
        """, unsafe_allow_html=True)
        
        if not lista_gerais:
            st.markdown("<p style='color: #7f8c8d; font-style: italic;'>Nenhuma falha distribuída identificada no período.</p>", unsafe_allow_html=True)
        else:
            for idx, prob in enumerate(lista_gerais):
                st.markdown(f"""
                <p style="font-size: 16px; color: #333; margin-bottom: 15px; font-weight: 500; line-height: 1.5;">
                    {idx + 1}. Analisar o desvio <b>[{prob['cod']}] - {prob['desc']}</b>. Representa <b>{prob['perc_setor']:.1f}%</b> das perdas do período e afeta a produção de forma distribuída.
                </p>
                """, unsafe_allow_html=True)
                
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div style="background-color: #f8f9fa; padding: 25px; border-radius: 8px; border: 1px solid #eaeaea; height: 100%;">
            <h3 style="color: #f39c12; margin-top: 0; font-size: 20px;">⚙️ Problemas Individuais (Foco por Máquina)</h3>
        """, unsafe_allow_html=True)
        
        if not lista_individuais:
            st.markdown("<p style='color: #7f8c8d; font-style: italic;'>Nenhuma falha altamente concentrada identificada no período.</p>", unsafe_allow_html=True)
        else:
            for idx, prob in enumerate(lista_individuais):
                st.markdown(f"""
                <p style="font-size: 16px; color: #333; margin-bottom: 15px; font-weight: 500; line-height: 1.5;">
                    {idx + 1}. Foco na máquina <b>{prob['maq_foco']}</b>: O desvio <b>[{prob['cod']}] - {prob['desc']}</b> está concentrado nela e representa <b>{prob['perc_setor']:.1f}%</b> de todas as perdas do setor.
                </p>
                """, unsafe_allow_html=True)
                
        st.markdown("</div>", unsafe_allow_html=True)