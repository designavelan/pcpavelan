import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import banco

def construir_menu_semanas(datas_unicas):
    if not datas_unicas: return {}
    datas_dt = [datetime.strptime(d, '%Y-%m-%d') for d in datas_unicas]
    datas_dt.sort()
    dicionario_semanas = {"[ Todas ]": {"inicio": None, "fim": None}}
    meses_pt = {1: 'JANEIRO', 2: 'FEVEREIRO', 3: 'MARÇO', 4: 'ABRIL', 5: 'MAIO', 6: 'JUNHO',
                7: 'JULHO', 8: 'AGOSTO', 9: 'SETEMBRO', 10: 'OUTUBRO', 11: 'NOVEMBRO', 12: 'DEZEMBRO'}
    mes_atual = None
    semana_count = 1
    
    for dt in datas_dt:
        inicio_semana = dt - timedelta(days=dt.weekday())
        fim_semana = inicio_semana + timedelta(days=4)
        titulo_mes = f"--- {meses_pt[dt.month]} {dt.year} ---"
        if f"{dt.year}-{dt.month}" != mes_atual:
            if titulo_mes not in dicionario_semanas:
                dicionario_semanas[titulo_mes] = {"inicio": None, "fim": None}
            mes_atual = f"{dt.year}-{dt.month}"
            semana_count = 1
            
        str_inicio = inicio_semana.strftime("%d/%m")
        str_fim = fim_semana.strftime("%d/%m")
        nome_semana = f"Semana {semana_count} ({str_inicio} a {str_fim})"
        if nome_semana not in dicionario_semanas.keys():
            dicionario_semanas[nome_semana] = {
                "inicio": inicio_semana.strftime("%Y-%m-%d"),
                "fim": (inicio_semana + timedelta(days=6)).strftime("%Y-%m-%d")
            }
            semana_count += 1
    return dicionario_semanas

def obter_filtros_atuais():
    cfg = banco.obter_configuracoes()
    return {
        'sem': cfg.get('f_sem', '[ Todas ]'),
        'de': cfg.get('f_de', '[ Todas ]'),
        'ate': cfg.get('f_ate', '[ Todas ]'),
        'setor': cfg.get('f_setor', '[ Todos ]'),
        'maquina': cfg.get('f_maq', '[ Todas ]'),
        'tipo': cfg.get('f_tipo', 'Parado')
    }

def salvar_filtros_global():
    try:
        supa = banco.conectar()
        dados = {
            "f_sem": st.session_state.get('g_sem', '[ Todas ]'),
            "f_de": st.session_state.get('g_de', '[ Todas ]'),
            "f_ate": st.session_state.get('g_ate', '[ Todas ]'),
            "f_setor": st.session_state.get('g_setor', '[ Todos ]'),
            "f_maq": st.session_state.get('g_maq', '[ Todas ]'),
            "f_tipo": st.session_state.get('g_tipo', 'Parado')
        }
        supa.table("configuracoes").update(dados).eq("id", 1).execute()
    except: pass

# ---> NOVA FUNÇÃO: Renderiza apenas o Setor para colocar fora das abas
def renderizar_filtro_setor(df_nuvem):
    if df_nuvem.empty: return
    cfg = banco.obter_configuracoes()
    if 'g_setor' not in st.session_state: st.session_state.g_setor = cfg.get('f_setor', '[ Todos ]')
    
    list_setores = ["[ Todos ]"] + sorted(df_nuvem['setor'].unique().tolist())
    if st.session_state.g_setor not in list_setores: st.session_state.g_setor = "[ Todos ]"
    
    st.selectbox("🏭 Setor Analisado:", list_setores, key='g_setor', on_change=salvar_filtros_global)

