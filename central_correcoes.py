import streamlit as st
import pandas as pd
from datetime import datetime
import banco

# Funções de Cache para evitar que a janela feche
def set_batch_action(pid, acao, p_data):
    if "batch_correcoes" not in st.session_state:
        st.session_state.batch_correcoes = {}
    st.session_state.batch_correcoes[pid] = (acao, p_data)

def clear_batch_action(pid):
    if "batch_correcoes" in st.session_state and pid in st.session_state.batch_correcoes:
        del st.session_state.batch_correcoes[pid]

def marcar_todos_aprovar(pendentes):
    if "batch_correcoes" not in st.session_state:
        st.session_state.batch_correcoes = {}
    for p in pendentes:
        st.session_state.batch_correcoes[p['id']] = ('aprovar', p)

@st.dialog("⚖️ Central de Correções", width="large")
def abrir_janela(admin_nome):
    # Inicia o cache se for a primeira vez que abre
    if "batch_correcoes" not in st.session_state:
        st.session_state.batch_correcoes = {}
        
    st.markdown("### ⚖️ Gestão de Correções de Produção")
    
    tab_pend, tab_recentes, tab_manual = st.tabs(["Fila de Aprovações", "Últimos Apontamentos", "Edição e Exclusão Avançada"])
    
    # ==========================================
    # ABA 1: FILA DE APROVAÇÕES (DO TABLET)
    # ==========================================
    with tab_pend:
        pendentes = banco.obter_solicitacoes_pendentes()
        if not pendentes:
            st.success("🎉 Nenhuma solicitação pendente no momento.")
            st.session_state.batch_correcoes = {} # Limpa cache se não houver pendentes
        else:
            # NOVO: BOTÃO APROVAR TODOS
            col_espaco, col_btn_todos = st.columns([7, 3])
            col_btn_todos.button("✅ Marcar Todos para Aprovar", on_click=marcar_todos_aprovar, args=(pendentes,), use_container_width=True)
            
            for p in pendentes:
                prod_info = p.get('producao_diaria', {})
                if isinstance(prod_info, list) and len(prod_info) > 0: prod_info = prod_info[0]
                
                nome_peca = prod_info.get('nome_peca', 'Desconhecida')
                setor = prod_info.get('setor', '')
                maq = prod_info.get('maquina', '')
                
                cod_peca_antigo = p.get('cod_peca_antigo')
                cod_peca_novo = p.get('cod_peca_novo')
                nome_peca_antigo = p.get('nome_peca_antigo')
                nome_peca_novo = p.get('nome_peca_novo')
                
                try: data_f = datetime.strptime(p['data_solicitacao'], "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M")
                except: data_f = p['data_solicitacao']
                
                st.markdown(f"**Registro #ID:** {p['id_producao']} ({setor} - {maq})")
                st.markdown(f"**Operador:** {p['operador_solicitante']} | **Data do Pedido:** {data_f}")
                
                # BLOCO VISUAL "DE ➔ PARA"
                st.markdown("<div style='background-color: #f8f9fa; padding: 12px; border-radius: 8px; border-left: 4px solid #f39c12; margin: 10px 0;'>", unsafe_allow_html=True)
                
                if nome_peca_antigo and nome_peca_novo and nome_peca_antigo != nome_peca_novo:
                    st.markdown(f"<div style='font-size:14px; margin-bottom:10px;'><b>🛠️ Correção de Peça:</b><br><span style='color:#e74c3c; text-decoration: line-through;'>De: {nome_peca_antigo}</span> <br><span style='color:#27ae60;'>Para: {nome_peca_novo}</span></div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='font-size:14px; margin-bottom:10px;'><b>🛠️ Peça:</b> {nome_peca} (Sem alteração)</div>", unsafe_allow_html=True)
                    
                if p['qtd_antiga'] != p['qtd_nova']:
                    st.markdown(f"<div style='font-size:14px;'><b>📦 Correção de Quantidade:</b><br><span style='color:#e74c3c; text-decoration: line-through;'>De: {p['qtd_antiga']}</span> <br><span style='color:#27ae60;'>Para: {p['qtd_nova']}</span></div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='font-size:14px;'><b>📦 Quantidade:</b> {p['qtd_antiga']} (Sem alteração)</div>", unsafe_allow_html=True)
                    
                st.markdown("</div>", unsafe_allow_html=True)
                
                if p.get('motivo'):
                    st.info(f"**Motivo:** {p['motivo']}")
                
                # ==========================================
                # LÓGICA DE CACHE (MARCAR PARA APROVAR/RECUSAR)
                # ==========================================
                estado_atual = st.session_state.batch_correcoes.get(p['id'], 'pendente')
                
                if estado_atual == 'pendente':
                    c1, c2 = st.columns(2)
                    # O 'on_click' impede que o modal feche!
                    c1.button("✅ Aprovar e Corrigir", key=f"apr_{p['id']}", type="primary", use_container_width=True, on_click=set_batch_action, args=(p['id'], 'aprovar', p))
                    c2.button("❌ Recusar Pedido", key=f"rec_{p['id']}", use_container_width=True, on_click=set_batch_action, args=(p['id'], 'recusar', p))
                elif isinstance(estado_atual, tuple) and estado_atual[0] == 'aprovar':
                    c1, c2 = st.columns([7, 3])
                    c1.success("✅ **Marcado para: Aprovar e Corrigir**")
                    c2.button("Desfazer", key=f"desf_{p['id']}", use_container_width=True, on_click=clear_batch_action, args=(p['id'],))
                elif isinstance(estado_atual, tuple) and estado_atual[0] == 'recusar':
                    c1, c2 = st.columns([7, 3])
                    c1.error("❌ **Marcado para: Recusar Pedido**")
                    c2.button("Desfazer", key=f"desf_{p['id']}", use_container_width=True, on_click=clear_batch_action, args=(p['id'],))

                st.markdown("<hr style='opacity: 0.2;'>", unsafe_allow_html=True)
                
            # ==========================================
            # RODAPÉ: BOTÕES GLOBAIS DE APLICAR / CANCELAR
            # ==========================================
            acoes_pendentes = len(st.session_state.batch_correcoes)
            if acoes_pendentes > 0:
                st.markdown(f"<div style='background-color: #f1f2f6; padding: 20px; border-radius: 8px; border: 2px solid #bdc3c7; text-align: center; margin-top: 20px;'>", unsafe_allow_html=True)
                st.markdown(f"<h4 style='color: #2c3e50; margin-bottom: 15px;'>💾 Fila de Processamento: {acoes_pendentes} ação(ões) marcada(s)</h4>", unsafe_allow_html=True)
                
                c_app, c_can = st.columns(2)
                
                if c_app.button("✅ Aplicar Alterações", type="primary", use_container_width=True):
                    with st.spinner("Processando solicitações..."):
                        # Executa as ações no banco
                        for pid, (acao, p_data) in st.session_state.batch_correcoes.items():
                            if acao == 'aprovar':
                                banco.aprovar_solicitacao(
                                    p_data['id'], 
                                    p_data['id_producao'], 
                                    p_data['qtd_nova'], 
                                    admin_nome,
                                    cod_peca_novo=p_data.get('cod_peca_novo'),
                                    nome_peca_novo=p_data.get('nome_peca_novo')
                                )
                            elif acao == 'recusar':
                                banco.recusar_solicitacao(p_data['id'], admin_nome)
                    
                    st.session_state.batch_correcoes = {}
                    st.rerun() # O Rerun aqui é o que faz a janela fechar!
                    
                if c_can.button("🚫 Cancelar Tudo", use_container_width=True):
                    st.session_state.batch_correcoes = {}
                    st.rerun() # O Rerun aqui é o que faz a janela fechar!
                
                st.markdown("</div>", unsafe_allow_html=True)

    # ==========================================
    # ABA 2: ÚLTIMOS APONTAMENTOS (BUSCA RÁPIDA)
    # ==========================================
    with tab_recentes:
        st.markdown("#### 🕒 Últimos 50 Apontamentos da Fábrica")
        st.markdown("Use esta tabela para localizar rapidamente o ID do registro que deseja editar ou excluir.")
        
        try:
            supa = banco.conectar()
            resp = supa.table("producao_diaria").select("id, setor, maquina, nome_peca, quantidade, data_registro, as_hora").order("id", desc=True).limit(50).execute()
            
            if resp.data:
                df_recentes = pd.DataFrame(resp.data)
                df_recentes['data_registro'] = pd.to_datetime(df_recentes['data_registro']).dt.strftime('%d/%m/%Y')
                
                df_recentes = df_recentes[['id', 'data_registro', 'as_hora', 'setor', 'maquina', 'nome_peca', 'quantidade']]
                df_recentes.columns = ['ID', 'Data', 'Hora', 'Setor', 'Máquina', 'Peça / Produto', 'Qtd']
                
                st.dataframe(df_recentes, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum registro encontrado no banco de dados.")
        except Exception as e:
            st.error(f"Erro ao carregar registros recentes: {e}")

    # ==========================================
    # ABA 3: EDIÇÃO E EXCLUSÃO (ZONA DE AÇÃO)
    # ==========================================
    with tab_manual:
        st.markdown("Busque um ID de produção para conferir os dados antes de fazer a alteração ou exclusão.")
        
        if "registro_busca_manual" not in st.session_state:
            st.session_state.registro_busca_manual = None

        col_busca1, col_busca2 = st.columns([7, 3])
        with col_busca1:
            id_busca_str = st.text_input("Digite o ID do Registro:", value="", placeholder="Ex: 15482", key="input_id_busca")
        with col_busca2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔍 Buscar Registro", use_container_width=True):
                if id_busca_str.strip().isdigit():
                    id_busca = int(id_busca_str.strip())
                    reg_encontrado = banco.obter_registro_por_id(id_busca)
                    if reg_encontrado:
                        st.session_state.registro_busca_manual = reg_encontrado
                    else:
                        st.session_state.registro_busca_manual = None
                        st.error("❌ Registro não encontrado. Verifique o ID.")
                else:
                    st.error("⚠️ Por favor, digite um ID numérico válido.")

        if st.session_state.registro_busca_manual:
            reg = st.session_state.registro_busca_manual
            
            data_reg = reg.get('data_registro', '')
            try: data_reg_br = datetime.strptime(data_reg, "%Y-%m-%d").strftime("%d/%m/%Y")
            except: data_reg_br = data_reg

            st.markdown("<hr style='opacity: 0.2; margin: 15px 0;'>", unsafe_allow_html=True)
            st.markdown("<h4 style='color: #2980b9; margin-bottom: 10px;'>📄 Dados do Registro Encontrado</h4>", unsafe_allow_html=True)
            
            html_info = f"""
            <div style="background-color: #eaf2f8; padding: 15px; border-radius: 8px; border: 1px solid #bce0fd; color: #2c3e50; font-size: 15px; line-height: 1.8; margin-bottom: 15px;">
                <b>ID:</b> {reg.get('id')}<br>
                <b>Setor:</b> {reg.get('setor')}<br>
                <b>Máquina:</b> {reg.get('maquina')}<br>
                <b>Peça:</b> {reg.get('nome_peca')}<br>
                <b>Código da Peça:</b> {reg.get('cod_peca')}<br>
                <b>Operador:</b> {reg.get('operador')}<br>
                <b>Data:</b> {data_reg_br}<br>
                <b>Horário:</b> {reg.get('das')} às {reg.get('as_hora')}<br>
                <b>Quantidade Registrada:</b> <span style="color: #e74c3c; font-weight: bold;">{reg.get('quantidade')}</span>
            </div>
            """
            st.markdown(html_info, unsafe_allow_html=True)
            
            st.markdown("#### ⚙️ Ações Disponíveis")
            
            col_edit, col_del = st.columns(2)
            
            with col_edit:
                st.markdown("<div style='background-color: #f8f9fa; padding: 15px; border-radius: 8px; border: 1px solid #e1e8ed; height: 100%;'>", unsafe_allow_html=True)
                st.markdown("<h5 style='color: #27ae60; margin-top: 0;'>✏️ Alterar Quantidade</h5>", unsafe_allow_html=True)
                
                qtd_atual = ""
                try: qtd_atual = str(int(float(reg.get('quantidade', 0))))
                except: pass

                nova_qtd_m_str = st.text_input("Nova Quantidade Correta:", value=qtd_atual, key=f"qtd_{reg['id']}")
                motivo_m = st.text_input("Motivo da Alteração:", key=f"motivo_{reg['id']}")
                
                if st.button("✅ Salvar Alteração", type="primary", use_container_width=True, key=f"btn_salvar_{reg['id']}"):
                    if nova_qtd_m_str.strip().isdigit():
                        nova_qtd_m = int(nova_qtd_m_str.strip())
                        if motivo_m:
                            sucesso, msg = banco.corrigir_registro_manual(reg['id'], nova_qtd_m, motivo_m, admin_nome)
                            if sucesso:
                                st.success("✅ Registro corrigido com sucesso!")
                                st.session_state.registro_busca_manual = None
                                st.rerun()
                            else:
                                st.error(msg)
                        else:
                            st.warning("⚠️ Informe um motivo para a auditoria antes de confirmar.")
                    else:
                        st.error("⚠️ A quantidade precisa ser um número inteiro válido.")
                st.markdown("</div>", unsafe_allow_html=True)

            with col_del:
                st.markdown("<div style='background-color: #fdf4f3; padding: 15px; border-radius: 8px; border: 1px solid #f5c6cb; height: 100%;'>", unsafe_allow_html=True)
                st.markdown("<h5 style='color: #c0392b; margin-top: 0;'>🗑️ Excluir Registro</h5>", unsafe_allow_html=True)
                st.markdown("<p style='font-size: 13px; color: #7f8c8d;'>Esta ação apagará permanentemente este apontamento do banco de dados e dos painéis de desempenho. <b>Não pode ser desfeita.</b></p>", unsafe_allow_html=True)
                
                st.markdown("<br>", unsafe_allow_html=True)
                confirma_del = st.checkbox("🚨 Tenho certeza que desejo excluir este registro.", key=f"check_del_{reg['id']}")
                
                if st.button("🗑️ Excluir Permanentemente", type="primary", use_container_width=True, disabled=not confirma_del, key=f"btn_del_{reg['id']}"):
                    try:
                        supa = banco.conectar()
                        supa.table("producao_diaria").delete().eq("id", reg['id']).execute()
                        
                        st.success("✅ Registro excluído permanentemente com sucesso!")
                        st.session_state.registro_busca_manual = None
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao excluir registro: {e}")
                st.markdown("</div>", unsafe_allow_html=True)