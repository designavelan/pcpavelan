import streamlit as st
import pandas as pd
import banco

def get_idx(lista, valor):
    return lista.index(valor) if valor in lista else 0

def renderizar(df_nuvem):
    st.markdown("### 👥 Controle de Acessos")
    st.markdown("Gerencie os perfis de permissão e os usuários do sistema. Defina onde cada operador irá atuar.")
    st.markdown("<hr style='opacity: 0.2;'>", unsafe_allow_html=True)
    
    tab_users, tab_perfis = st.tabs(["👤 Gestão de Usuários", "🛡️ Gestão de Perfis"])
    
    supa = banco.conectar()
    df_perfis = banco.obter_perfis()
    
    # ⚠️ LISTA ATUALIZADA: Painel de OPs, Desempenho, Produtos, Caixas e Permissão Virtual da Central
    todas_abas_sistema = [
        "📱 Chão de Fábrica", "🔴 Ao Vivo", "🎯 Painel de OPs", 
        "🏆 Desempenho", "💡 Plano de Ação", "📈 Disponibilidade", 
        "📋 Apontamentos", "🔎 Ocorrências", "📦 Produtos", "📦 Caixas",
        "⚙️ Configurações", "👥 Controle de Acessos", "🔔 Central de Correções"
    ]
    
    lista_setores = sorted(df_nuvem['setor'].dropna().unique().tolist()) if not df_nuvem.empty else []
    lista_maquinas_geral = sorted(df_nuvem['maquina'].dropna().unique().tolist()) if not df_nuvem.empty else []
    opcoes_perfis = df_perfis['nome_perfil'].tolist() if not df_perfis.empty else []

    # ==========================================
    # ABA 2: GESTÃO DE PERFIS (Hierarquia)
    # ==========================================
    with tab_perfis:
        acao_perfil = st.radio("Selecione a ação:", ["➕ Criar Novo Perfil", "✏️ Editar Perfil Existente"], horizontal=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        if acao_perfil == "➕ Criar Novo Perfil":
            st.markdown("#### Criar Novo Perfil")
            c1, c2 = st.columns([1, 2])
            with c1: novo_nome_perfil = st.text_input("Nome do Cargo / Perfil", placeholder="Ex: Gestor, Operador...")
            with c2: novas_abas = st.multiselect("Abas Permitidas para este perfil:", todas_abas_sistema)
                
            if st.button("💾 Salvar Novo Perfil", type="primary"):
                if not novo_nome_perfil or not novas_abas:
                    st.warning("Preencha o nome do perfil e escolha pelo menos uma aba.")
                elif novo_nome_perfil.lower() == "administrador":
                    st.error("O nome 'Administrador' é reservado pelo sistema.")
                else:
                    try:
                        str_abas = ", ".join(novas_abas)
                        banco.conectar().table("perfis_acesso").insert({"nome_perfil": novo_nome_perfil, "abas_permitidas": str_abas}).execute()
                        st.success("✅ Perfil criado com sucesso!")
                        st.rerun()
                    except Exception as e: st.error(f"Erro ao salvar: {e}")

        else: # EDITAR PERFIL
            st.markdown("#### Editar Perfil")
            if not df_perfis.empty:
                perfil_selecionado = st.selectbox("Selecione o perfil que deseja editar:", opcoes_perfis)
                
                if perfil_selecionado:
                    dados_p = df_perfis[df_perfis['nome_perfil'] == perfil_selecionado].iloc[0]
                    
                    if dados_p['is_admin']:
                        st.info("👑 O perfil Administrador é blindado pelo sistema. Ele possui acesso permanente a TODAS as abas e não pode ser editado.")
                    else:
                        abas_atuais = [a.strip() for a in dados_p['abas_permitidas'].split(',')]
                        abas_validas_atuais = [a for a in abas_atuais if a in todas_abas_sistema]
                        
                        ed_abas = st.multiselect(f"Abas Permitidas para '{perfil_selecionado}':", todas_abas_sistema, default=abas_validas_atuais)
                        
                        if st.button("💾 Salvar Alterações no Perfil", type="primary"):
                            if not ed_abas: st.warning("Escolha pelo menos uma aba.")
                            else:
                                banco.atualizar_perfil(int(dados_p['id']), {"abas_permitidas": ", ".join(ed_abas)})
                                st.success("✅ Permissões atualizadas com sucesso!")
                                st.rerun()
            else: st.info("Nenhum perfil disponível.")

    # ==========================================
    # ABA 1: GESTÃO DE USUÁRIOS
    # ==========================================
    with tab_users:
        st.markdown("#### Lista de Usuários")
        usuarios_lista = banco.obter_usuarios_completo()
        
        if usuarios_lista:
            df_users_view = pd.DataFrame(usuarios_lista)
            df_users_view['Nome do Perfil'] = df_users_view['perfis_acesso'].apply(lambda x: x['nome_perfil'] if isinstance(x, dict) else "")
            df_exibicao = df_users_view[['nome', 'username', 'Nome do Perfil', 'setor', 'maquina', 'ativo']].copy()
            df_exibicao.columns = ['Nome', 'Login', 'Perfil', 'Setor Vinculado', 'Máquina Vinculada', 'Ativo?']
            st.dataframe(df_exibicao, hide_index=True, use_container_width=True)
        else:
            st.info("Nenhum usuário cadastrado.")
            df_users_view = pd.DataFrame()
            
        st.markdown("<hr style='opacity: 0.1;'>", unsafe_allow_html=True)
        acao_user = st.radio("Selecione a ação:", ["➕ Cadastrar Novo Usuário", "✏️ Editar Usuário Existente"], horizontal=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        if acao_user == "➕ Cadastrar Novo Usuário":
            st.markdown("#### Cadastrar Novo")
            u1, u2 = st.columns(2)
            with u1:
                n_nome = st.text_input("Nome Completo", placeholder="Ex: João da Silva")
                n_user = st.text_input("Login de Acesso", placeholder="Ex: joao.silva")
                n_senha = st.text_input("Senha", type="password")
            with u2:
                n_perfil = st.selectbox("Perfil de Permissão", opcoes_perfis)
                n_setor = st.selectbox("Setor Vinculado", ["[ Todos ]"] + lista_setores)
                
                opcoes_maq = ["[ Todas ]"] + lista_maquinas_geral if n_setor == "[ Todos ]" else ["[ Todas ]"] + sorted(df_nuvem[df_nuvem['setor'] == n_setor]['maquina'].dropna().unique().tolist())
                n_maquina = st.selectbox("Máquina Vinculada", opcoes_maq)
                
            if st.button("💾 Cadastrar Usuário", type="primary"):
                if not n_nome or not n_user or not n_senha: st.warning("Preencha Nome, Login e Senha obrigatoriamente.")
                else:
                    try:
                        perfil_id = df_perfis[df_perfis['nome_perfil'] == n_perfil].iloc[0]['id']
                        dados_novo = {
                            "nome": n_nome, "username": n_user.lower().strip(), "senha": banco.hash_senha(n_senha),
                            "perfil_id": int(perfil_id), "setor": n_setor, "maquina": n_maquina, "ativo": True
                        }
                        banco.conectar().table("usuarios").insert(dados_novo).execute()
                        st.success("✅ Usuário cadastrado com sucesso!")
                        st.rerun()
                    except Exception as e: st.error(f"Erro ao salvar: O login já existe. ({e})")
        
        else: # EDITAR USUÁRIO
            st.markdown("#### Editar Usuário")
            if not df_users_view.empty:
                nomes_login = [f"{row['nome']} ({row['username']})" for _, row in df_users_view.iterrows()]
                user_selecionado = st.selectbox("Selecione o usuário para editar:", nomes_login)
                
                if user_selecionado:
                    login_alvo = user_selecionado.split("(")[-1].replace(")", "")
                    dados_u = df_users_view[df_users_view['username'] == login_alvo].iloc[0]
                    
                    e1, e2 = st.columns(2)
                    with e1:
                        ed_nome = st.text_input("Nome Completo", value=dados_u['nome'])
                        ed_user = st.text_input("Login de Acesso", value=dados_u['username'])
                        ed_senha = st.text_input("Nova Senha (Deixe em branco para NÃO alterar)", type="password")
                        ed_ativo = st.checkbox("Usuário Ativo (Permitir acesso)", value=bool(dados_u['ativo']))
                    with e2:
                        idx_perfil = get_idx(opcoes_perfis, dados_u['Nome do Perfil'])
                        ed_perfil = st.selectbox("Alterar Perfil", opcoes_perfis, index=idx_perfil)
                        
                        opcoes_setor = ["[ Todos ]"] + lista_setores
                        idx_setor = get_idx(opcoes_setor, dados_u['setor'])
                        ed_setor = st.selectbox("Alterar Setor Vinculado", opcoes_setor, index=idx_setor)
                        
                        opcoes_maq = ["[ Todas ]"] + lista_maquinas_geral if ed_setor == "[ Todos ]" else ["[ Todas ]"] + sorted(df_nuvem[df_nuvem['setor'] == ed_setor]['maquina'].dropna().unique().tolist())
                        idx_maq = get_idx(opcoes_maq, dados_u['maquina'])
                        ed_maquina = st.selectbox("Alterar Máquina Vinculada", opcoes_maq, index=idx_maq)
                        
                    if st.button("💾 Salvar Alterações no Usuário", type="primary"):
                        if not ed_nome or not ed_user: st.warning("Nome e Login não podem ficar vazios.")
                        else:
                            try:
                                perfil_id = df_perfis[df_perfis['nome_perfil'] == ed_perfil].iloc[0]['id']
                                dados_update = {
                                    "nome": ed_nome, "username": ed_user.lower().strip(),
                                    "perfil_id": int(perfil_id), "setor": ed_setor, "maquina": ed_maquina, "ativo": ed_ativo
                                }
                                if ed_senha: dados_update["senha"] = banco.hash_senha(ed_senha)
                                
                                banco.atualizar_usuario(int(dados_u['id']), dados_update)
                                st.success("✅ Usuário atualizado com sucesso!")
                                st.rerun()
                            except Exception as e: st.error(f"Erro ao atualizar: {e}")