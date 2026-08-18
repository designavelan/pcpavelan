import streamlit as st
import banco
from datetime import datetime
import base64

def obter_parametros():
    cfg = banco.obter_configuracoes()
    meta = float(cfg.get('meta_disponibilidade', 85.0))
    m_das = cfg.get('manha_das', '07:00')
    m_as = cfg.get('manha_as', '12:00')
    t_das = cfg.get('tarde_das', '13:00')
    t_as = cfg.get('tarde_as', '16:20')

    fmt = '%H:%M'
    try:
        m_min = (datetime.strptime(m_as, fmt) - datetime.strptime(m_das, fmt)).total_seconds() / 60
        t_min = (datetime.strptime(t_as, fmt) - datetime.strptime(t_das, fmt)).total_seconds() / 60
        jornada = m_min + t_min
    except:
        jornada = 520
    return meta, jornada, m_das, m_as, t_das, t_as

def calcular_diferenca(inicio, fim):
    try:
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
    
    aba_atual = cfg.get('aba_padrao', '🔍 Filtros')
    
    m_das = cfg.get('manha_das', '07:00')
    m_as = cfg.get('manha_as', '12:00')
    t_das = cfg.get('tarde_das', '13:00')
    t_as = cfg.get('tarde_as', '16:20')

    st.markdown("### ⚙️ Preferências do Sistema")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### 🖼️ Identidade Visual")
        novo_titulo = st.text_input("Nome do Sistema", value=titulo_atual)
        
        logo_atual = cfg.get('logo_base64', None)
        if logo_atual:
            st.markdown(f'<img src="data:image/png;base64,{logo_atual}" style="max-height: 60px; margin-bottom: 10px; border-radius: 5px;">', unsafe_allow_html=True)
        up_logo = st.file_uploader("Enviar Nova Logomarca (PNG ou JPG)", type=['png', 'jpg', 'jpeg'])
        
        # =======================================================
        # INICIALIZAÇÃO E ORDEM (AJUSTADO)
        # =======================================================
        st.markdown("##### 🖥️ Inicialização e Ordem das Abas")
        
        opcoes_abas = ["🔍 Filtros", "📈 Disponibilidade", "📋 Apontamentos", "⚙️ Configurações"]
        idx = opcoes_abas.index(aba_atual) if aba_atual in opcoes_abas else 0
        
        # Agora são configurações complementares, mas independentes
        nova_aba = st.selectbox("Qual tela deve abrir por padrão ao iniciar o sistema?", opcoes_abas, index=idx)
        
        st.markdown("<p style='font-size: 13px; color: #666; margin-top: 5px;'>Defina a ordem visual em que as abas vão aparecer da esquerda para a direita:</p>", unsafe_allow_html=True)
        
        todas_abas_padrao = ["🔍 Filtros", "📈 Disponibilidade", "📋 Apontamentos", "⚙️ Configurações"]
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
        # =======================================================

    with c2:
        st.markdown("##### 🕒 Jornada de Trabalho (Turnos)")
        t1, t2 = st.columns(2)
        with t1: n_mdas = st.text_input("Manhã - Início", value=m_das)
        with t2: n_mas = st.text_input("Manhã - Fim", value=m_as)
        
        min_m, str_m = calcular_diferenca(n_mdas, n_mas)
        st.markdown(f"<div style='text-align: right; color: #666; font-size: 14px; margin-top: -10px; margin-bottom: 15px;'><i>Total Manhã: <b>{str_m}</b></i></div>", unsafe_allow_html=True)

        t3, t4 = st.columns(2)
        with t3: n_tdas = st.text_input("Tarde - Início", value=t_das)
        with t4: n_tas = st.text_input("Tarde - Fim", value=t_as)

        min_t, str_t = calcular_diferenca(n_tdas, n_tas)
        st.markdown(f"<div style='text-align: right; color: #666; font-size: 14px; margin-top: -10px; margin-bottom: 15px;'><i>Total Tarde: <b>{str_t}</b></i></div>", unsafe_allow_html=True)

        total_min = min_m + min_t
        tot_h = int(total_min // 60)
        tot_m = int(total_min % 60)
        str_tot = f"{tot_h:02d}:{tot_m:02d}h"
        
        st.markdown(f"""
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; border: 1px solid #e0e0e0; text-align: center; margin-top: 10px;">
            <span style="color: #777; font-size: 13px; text-transform: uppercase; letter-spacing: 1px;">Jornada Total Diária</span><br>
            <span style="color: #2c3e50; font-size: 24px; font-weight: bold;">{str_tot}</span>
        </div>
        """, unsafe_allow_html=True)

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
                "manha_das": n_mdas,
                "manha_as": n_mas,
                "tarde_das": n_tdas,
                "tarde_as": n_tas,
                "ordem_abas": ",".join(ordem_final) 
            }
            if up_logo is not None:
                dados["logo_base64"] = base64.b64encode(up_logo.getvalue()).decode()
                
            supa.table("configuracoes").update(dados).eq("id", 1).execute()
            st.success("✅ Ajustes gerais salvos! Recarregue a página (F5) para aplicar.")
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")

def renderizar_config_abas():
    cfg = banco.obter_configuracoes()
    m_cronico = cfg.get('mostrar_cronico', True)
    m_especifico = cfg.get('mostrar_especifico', True)
    meta_atual = float(cfg.get('meta_disponibilidade', 85.0))

    st.markdown("### 📑 Configurações Específicas por Aba")
    st.markdown("Utilize esta seção para ajustar parâmetros e recursos visuais exclusivos de cada tela do sistema.")
    st.markdown("<br>", unsafe_allow_html=True)

    with st.expander("📈 Aba: Disponibilidade", expanded=True):
        st.markdown("Defina a meta diária de disponibilidade (linha vermelha) para ser exibida nos gráficos:")
        nova_meta = st.number_input("Valor da Meta (%)", value=meta_atual, step=1.0)

    with st.expander("📋 Aba: Apontamentos", expanded=True):
        st.markdown("Controle de exibição dos alertas de inteligência na tabela de ocorrências:")
        novo_cronico = st.checkbox("Ativar marcação CRÔNICO", value=m_cronico)
        novo_especifico = st.checkbox("Ativar marcação ESPECÍFICO", value=m_especifico)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 Salvar Configurações de Abas", type="primary"):
        try:
            supa = banco.conectar()
            dados = {
                "meta_disponibilidade": nova_meta, 
                "mostrar_cronico": novo_cronico,
                "mostrar_especifico": novo_especifico
            }
            supa.table("configuracoes").update(dados).eq("id", 1).execute()
            st.success("✅ Configurações salvas com sucesso! Recarregue a página (F5) para aplicar.")
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")