import streamlit as st
import pandas as pd
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

def ler_caminho_matriz():
    if os.path.exists("matriz_config.json"):
        try:
            with open("matriz_config.json", "r") as f:
                return json.load(f).get("caminho", "")
        except: pass
    return ""

def salvar_caminho_matriz(caminho):
    with open("matriz_config.json", "w") as f:
        json.dump({"caminho": caminho}, f)

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
        m_min = (datetime.strptime(m_as, fmt) - datetime.strptime(m_das, fmt)).total_seconds() / 60
        t_min = (datetime.strptime(t_as, fmt) - datetime.strptime(t_das, fmt)).total_seconds() / 60
        lm_min = (datetime.strptime(lm_as, fmt) - datetime.strptime(lm_das, fmt)).total_seconds() / 60 if lm_as and lm_das else 0
        lt_min = (datetime.strptime(lt_as, fmt) - datetime.strptime(lt_das, fmt)).total_seconds() / 60 if lt_as and lt_das else 0
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
        opcoes_abas = ["📱 Chão de Fábrica", "🔴 Ao Vivo", "🏆 Desempenho", "💡 Plano de Ação", "📈 Disponibilidade", "📋 Apontamentos", "🔎 Ocorrências", "📦 Produtos", "⚙️ Configurações", "👥 Controle de Acessos"]
        idx = opcoes_abas.index(aba_padrao_salva) if aba_padrao_salva in opcoes_abas else 1
        
        nova_aba = st.selectbox("Qual tela deve abrir por padrão ao iniciar o sistema?", opcoes_abas, index=idx)
        
        novo_lembrar = st.checkbox("Lembrar última aba utilizada", value=lembrar_aba_salva)
        st.markdown("<p style='font-size: 13px; color: #666; margin-top: -10px;'>Se ativado, o sistema abre onde você parou. Se desativado, usa sempre a aba padrão acima.</p>", unsafe_allow_html=True)
        
        st.markdown("<p style='font-size: 13px; color: #666; margin-top: 15px;'>Defina a ordem visual em que as abas vão aparecer da esquerda para a direita:</p>", unsafe_allow_html=True)
        todas_abas_padrao = ["📱 Chão de Fábrica", "🔴 Ao Vivo", "🏆 Desempenho", "💡 Plano de Ação", "📈 Disponibilidade", "📋 Apontamentos", "🔎 Ocorrências", "📦 Produtos", "⚙️ Configurações", "👥 Controle de Acessos"]
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

        total_min_util = min_m_util + min_t_util
        str_tot_util = f"{int(total_min_util // 60):02d}:{int(total_min_util % 60):02d}h"
        
        st.markdown(f"""
        <div style="background-color: #e8f8f5; padding: 15px; border-radius: 8px; border: 1px solid #27ae60; text-align: center; margin-top: 10px;">
            <span style="color: #27ae60; font-size: 13px; text-transform: uppercase; font-weight: bold; letter-spacing: 1px;">Jornada Total Diária (Útil)</span><br>
            <span style="color: #2c3e50; font-size: 28px; font-weight: 900;">{str_tot_util}</span>
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
    
    with st.expander("📦 Aba: Produtos (Integração com Excel)", expanded=True):
        st.markdown("Defina o caminho local da sua planilha **Matriz** para permitir a sincronização automática nos computadores da fábrica.")
        caminho_atual = ler_caminho_matriz()
        
        c1, c2 = st.columns([8,2])
        with c1: novo_caminho = st.text_input("Caminho do arquivo", value=caminho_atual, placeholder="Ex: D:\\Google Drive\\Matriz.xlsx")
        with c2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("💾 Salvar Caminho", use_container_width=True):
                salvar_caminho_matriz(novo_caminho)
                st.success("✅ Caminho vinculado!")
    
    with st.expander("🔴 Aba: Ao Vivo"):
        st.markdown("Controle o comportamento do painel de monitoramento da fábrica em tempo real (Sistema Andon):")
        
        cv1, cv2, cv3 = st.columns(3)
        with cv1: novo_ref = st.number_input("Taxa de Atualização Automática (Segundos)", value=ao_vivo_ref, step=5, min_value=5)
        with cv2: novo_crit = st.number_input("Limite para Alerta Crítico (Minutos)", value=ao_vivo_crit, step=1, min_value=1)
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
                "meta_disponibilidade": nova_meta, "mostrar_cronico": novo_cronico, "mostrar_especifico": novo_especifico,
                "top_gerais": novo_top_g, "top_individuais": novo_top_i, "perc_individual": novo_perc_i,
                "ao_vivo_refresh": novo_ref, "ao_vivo_critico": novo_crit, "ao_vivo_vel_barra": novo_vel
            }
            supa.table("configuracoes").update(dados).eq("id", 1).execute()
            salvar_breakpoints(novo_cel, novo_tab)
            st.success("✅ Configurações salvas com sucesso! Recarregue a página (F5) para aplicar.")
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")

def renderizar_estrutura():
    st.markdown("### 🏭 Estrutura da Fábrica")
    st.markdown("Cadastre novos setores e máquinas, ou edite os nomes atuais. As alterações feitas aqui serão atualizadas **automaticamente em todo o histórico e nos usuários vinculados**.")
    st.markdown("<hr style='opacity: 0.2;'>", unsafe_allow_html=True)
    
    df_est = banco.obter_estrutura()
    supa = banco.conectar()
    
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("#### ➕ Cadastrar Novo")
        n_setor = st.text_input("Nome do Setor", placeholder="Ex: Montagem")
        n_maq = st.text_input("Nome da Máquina", placeholder="Ex: Esteira 1")
        n_dupla = st.checkbox("Esta máquina permite produção dupla (simultânea)", value=False)
        
        if st.button("💾 Cadastrar Estrutura", type="primary"):
            if n_setor and n_maq:
                try:
                    banco.adicionar_estrutura(n_setor.strip(), n_maq.strip())
                    supa.table("estrutura_fabrica").update({"permite_producao_dupla": n_dupla}).eq("setor", n_setor.strip()).eq("maquina", n_maq.strip()).execute()
                    st.success("✅ Máquina cadastrada com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error("Erro: Esta máquina já está cadastrada neste setor.")
            else:
                st.warning("Preencha o Setor e a Máquina.")
                
    with c2:
        st.markdown("#### ✏️ Editar Existente (Cascata)")
        if not df_est.empty:
            df_est['nome_exibicao'] = df_est['setor'] + " ➔ " + df_est['maquina']
            opcoes = df_est['nome_exibicao'].tolist()
            
            selecionada = st.selectbox("Selecione para alterar:", opcoes)
            
            linha = df_est[df_est['nome_exibicao'] == selecionada].iloc[0]
            setor_ant = linha['setor']
            maq_ant = linha['maquina']
            id_est = int(linha['id'])
            
            val_raw = linha.get('permite_producao_dupla', False)
            val_dupla_ant = True if str(val_raw).strip().lower() == 'true' or val_raw is True else False
            
            e_setor = st.text_input("Renomear Setor", value=setor_ant)
            e_maq = st.text_input("Renomear Máquina", value=maq_ant)
            e_dupla = st.checkbox("Esta máquina permite produção dupla (simultânea)", value=val_dupla_ant, key=f"chk_{id_est}")
            
            if st.button("🔄 Salvar e Aplicar Cascata", type="primary"):
                if e_setor and e_maq:
                    mudou_nome = (e_setor.strip() != setor_ant or e_maq.strip() != maq_ant)
                    mudou_dupla = (e_dupla != val_dupla_ant)
                    
                    if mudou_nome or mudou_dupla:
                        with st.spinner("Atualizando todo o sistema (Isso pode levar alguns segundos)..."):
                            try:
                                if mudou_nome:
                                    banco.atualizar_estrutura_cascata(id_est, setor_ant, maq_ant, e_setor.strip(), e_maq.strip())
                                
                                supa.table("estrutura_fabrica").update({"permite_producao_dupla": e_dupla}).eq("id", id_est).execute()
                                
                                st.success("✅ Estrutura atualizada com sucesso!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro na atualização: {e}")
                    else:
                        st.info("Nenhuma alteração foi feita.")
                else:
                    st.warning("Os campos não podem ficar vazios.")
        else:
            st.info("Nenhuma estrutura cadastrada ainda.")

def renderizar_produtos_linha():
    st.markdown("### 🟢 Produtos em Linha (Chão de Fábrica)")
    st.markdown("Defina de forma rápida quais produtos devem aparecer como opção principal no tablet do operador. Você pode adicionar ou remover itens a qualquer momento.")
    st.markdown("<hr style='opacity: 0.2;'>", unsafe_allow_html=True)
    
    supa = banco.conectar()
    
    df_produtos = banco.obter_produtos_matriz()
    lista_todos = []
    if not df_produtos.empty:
        lista_todos = sorted(df_produtos['produto_formula'].dropna().unique().tolist())
        
    resp = supa.table("produtos_ativos").select("*").execute()
    ativos = [row['produto_formula'] for row in resp.data] if resp.data else []
    
    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.markdown("#### 🔍 Pesquisar e Adicionar")
        st.markdown("<p style='font-size: 14px; color: #7f8c8d;'>Digite o nome do produto na caixa abaixo para filtrar. Selecione e clique em adicionar.</p>", unsafe_allow_html=True)
        
        opcoes_disponiveis = [p for p in lista_todos if p not in ativos]
        
        # Esse selectbox do Streamlit automaticamente permite digitar e pesquisar!
        prod_selecionado = st.selectbox("Buscar Produto:", [""] + opcoes_disponiveis, key="sel_add_prod")
        
        if st.button("➕ Adicionar à Lista", type="primary"):
            if prod_selecionado:
                try:
                    supa.table("produtos_ativos").insert({"produto_formula": prod_selecionado}).execute()
                    st.success(f"✅ '{prod_selecionado}' adicionado com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao adicionar: {e}")
            else:
                st.warning("Selecione um produto primeiro.")
                
    with c2:
        st.markdown(f"#### 📋 Lista de Produtos em Linha ({len(ativos)})")
        
        if not ativos:
            st.info("Nenhum produto configurado como 'Em Linha' no momento.")
        else:
            st.markdown("<div style='max-height: 400px; overflow-y: auto; padding-right: 10px;'>", unsafe_allow_html=True)
            for prod in sorted(ativos):
                col1, col2 = st.columns([8, 2])
                with col1:
                    st.markdown(f"<div style='background-color: #f8f9fa; padding: 10px; border-radius: 5px; border-left: 4px solid #27ae60; margin-bottom: 8px; font-weight: bold; color: #2c3e50;'>{prod}</div>", unsafe_allow_html=True)
                with col2:
                    if st.button("🗑️", key=f"del_{prod}", help="Remover da lista"):
                        supa.table("produtos_ativos").delete().eq("produto_formula", prod).execute()
                        st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)