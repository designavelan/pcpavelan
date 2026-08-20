import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import streamlit.components.v1 as components
import json
import os
import banco 

ARQUIVO_MEMORIA = "filtros_cache.json"

def ler_breakpoints():
    if os.path.exists("layout_config.json"):
        try:
            with open("layout_config.json", "r") as f:
                return json.load(f)
        except: pass
    return {"bp_celular": 768, "bp_tablet": 1024}

def carregar_memoria():
    if os.path.exists(ARQUIVO_MEMORIA):
        try:
            with open(ARQUIVO_MEMORIA, "r") as f:
                return json.load(f)
        except: pass
    return {}

def salvar_memoria():
    dados = {
        "periodo_tipo": st.session_state.get("periodo_tipo", ""),
        "data_de": st.session_state.get("data_de", ""),
        "data_ate": st.session_state.get("data_ate", ""),
        "setor_global": st.session_state.get("setor_global", ""),
        "maquina_global": st.session_state.get("maquina_global", ""),
        "tipo_global": st.session_state.get("tipo_global", ""),
        "ocorrencia_selecionada": st.session_state.get("ocorrencia_selecionada", ""),
        "aba_atual": st.session_state.get("aba_atual", "") 
    }
    try:
        with open(ARQUIVO_MEMORIA, "w") as f:
            json.dump(dados, f)
    except: pass

def iniciar_estados():
    mem = carregar_memoria() 
    if 'periodo_tipo' not in st.session_state: st.session_state.periodo_tipo = mem.get("periodo_tipo", "Último dia com dados")
    if 'data_de' not in st.session_state: st.session_state.data_de = mem.get("data_de", None)
    if 'data_ate' not in st.session_state: st.session_state.data_ate = mem.get("data_ate", None)
    if 'setor_global' not in st.session_state: st.session_state.setor_global = mem.get("setor_global", "[ Todos ]")
    if 'maquina_global' not in st.session_state: st.session_state.maquina_global = mem.get("maquina_global", "[ Todas ]")
    if 'tipo_global' not in st.session_state: st.session_state.tipo_global = mem.get("tipo_global", "Parado") 
    
    if 'ocorrencia_selecionada' not in st.session_state: 
        st.session_state.ocorrencia_selecionada = mem.get("ocorrencia_selecionada", "")
    
    if 'periodo_custom_de' not in st.session_state:
        try: st.session_state.periodo_custom_de = datetime.strptime(st.session_state.data_de, '%Y-%m-%d').date()
        except: st.session_state.periodo_custom_de = (datetime.utcnow() - timedelta(hours=3)).date()
        
    if 'periodo_custom_ate' not in st.session_state:
        try: st.session_state.periodo_custom_ate = datetime.strptime(st.session_state.data_ate, '%Y-%m-%d').date()
        except: st.session_state.periodo_custom_ate = (datetime.utcnow() - timedelta(hours=3)).date()

def obter_datas_validas(df_nuvem):
    if df_nuvem.empty or 'data_registro' not in df_nuvem.columns: return []
    datas = pd.to_datetime(df_nuvem['data_registro']).dt.strftime('%Y-%m-%d').dropna().unique().tolist()
    return sorted(datas)

def calcular_opcoes(datas_validas):
    # Relógio travado no Fuso Horário correto para não virar o dia antes da hora
    hoje = (datetime.utcnow() - timedelta(hours=3)).date()
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

    # --- NOVA OPÇÃO: HOJE ---
    # Fica disponível para permitir o monitoramento das máquinas em tempo real
    str_hoje = hoje.strftime('%Y-%m-%d')
    opcoes.append("Hoje")
    mapa["Hoje"] = (str_hoje, str_hoje)

    if datas_validas:
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

def renderizar_barra_superior(df_nuvem):
    iniciar_estados()
    datas_validas = obter_datas_validas(df_nuvem)
    if not datas_validas:
        st.warning("O banco de dados de apontamentos está vazio.")
        return

    opcoes_per, mapa_per = calcular_opcoes(datas_validas)
    if st.session_state.data_de is None:
        st.session_state.data_de = mapa_per.get("Último dia com dados", (datas_validas[-1], datas_validas[-1]))[0]
        st.session_state.data_ate = mapa_per.get("Último dia com dados", (datas_validas[-1], datas_validas[-1]))[1]

    tipo_salvo = st.session_state.periodo_tipo
    if tipo_salvo in mapa_per:
        st.session_state.data_de = mapa_per[tipo_salvo][0]
        st.session_state.data_ate = mapa_per[tipo_salvo][1]
    elif tipo_salvo not in ["Data Específica", "Período personalizado"]:
        st.session_state.periodo_tipo = "Último dia com dados"
        st.session_state.data_de = mapa_per.get("Último dia com dados", (datas_validas[-1], datas_validas[-1]))[0]
        st.session_state.data_ate = mapa_per.get("Último dia com dados", (datas_validas[-1], datas_validas[-1]))[1]

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
        st.session_state.maquina_global = "[ Todas ]" 
        
    def sync_maq(): 
        st.session_state.maquina_global = st.session_state.seletor_maquina

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

    st.session_state['seletor_periodo'] = st.session_state.periodo_tipo
    st.session_state['seletor_setor'] = st.session_state.setor_global
    st.session_state['seletor_maquina'] = st.session_state.maquina_global

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

