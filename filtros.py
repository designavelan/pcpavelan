import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import streamlit.components.v1 as components
import json
import os

# --- LÊ A CONFIGURAÇÃO DE TELAS ---
def ler_breakpoints():
    if os.path.exists("layout_config.json"):
        try:
            with open("layout_config.json", "r") as f:
                return json.load(f)
        except: pass
    return {"bp_celular": 768, "bp_tablet": 1024}

# --- MEMÓRIA DOS FILTROS (A "CAIXA PRETA") ---
ARQUIVO_MEMORIA = "filtros_cache.json"

def carregar_memoria():
    if os.path.exists(ARQUIVO_MEMORIA):
        try:
            with open(ARQUIVO_MEMORIA, "r") as f:
                return json.load(f)
        except: pass
    return {}

def salvar_memoria():
    dados = {
        "periodo_tipo": st.session_state.periodo_tipo,
        "data_de": st.session_state.data_de,
        "data_ate": st.session_state.data_ate,
        "setor_global": st.session_state.setor_global,
        "maquina_global": st.session_state.maquina_global,
        "tipo_global": st.session_state.tipo_global
    }
    try:
        with open(ARQUIVO_MEMORIA, "w") as f:
            json.dump(dados, f)
    except: pass

# --- SETUP INICIAL DE ESTADOS GLOBAIS ---
def iniciar_estados():
    mem = carregar_memoria() # Puxa a lembrança da última sessão
    
    if 'periodo_tipo' not in st.session_state: st.session_state.periodo_tipo = mem.get("periodo_tipo", "Último dia com dados")
    if 'data_de' not in st.session_state: st.session_state.data_de = mem.get("data_de", None)
    if 'data_ate' not in st.session_state: st.session_state.data_ate = mem.get("data_ate", None)
    if 'setor_global' not in st.session_state: st.session_state.setor_global = mem.get("setor_global", "[ Todos ]")
    if 'maquina_global' not in st.session_state: st.session_state.maquina_global = mem.get("maquina_global", "[ Todas ]")
    if 'tipo_global' not in st.session_state: st.session_state.tipo_global = mem.get("tipo_global", "Parado") 
    
    if 'periodo_custom_de' not in st.session_state:
        try: st.session_state.periodo_custom_de = datetime.strptime(st.session_state.data_de, '%Y-%m-%d').date()
        except: st.session_state.periodo_custom_de = datetime.now().date()
        
    if 'periodo_custom_ate' not in st.session_state:
        try: st.session_state.periodo_custom_ate = datetime.strptime(st.session_state.data_ate, '%Y-%m-%d').date()
        except: st.session_state.periodo_custom_ate = datetime.now().date()

# --- INTELIGÊNCIA DO CALENDÁRIO ---
def obter_datas_validas(df_nuvem):
    if df_nuvem.empty or 'data_registro' not in df_nuvem.columns: return []
    datas = pd.to_datetime(df_nuvem['data_registro']).dt.strftime('%Y-%m-%d').dropna().unique().tolist()
    return sorted(datas)

def calcular_opcoes(datas_validas):
    hoje = datetime.now().date()
    ontem = hoje - timedelta(days=1)
    anteontem = hoje - timedelta(days=2)
    inicio_semana = hoje - timedelta(days=hoje.weekday())
    fim_semana = inicio_semana + timedelta(days=4) 
    inicio_semana_passada = inicio_semana - timedelta(days=7)
    fim_semana_passada = inicio_semana_passada + timedelta(days=4) 
    inicio_mes = hoje.replace(day=1)

    opcoes = []
    mapa = {}

    if datas_validas:
        ultimo = datas_validas[-1]
        opcoes.append("Último dia com dados")
        mapa["Último dia com dados"] = (ultimo, ultimo)

        str_ontem = ontem.strftime('%Y-%m-%d')
        if str_ontem in datas_validas:
            opcoes.append("Ontem")
            mapa["Ontem"] = (str_ontem, str_ontem)

        str_anteontem = anteontem.strftime('%Y-%m-%d')
        if str_anteontem in datas_validas:
            opcoes.append("Anteontem")
            mapa["Anteontem"] = (str_anteontem, str_anteontem)

        d_semana = [d for d in datas_validas if inicio_semana.strftime('%Y-%m-%d') <= d <= fim_semana.strftime('%Y-%m-%d')]
        if d_semana:
            opcoes.append("Esta semana")
            mapa["Esta semana"] = (inicio_semana.strftime('%Y-%m-%d'), fim_semana.strftime('%Y-%m-%d'))

        d_sem_passada = [d for d in datas_validas if inicio_semana_passada.strftime('%Y-%m-%d') <= d <= fim_semana_passada.strftime('%Y-%m-%d')]
        if d_sem_passada:
            opcoes.append("Semana passada")
            mapa["Semana passada"] = (inicio_semana_passada.strftime('%Y-%m-%d'), fim_semana_passada.strftime('%Y-%m-%d'))

        d_mes = [d for d in datas_validas if inicio_mes.strftime('%Y-%m-%d') <= d <= hoje.strftime('%Y-%m-%d')]
        if d_mes:
            opcoes.append("Este mês")
            mapa["Este mês"] = (inicio_mes.strftime('%Y-%m-%d'), hoje.strftime('%Y-%m-%d'))

    opcoes.append("Data Específica")
    opcoes.append("Período personalizado")
    return opcoes, mapa

