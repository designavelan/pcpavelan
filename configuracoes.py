import streamlit as st
import pandas as pd
from datetime import datetime, date, time
import banco

def obter_parametros():
    """Lê do banco de dados e retorna a meta e os minutos da jornada."""
    supabase = banco.conectar()
    try:
        resp = supabase.table("configuracoes").select("*").eq("id", 1).execute()
        cfg = resp.data[0] if resp.data else {}
    except:
        cfg = {}
    
    meta = float(cfg.get('meta_disponibilidade', 85.0))
    try: m_das = datetime.strptime(cfg.get('manha_das', '07:00'), "%H:%M").time()
    except: m_das = time(7, 0)
    try: m_as = datetime.strptime(cfg.get('manha_as', '12:00'), "%H:%M").time()
    except: m_as = time(12, 0)
    try: t_das = datetime.strptime(cfg.get('tarde_das', '13:00'), "%H:%M").time()
    except: t_das = time(13, 0)
    try: t_as = datetime.strptime(cfg.get('tarde_as', '16:20'), "%H:%M").time()
    except: t_as = time(16, 20)
    
    t_m_in = datetime.combine(date.today(), m_das)
    t_m_out = datetime.combine(date.today(), m_as)
    t_t_in = datetime.combine(date.today(), t_das)
    t_t_out = datetime.combine(date.today(), t_as)
    
    if t_m_out < t_m_in: t_m_out += pd.Timedelta(days=1)
    if t_t_out < t_t_in: t_t_out += pd.Timedelta(days=1)
    
    jornada = ((t_m_out - t_m_in).total_seconds() + (t_t_out - t_t_in).total_seconds()) / 60.0
    
    return meta, jornada, m_das, m_as, t_das, t_as

def renderizar():
    """Desenha a aba de Configurações na tela."""
    st.subheader("⚙️ Configurações Gerais do Sistema")
    st.markdown("---")
    
    meta, jornada, m_das, m_as, t_das, t_as = obter_parametros()
    
    col_cfg1, col_cfg2 = st.columns([1, 1.5])
    
    with col_cfg1:
        st.markdown("#### 🎯 Parâmetros de Metas")
        st.info("⚠️ **Atenção:** Esta meta é referente EXCLUSIVAMENTE à **Disponibilidade**.")
        meta_disp = st.number_input("Meta de Disponibilidade (%)", value=meta, step=1.0)
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 Salvar Configurações", type="primary"):
            with st.spinner("Salvando na nuvem..."):
                supabase = banco.conectar()
                dados_cfg = {
                    "id": 1,
                    "meta_disponibilidade": meta_disp,
                    "manha_das": st.session_state.m_das.strftime("%H:%M"),
                    "manha_as": st.session_state.m_as.strftime("%H:%M"),
                    "tarde_das": st.session_state.t_das.strftime("%H:%M"),
                    "tarde_as": st.session_state.t_as.strftime("%H:%M")
                }
                supabase.table("configuracoes").upsert(dados_cfg).execute()
                st.success("Configurações atualizadas com sucesso!")
                st.rerun()

    with col_cfg2:
        st.markdown("#### ⏱️ Jornada de Trabalho (Teto Máximo)")
        cfg_t1, cfg_t2, cfg_t3 = st.columns(3)
        with cfg_t1:
            st.markdown("**Manhã**")
            st.time_input("Das:", value=m_das, key="m_das")
            st.time_input("Às:", value=m_as, key="m_as")
        with cfg_t2:
            st.markdown("**Tarde**")
            st.time_input("Das:", value=t_das, key="t_das")
            st.time_input("Às:", value=t_as, key="t_as")
            
        with cfg_t3:
            st.markdown("**Resumo do Turno**")
            # Recalcula dinamicamente baseado no que está digitado na tela agora
            in_m = st.session_state.get('m_das', m_das)
            out_m = st.session_state.get('m_as', m_as)
            in_t = st.session_state.get('t_das', t_das)
            out_t = st.session_state.get('t_as', t_as)
            
            dt_in_m = datetime.combine(date.today(), in_m)
            dt_out_m = datetime.combine(date.today(), out_m)
            dt_in_t = datetime.combine(date.today(), in_t)
            dt_out_t = datetime.combine(date.today(), out_t)
            
            if dt_out_m < dt_in_m: dt_out_m += pd.Timedelta(days=1)
            if dt_out_t < dt_in_t: dt_out_t += pd.Timedelta(days=1)
            
            min_m = (dt_out_m - dt_in_m).total_seconds() / 60.0
            min_t = (dt_out_t - dt_in_t).total_seconds() / 60.0
            
            st.info(f"**Manhã:** {banco.minutos_para_string(min_m)}\n\n**Tarde:** {banco.minutos_para_string(min_t)}\n\n**Total:** {banco.minutos_para_string(min_m + min_t)}")