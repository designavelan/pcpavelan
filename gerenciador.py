import streamlit as st
import pandas as pd
import banco
import time

def renderizar(df_nuvem):
    st.markdown("### 🛠️ Gerenciador de Dados (Editor)")
    st.markdown("Use esta ferramenta como uma 'borracha' para limpar testes ou corrigir apontamentos com horários errados. **Atenção: As exclusões e alterações feitas aqui afetam permanentemente o banco de dados oficial.**")
    
    if df_nuvem.empty:
        st.info("O banco de dados está vazio no momento.")
        return

    supa = banco.conectar()
    
    # ==========================================
    # 1. FILTRO HIERÁRQUICO (DATA -> SETOR -> MÁQUINA)
    # ==========================================
    c1, c2, c3 = st.columns(3)
    
    with c1:
        datas_disponiveis = sorted(df_nuvem['data_registro'].dropna().unique().tolist(), reverse=True)
        if not datas_disponiveis:
            st.warning("Nenhuma data com registros encontrada.")
            return
        data_selecionada = st.selectbox("📅 Selecione a Data", datas_disponiveis)
        
    # Filtra os dados da nuvem para a data escolhida para popular os próximos menus
    df_dia = df_nuvem[df_nuvem['data_registro'] == data_selecionada]
        
    with c2:
        setores_disponiveis = ["[ Todos ]"] + sorted(df_dia['setor'].dropna().unique().tolist())
        setor_selecionado = st.selectbox("🏢 Selecione o Setor", setores_disponiveis)
        
    with c3:
        if setor_selecionado == "[ Todos ]":
            maquinas_disponiveis = ["[ Todas ]"] + sorted(df_dia['maquina'].dropna().unique().tolist())
        else:
            maquinas_disponiveis = ["[ Todas ]"] + sorted(df_dia[df_dia['setor'] == setor_selecionado]['maquina'].dropna().unique().tolist())
        
        maquina_selecionada = st.selectbox("⚙️ Selecione a Máquina", maquinas_disponiveis)

    st.markdown("<hr style='opacity: 0.2;'>", unsafe_allow_html=True)
    
    # ==========================================
    # 2. BUSCA NO BANCO DE DADOS (SUPABASE)
    # ==========================================
    # Constrói a busca dinamicamente respeitando a hierarquia
    query = supa.table("producao_diaria").select("*").eq("data_registro", data_selecionada)
    
    if setor_selecionado != "[ Todos ]":
        query = query.eq("setor", setor_selecionado)
        
    if maquina_selecionada != "[ Todas ]":
        query = query.eq("maquina", maquina_selecionada)
        
    resp = query.execute()
    
    if not resp.data:
        st.info("Nenhum registro encontrado com estes filtros.")
        return
        
    df_edit = pd.DataFrame(resp.data)
    # Organiza do mais recente pro mais antigo e agrupa pelas máquinas
    df_edit = df_edit.sort_values(by=["as_hora", "maquina"], ascending=[False, True]).reset_index(drop=True)
    
    mapa_ids = df_edit['id'].to_dict()
    
    # Adicionamos Setor e Máquina na visualização, afinal, o usuário pode estar vendo "[ Todas ]"
    colunas_exibicao = ['setor', 'maquina', 'cod_ocorrencia', 'das', 'as_hora', 'origem']
    
    # Proteção caso a coluna não exista em dados muito antigos
    for col in colunas_exibicao:
        if col not in df_edit.columns:
            df_edit[col] = ""
            
    df_display = df_edit[colunas_exibicao].copy()
    
    titulo_maq = maquina_selecionada if maquina_selecionada != "[ Todas ]" else "Todas as Máquinas"
    titulo_setor = setor_selecionado if setor_selecionado != "[ Todos ]" else "Todos os Setores"
    
    st.markdown(f"#### Editando: **{titulo_maq}** ({titulo_setor}) | {pd.to_datetime(data_selecionada).strftime('%d/%m/%Y')}")
    st.markdown("<span style='color: #7f8c8d; font-size: 14px;'>Para excluir uma linha, <b>selecione a caixinha à esquerda dela</b> e aperte a tecla <b>Delete</b> no seu teclado (ou clique no ícone de lixeira no canto superior direito da tabela). Para editar um horário, basta dar dois cliques rápidos na célula.</span>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    chave_editor = f"editor_{data_selecionada}_{setor_selecionado}_{maquina_selecionada}"
    
    # Pega a lista completa da nuvem para os dropdowns de edição na tabela
    lista_todos_setores = sorted(df_nuvem['setor'].dropna().unique().tolist())
    lista_todas_maq = sorted(df_nuvem['maquina'].dropna().unique().tolist())
    
    # ==========================================
    # 3. PLANILHA DE EDIÇÃO (DATA EDITOR)
    # ==========================================
    mudancas = st.data_editor(
        df_display,
        key=chave_editor,
        num_rows="dynamic", 
        use_container_width=True,
        column_config={
            "setor": st.column_config.SelectboxColumn("Setor", options=lista_todos_setores, required=True),
            "maquina": st.column_config.SelectboxColumn("Máquina", options=lista_todas_maq, required=True),
            "cod_ocorrencia": st.column_config.TextColumn("Código do Problema", required=True),
            "das": st.column_config.TextColumn("Hora Início (HH:MM)", required=True),
            "as_hora": st.column_config.TextColumn("Hora Fim (HH:MM)", required=True),
            "origem": st.column_config.TextColumn("Origem do Apontamento", disabled=True)
        }
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("💾 Salvar Alterações no Banco de Dados", type="primary"):
        state_changes = st.session_state.get(chave_editor, {})
        
        linhas_deletadas = state_changes.get("deleted_rows", [])
        linhas_editadas = state_changes.get("edited_rows", {})
        linhas_adicionadas = state_changes.get("added_rows", [])
        
        if not linhas_deletadas and not linhas_editadas and not linhas_adicionadas:
            st.warning("⚠️ Você não fez nenhuma alteração na tabela. Nada foi salvo.")
            return
            
        try:
            with st.spinner("Sincronizando alterações com a nuvem..."):
                
                # PROCESSA EXCLUSÕES
                for idx in linhas_deletadas:
                    id_banco = mapa_ids[idx]
                    supa.table("producao_diaria").delete().eq("id", id_banco).execute()
                    
                # PROCESSA EDIÇÕES
                for idx, alteracoes in linhas_editadas.items():
                    id_banco = mapa_ids[idx]
                    supa.table("producao_diaria").update(alteracoes).eq("id", id_banco).execute()
                    
                # PROCESSA ADIÇÕES 
                for nova_linha in linhas_adicionadas:
                    # Se o usuário não selecionar no dropdown, o sistema tenta inferir do filtro atual
                    s_val = nova_linha.get("setor", setor_selecionado if setor_selecionado != "[ Todos ]" else "")
                    m_val = nova_linha.get("maquina", maquina_selecionada if maquina_selecionada != "[ Todas ]" else "")
                    
                    dados_insert = {
                        "data_registro": data_selecionada,
                        "setor": s_val,
                        "maquina": m_val,
                        "origem": "Edição Manual",
                        "cod_ocorrencia": nova_linha.get("cod_ocorrencia", ""),
                        "das": nova_linha.get("das", ""),
                        "as_hora": nova_linha.get("as_hora", "")
                    }
                    supa.table("producao_diaria").insert(dados_insert).execute()
                    
            st.success("✅ Banco de dados atualizado com sucesso!")
            
            # Limpa o cache para recarregar a tabela fresquinha
            if chave_editor in st.session_state:
                del st.session_state[chave_editor]
            time.sleep(1)
            st.rerun()
            
        except Exception as e:
            st.error(f"Erro ao salvar no banco de dados: {e}")