# --- RENDERIZADOR GLOBAL ---
def renderizar_barra_superior(df_nuvem):
    iniciar_estados()
    datas_validas = obter_datas_validas(df_nuvem)
    
    if not datas_validas:
        st.warning("O banco de dados de apontamentos está vazio.")
        return

    opcoes_per, mapa_per = calcular_opcoes(datas_validas)

    # 1. Fallback caso seja a primeira vez de todas rodando o app
    if st.session_state.data_de is None:
        st.session_state.data_de = mapa_per.get("Último dia com dados", (datas_validas[-1], datas_validas[-1]))[0]
        st.session_state.data_ate = mapa_per.get("Último dia com dados", (datas_validas[-1], datas_validas[-1]))[1]

    # 2. Atualiza datas dinâmicas silenciosamente (Para os casos de virada de semana/mês)
    tipo_salvo = st.session_state.periodo_tipo
    if tipo_salvo in mapa_per:
        st.session_state.data_de = mapa_per[tipo_salvo][0]
        st.session_state.data_ate = mapa_per[tipo_salvo][1]
    elif tipo_salvo not in ["Data Específica", "Período personalizado"]:
        st.session_state.periodo_tipo = "Último dia com dados"
        st.session_state.data_de = mapa_per.get("Último dia com dados", (datas_validas[-1], datas_validas[-1]))[0]
        st.session_state.data_ate = mapa_per.get("Último dia com dados", (datas_validas[-1], datas_validas[-1]))[1]

    # Callbacks de sincronização e regras de UX
    def on_change_periodo():
        val = st.session_state.seletor_periodo
        st.session_state.periodo_tipo = val
        if val in mapa_per:
            st.session_state.data_de = mapa_per[val][0]
            st.session_state.data_ate = mapa_per[val][1]

    def on_click_voltar():
        anteriores = [d for d in datas_validas if d < st.session_state.data_de]
        if anteriores:
            st.session_state.data_de = anteriores[-1]
            st.session_state.data_ate = anteriores[-1]
            st.session_state.periodo_tipo = "Data Específica"

    def on_click_avancar():
        proximos = [d for d in datas_validas if d > st.session_state.data_ate]
        if proximos:
            st.session_state.data_de = proximos[0]
            st.session_state.data_ate = proximos[0]
            st.session_state.periodo_tipo = "Data Específica"

    def sync_setor(): 
        st.session_state.setor_global = st.session_state.seletor_setor
        st.session_state.maquina_global = "[ Todas ]" # Melhora UX: evita manter máquina de outro setor
        
    def sync_maq(): 
        st.session_state.maquina_global = st.session_state.seletor_maquina

    # Preparação dos índices para exibir o que está na memória
    try: idx_per = opcoes_per.index(st.session_state.periodo_tipo)
    except: idx_per = 0

    lista_setores = ["[ Todos ]"] + sorted(df_nuvem['setor'].dropna().unique().tolist())
    try: idx_setor = lista_setores.index(st.session_state.setor_global)
    except: 
        idx_setor = 0
        st.session_state.setor_global = "[ Todos ]"

    if df_nuvem.empty: maq = ["[ Todas ]"]
    elif st.session_state.setor_global != "[ Todos ]":
        maq = ["[ Todas ]"] + sorted(df_nuvem[df_nuvem['setor'] == st.session_state.setor_global]['maquina'].dropna().unique().tolist())
    else: maq = ["[ Todas ]"] + sorted(df_nuvem['maquina'].dropna().unique().tolist())
    
    try: idx_m = maq.index(st.session_state.maquina_global)
    except: 
        idx_m = 0
        st.session_state.maquina_global = "[ Todas ]"

    pode_voltar = any(d < st.session_state.data_de for d in datas_validas)
    pode_avancar = any(d > st.session_state.data_ate for d in datas_validas)

    d1 = pd.to_datetime(st.session_state.data_de).strftime('%d/%m/%y')
    d2 = pd.to_datetime(st.session_state.data_ate).strftime('%d/%m/%y')
    texto_data_curto = f"{d1}" if d1 == d2 else f"{d1} a {d2}"

    # ANTI-TECLADO JS (Obrigatório para a UX no celular)
    components.html("""
    <script>
        setInterval(() => {
            const inputs = window.parent.document.querySelectorAll('div[data-baseweb="select"] input');
            inputs.forEach(input => {
                if(!input.hasAttribute('readonly')) {
                    input.setAttribute('readonly', 'true');
                    input.style.caretColor = 'transparent';
                    input.style.cursor = 'pointer';
                }
            });
        }, 300);
    </script>
    """, height=0)

    # =========================================================
    # A GAVETA DE FILTROS DEFINITIVA
    # =========================================================
    with st.expander(f"⚙️ Filtros | 📅 {texto_data_curto} | 🏢 {st.session_state.setor_global}"):
        st.selectbox("📅 Período", opcoes_per, index=idx_per, key='seletor_periodo', on_change=on_change_periodo)
        
        c1, c2 = st.columns(2)
        with c1: st.button("⬅️ Navegar para dia anterior", disabled=not pode_voltar, on_click=on_click_voltar, use_container_width=True)
        with c2: st.button("Navegar para próximo dia ➡️", disabled=not pode_avancar, on_click=on_click_avancar, use_container_width=True)
        
        if st.session_state.periodo_tipo == "Período personalizado":
            cd1, cd2 = st.columns(2)
            with cd1: st.date_input("De:", key="periodo_custom_de")
            with cd2: st.date_input("Até:", key="periodo_custom_ate")
            st.session_state.data_de = st.session_state.periodo_custom_de.strftime('%Y-%m-%d')
            st.session_state.data_ate = st.session_state.periodo_custom_ate.strftime('%Y-%m-%d')

        cs1, cs2 = st.columns(2)
        with cs1: st.selectbox("🏢 Setor", lista_setores, index=idx_setor, key='seletor_setor', on_change=sync_setor)
        with cs2: st.selectbox("⚙️ Máquina", maq, index=idx_m, key='seletor_maquina', on_change=sync_maq)

