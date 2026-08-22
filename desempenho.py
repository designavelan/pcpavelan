import streamlit as st
import pandas as pd
import plotly.express as px
import banco
from datetime import timedelta

def criar_cartao(titulo, valor_principal, valor_secundario="", cor_borda="#3498db"):
    html = f"""
    <div style="background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #eaeaea; border-left: 5px solid {cor_borda}; text-align: left; box-shadow: 0 4px 10px rgba(0,0,0,0.05); height: 100%; display: flex; flex-direction: column; justify-content: center;">
        <p style="margin: 0 0 5px 0; color: #7f8c8d; font-size: 13px; text-transform: uppercase; font-weight: 800; letter-spacing: 1px;">{titulo}</p>
        <h2 style="margin: 0; color: #2c3e50; font-size: 32px; font-weight: 900; line-height: 1.1;">{valor_principal}</h2>
        <p style="margin: 8px 0 0 0; color: #95a5a6; font-size: 13px; font-weight: 600;">{valor_secundario}</p>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def renderizar():
    st.markdown("""
        <style>
        ::-webkit-scrollbar { display: none; }
        .block-container { max-width: 98% !important; padding-top: 1rem !important; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<h2 style='color: #2c3e50; font-weight: 900; text-transform: uppercase;'>🏆 Desempenho e Capacidade Produtiva</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #7f8c8d; font-size: 16px; font-weight: 500;'>Acompanhe os recordes de produção, compare o desempenho entre máquinas e visualize a eficiência real dos operadores.</p>", unsafe_allow_html=True)
    st.markdown("<hr style='opacity: 0.2; margin-top: 10px; margin-bottom: 25px;'>", unsafe_allow_html=True)

    supa = banco.conectar()
    
    # Busca os dados de recordes
    resp = supa.table("producao_recordes").select("*").execute()
    if not resp.data:
        st.info("Ainda não há recordes de produção registrados. Conclua os lotes no Chão de Fábrica para o sistema começar a gerar este histórico de inteligência.")
        return
        
    df = pd.DataFrame(resp.data)
    df['data_recorde'] = pd.to_datetime(df['data_recorde'])
    df['pecas_por_hora'] = df['pecas_por_hora'].astype(float)
    
    # ==========================================
    # CÁLCULO DA COLUNA "PRODUÇÃO" (INÍCIO / FIM — QTDE)
    # ==========================================
    def formatar_producao(row):
        try:
            fim = row['data_recorde']
            minutos = float(row.get('tempo_gasto_minutos', 0))
            qtd = int(row.get('quantidade_produzida', 0))
            
            inicio = fim - pd.Timedelta(minutes=minutos)
            
            # Formatação sem zero à esquerda na hora (ex: 9:02)
            inicio_str = f"{inicio.hour}:{inicio.minute:02d}"
            fim_str = f"{fim.hour}:{fim.minute:02d}"
            
            return f"{inicio_str} / {fim_str} — {qtd} peças"
        except:
            return "---"
            
    df['str_producao'] = df.apply(formatar_producao, axis=1)

    # ==========================================
    # LÓGICA DO MODELO HÍBRIDO (ATUALIZAÇÃO DE NOME)
    # ==========================================
    df_produtos = banco.obter_produtos_matriz()
    if not df_produtos.empty:
        dict_produtos = {}
        for _, row in df_produtos.iterrows():
            codigo = str(row.get('cod', '')).strip()
            nome_formatado = f"{row.get('produto_formula', '')} ➔ {row.get('descricao', '')}"
            dict_produtos[codigo] = nome_formatado
        
        df['nome_peca'] = df.apply(lambda r: dict_produtos.get(str(r.get('cod_peca', '')).strip(), r['nome_peca']), axis=1)

    # ==========================================
    # 1. FILTROS ESTRATÉGICOS
    # ==========================================
    st.markdown("<div style='background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; margin-bottom: 25px;'>", unsafe_allow_html=True)
    st.markdown("<h4 style='margin-top: 0; color: #34495e;'>🔎 Filtros de Análise</h4>", unsafe_allow_html=True)
    
    c1, c2, c3, c4 = st.columns(4)
    
    lista_setores = ['[ Todos ]'] + sorted(df['setor'].dropna().unique().tolist())
    with c1: sel_setor = st.selectbox("Setor", lista_setores)
    if sel_setor != '[ Todos ]': df = df[df['setor'] == sel_setor]
    
    lista_maquinas = ['[ Todas ]'] + sorted(df['maquina'].dropna().unique().tolist())
    with c2: sel_maq = st.selectbox("Máquina", lista_maquinas)
    if sel_maq != '[ Todas ]': df = df[df['maquina'] == sel_maq]
    
    lista_pecas = ['[ Todas ]'] + sorted(df['nome_peca'].dropna().unique().tolist())
    with c3: sel_peca = st.selectbox("Produto / Peça", lista_pecas)
    if sel_peca != '[ Todas ]': df = df[df['nome_peca'] == sel_peca]
    
    lista_mod = ['[ Todas ]'] + sorted(df['modalidade_processo'].dropna().unique().tolist())
    with c4: sel_mod = st.selectbox("Modalidade", lista_mod)
    if sel_mod != '[ Todas ]': df = df[df['modalidade_processo'] == sel_mod]
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    if df.empty:
        st.warning("Nenhum dado encontrado para os filtros selecionados.")
        return

    # ==========================================
    # 2. HALL DA FAMA (Métricas Principais)
    # ==========================================
    melhor_idx = df['pecas_por_hora'].idxmax()
    melhor_recorde = df.loc[melhor_idx]
    
    desc_peca = str(melhor_recorde['nome_peca']).split('➔')[-1].strip() if '➔' in str(melhor_recorde['nome_peca']) else str(melhor_recorde['nome_peca'])
    
    titulo_hall = f"🌟 Hall da Fama — {desc_peca}" if sel_peca != '[ Todas ]' else "🌟 Hall da Fama (Maior Recorde Global no Filtro)"
    st.markdown(f"<h3 style='color: #2c3e50; font-weight: 900; margin-bottom: 15px;'>{titulo_hall}</h3>", unsafe_allow_html=True)
    
    m1, m2, m3, m4 = st.columns(4)
    
    # Subtítulo combinado: Linha 1 a Produção (contexto) / Linha 2 a Modalidade
    sub_pico = f"{melhor_recorde['str_producao']} <br> Modalidade: {melhor_recorde['modalidade_processo']}"
    
    with m1: criar_cartao("Pico de Produção", f"{melhor_recorde['pecas_por_hora']:.0f} pç/h", sub_pico, "#3498db")
    with m2: criar_cartao("Operador de Elite", melhor_recorde['operador'], "Responsável pelo recorde", "#f39c12")
    with m3: criar_cartao("Máquina Campeã", melhor_recorde['maquina'], f"Setor: {melhor_recorde['setor']}", "#27ae60")
    with m4: criar_cartao("Data do Feito", melhor_recorde['data_recorde'].strftime("%d/%m/%Y"), melhor_recorde['data_recorde'].strftime("às %H:%M"), "#9b59b6")
    
    st.markdown("<hr style='opacity: 0.2; margin: 35px 0;'>", unsafe_allow_html=True)
    
    # ==========================================
    # 3. GRÁFICOS E TABELAS
    # ==========================================
    g1, g2 = st.columns([6, 4])
    
    with g1:
        st.markdown("<h4 style='color: #2c3e50; font-weight: 800;'>📊 Racha de Máquinas (Recordes Atuais)</h4>", unsafe_allow_html=True)
        df_atuais = df[df['is_recorde_atual'] == True].copy()
        
        if df_atuais.empty:
            st.info("Não há recordes marcados como 'atuais' neste filtro.")
        else:
            if sel_peca != '[ Todas ]':
                fig = px.bar(df_atuais, x='maquina', y='pecas_por_hora', color='maquina', text='pecas_por_hora',
                             hover_data=['operador', 'str_producao', 'modalidade_processo'],
                             color_discrete_sequence=px.colors.qualitative.Bold)
                titulo_grafico = "Capacidade por Máquina para a mesma peça"
            else:
                df_top = df_atuais.sort_values('pecas_por_hora', ascending=False).head(10)
                df_top['Label'] = df_top['maquina'] + "<br>(" + df_top['nome_peca'].str.split('➔').str[-1].str.strip() + ")"
                fig = px.bar(df_top, x='Label', y='pecas_por_hora', color='maquina', text='pecas_por_hora',
                             hover_data=['operador', 'str_producao', 'modalidade_processo', 'nome_peca'],
                             color_discrete_sequence=px.colors.qualitative.Bold)
                titulo_grafico = "Top 10 Maiores Velocidades Registradas"
                         
            fig.update_traces(texttemplate='<b>%{text:.0f}</b>', textposition='outside', textfont=dict(size=14))
            fig.update_layout(
                showlegend=False, xaxis_title="", yaxis_title="Peças por Hora", 
                margin=dict(t=30, b=0, l=0, r=0), height=350,
                title=dict(text=titulo_grafico, font=dict(size=14, color="#7f8c8d")),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)"
            )
            fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#f0f0f0', range=[0, df_atuais['pecas_por_hora'].max() * 1.2])
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with g2:
        st.markdown("<h4 style='color: #2c3e50; font-weight: 800;'>📖 Histórico de Evolução</h4>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 13px; color: #7f8c8d; margin-top: -10px;'>Acompanhe os recordes antigos que já foram superados.</p>", unsafe_allow_html=True)
        
        df_hist = df[['data_recorde', 'operador', 'pecas_por_hora', 'str_producao', 'modalidade_processo', 'is_recorde_atual']].copy()
        df_hist = df_hist.sort_values('data_recorde', ascending=False)
        
        df_hist['Data'] = df_hist['data_recorde'].dt.strftime("%d/%m/%Y")
        df_hist['Pç/h'] = df_hist['pecas_por_hora'].round(0).astype(int)
        df_hist['Status'] = df_hist['is_recorde_atual'].apply(lambda x: "🏆 Rei Atual" if x else "⏳ Superado")
        
        # INCLUINDO A NOVA COLUNA "PRODUÇÃO" NA TABELA
        df_tabela = df_hist[['Data', 'Pç/h', 'str_producao', 'operador', 'modalidade_processo', 'Status']]
        df_tabela.columns = ['Data', 'Pç/h', 'Produção', 'Operador', 'Modo', 'Status']
        
        st.dataframe(df_tabela, use_container_width=True, hide_index=True, height=330)