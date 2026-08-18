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

def renderizar(df_nuvem):
    if df_nuvem.empty:
        return None

    # Busca a memória eterna do Banco de Dados
    cfg = banco.obter_configuracoes()

    df_nuvem['data_registro_fmt'] = pd.to_datetime(df_nuvem['data_registro']).dt.strftime('%Y-%m-%d')
    datas_lista = sorted(df_nuvem['data_registro_fmt'].unique().tolist())
    ultima_data = datas_lista[-1] if datas_lista else "[ Todas ]"
    
    # INICIALIZA A MEMÓRIA BASEADA NO BANCO DE DADOS
    if 'g_sem' not in st.session_state: st.session_state.g_sem = cfg.get('f_sem', '[ Todas ]')
    if 'g_de' not in st.session_state: st.session_state.g_de = cfg.get('f_de', '[ Todas ]')
    if 'g_ate' not in st.session_state: st.session_state.g_ate = cfg.get('f_ate', '[ Todas ]')
    if 'g_setor' not in st.session_state: st.session_state.g_setor = cfg.get('f_setor', '[ Todos ]')
    if 'g_maq' not in st.session_state: st.session_state.g_maq = cfg.get('f_maq', '[ Todas ]')
    if 'g_tipo' not in st.session_state: st.session_state.g_tipo = cfg.get('f_tipo', 'Parado')

    dict_semanas = construir_menu_semanas(datas_lista)

    # FUNÇÃO QUE SALVA NO BANCO SEMPRE QUE UM FILTRO É MEXIDO
    def salvar_filtros():
        try:
            supa = banco.conectar()
            dados = {
                "f_sem": st.session_state.g_sem,
                "f_de": st.session_state.g_de,
                "f_ate": st.session_state.g_ate,
                "f_setor": st.session_state.g_setor,
                "f_maq": st.session_state.g_maq,
                "f_tipo": st.session_state.g_tipo
            }
            supa.table("configuracoes").update(dados).eq("id", 1).execute()
        except:
            pass

    def set_ultimo_dia():
        st.session_state.g_de = ultima_data
        st.session_state.g_ate = ultima_data
        st.session_state.g_sem = "[ Todas ]"
        salvar_filtros()

    col_espaco, col_btn = st.columns([8, 1.5])
    with col_btn:
        st.button("📅 Último Dia", on_click=set_ultimo_dia, use_container_width=True)

    c1, c2, c3, c4, c5, c6 = st.columns([1.5, 1, 1, 1.2, 1.2, 1.2])
    
    def callback_semana():
        esc = st.session_state.g_sem
        if esc != "[ Todas ]" and "---" not in esc:
            inicio = dict_semanas[esc]['inicio']
            fim = dict_semanas[esc]['fim']
            st.session_state.g_de = inicio if inicio in datas_lista else datas_lista[0] 
            st.session_state.g_ate = fim if fim in datas_lista else datas_lista[-1] 
        salvar_filtros()
            
    with c1: 
        if st.session_state.g_sem not in list(dict_semanas.keys()): st.session_state.g_sem = "[ Todas ]"
        st.selectbox("Semana:", list(dict_semanas.keys()), key='g_sem', on_change=callback_semana)
    
    with c2: 
        if st.session_state.g_de not in ["[ Todas ]"] + datas_lista: st.session_state.g_de = "[ Todas ]"
        st.selectbox("De:", ["[ Todas ]"] + datas_lista, key='g_de', on_change=salvar_filtros)
        
    with c3: 
        if st.session_state.g_ate not in ["[ Todas ]"] + datas_lista: st.session_state.g_ate = "[ Todas ]"
        st.selectbox("Até:", ["[ Todas ]"] + datas_lista, key='g_ate', on_change=salvar_filtros)
        
    with c4: 
        list_setores = ["[ Todos ]"] + sorted(df_nuvem['setor'].unique().tolist())
        if st.session_state.g_setor not in list_setores: st.session_state.g_setor = "[ Todos ]"
        st.selectbox("Setor:", list_setores, key='g_setor', on_change=salvar_filtros)
        
    with c5:
        maq_base = df_nuvem['maquina'] if st.session_state.g_setor == "[ Todos ]" else df_nuvem[df_nuvem['setor'] == st.session_state.g_setor]['maquina']
        list_maq = ["[ Todas ]"] + sorted(maq_base.unique().tolist())
        # Proteção: se mudar de setor e a máquina não existir, volta pra Todas
        if st.session_state.g_maq not in list_maq: st.session_state.g_maq = "[ Todas ]"
        st.selectbox("Máquina:", list_maq, key='g_maq', on_change=salvar_filtros)
        
    with c6: 
        list_tipos = ["[ Todos ]", "Parado", "Trabalhando"]
        if st.session_state.g_tipo not in list_tipos: st.session_state.g_tipo = "Parado"
        st.selectbox("Tipo:", list_tipos, key='g_tipo', on_change=salvar_filtros)

    st.markdown("---")

    return {
        'de': st.session_state.g_de,
        'ate': st.session_state.g_ate,
        'setor': st.session_state.g_setor,
        'maquina': st.session_state.g_maq,
        'tipo': st.session_state.g_tipo
    }