# --- ABA ANTIGA (Removida, mantemos a função vazia para não dar erro no app.py caso precise) ---
def renderizar_ui(df_nuvem):
    pass

# --- EXPORTADOR ---
def obter_filtros_atuais():
    iniciar_estados()
    filtros = {
        'de': st.session_state.data_de if st.session_state.data_de else "[ Todas ]",
        'ate': st.session_state.data_ate if st.session_state.data_ate else "[ Todas ]",
        'setor': st.session_state.setor_global,
        'maquina': st.session_state.maquina_global,
        'tipo': st.session_state.tipo_global
    }
    salvar_memoria() # <-- SALVA TUDO AUTOMATICAMENTE AQUI!
    return filtros

# --- TÍTULOS ---
def renderizar_cabecalho_global(nome_aba):
    d1 = pd.to_datetime(st.session_state.data_de).strftime('%d/%m/%Y') if st.session_state.data_de else ""
    d2 = pd.to_datetime(st.session_state.data_ate).strftime('%d/%m/%Y') if st.session_state.data_ate else ""
    
    tipo_per = st.session_state.periodo_tipo
    
    if d1 == d2: texto_data = f"Período: {d1} · {tipo_per}"
    else: texto_data = f"Período: {d1} a {d2} · {tipo_per}"
    
    if st.session_state.setor_global != "[ Todos ]": titulo = f"{nome_aba} — Setor {st.session_state.setor_global}"
    else: titulo = nome_aba
        
    html = f"""
    <div style="text-align: center; margin-bottom: 20px;">
        <h2 style="color: #2c3e50; font-weight: 700; margin-bottom: 5px;">{titulo}</h2>
        <div style="color: #e67e22; font-weight: 600; font-size: 16px;">
            <span style="font-size: 18px; margin-right: 5px;">📅</span> {texto_data}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)