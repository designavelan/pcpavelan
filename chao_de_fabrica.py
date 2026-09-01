import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import banco
import json

# Importando nossos novos módulos MVC
import chao_de_fabrica_ui as ui
import chao_de_fabrica_logica as logica

# ==========================================
# MOTOR DE CACHE E FUNÇÕES AUXILIARES
# ==========================================
@st.cache_data(ttl=60, show_spinner=False)
def cache_obter_produtos():
    return banco.obter_produtos_matriz()

@st.cache_data(ttl=60, show_spinner=False)
def cache_obter_caixas():
    supa = banco.conectar()
    try:
        resp = supa.table("caixas_matriz").select("*").execute()
        return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    except:
        return pd.DataFrame()

@st.cache_data(ttl=60, show_spinner=False)
def cache_obter_ativos():
    supa = banco.conectar()
    try:
        resp = supa.table("produtos_ativos").select("produto_formula").execute()
        return [r['produto_formula'] for r in resp.data] if resp.data else []
    except:
        return []

@st.cache_data(ttl=120, show_spinner=False)
def cache_obter_estrutura():
    return banco.obter_estrutura()

# ==========================================
# JANELAS FLUTUANTES (POP-UPS)
# ==========================================
@st.dialog("📝 Solicitar Correção de Apontamento")
def abrir_dialog_correcao(id_reg, qtd_atual, nomes_operadores, cod_peca_atual, nome_peca_atual, is_embalagem):
    st.markdown(f"<h4 style='color:#2c3e50; margin-top:0;'>Registro: #{id_reg}</h4>", unsafe_allow_html=True)
    
    st.markdown("**Apontamento Atual:**")
    st.info(f"**Peça:** {nome_peca_atual}\n\n**Quantidade:** {qtd_atual}")
    
    st.markdown("---")
    st.markdown("##### 🛠️ Como deveria ser?")
    st.markdown("<p style='font-size:13px; color:#7f8c8d; margin-top:-10px;'>Altere apenas o que estiver errado.</p>", unsafe_allow_html=True)
    
    df_produtos = cache_obter_produtos()
    produtos_ativos = cache_obter_ativos()
    
    lista_todos = sorted(df_produtos['produto_formula'].dropna().unique().tolist()) if not df_produtos.empty else []
    
    prod_atual = nome_peca_atual.split(" ➔ ")[0] if " ➔ " in nome_peca_atual else nome_peca_atual
    idx_prod = lista_todos.index(prod_atual) if prod_atual in lista_todos else 0
    
    novo_prod = st.selectbox("1. Produto Correto:", lista_todos, index=idx_prod)
    
    if is_embalagem:
        df_caixas = cache_obter_caixas()
        if not df_caixas.empty:
            df_cx_filtro = df_caixas[df_caixas['produto_formula'] == novo_prod]
            lista_pecas = [f"Caixa {row['num_caixa']} (Cód: {row['cod_caixa']})" if str(row['cod_caixa']).strip() not in ["", "None", "nan"] else f"Caixa {row['num_caixa']} (Cód: VIRTUAL-{novo_prod}-{row['num_caixa']})".replace(" ", "_").upper() for _, row in df_cx_filtro.iterrows()]
        else:
            lista_pecas = []
    else:
        df_pecas = df_produtos[df_produtos['produto_formula'] == novo_prod]
        lista_pecas = [f"{row['descricao']} (Cód: {row['cod']})" for _, row in df_pecas.iterrows()]
        
    idx_peca = 0
    for i, p in enumerate(lista_pecas):
        if str(cod_peca_atual) in p:
            idx_peca = i
            break
            
    nova_peca_display = st.selectbox("2. Peça/Volume Correto:", lista_pecas, index=idx_peca if lista_pecas else 0)
    
    try: val_inicial = int(float(qtd_atual))
    except: val_inicial = 0
        
    nova_qtd = st.number_input("3. Quantidade Correta:", min_value=0, step=1, value=val_inicial)
    motivo = st.text_area("Motivo da correção:", placeholder="Ex: Selecionei a peça errada na hora da pressa...")
    
    if st.button("Enviar Solicitação", type="primary", use_container_width=True):
        if nova_peca_display:
            novo_cod_peca = nova_peca_display.split("(Cód: ")[-1].replace(")", "").strip()
            novo_nome_peca_final = f"{novo_prod} ➔ {nova_peca_display.split(' (Cód:')[0]}"
        else:
            novo_cod_peca = cod_peca_atual
            novo_nome_peca_final = nome_peca_atual
            
        if nova_qtd == val_inicial and novo_cod_peca == cod_peca_atual:
            st.warning("⚠️ Você não alterou nem a peça nem a quantidade.")
        elif not motivo:
            st.warning("⚠️ Informe o motivo da correção para a auditoria.")
        else:
            sucesso, msg = banco.enviar_solicitacao_correcao(
                id_reg, nomes_operadores, val_inicial, nova_qtd, motivo,
                cod_peca_atual, novo_cod_peca, nome_peca_atual, novo_nome_peca_final
            )
            if sucesso:
                st.success("✅ Solicitação enviada para aprovação do Gestor!")
                st.rerun()
            else:
                st.error(msg)

@st.dialog("🔄 Trocar de Máquina")
def abrir_dialog_troca_maquina(status_atual, df_est, usuario):
    if status_atual != 'Livre':
        st.error("⚠️ Operação Bloqueada!")
        st.warning(f"Sua máquina atual está **{status_atual}**. Você precisa finalizar a ação em andamento e deixá-la 'Livre' antes de assumir outro equipamento.")
        if st.button("Entendi", use_container_width=True):
            st.rerun()
        return
        
    st.markdown("Selecione o novo local de trabalho:")
    lista_setores = sorted(df_est['setor'].dropna().unique().tolist())
    
    idx_setor = lista_setores.index(usuario.get('setor')) if usuario.get('setor') in lista_setores else 0
    novo_setor = st.selectbox("🏭 Novo Setor:", lista_setores, index=idx_setor)
    
    lista_maq = sorted(df_est[df_est['setor'] == novo_setor]['maquina'].dropna().unique().tolist())
    
    idx_maq = lista_maq.index(usuario.get('maquina')) if usuario.get('maquina') in lista_maq else 0
    nova_maq = st.selectbox("⚙️ Nova Máquina:", lista_maq, index=idx_maq)
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Confirmar Troca ✅", type="primary", use_container_width=True):
        try:
            supa = banco.conectar()
            supa.table("usuarios").update({
                "setor": novo_setor,
                "maquina": nova_maq
            }).eq("id", usuario['id']).execute()
            
            st.session_state['usuario_logado']['setor'] = novo_setor
            st.session_state['usuario_logado']['maquina'] = nova_maq
            
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao trocar de máquina: {e}")

