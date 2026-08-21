import streamlit as st
import banco
from datetime import datetime
import base64
import json
import os

def ler_breakpoints():
    if os.path.exists("layout_config.json"):
        try:
            with open("layout_config.json", "r") as f:
                return json.load(f)
        except: pass
    return {"bp_celular": 768, "bp_tablet": 1024}

def salvar_breakpoints(cel, tab):
    with open("layout_config.json", "w") as f:
        json.dump({"bp_celular": cel, "bp_tablet": tab}, f)

def obter_parametros():
    cfg = banco.obter_configuracoes()
    meta = float(cfg.get('meta_disponibilidade', 85.0))
    m_das = cfg.get('manha_das', '07:00')
    m_as = cfg.get('manha_as', '12:00')
    t_das = cfg.get('tarde_das', '13:00')
    t_as = cfg.get('tarde_as', '16:20')
    
    lm_das = cfg.get('lanche_m_das', '')
    lm_as = cfg.get('lanche_m_as', '')
    lt_das = cfg.get('lanche_t_das', '')
    lt_as = cfg.get('lanche_t_as', '')

    fmt = '%H:%M'
    try:
        # Calcula os turnos brutos
        m_min = (datetime.strptime(m_as, fmt) - datetime.strptime(m_das, fmt)).total_seconds() / 60
        t_min = (datetime.strptime(t_as, fmt) - datetime.strptime(t_das, fmt)).total_seconds() / 60
        
        # Calcula os intervalos programados (Lanches)
        lm_min = (datetime.strptime(lm_as, fmt) - datetime.strptime(lm_das, fmt)).total_seconds() / 60 if lm_as and lm_das else 0
        lt_min = (datetime.strptime(lt_as, fmt) - datetime.strptime(lt_das, fmt)).total_seconds() / 60 if lt_as and lt_das else 0
        
        # A Jornada que alimenta o sistema todo passa a ser EXCLUSIVAMENTE o Tempo Útil!
        jornada = max(0, m_min - max(0, lm_min)) + max(0, t_min - max(0, lt_min))
    except:
        jornada = 520
        
    return meta, jornada, m_das, m_as, t_das, t_as