def obter_filtros_atuais():
    iniciar_estados()
    filtros = {
        'de': st.session_state.data_de if st.session_state.data_de else "[ Todas ]",
        'ate': st.session_state.data_ate if st.session_state.data_ate else "[ Todas ]",
        'setor': st.session_state.setor_global,
        'maquina': st.session_state.maquina_global,
        'tipo': st.session_state.tipo_global
    }
    salvar_memoria()
    return filtros

# ===============================================
# CONSTRUTOR DO TÍTULO GLOBAL INTELIGENTE
# ===============================================
def renderizar_cabecalho_global(nome_aba):
    d1 = pd.to_datetime(st.session_state.data_de).strftime('%d/%m/%Y') if st.session_state.data_de else ""
    d2 = pd.to_datetime(st.session_state.data_ate).strftime('%d/%m/%Y') if st.session_state.data_ate else ""
    tipo_per = st.session_state.periodo_tipo
    
    df_nuvem = banco.obter_dados_nuvem()
    qtd_dias = 0
    if not df_nuvem.empty and st.session_state.data_de and st.session_state.data_ate:
        df_temp = df_nuvem.copy()
        df_temp['data_registro'] = pd.to_datetime(df_temp['data_registro']).dt.strftime('%Y-%m-%d')
        
        df_temp = df_temp[(df_temp['data_registro'] >= st.session_state.data_de) & (df_temp['data_registro'] <= st.session_state.data_ate)]
        
        if st.session_state.setor_global != "[ Todos ]":
            df_temp = df_temp[df_temp['setor'] == st.session_state.setor_global]
            
        if st.session_state.maquina_global != "[ Todas ]":
            df_temp = df_temp[df_temp['maquina'] == st.session_state.maquina_global]
            
        qtd_dias = df_temp['data_registro'].nunique()
        
    if qtd_dias == 0:
        texto_dias = ""
    elif qtd_dias == 1:
        texto_dias = f" - 1 Dia"
    else:
        texto_dias = f" - {qtd_dias} Dias"
    
    if d1 == d2: texto_data = f"Período: {d1} · {tipo_per}{texto_dias}"
    else: texto_data = f"Período: {d1} a {d2} · {tipo_per}{texto_dias}"
    
    titulo = nome_aba
    if st.session_state.setor_global != "[ Todos ]": 
        titulo += f" — Setor {st.session_state.setor_global}"
    
    if st.session_state.maquina_global != "[ Todas ]": 
        titulo += f" — Máquina {st.session_state.maquina_global}"
        
    html = f"""
    <div style="text-align: center; margin-bottom: 20px;">
        <h2 style="color: #2c3e50; font-weight: 700; margin-bottom: 5px;">{titulo}</h2>
        <div style="color: #e67e22; font-weight: 600; font-size: 16px;">
            <span style="font-size: 18px; margin-right: 5px;">📅</span> {texto_data}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
    
    bp = ler_breakpoints()
    bp_cel = bp.get("bp_celular", 768)
    bp_tab = bp.get("bp_tablet", 1024)
    
    css = f"""
    <style>
    @media (max-width: {bp_tab}px) {{
        .stack-charts {{ flex-wrap: wrap !important; }}
        .stack-charts > div[data-testid="column"] {{
            min-width: 100% !important;
            width: 100% !important;
            flex: 1 1 100% !important;
            margin-bottom: 20px !important;
        }}
        .stack-kpis {{ flex-wrap: wrap !important; }}
        .stack-kpis > div[data-testid="column"] {{
            min-width: 48% !important;
            width: 48% !important;
            flex: 1 1 48% !important;
            margin-bottom: 15px !important;
        }}
    }}
    @media (max-width: {bp_cel}px) {{
        .stack-kpis > div[data-testid="column"] {{
            min-width: 100% !important;
            width: 100% !important;
            flex: 1 1 100% !important;
        }}
    }}
    </style>
    <script>
        setInterval(() => {{
            const chartMarkers = window.parent.document.querySelectorAll('.graficos-container');
            chartMarkers.forEach(m => {{
                const col = m.closest('div[data-testid="column"]');
                if(col && col.parentElement && !col.parentElement.classList.contains('stack-charts')) {{
                    col.parentElement.classList.add('stack-charts');
                }}
            }});
            const kpiMarkers = window.parent.document.querySelectorAll('.kpis-container');
            kpiMarkers.forEach(m => {{
                const col = m.closest('div[data-testid="column"]');
                if(col && col.parentElement && !col.parentElement.classList.contains('stack-kpis')) {{
                    col.parentElement.classList.add('stack-kpis');
                }}
            }});
            const inputs = window.parent.document.querySelectorAll('div[data-baseweb="select"] input');
            inputs.forEach(input => {{
                if(!input.hasAttribute('readonly')) {{
                    input.setAttribute('readonly', 'true');
                    input.style.caretColor = 'transparent';
                    input.style.cursor = 'pointer';
                }}
            }});
        }}, 500);
    </script>
    """
    components.html(css, height=0)