# ==========================================
# RENDERIZAÇÃO PRINCIPAL
# ==========================================
def renderizar(df_nuvem, df_codigos):
    if 'tk_counter' not in st.session_state: 
        st.session_state['tk_counter'] = 0

    ui.injetar_css_global()

    supa = banco.conectar()
    df_est = cache_obter_estrutura()
    if df_est.empty:
        st.warning("⚠️ Nenhuma estrutura de fábrica cadastrada. Vá na aba Configurações > Estrutura.")
        return

    mapa_cores = banco.obter_mapa_cores()

    usuario = st.session_state.get('usuario_logado', {})
    user_setor = str(usuario.get('setor', '[ Todos ]')).strip()
    user_maq = str(usuario.get('maquina', '[ Todas ]')).strip()

    is_travado = (user_setor != "[ Todos ]" and user_maq != "[ Todas ]" and user_setor != "" and user_maq != "")
    lista_setores_nuvem = sorted(df_est['setor'].dropna().unique().tolist())

    # ==========================================
    # BLOQUEIO DE SEGURANÇA PARA OPERADORES SEM MÁQUINA VINCULADA
    # ==========================================
    perfil_atual = usuario.get('perfis_acesso', {})
    is_admin = perfil_atual.get('is_admin', False)

    if not is_admin and not is_travado:
        st.markdown(f"<div style='text-align: center; margin-top: 50px;'><h2 style='color: #2c3e50;'>👋 Olá, {usuario.get('nome', 'Operador')}!</h2>", unsafe_allow_html=True)
        st.markdown("<p style='color: #7f8c8d; font-size: 16px; text-align: center;'>Para iniciarmos o seu turno, precisamos saber onde você vai trabalhar hoje.</p></div>", unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns([2.5, 5, 2.5])
        with c2:
            st.info("💡 **Atenção:** Selecione a máquina correta que você irá operar para que o sistema registre sua produção e garanta a precisão dos indicadores.")
            
            idx_setor = lista_setores_nuvem.index(user_setor) if user_setor in lista_setores_nuvem else 0
            novo_setor = st.selectbox("🏭 1. Selecione seu Setor:", lista_setores_nuvem, index=idx_setor)
            
            lista_maq_db = sorted(df_est[df_est['setor'] == novo_setor]['maquina'].dropna().unique().tolist())
            nova_maq = st.selectbox("⚙️ 2. Selecione sua Máquina:", lista_maq_db)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button("✅ Confirmar Local de Trabalho", type="primary", use_container_width=True):
                if nova_maq:
                    try:
                        supa.table("usuarios").update({
                            "setor": novo_setor,
                            "maquina": nova_maq
                        }).eq("id", usuario['id']).execute()
                        
                        st.session_state['usuario_logado']['setor'] = novo_setor
                        st.session_state['usuario_logado']['maquina'] = nova_maq
                        
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao vincular máquina: {e}")
                else:
                    st.warning("Selecione uma máquina válida para continuar.")
        return # Sai da função para bloquear o restante da tela

    # Se passou pelo bloqueio, a lógica continua normalmente
    if is_travado:
        setor_selecionado = user_setor
        maquina_selecionada = user_maq
        nomes_operadores = usuario.get('nome', 'Operador Desconhecido')
        operadores_vinculados = [nomes_operadores]
    else:
        setor_selecionado = st.session_state.get("cf_setor", lista_setores_nuvem[0] if lista_setores_nuvem else "")
        if setor_selecionado not in lista_setores_nuvem and lista_setores_nuvem: setor_selecionado = lista_setores_nuvem[0]
            
        lista_maquinas_nuvem = sorted(df_est[df_est['setor'] == setor_selecionado]['maquina'].dropna().unique().tolist())
        maquina_selecionada = st.session_state.get("cf_maquina", lista_maquinas_nuvem[0] if lista_maquinas_nuvem else "")
        if maquina_selecionada not in lista_maquinas_nuvem and lista_maquinas_nuvem: maquina_selecionada = lista_maquinas_nuvem[0]

        usuarios_cadastrados = banco.obter_usuarios_completo()
        operadores_vinculados = [
            u['nome'] for u in usuarios_cadastrados 
            if str(u.get('setor')) == str(setor_selecionado) and str(u.get('maquina')) == str(maquina_selecionada) and u.get('ativo') == True
        ]
        nomes_operadores = " / ".join(operadores_vinculados) if operadores_vinculados else "Sem Operador"

    df_produtos = cache_obter_produtos()
    produtos_ativos = cache_obter_ativos()
    is_embalagem = (str(setor_selecionado).strip().upper() == "EMBALAGEM")

    permite_dupla = False
    maq_row = df_est[(df_est['setor'] == setor_selecionado) & (df_est['maquina'] == maquina_selecionada)]
    if not maq_row.empty:
        val_raw = maq_row.iloc[0].get('permite_producao_dupla', False)
        permite_dupla = True if str(val_raw).strip().lower() == 'true' or val_raw is True else False

    hoje_str = logica.obter_hora_atual().strftime("%Y-%m-%d")
    producao_hoje_pecas = {}
    
    if not df_nuvem.empty and 'maquina' in df_nuvem.columns and 'setor' in df_nuvem.columns:
        if 'tipo' not in df_nuvem.columns: df_nuvem['tipo'] = 'PARADA'
        
        df_prod_hoje = df_nuvem[
            (df_nuvem['maquina'] == maquina_selecionada) & 
            (df_nuvem['setor'] == setor_selecionado) & 
            (df_nuvem['data_registro'] == hoje_str) & 
            (df_nuvem['tipo'].astype(str).str.strip().str.upper() == 'PRODUÇÃO')
        ]
        
        for _, row_prod in df_prod_hoje.iterrows():
            c_peca = str(row_prod.get('cod_peca', '')).strip()
            qtd = row_prod.get('quantidade', 0)
            try: qtd = int(qtd)
            except: qtd = 0
            
            if c_peca not in producao_hoje_pecas:
                producao_hoje_pecas[c_peca] = []
            if qtd > 0:
                producao_hoje_pecas[c_peca].append(qtd)

    response = supa.table("status_maquinas").select("*").eq("maquina", maquina_selecionada).eq("setor", setor_selecionado).execute()
    status_db = 'Livre'
    hora_inicio_str = None
    cod_ocorrencia = None
    cod_peca_atual = None
    ultimo_produto_sel = ""
    ultima_peca_sel = ""
    
    if response.data:
        dados_maq = response.data[0]
        status_db = dados_maq.get('status', 'Livre')
        if status_db == 'Trabalhando': status_db = 'Livre'
        hora_inicio_str = dados_maq.get('hora_inicio')
        cod_ocorrencia = dados_maq.get('cod_ocorrencia')
        cod_peca_atual = dados_maq.get('cod_peca_atual')
        
        ultimo_produto_sel = dados_maq.get('ultimo_produto_sel', "")
        ultima_peca_sel = dados_maq.get('ultima_peca_sel', "")
    else:
        try:
            supa.table("status_maquinas").insert({
                "setor": setor_selecionado, 
                "maquina": maquina_selecionada, 
                "status": "Livre"
            }).execute()
        except:
            pass

    if not df_codigos.empty:
        if 'exibir_na_lista' in df_codigos.columns:
            setor_upper = str(setor_selecionado).strip().upper()
            def filtrar_por_setor(valor):
                if pd.isna(valor) or str(valor).strip() == '': return False
                partes = [p.strip().upper() for p in str(valor).split(',')]
                return 'TODOS' in partes or setor_upper in partes
            df_codigos_parado = df_codigos[df_codigos['exibir_na_lista'].apply(filtrar_por_setor)]
        else:
            if 'tipo' in df_codigos.columns: df_codigos_parado = df_codigos[(df_codigos['tipo'].astype(str).str.strip().str.upper() != 'PRODUÇÃO') & (df_codigos['codigo'].astype(str).str.strip().str.upper() != 'P')]
            else: df_codigos_parado = pd.DataFrame()
    else: df_codigos_parado = pd.DataFrame()

    def limpar_gatilho():
        st.session_state["trigger_60s"] = ""

    st.text_input("trigger_60s_js", key="trigger_60s", label_visibility="collapsed", on_change=limpar_gatilho)

    if status_db == 'Livre':
        tab_prod, tab_parada = st.tabs(["🟢 MODO PRODUÇÃO", "🔴 MODO PARADA"])
        
        with tab_prod:
            last_prod = ultimo_produto_sel if ultimo_produto_sel else ""
            last_peca = ultima_peca_sel if ultima_peca_sel else ""
            
            st.markdown("<br>", unsafe_allow_html=True)
            c_header1, c_header2 = st.columns([7, 3])
            with c_header1: st.markdown("<div style='font-size: 20px; font-weight: bold; color: #2c3e50; margin:0;'>📦 Seleção de Material</div>", unsafe_allow_html=True)
            with c_header2: mostrar_todos = st.checkbox("Exibir Produtos Fora de Linha", value=False)
            
            if not df_produtos.empty:
                lista_todos = sorted(df_produtos['produto_formula'].dropna().unique().tolist())
                
                if mostrar_todos or not produtos_ativos: 
                    lista_exibicao = lista_todos.copy()
                else: 
                    lista_exibicao = [p for p in lista_todos if p in produtos_ativos]
                
                if last_prod and last_prod not in lista_exibicao and last_prod in lista_todos:
                    lista_exibicao.append(last_prod)
                    lista_exibicao = sorted(lista_exibicao)
                
                mapa_ops = {}
                ops_ativas_unicas = []
                try:
                    resp_ops = supa.table("planejamento_ops").select("*").eq("status", "Em Andamento").order("ordem_prioridade", desc=False).order("id", desc=True).execute()
                    for op in (resp_ops.data if resp_ops.data else []):
                        p_name = op['produto_formula']
                        if p_name not in ops_ativas_unicas:
                            ops_ativas_unicas.append(p_name)
                            mapa_ops[p_name] = op
                except:
                    pass
                
                separador = "───────────────────────────────"
                lista_exibicao_final = []
                mapa_prod_real = {}
                ops_presentes = [p for p in ops_ativas_unicas if p in lista_todos]
                
                for idx_op, p in enumerate(ops_presentes):
                    numero_op = idx_op + 1
                    display_name = f"🔥 [OP {numero_op}] {p}"
                    lista_exibicao_final.append(display_name)
                    mapa_prod_real[display_name] = p
                    
                if ops_presentes:
                    lista_exibicao_final.append(separador)
                    mapa_prod_real[separador] = None
                    
                for p in lista_exibicao:
                    if p not in ops_presentes:
                        lista_exibicao_final.append(p)
                        mapa_prod_real[p] = p
                
                chave_mem_prod = f"mem_prod_{setor_selecionado}_{maquina_selecionada}"
                if chave_mem_prod not in st.session_state:
                    initial_val = ""
                    if last_prod:
                        if last_prod in ops_presentes:
                            numero_op = ops_presentes.index(last_prod) + 1
                            initial_val = f"🔥 [OP {numero_op}] {last_prod}"
                        elif last_prod in lista_exibicao and last_prod not in ops_presentes:
                            initial_val = last_prod
                    elif ops_presentes and len(lista_exibicao_final) > 1:
                        initial_val = lista_exibicao_final[0]
                    st.session_state[chave_mem_prod] = initial_val

                sel_prod_display = st.session_state[chave_mem_prod]
                chave_wid_prod = f"sel_prod_{setor_selecionado}_{maquina_selecionada}_{st.session_state.get('prod_counter', 0)}"
                
                idx_prod = 0
                if last_prod:
                    if last_prod in ops_presentes:
                        numero_op = ops_presentes.index(last_prod) + 1
                        display_memoria = f"🔥 [OP {numero_op}] {last_prod}"
                        try: idx_prod = lista_exibicao_final.index(display_memoria)
                        except: idx_prod = 0
                    elif last_prod in lista_exibicao and last_prod not in ops_presentes:
                        try: idx_prod = lista_exibicao_final.index(last_prod)
                        except: idx_prod = 0
                elif ops_presentes and len(lista_exibicao_final) > 1:
                    idx_prod = 0
                
                sel_prod_display = st.selectbox("1. Produto:", options=lista_exibicao_final, index=idx_prod if lista_exibicao_final else None, key=chave_wid_prod)
                
                if sel_prod_display == separador:
                    st.warning("⚠️ Você selecionou a linha divisória. Por favor, escolha um produto acima ou abaixo dela.")
                    sel_prod = None
                else:
                    sel_prod = mapa_prod_real.get(sel_prod_display)

                if sel_prod:
                    is_in_op = sel_prod in mapa_ops
                    producao_op_pecas = {}
                    
                    if is_in_op:
                        op_info = mapa_ops[sel_prod]
                        data_inicio_op = op_info['data_inicio'].split(" ")[0].split("T")[0]
                        qtd_op = int(op_info['quantidade_planejada'])

                        if not df_nuvem.empty and 'setor' in df_nuvem.columns:
                            df_op_prod = df_nuvem[
                                (df_nuvem['setor'] == setor_selecionado) &
                                (df_nuvem['data_registro'] >= data_inicio_op) &
                                (df_nuvem['cod_peca'].notna()) &
                                (df_nuvem['tipo'].astype(str).str.strip().str.upper() == 'PRODUÇÃO')
                            ]
                            for _, r in df_op_prod.iterrows():
                                c = str(r.get('cod_peca', '')).strip()
                                q = int(float(r.get('quantidade', 0))) if pd.notna(r.get('quantidade')) else 0
                                producao_op_pecas[c] = producao_op_pecas.get(c, 0) + q

                    if is_embalagem:
                        df_caixas = cache_obter_caixas()
                        if not df_caixas.empty:
                            df_cx_filtro = df_caixas[df_caixas['produto_formula'] == sel_prod]
                            lista_pecas_limpa = []
                            for _, row in df_cx_filtro.iterrows():
                                tipo_cx = str(row.get('tipo', '')).strip()
                                if tipo_cx not in ["", "None", "nan"]:
                                    continue 
                                    
                                cod_cx = str(row.get('cod_caixa', '')).strip()
                                num_cx = str(row.get('num_caixa', '')).strip()
                                
                                if cod_cx in ["", "None", "nan"]:
                                    cod_cx = f"VIRTUAL-{sel_prod}-{num_cx}".replace(" ", "_").upper()
                                    
                                lista_pecas_limpa.append(f"Caixa {num_cx} (Cód: {cod_cx})")
                        else:
                            lista_pecas_limpa = []
                        df_pecas = pd.DataFrame()
                    else:
                        df_pecas = df_produtos[df_produtos['produto_formula'] == sel_prod]
                        lista_pecas_limpa = [f"{row['descricao']} (Cód: {row['cod']})" for _, row in df_pecas.iterrows()]
                    
                    if sel_prod == last_prod and last_peca and last_peca not in lista_pecas_limpa:
                        lista_pecas_limpa.append(last_peca)
                        
                    lista_pendentes = []
                    lista_concluidas = []
                    mapa_exibicao_limpa = {}
                    
                    for peca_limpa in lista_pecas_limpa:
                        codigo_ext = peca_limpa.split("(Cód: ")[-1].replace(")", "").strip()
                        
                        if codigo_ext in producao_hoje_pecas and producao_hoje_pecas[codigo_ext]:
                            lista_qtds = producao_hoje_pecas[codigo_ext]
                            total_hoje = sum(lista_qtds)
                            resumo_hoje = f"📦 Produzido hoje: {' + '.join(map(str, lista_qtds))} = {total_hoje} un." if len(lista_qtds) > 1 else f"📦 Produzido hoje: {total_hoje} un."
                        else:
                            resumo_hoje = "📦 Produzido hoje: 0 un."
                            
                        if is_in_op:
                            qnt_por_produto = 1
                            if not is_embalagem and not df_pecas.empty:
                                df_peca_info = df_pecas[df_pecas['cod'].astype(str) == codigo_ext]
                                if not df_peca_info.empty:
                                    try: qnt_por_produto = int(float(df_peca_info.iloc[0].get('qnt', 1)))
                                    except: qnt_por_produto = 1

                            meta = qnt_por_produto * qtd_op
                            prod = producao_op_pecas.get(codigo_ext, 0)
                            perc = (prod / meta * 100) if meta > 0 else 0
                            is_concluida = prod >= meta
                            str_perc = str(round(perc, 1)).replace('.', ',')

                            linha_op = f"🎯 OP — Necessidade: {meta} | Produzido: {prod} | {str_perc}%"
                            
                            if is_concluida:
                                texto_completo = f"✅ [CONCLUÍDA] {peca_limpa} *{resumo_hoje}* *{linha_op}*"
                                lista_concluidas.append(texto_completo)
                            else:
                                texto_completo = f"{peca_limpa} *{resumo_hoje}* *{linha_op}*"
                                lista_pendentes.append(texto_completo)
                        else:
                            texto_completo = f"{peca_limpa} *{resumo_hoje}*"
                            lista_pendentes.append(texto_completo)
                            
                        mapa_exibicao_limpa[texto_completo] = peca_limpa

                    mostrar_concluidas = False
                    if lista_concluidas:
                        st.markdown("<br>", unsafe_allow_html=True)
                        cb_key = f"cb_conc_{setor_selecionado}_{maquina_selecionada}"
                        mostrar_concluidas = st.checkbox("☑️ Exibir peças já concluídas na OP (Retrabalho/Reposição)", key=cb_key, value=False)
                        st.markdown("<br>", unsafe_allow_html=True)

                    lista_exibicao_pecas = lista_pendentes.copy()
                    if mostrar_concluidas:
                        lista_exibicao_pecas.extend(lista_concluidas)
                        
                    idx_peca = 0
                    if sel_prod == last_prod and last_peca:
                        for i, txt in enumerate(lista_exibicao_pecas):
                            if mapa_exibicao_limpa[txt] == last_peca:
                                idx_peca = i
                                break
                    
                    if not lista_exibicao_pecas:
                        st.success("🎉 Todas as peças deste produto já atingiram a meta da OP! (Use a caixinha acima se precisar relançar alguma).")
                    else:
                        ui.injetar_css_kanban()
                        titulo_peca = "2. Toque na embalagem/volume:" if is_embalagem else "2. Toque na peça para selecionar:"
                        st.markdown(f"<h4 style='color: #2c3e50; font-size: 16px; margin-top: 15px;'>{titulo_peca}</h4>", unsafe_allow_html=True)
                        
                        chave_radio_peca = f"radio_peca_{setor_selecionado}_{maquina_selecionada}"
                        sel_peca_exibicao = st.radio("Selecione a Peça", lista_exibicao_pecas, index=idx_peca, label_visibility="collapsed", key=chave_radio_peca)
                        
                        if sel_peca_exibicao and sel_peca_exibicao in mapa_exibicao_limpa:
                            peca_atual_limpa = mapa_exibicao_limpa[sel_peca_exibicao]
                            nome_peca_curto = peca_atual_limpa.split("(Cód:")[0].strip()
                        else:
                            nome_peca_curto = "VOLUME" if is_embalagem else "PEÇA"
                            
                        texto_btn_iniciar = f"▶️ INICIAR: {nome_peca_curto}"
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        chave_btn_iniciar = f"btn_ini_{maquina_selecionada}_{st.session_state.get('prod_counter', 0)}"
                        
                        if st.button(texto_btn_iniciar, type="primary", use_container_width=True, key=chave_btn_iniciar):
                            sel_peca_limpa = mapa_exibicao_limpa[sel_peca_exibicao]
                            codigo_peca = sel_peca_limpa.split("(Cód: ")[-1].replace(")", "").strip()
                            agora = logica.obter_hora_atual().strftime("%Y-%m-%d %H:%M:%S")
                            
                            val_cod_peca_db = codigo_peca
                            
                            supa.table("status_maquinas").update({
                                "status": "Produzindo", "cod_peca_atual": val_cod_peca_db, 
                                "hora_inicio": agora, "cod_ocorrencia": "P",
                                "ultimo_produto_sel": sel_prod,
                                "ultima_peca_sel": sel_peca_limpa
                            }).eq("maquina", maquina_selecionada).eq("setor", setor_selecionado).execute()
                            
                            sucesso, erro = logica.registrar_telemetria(supa, setor_selecionado, maquina_selecionada, "Iniciou Produção", df_est)
                            
                            st.session_state['prod_counter'] = st.session_state.get('prod_counter', 0) + 1
                            st.rerun()

            else:
                st.info("Nenhum produto cadastrado na Matriz.")

        with tab_parada:
            st.markdown("<br>", unsafe_allow_html=True)
            if not df_codigos_parado.empty:
                valid_codes = {str(row['codigo']).strip(): str(row['descricao']).strip() for _, row in df_codigos_parado.iterrows()}
                valid_codes_json = json.dumps(valid_codes)
                
                with st.form(key=f"form_parada_livre_{setor_selecionado}_{maquina_selecionada}"):
                    tab_tcl, tab_lst = st.tabs(["🔢 Teclado Numérico", "📄 Selecionar na Lista"])
                    
                    with tab_tcl:
                        chave_dinamica = f"input_js_{st.session_state['tk_counter']}"
                        codigo_js = st.text_input("input_codigo_js", key=chave_dinamica, label_visibility="collapsed")
                        
                        ui.components.html(ui.obter_html_teclado_parada(valid_codes_json, "input_codigo_js", "🔴 CONFIRMAR PARADA"), height=650)

                    with tab_lst:
                        opcoes_prob = [f"{str(row['descricao']).strip()} ({str(row['codigo']).strip()})" for _, row in df_codigos_parado.iterrows()]
                        problema_selecionado = st.selectbox("Selecione o problema:", [""] + opcoes_prob)
                        st.markdown("<br>", unsafe_allow_html=True)
                        btn_submit_lista_parada = st.form_submit_button("🔴 CONFIRMAR PARADA", use_container_width=True)
                        
                    if btn_submit_lista_parada or (codigo_js and codigo_js in valid_codes):
                        cod_final = codigo_js if (codigo_js and codigo_js in valid_codes) else problema_selecionado.split("(")[-1].replace(")", "").strip() if problema_selecionado else None
                        if cod_final:
                            agora = logica.obter_hora_atual().strftime("%Y-%m-%d %H:%M:%S")
                            
                            supa.table("status_maquinas").update({
                                "status": "Parado", 
                                "cod_peca_atual": None, "cod_ocorrencia": cod_final, "hora_inicio": agora
                            }).eq("maquina", maquina_selecionada).eq("setor", setor_selecionado).execute()
                            
                            sucesso, erro = logica.registrar_telemetria(supa, setor_selecionado, maquina_selecionada, f"Parada Iniciada ({cod_final})", df_est)
                            
                            st.session_state['tk_counter'] += 1 
                            st.rerun()
            else: st.warning(f"⚠️ Não há nenhum código configurado para este setor.")

    elif status_db == 'Produzindo':
        nome_peca = "Peça Desconhecida"
        
        if not cod_peca_atual and is_embalagem and ultima_peca_sel and "(Cód:" in ultima_peca_sel:
            cod_peca_atual = ultima_peca_sel.split("(Cód: ")[-1].replace(")", "").strip()
            
        if cod_peca_atual:
            if is_embalagem:
                if str(cod_peca_atual).startswith("VIRTUAL-"):
                    if ultima_peca_sel:
                        nome_cx = ultima_peca_sel.split(" (Cód:")[0].strip()
                        nome_peca = f"{ultimo_produto_sel} ➔ {nome_cx}"
                else:
                    df_caixas = cache_obter_caixas()
                    if not df_caixas.empty:
                        df_filtro = df_caixas[df_caixas['cod_caixa'].astype(str) == str(cod_peca_atual)]
                        if not df_filtro.empty:
                            nome_peca = f"{df_filtro.iloc[0]['produto_formula']} ➔ Caixa {df_filtro.iloc[0]['num_caixa']}"
            else:
                if not df_produtos.empty:
                    df_filtro = df_produtos[df_produtos['cod'].astype(str) == str(cod_peca_atual)]
                    if not df_filtro.empty:
                        nome_peca = f"{df_filtro.iloc[0]['produto_formula']} ➔ {df_filtro.iloc[0]['descricao']}"

        hora_inicio_iso = hora_inicio_str.replace(" ", "T") if hora_inicio_str else ""
        
        ui.components.html(ui.obter_html_cronometro_produzindo(nome_peca, cod_peca_atual, hora_inicio_iso), height=250)
        
        chave_estado_fin = f"fin_estado_{setor_selecionado}_{maquina_selecionada}"
        estado_fin = st.session_state.get(chave_estado_fin, None)
        
        if hora_inicio_str:
            hora_fim_calc = logica.obter_hora_atual()
            hora_inicio_calc = datetime.strptime(hora_inicio_str, "%Y-%m-%d %H:%M:%S")
            duracao_calc = (hora_fim_calc - hora_inicio_calc).total_seconds()
        else:
            duracao_calc = 999
            
        if not estado_fin:
            st.markdown("<br>", unsafe_allow_html=True)
            
            btn_canc = st.button("❌ CANCELAR PRODUÇÃO (Erro de Seleção)", use_container_width=True, key=f"btn_canc_{maquina_selecionada}")
            
            c1, c2 = st.columns(2)
            with c1: 
                btn_fin = st.button("✅ FINALIZAR (Concluído)", use_container_width=True, type="primary", key=f"btn_fin_{maquina_selecionada}")
            with c2: 
                btn_int = st.button("🔴 INTERROMPER (Por Falha)", use_container_width=True, type="primary", key=f"btn_int_{maquina_selecionada}")

            if btn_canc:
                if duracao_calc < 60:
                    supa.table("status_maquinas").update({
                        "status": "Livre", "hora_inicio": None, "cod_ocorrencia": None, "cod_peca_atual": None
                    }).eq("maquina", maquina_selecionada).eq("setor", setor_selecionado).execute()
                    
                    sucesso, erro = logica.registrar_telemetria(supa, setor_selecionado, maquina_selecionada, "Produção Cancelada", df_est)
                    st.session_state['prod_counter'] = st.session_state.get('prod_counter', 0) + 1
                    st.rerun()
                else:
                    st.error("⚠️ O período de cancelamento (1 minuto) já foi encerrado.")
                    
            if btn_fin:
                if duracao_calc >= 60:
                    st.session_state[chave_estado_fin] = "CONCLUIDO"
                    st.rerun()
                else:
                    st.error("⚠️ Aguarde o período inicial de 1 minuto para finalizar.")
                    
            if btn_int:
                if duracao_calc >= 60:
                    st.session_state[chave_estado_fin] = "INTERROMPIDO"
                    st.rerun()
                else:
                    st.error("⚠️ Aguarde o período inicial de 1 minuto para interromper.")

        elif estado_fin == "CONCLUIDO":
            with st.form(key=f"form_conc_{setor_selecionado}_{maquina_selecionada}"):
                st.markdown("<div style='font-size: 18px; font-weight: 800; color: #2c3e50; margin:0;'>📊 Fechamento da Produção</div>", unsafe_allow_html=True)
                st.markdown("<hr style='opacity: 0.2; margin-top: 5px; margin-bottom: 20px;'>", unsafe_allow_html=True)
                
                qtd_str = st.text_input("input_qtd_js", value="0", label_visibility="collapsed")
                ui.components.html(ui.obter_html_teclado_qtd("input_qtd_js"), height=550)
                
                modalidade_escolhida = "Simples"
                if permite_dupla:
                    st.markdown("<div style='margin-top: 15px; margin-bottom: 5px; color: #2c3e50; font-weight: bold; font-size:18px;'>⚙️ Modalidade de Produção</div>", unsafe_allow_html=True)
                    modalidade_escolhida = st.radio("mod_inv", ["Simples", "Dupla"], horizontal=True, label_visibility="collapsed")
                
                st.markdown("<br>", unsafe_allow_html=True)
                cb1, cb2 = st.columns(2)
                with cb1:
                    btn_salvar = st.form_submit_button("💾 CONFIRMAR E SALVAR", type="primary", use_container_width=True)
                with cb2:
                    btn_cancelar = st.form_submit_button("❌ Cancelar Operação", use_container_width=True)
                    
                if btn_salvar:
                    try: qtd_final = int(qtd_str)
                    except: qtd_final = 0
                    
                    sucesso, msg = logica.salvar_producao(supa, setor_selecionado, maquina_selecionada, nomes_operadores, hora_inicio_str, cod_peca_atual, nome_peca, qtd_final, modalidade_escolhida, None, df_codigos, df_est)
                    
                    st.session_state[chave_estado_fin] = None
                    st.session_state['tk_counter'] += 1
                    st.session_state['prod_counter'] = st.session_state.get('prod_counter', 0) + 1
                    chave_w_p = f"sel_prod_{setor_selecionado}_{maquina_selecionada}"
                    if chave_w_p in st.session_state: del st.session_state[chave_w_p]
                    st.cache_data.clear()
                    st.rerun()
                    
                if btn_cancelar:
                    st.session_state[chave_estado_fin] = None
                    st.session_state['tk_counter'] += 1
                    st.rerun()
                    
        elif estado_fin == "INTERROMPIDO":
            with st.form(key=f"form_int_{setor_selecionado}_{maquina_selecionada}"):
                st.markdown("<div style='font-size: 18px; font-weight: 800; color: #2c3e50; margin:0;'>🚨 Interrupção da Produção</div>", unsafe_allow_html=True)
                st.markdown("<hr style='opacity: 0.2; margin-top: 5px; margin-bottom: 20px;'>", unsafe_allow_html=True)
                
                qtd_str_int = st.text_input("input_qtd_js_int", value="0", label_visibility="collapsed")
                ui.components.html(ui.obter_html_teclado_qtd("input_qtd_js_int"), height=550)
                
                modalidade_escolhida = "Simples"
                if permite_dupla:
                    st.markdown("<div style='margin-top: 15px; margin-bottom: 5px; color: #2c3e50; font-weight: bold; font-size:18px;'>⚙️ Modalidade de Produção</div>", unsafe_allow_html=True)
                    modalidade_escolhida = st.radio("mod_inv_int", ["Simples", "Dupla"], horizontal=True, label_visibility="collapsed")
                
                st.markdown("<h3 style='margin-top:15px; color:#c0392b;'>Motivo da Interrupção</h3>", unsafe_allow_html=True)
                
                if not df_codigos_parado.empty:
                    valid_codes = {str(row['codigo']).strip(): str(row['descricao']).strip() for _, row in df_codigos_parado.iterrows()}
                    valid_codes_json = json.dumps(valid_codes)
                    
                    tab_tcl_int, tab_lst_int = st.tabs(["🔢 Teclado Numérico", "📄 Selecionar na Lista"])
                    
                    with tab_tcl_int:
                        codigo_js_int = st.text_input("input_codigo_js_int", label_visibility="collapsed")
                        ui.components.html(ui.obter_html_teclado_parada(valid_codes_json, "input_codigo_js_int", "🔴 CONFIRMAR INTERRUPÇÃO"), height=650)

                    with tab_lst_int:
                        opcoes_prob = [f"{str(row['descricao']).strip()} ({str(row['codigo']).strip()})" for _, row in df_codigos_parado.iterrows()]
                        problema_selecionado = st.selectbox("Selecione o problema:", [""] + opcoes_prob)
                        st.markdown("<br>", unsafe_allow_html=True)
                        btn_submit_lista_int = st.form_submit_button("🔴 CONFIRMAR INTERRUPÇÃO", use_container_width=True)
                        
                st.markdown("<br>", unsafe_allow_html=True)
                btn_cancelar_int = st.form_submit_button("❌ Cancelar Operação (Voltar)", use_container_width=True)
                
                if btn_cancelar_int:
                    st.session_state[chave_estado_fin] = None
                    st.session_state['tk_counter'] += 1
                    st.rerun()
                elif btn_submit_lista_int or (codigo_js_int and codigo_js_int in valid_codes):
                    cod_final = codigo_js_int if (codigo_js_int and codigo_js_int in valid_codes) else problema_selecionado.split("(")[-1].replace(")", "").strip() if problema_selecionado else None
                    if cod_final:
                        try: qtd_val_int = int(qtd_str_int)
                        except: qtd_val_int = 0
                        
                        sucesso, msg = logica.salvar_producao(supa, setor_selecionado, maquina_selecionada, nomes_operadores, hora_inicio_str, cod_peca_atual, nome_peca, qtd_val_int, modalidade_escolhida, cod_final, df_codigos, df_est)
                        
                        st.session_state[chave_estado_fin] = None
                        st.session_state['tk_counter'] += 1
                        st.session_state['prod_counter'] = st.session_state.get('prod_counter', 0) + 1
                        chave_w_p = f"sel_prod_{setor_selecionado}_{maquina_selecionada}"
                        if chave_w_p in st.session_state: del st.session_state[chave_w_p]
                        st.cache_data.clear()
                        st.rerun()

    elif status_db == 'Parado':
        desc_problema = "Desconhecido"
        tipo_problema = "PARADA" 
        
        if cod_ocorrencia and not df_codigos.empty:
            filtro_desc = df_codigos[df_codigos['codigo'].astype(str) == str(cod_ocorrencia)]
            if not filtro_desc.empty:
                desc_problema = str(filtro_desc.iloc[0]['descricao']).strip()
                if 'tipo' in filtro_desc.columns: tipo_problema = str(filtro_desc.iloc[0]['tipo']).strip().upper()

        hora_inicio_iso = hora_inicio_str.replace(" ", "T") if hora_inicio_str else ""
        is_pausa = (tipo_problema == 'NÃO CONTA' or 'DESCONSIDERAR' in tipo_problema)
        
        cor_dinamica = mapa_cores.get(tipo_problema)
        
        if cor_dinamica:
            cor_fundo = cor_dinamica
            cor_sombra = f"{cor_dinamica}66" 
        else:
            cor_fundo = "#f39c12" if is_pausa else "#c0392b"
            cor_sombra = "rgba(243, 156, 18, 0.4)" if is_pausa else "rgba(192, 57, 43, 0.4)"
            
        if is_pausa:
            titulo_card = "☕ PAUSA PROGRAMADA"
        elif tipo_problema == "PARADA":
            titulo_card = "🔴 MÁQUINA PARADA"
        else:
            titulo_card = f"🔴 {tipo_problema}"
            
        texto_botao = "✅ FINALIZAR INTERVALO" if is_pausa else "✅ FINALIZAR REGISTRO"

        ui.components.html(ui.obter_html_cronometro_parado(titulo_card, desc_problema, cod_ocorrencia, hora_inicio_iso, cor_fundo, cor_sombra, texto_botao), height=250)
        
        st.markdown("<br>", unsafe_allow_html=True)
        btn_canc_parada = st.button("❌ CANCELAR PARADA (Erro de Seleção)", use_container_width=True)
        btn_fin_parada = st.button(texto_botao, use_container_width=True, type="primary")
        
        if btn_canc_parada or btn_fin_parada:
            hora_fim = logica.obter_hora_atual()
            hora_inicio_obj = datetime.strptime(hora_inicio_str, "%Y-%m-%d %H:%M:%S")
            duracao_segundos = (hora_fim - hora_inicio_obj).total_seconds()
            
            if duracao_segundos >= 60 and btn_fin_parada:
                dados_nuvem = {
                    "data_registro": hora_inicio_obj.strftime("%Y-%m-%d"),
                    "setor": setor_selecionado, "maquina": maquina_selecionada, 
                    "tipo": tipo_problema,
                    "cod_ocorrencia": cod_ocorrencia, "operador": nomes_operadores,
                    "das": hora_inicio_obj.strftime("%H:%M"), "as_hora": hora_fim.strftime("%H:%M"), "origem": "Chão de Fábrica"
                }
                supa.table("producao_diaria").insert(dados_nuvem).execute()
            
            supa.table("status_maquinas").update({
                "status": "Livre", "hora_inicio": None, "cod_ocorrencia": None, "cod_peca_atual": None
            }).eq("maquina", maquina_selecionada).eq("setor", setor_selecionado).execute()
            
            texto_acao = "Registro Finalizado (Máquina Livre)" if btn_fin_parada else "Parada Cancelada (Erro Seleção)"
            sucesso, erro = logica.registrar_telemetria(supa, setor_selecionado, maquina_selecionada, texto_acao, df_est)
            
            st.rerun()

    # ==========================================
    # 4. HISTÓRICO EXCLUSIVO DO TABLET E CORREÇÕES
    # ==========================================
    st.markdown("<hr style='opacity: 0.2; margin-top: 20px; margin-bottom: 20px;'>", unsafe_allow_html=True)
    st.markdown("<div style='font-size: 20px; font-weight: bold; color: #2c3e50; margin-bottom: 15px;'>📋 Últimos Registros de Hoje</div>", unsafe_allow_html=True)
    
    hoje_str = logica.obter_hora_atual().strftime("%Y-%m-%d")
    
    if df_nuvem.empty or 'maquina' not in df_nuvem.columns: df_hist = pd.DataFrame()
    else:
        if 'origem' not in df_nuvem.columns: df_nuvem['origem'] = 'Importação'
        if 'tipo' not in df_nuvem.columns: df_nuvem['tipo'] = 'PARADA'
        df_hist = df_nuvem[(df_nuvem['maquina'] == maquina_selecionada) & (df_nuvem['setor'] == setor_selecionado) & (df_nuvem['data_registro'] == hoje_str) & (df_nuvem['origem'] == 'Chão de Fábrica')].copy()
    
    if df_hist.empty: 
        st.info("Nenhum apontamento nesta máquina hoje.")
    else:
        df_hist = df_hist.sort_values(by=['data_registro', 'as_hora'], ascending=[False, False]).head(50)
        
        try:
            resp_pend = supa.table("solicitacoes_correcao").select("id_producao").eq("status", "Pendente").execute()
            ids_pendentes = [r['id_producao'] for r in resp_pend.data] if resp_pend.data else []
        except:
            ids_pendentes = []

        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        
        for i, row in df_hist.iterrows():
            tipo_bd = str(row.get('tipo', '')).strip().upper()
            codigo_bd = str(row.get('cod_ocorrencia', '')).strip().upper()
            das_h = row['das']
            as_h = row['as_hora']
            id_reg = row.get('id', 'S/ID')
            
            if codigo_bd == 'P':
                cor_borda = "#27ae60"
                cor_fundo = "#f4fcf7"
                cod_peca = row.get('cod_peca', 'S/N')
                qtd_val = row.get('quantidade', 0)
                try:
                    if float(qtd_val).is_integer(): qtd_peca = str(int(float(qtd_val)))
                    else: qtd_peca = str(float(qtd_val))
                except:
                    qtd_peca = str(qtd_val)
                
                nome_peca_hist = str(row.get('nome_peca', 'Peça Desconhecida'))
                if " ➔ " in nome_peca_hist:
                    partes_nome = nome_peca_hist.split(" ➔ ")
                    produto_nome = partes_nome[0]
                    peca_nome = partes_nome[1]
                else:
                    produto_nome = "Produto"
                    peca_nome = nome_peca_hist
                    
                modalidade = str(row.get('modalidade_processo', 'Simples')).strip().upper()
                if modalidade == 'DUPLA':
                    tag_modalidade = "<span style='font-size: 11px; color: #fff; font-weight: 800; margin-left: 12px; background: #e67e22; padding: 3px 8px; border-radius: 4px; box-shadow: 0 1px 2px rgba(0,0,0,0.1); letter-spacing: 0.5px;'>[ MÓDULO DUPLO ]</span>"
                else:
                    tag_modalidade = ""
                
                titulo = produto_nome
            else:
                desc_oco = "Sem Descrição"
                if not df_codigos.empty:
                    f_cod = df_codigos[df_codigos['codigo'].astype(str).str.upper() == codigo_bd]
                    if not f_cod.empty: desc_oco = str(f_cod.iloc[0]['descricao']).strip()
                
                cor_mapa = mapa_cores.get(tipo_bd)
                if cor_mapa:
                    cor_borda = cor_mapa
                    cor_fundo = f"{cor_mapa}1A"
                    nome_exibicao = "Pausa" if (tipo_bd == "NÃO CONTA" or "DESCONSIDERAR" in tipo_bd) else tipo_bd.title()
                    titulo = f"{nome_exibicao}: {desc_oco} ({codigo_bd})"
                else:
                    if tipo_bd == "NÃO CONTA" or "DESCONSIDERAR" in tipo_bd:
                        cor_borda = "#f39c12"
                        cor_fundo = "#fdf8f3"
                        titulo = f"Pausa: {desc_oco} ({codigo_bd})"
                    else:
                        cor_borda = "#e74c3c"
                        cor_fundo = "#fdf4f3"
                        titulo = f"Parada: {desc_oco} ({codigo_bd})"
            
            html_card = f"<div style='border-left: 6px solid {cor_borda}; background-color: {cor_fundo}; padding: 12px 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #eee; margin-bottom: 5px;'>"
            html_card += "<div style='display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;'>"
            html_card += f"<div style='font-size: 16px; font-weight: 800; color: #2c3e50; line-height: 1.2;'>{titulo}</div>"
            html_card += f"<div style='font-size: 13px; font-weight: 700; color: #7f8c8d; background: #fff; padding: 2px 8px; border-radius: 4px; border: 1px solid #ddd; white-space: nowrap; margin-left: 10px;'>⏱️ {das_h} às {as_h}</div>"
            html_card += "</div>"
            
            tag_id_html = f"<div style='background: #ecf0f1; padding: 2px 6px; border-radius: 4px; color: #7f8c8d; font-size: 12px; font-family: monospace; font-weight: bold; border: 1px solid #bdc3c7;'>#ID: {id_reg}</div>"
            
            if codigo_bd == 'P':
                html_card += f"<div style='font-size: 15px; font-weight: 700; color: #34495e;'>{peca_nome} <span style='font-size: 12px; color: #7f8c8d; font-weight: normal;'>(Cód: {cod_peca})</span></div>"
                html_card += f"<div style='margin-top: 8px; display: flex; justify-content: space-between; align-items: flex-end;'>"
                html_card += f"<div style='font-size: 18px; font-weight: 900; color: #27ae60; display: flex; align-items: center;'>Qtde: {qtd_peca} {tag_modalidade}</div>"
                html_card += tag_id_html
                html_card += "</div>"
            else:
                html_card += f"<div style='margin-top: 8px; display: flex; justify-content: flex-end;'>{tag_id_html}</div>"
                
            html_card += "</div>"
            
            st.markdown(html_card, unsafe_allow_html=True)
            
            if codigo_bd == 'P' and id_reg != 'S/ID':
                col_vazia, col_btn = st.columns([5, 5])
                with col_btn:
                    if id_reg in ids_pendentes:
                        st.button("⏳ Correção Pendente", key=f"btn_pend_{id_reg}", disabled=True, use_container_width=True)
                    else:
                        if st.button("📝 Solicitar Correção", key=f"btn_corr_{id_reg}", use_container_width=True):
                            abrir_dialog_correcao(id_reg, qtd_peca, nomes_operadores, cod_peca, nome_peca_hist, is_embalagem)
            
            st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True)

    # ==========================================
    # 5. RODAPÉ DO TERMINAL
    # ==========================================
    st.markdown("<hr style='opacity: 0.2; margin-top: 15px;'>", unsafe_allow_html=True)
    texto_rodape = f"{setor_selecionado} &nbsp;|&nbsp; {maquina_selecionada} &nbsp;|&nbsp; {nomes_operadores}"
    st.markdown(f"<div style='text-align: center; color: #7f8c8d; font-size: 16px; margin-bottom: 25px; font-weight: 700; text-transform: uppercase;'>{texto_rodape}</div>", unsafe_allow_html=True)

    if not is_travado:
        st.info("💡 Modo de Gestão: Altere a máquina abaixo para visualizar seu status.")
        cr1, cr2 = st.columns(2)
        with cr1: st.selectbox("🏭 Setor", lista_setores_nuvem, key="cf_setor")
        with cr2: st.selectbox("⚙️ Máquina", lista_maquinas_nuvem, key="cf_maquina")

    cfg = banco.obter_configuracoes()
    titulo_app = cfg.get('titulo_programa', 'PCP Avelan')
    logo_b64 = cfg.get('logo_base64', None)
    
    c1, c2 = st.columns([7, 3])
    with c1:
        if logo_b64: st.markdown(f'<div style="display: flex; align-items: center; gap: 15px;"><img src="data:image/png;base64,{logo_b64}" style="max-height: 40px;"><h3 style="margin:0; color: #2c3e50;">{titulo_app}</h3></div>', unsafe_allow_html=True)
        else: st.markdown(f'<h3 style="margin:0; color: #2c3e50;">🏭 {titulo_app}</h3>', unsafe_allow_html=True)
    with c2:
        if is_travado:
            if st.button("🔄 Trocar de Máquina", use_container_width=True, key="btn_trocar_maq"):
                abrir_dialog_troca_maquina(status_db, df_est, usuario)
        
        if st.button("🚪 Sair do Sistema", use_container_width=True, key="btn_sair_cf"):
            st.session_state['usuario_logado'] = None
            try: st.query_params.clear()
            except: st.experimental_set_query_params()
            st.rerun()

    ui.injetar_js_botoes()