def calcular_diferenca(inicio, fim):
    try:
        if not inicio or not fim: return 0, "00:00h"
        fmt = '%H:%M'
        minutos = (datetime.strptime(fim, fmt) - datetime.strptime(inicio, fmt)).total_seconds() / 60
        if minutos < 0: minutos += 24 * 60 
        h = int(minutos // 60)
        m = int(minutos % 60)
        return minutos, f"{h:02d}:{m:02d}h"
    except:
        return 0, "00:00h"

def renderizar():
    cfg = banco.obter_configuracoes()
    titulo_atual = cfg.get('titulo_programa', 'PCP Avelan')
    aba_padrao_salva = cfg.get('aba_padrao', '💡 Plano de Ação')
    lembrar_aba_salva = cfg.get('lembrar_aba', True)
    
    m_das = cfg.get('manha_das', '07:00')
    m_as = cfg.get('manha_as', '12:00')
    t_das = cfg.get('tarde_das', '13:00')
    t_as = cfg.get('tarde_as', '16:20')
    
    lm_das = cfg.get('lanche_m_das', '')
    lm_as = cfg.get('lanche_m_as', '')
    lt_das = cfg.get('lanche_t_das', '')
    lt_as = cfg.get('lanche_t_as', '')

    st.markdown("### ⚙️ Preferências do Sistema")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### 🖼️ Identidade Visual")
        novo_titulo = st.text_input("Nome do Sistema", value=titulo_atual)
        
        logo_atual = cfg.get('logo_base64', None)
        if logo_atual:
            st.markdown(f'<img src="data:image/png;base64,{logo_atual}" style="max-height: 60px; margin-bottom: 10px; border-radius: 5px;">', unsafe_allow_html=True)
        up_logo = st.file_uploader("Enviar Nova Logomarca (PNG ou JPG)", type=['png', 'jpg', 'jpeg'])
        
        st.markdown("##### 🖥️ Inicialização e Ordem das Abas")
        opcoes_abas = ["📱 Chão de Fábrica", "🔴 Ao Vivo", "💡 Plano de Ação", "📈 Disponibilidade", "📋 Apontamentos", "🔎 Ocorrências", "⚙️ Configurações"]
        idx = opcoes_abas.index(aba_padrao_salva) if aba_padrao_salva in opcoes_abas else 1
        
        nova_aba = st.selectbox("Qual tela deve abrir por padrão ao iniciar o sistema?", opcoes_abas, index=idx)
        
        novo_lembrar = st.checkbox("Lembrar última aba utilizada", value=lembrar_aba_salva)
        st.markdown("<p style='font-size: 13px; color: #666; margin-top: -10px;'>Se ativado, o sistema abre onde você parou. Se desativado, usa sempre a aba padrão acima.</p>", unsafe_allow_html=True)
        
        st.markdown("<p style='font-size: 13px; color: #666; margin-top: 15px;'>Defina a ordem visual em que as abas vão aparecer da esquerda para a direita:</p>", unsafe_allow_html=True)
        todas_abas_padrao = ["📱 Chão de Fábrica", "🔴 Ao Vivo", "💡 Plano de Ação", "📈 Disponibilidade", "📋 Apontamentos", "🔎 Ocorrências", "⚙️ Configurações"]
        ordem_str = cfg.get('ordem_abas', None)
        
        if ordem_str:
            ordem_atual = [a.strip() for a in ordem_str.split(',') if a.strip() in todas_abas_padrao]
            for a in todas_abas_padrao:
                if a not in ordem_atual: ordem_atual.append(a)
        else:
            ordem_atual = todas_abas_padrao.copy()
                
        nova_ordem = st.multiselect("Organizador Visual (Arraste ou clique no X):", options=todas_abas_padrao, default=ordem_atual)
        if len(nova_ordem) < len(todas_abas_padrao):
            st.warning("⚠️ Adicione todas as abas para não esconder nenhuma tela acidentalmente.")

    with c2:
        st.markdown("##### 🕒 Jornada de Trabalho (Turnos)")
        
        # --- TURNO DA MANHÃ ---
        t1, t2 = st.columns(2)
        with t1: n_mdas = st.text_input("Manhã - Início", value=m_das)
        with t2: n_mas = st.text_input("Manhã - Fim", value=m_as)
        
        lm1, lm2 = st.columns(2)
        with lm1: n_lmdas = st.text_input("Lanche da Manhã - Início (Opcional)", value=lm_das, placeholder="Ex: 09:30")
        with lm2: n_lmas = st.text_input("Lanche da Manhã - Fim (Opcional)", value=lm_as, placeholder="Ex: 09:40")
        
        min_m_bruto, _ = calcular_diferenca(n_mdas, n_mas)
        min_lm, _ = calcular_diferenca(n_lmdas, n_lmas)
        min_m_util = max(0, min_m_bruto - min_lm)
        str_m_util = f"{int(min_m_util // 60):02d}:{int(min_m_util % 60):02d}h"
        
        st.markdown(f"<div style='text-align: right; color: #27ae60; font-size: 14px; margin-top: -10px; margin-bottom: 15px;'><i>Total Manhã (Útil): <b>{str_m_util}</b></i></div>", unsafe_allow_html=True)

        # --- TURNO DA TARDE ---
        t3, t4 = st.columns(2)
        with t3: n_tdas = st.text_input("Tarde - Início", value=t_das)
        with t4: n_tas = st.text_input("Tarde - Fim", value=t_as)
        
        lt1, lt2 = st.columns(2)
        with lt1: n_ltdas = st.text_input("Lanche da Tarde - Início (Opcional)", value=lt_das, placeholder="Ex: 15:30")
        with lt2: n_ltas = st.text_input("Lanche da Tarde - Fim (Opcional)", value=lt_as, placeholder="Ex: 15:40")

        min_t_bruto, _ = calcular_diferenca(n_tdas, n_tas)
        min_lt, _ = calcular_diferenca(n_ltdas, n_ltas)
        min_t_util = max(0, min_t_bruto - min_lt)
        str_t_util = f"{int(min_t_util // 60):02d}:{int(min_t_util % 60):02d}h"
        
        st.markdown(f"<div style='text-align: right; color: #27ae60; font-size: 14px; margin-top: -10px; margin-bottom: 15px;'><i>Total Tarde (Útil): <b>{str_t_util}</b></i></div>", unsafe_allow_html=True)

        # --- JORNADA GERAL ---
        total_min_util = min_m_util + min_t_util
        str_tot_util = f"{int(total_min_util // 60):02d}:{int(total_min_util % 60):02d}h"
        
        st.markdown(f"""
        <div style="background-color: #e8f8f5; padding: 15px; border-radius: 8px; border: 1px solid #27ae60; text-align: center; margin-top: 10px;">
            <span style="color: #27ae60; font-size: 13px; text-transform: uppercase; font-weight: bold; letter-spacing: 1px;">Jornada Total Diária (Útil)</span><br>
            <span style="color: #2c3e50; font-size: 28px; font-weight: 900;">{str_tot_util}</span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### 🔎 Status Padrão de Análise")
        tipos = ["Parado", "Trabalhando", "Todos"]
        if 'tipo_global' not in st.session_state: st.session_state.tipo_global = "Parado"
        try: idx_t = tipos.index(st.session_state.tipo_global)
        except: idx_t = 0
        st.selectbox("Status da Operação", tipos, index=idx_t, key='tipo_global')

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 Salvar Ajustes Gerais", type="primary"):
        try:
            ordem_final = nova_ordem.copy()
            for a in todas_abas_padrao:
                if a not in ordem_final: ordem_final.append(a)

            supa = banco.conectar()
            dados = {
                "titulo_programa": novo_titulo,
                "aba_padrao": nova_aba,
                "lembrar_aba": novo_lembrar,
                "manha_das": n_mdas,
                "manha_as": n_mas,
                "tarde_das": n_tdas,
                "tarde_as": n_tas,
                "lanche_m_das": n_lmdas,
                "lanche_m_as": n_lmas,
                "lanche_t_das": n_ltdas,
                "lanche_t_as": n_ltas,
                "ordem_abas": ",".join(ordem_final) 
            }
            if up_logo is not None:
                dados["logo_base64"] = base64.b64encode(up_logo.getvalue()).decode()
                
            supa.table("configuracoes").update(dados).eq("id", 1).execute()
            st.success("✅ Ajustes gerais salvos! Recarregue a página (F5) para aplicar em todo o sistema.")
        except Exception as e:
            st.error(f"Erro ao salvar no banco de dados: {e}")

def renderizar_config_abas():
    cfg = banco.obter_configuracoes()
    m_cronico = cfg.get('mostrar_cronico', True)
    m_especifico = cfg.get('mostrar_especifico', True)
    meta_atual = float(cfg.get('meta_disponibilidade', 85.0))
    
    top_g = int(cfg.get('top_gerais', 3))
    top_i = int(cfg.get('top_individuais', 3))
    perc_i = float(cfg.get('perc_individual', 70.0))
    
    ao_vivo_ref = int(cfg.get('ao_vivo_refresh', 60))
    ao_vivo_crit = int(cfg.get('ao_vivo_critico', 15))
    vel_atual = int(cfg.get('ao_vivo_vel_barra', 8))

    st.markdown("### 📑 Configurações Específicas por Aba")
    st.markdown("<br>", unsafe_allow_html=True)
    
    with st.expander("🔴 Aba: Ao Vivo", expanded=True):
        st.markdown("Controle o comportamento do painel de monitoramento da fábrica em tempo real (Sistema Andon):")
        
        cv1, cv2, cv3 = st.columns(3)
        with cv1:
            novo_ref = st.number_input("Taxa de Atualização Automática (Segundos)", value=ao_vivo_ref, step=5, min_value=5)
        with cv2:
            novo_crit = st.number_input("Limite para Alerta Crítico (Minutos)", value=ao_vivo_crit, step=1, min_value=1)
        with cv3:
            mapa_vel = {"Lenta": 4, "Normal": 8, "Rápida": 12}
            idx_vel = list(mapa_vel.values()).index(vel_atual) if vel_atual in mapa_vel.values() else 1
            escolha_vel = st.selectbox("Velocidade da Barra de Informações", list(mapa_vel.keys()), index=idx_vel)
            novo_vel = mapa_vel[escolha_vel]

    with st.expander("💡 Aba: Plano de Ação"):
        st.markdown("Defina os limites e critérios matemáticos para a geração automática do relatório de ação:")
        
        c1, c2, c3 = st.columns(3)
        with c1: novo_top_g = st.number_input("Qtd. Problemas Gerais (Top X)", value=top_g, step=1, min_value=1)
        with c2: novo_top_i = st.number_input("Qtd. Problemas Individuais (Top X)", value=top_i, step=1, min_value=1)
        with c3: novo_perc_i = st.number_input("Concentração P/ Individual (%)", value=perc_i, step=1.0, min_value=1.0, max_value=100.0)

    with st.expander("📈 Aba: Disponibilidade"):
        st.markdown("Defina a meta diária de disponibilidade (linha vermelha) para ser exibida nos gráficos:")
        nova_meta = st.number_input("Valor da Meta (%)", value=meta_atual, step=1.0)

    with st.expander("📋 Aba: Apontamentos"):
        st.markdown("Controle de exibição dos alertas de inteligência na tabela de ocorrências:")
        novo_cronico = st.checkbox("Ativar marcação CRÔNICO", value=m_cronico)
        novo_especifico = st.checkbox("Ativar marcação ESPECÍFICO", value=m_especifico)

    with st.expander("📱 Ajustes de Layout (Celular, Tablet e PC)"):
        st.markdown("Defina os limites de largura (em pixels) para que o sistema organize os gráficos automaticamente.")
        bp = ler_breakpoints()
        cel_atual = bp.get("bp_celular", 768)
        tab_atual = bp.get("bp_tablet", 1024)
        
        c1, c2 = st.columns(2)
        with c1: novo_cel = st.number_input("Largura Máxima do Celular (px)", value=cel_atual, step=10)
        with c2: novo_tab = st.number_input("Largura Máxima do Tablet (px)", value=tab_atual, step=10)
        
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 Salvar Configurações de Abas e Telas", type="primary"):
        try:
            supa = banco.conectar()
            dados = {
                "meta_disponibilidade": nova_meta, 
                "mostrar_cronico": novo_cronico,
                "mostrar_especifico": novo_especifico,
                "top_gerais": novo_top_g,
                "top_individuais": novo_top_i,
                "perc_individual": novo_perc_i,
                "ao_vivo_refresh": novo_ref,
                "ao_vivo_critico": novo_crit,
                "ao_vivo_vel_barra": novo_vel
            }
            supa.table("configuracoes").update(dados).eq("id", 1).execute()
            salvar_breakpoints(novo_cel, novo_tab)
            st.success("✅ Configurações salvas com sucesso! Recarregue a página (F5) para aplicar.")
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")