def renderizar_ui(df_nuvem):
    if df_nuvem.empty:
        st.info("Importe dados de produção para visualizar os filtros.")
        return

    cfg = banco.obter_configuracoes()
    df_nuvem['data_registro_fmt'] = pd.to_datetime(df_nuvem['data_registro']).dt.strftime('%Y-%m-%d')
    datas_lista = sorted(df_nuvem['data_registro_fmt'].unique().tolist())
    ultima_data = datas_lista[-1] if datas_lista else "[ Todas ]"
    
    if 'g_sem' not in st.session_state: st.session_state.g_sem = cfg.get('f_sem', '[ Todas ]')
    if 'g_de' not in st.session_state: st.session_state.g_de = cfg.get('f_de', '[ Todas ]')
    if 'g_ate' not in st.session_state: st.session_state.g_ate = cfg.get('f_ate', '[ Todas ]')
    if 'g_maq' not in st.session_state: st.session_state.g_maq = cfg.get('f_maq', '[ Todas ]')
    if 'g_tipo' not in st.session_state: st.session_state.g_tipo = cfg.get('f_tipo', 'Parado')

    dict_semanas = construir_menu_semanas(datas_lista)

    def set_ultimo_dia():
        st.session_state.g_de = ultima_data
        st.session_state.g_ate = ultima_data
        st.session_state.g_sem = "[ Todas ]"
        salvar_filtros_global()

    st.markdown("### 🔍 Filtros de Visualização")
    st.markdown("As configurações selecionadas aqui serão aplicadas a todas as abas.")
    st.markdown("<br>", unsafe_allow_html=True)

    col_btn1, col_btn2, col_btn3 = st.columns([3, 3, 2])
    with col_btn3:
        st.button("📅 Selecionar Último Dia", on_click=set_ultimo_dia, use_container_width=True)

    c1, c2, c3 = st.columns(3)
    def callback_semana():
        esc = st.session_state.g_sem
        if esc != "[ Todas ]" and "---" not in esc:
            inicio = dict_semanas[esc]['inicio']
            fim = dict_semanas[esc]['fim']
            st.session_state.g_de = inicio if inicio in datas_lista else datas_lista[0] 
            st.session_state.g_ate = fim if fim in datas_lista else datas_lista[-1] 
        salvar_filtros_global()
            
    with c1: 
        if st.session_state.g_sem not in list(dict_semanas.keys()): st.session_state.g_sem = "[ Todas ]"
        st.selectbox("Período da Semana:", list(dict_semanas.keys()), key='g_sem', on_change=callback_semana)
    with c2: 
        if st.session_state.g_de not in ["[ Todas ]"] + datas_lista: st.session_state.g_de = "[ Todas ]"
        st.selectbox("Data Inicial (De):", ["[ Todas ]"] + datas_lista, key='g_de', on_change=salvar_filtros_global)
    with c3: 
        if st.session_state.g_ate not in ["[ Todas ]"] + datas_lista: st.session_state.g_ate = "[ Todas ]"
        st.selectbox("Data Final (Até):", ["[ Todas ]"] + datas_lista, key='g_ate', on_change=salvar_filtros_global)
        
    st.markdown("<br>", unsafe_allow_html=True)

    # REMOVIDO O SETOR DAQUI, AGORA SÃO APENAS 2 COLUNAS
    c4, c5 = st.columns(2)
    with c4:
        maq_base = df_nuvem['maquina'] if st.session_state.g_setor == "[ Todos ]" else df_nuvem[df_nuvem['setor'] == st.session_state.g_setor]['maquina']
        list_maq = ["[ Todas ]"] + sorted(maq_base.unique().tolist())
        if st.session_state.g_maq not in list_maq: st.session_state.g_maq = "[ Todas ]"
        st.selectbox("Filtro por Máquina:", list_maq, key='g_maq', on_change=salvar_filtros_global)
    with c5: 
        list_tipos = ["[ Todos ]", "Parado", "Trabalhando"]
        if st.session_state.g_tipo not in list_tipos: st.session_state.g_tipo = "Parado"
        st.selectbox("Visualização (Tipo):", list_tipos, key='g_tipo', on_change=salvar_filtros_global)
        # ... (mantenha todo o código existente do filtros.py acima) ...

def renderizar_cabecalho_global(titulo_modulo):
    """Função reutilizável para gerar os títulos e períodos em qualquer aba"""
    cfg = banco.obter_configuracoes()
    setor = st.session_state.get('g_setor', cfg.get('f_setor', '[ Todos ]'))
    maquina = st.session_state.get('g_maq', cfg.get('f_maq', '[ Todas ]'))
    semana = st.session_state.get('g_sem', cfg.get('f_sem', '[ Todas ]'))
    de = st.session_state.get('g_de', cfg.get('f_de', '[ Todas ]'))
    ate = st.session_state.get('g_ate', cfg.get('f_ate', '[ Todas ]'))

    # Lógica do Título Principal
    if maquina != "[ Todas ]":
        local = maquina
    elif setor != "[ Todos ]":
        local = f"Setor {setor}"
    else:
        local = "Fábrica Geral"

    titulo_final = f"{titulo_modulo} — {local}"

    # Lógica do Subtítulo (Período)
    if semana != "[ Todas ]" and "---" not in semana:
        periodo_str = semana
    else:
        if de == ate and de != "[ Todas ]":
            d_fmt = pd.to_datetime(de).strftime('%d/%m/%Y')
            periodo_str = f"Dia: {d_fmt}"
        elif de != "[ Todas ]" and ate != "[ Todas ]":
            d_fmt = pd.to_datetime(de).strftime('%d/%m/%Y')
            a_fmt = pd.to_datetime(ate).strftime('%d/%m/%Y')
            periodo_str = f"Período: {d_fmt} a {a_fmt}"
        else:
            periodo_str = "Todo o Período"

    # Renderiza em HTML centralizado (Tema Claro)
    html = f"""
    <div style="text-align: center; margin-bottom: 30px; margin-top: 10px;">
        <h2 style="color: #2c3e50; margin-bottom: 5px; font-weight: bold;">{titulo_final}</h2>
        <h5 style="color: #e67e22; margin-top: 0;">📅 {periodo_str}</h5>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)