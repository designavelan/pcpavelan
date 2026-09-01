import streamlit as st
import pandas as pd
from datetime import datetime
import banco

# ==========================================
# FUNÇÕES DE VALIDAÇÃO (CHOQUE DE HORÁRIO)
# ==========================================
def _converter_para_minutos(hora_str):
    try:
        h, m = map(int, str(hora_str).strip().split(':'))
        return h * 60 + m
    except:
        return -1

def _verificar_choque_horarios(df_dados):
    for _, row in df_dados.iterrows():
        min_i = _converter_para_minutos(row['das'])
        min_f = _converter_para_minutos(row['as_hora'])
        if min_i == -1 or min_f == -1:
            return False, f"Formato de hora inválido no ID {row['id']}. Use o formato HH:MM."
        if min_f <= min_i:
            return False, f"A hora final deve ser maior que a hora inicial no ID {row['id']}."

    df_verificacao = df_dados.copy()
    df_verificacao['das_min'] = df_verificacao['das'].apply(_converter_para_minutos)
    df_verificacao = df_verificacao.sort_values('das_min')

    fim_anterior = -1
    id_anterior = None
    for _, row in df_verificacao.iterrows():
        inicio_atual = row['das_min']
        if inicio_atual < fim_anterior:
            return False, f"🚨 Choque de horário detectado entre o ID {id_anterior} e ID {row['id']}."
        fim_anterior = _converter_para_minutos(row['as_hora'])
        id_anterior = row['id']

    return True, "Horários validados com sucesso!"

@st.dialog("➕ Inserir Novo Apontamento")
def dialog_inserir_auditoria(data_selecionada, setor_selecionado, maquina_selecionada, df_produtos, df_codigos, df_caixas):
    st.markdown(f"**Data:** {data_selecionada.strftime('%d/%m/%Y')} | **Local:** {setor_selecionado} / {maquina_selecionada}")
    
    tipo_reg = st.radio("Tipo de Apontamento:", ["PRODUÇÃO", "PARADA / PAUSA"], horizontal=True)
    is_embalagem = str(setor_selecionado).strip().upper() == "EMBALAGEM"
    
    cod_ocorrencia = "P"
    cod_peca = None
    nome_peca = None
    
    if tipo_reg == "PRODUÇÃO":
        lista_prods = sorted(df_produtos['produto_formula'].dropna().unique().tolist()) if not df_produtos.empty else []
        prod_sel = st.selectbox("1. Produto:", lista_prods)
        
        if is_embalagem:
            df_cx_filtro = df_caixas[df_caixas['produto_formula'] == prod_sel] if not df_caixas.empty else pd.DataFrame()
            lista_pecas = [f"Caixa {r['num_caixa']} (Cód: {r['cod_caixa']})" for _, r in df_cx_filtro.iterrows()] if not df_cx_filtro.empty else []
        else:
            df_pecas_filtro = df_produtos[df_produtos['produto_formula'] == prod_sel] if not df_produtos.empty else pd.DataFrame()
            lista_pecas = [f"{r['descricao']} (Cód: {r['cod']})" for _, r in df_pecas_filtro.iterrows()] if not df_pecas_filtro.empty else []
            
        peca_sel = st.selectbox("2. Peça / Volume:", lista_pecas)
        if peca_sel:
            cod_peca = peca_sel.split("(Cód: ")[-1].replace(")", "").strip()
            nome_peca = f"{prod_sel} ➔ {peca_sel.split(' (Cód:')[0]}"
            
    else:
        df_codigos_parada = df_codigos[(df_codigos['tipo'].astype(str).str.upper() != 'PRODUÇÃO') & (df_codigos['codigo'].astype(str).str.upper() != 'P')] if not df_codigos.empty else pd.DataFrame()
        lista_paradas = [f"{r['descricao']} ({r['codigo']})" for _, r in df_codigos_parada.iterrows()]
        parada_sel = st.selectbox("Motivo da Parada/Pausa:", lista_paradas)
        if parada_sel:
            cod_ocorrencia = parada_sel.split("(")[-1].replace(")", "").strip()
            nome_peca = None
            
    c1, c2 = st.columns(2)
    with c1: das_str = st.text_input("Hora Inicial (HH:MM):", placeholder="Ex: 08:00")
    with c2: as_str = st.text_input("Hora Final (HH:MM):", placeholder="Ex: 08:30")
    
    cq1, cq2 = st.columns(2)
    with cq1: 
        qtd_val = st.number_input("Quantidade:", min_value=0, step=1) if tipo_reg == "PRODUÇÃO" else 0
    with cq2:
        mod_val = st.selectbox("Modalidade:", ["Simples", "Dupla"]) if tipo_reg == "PRODUÇÃO" else "Simples"
        
    if st.button("💾 Inserir Registro no Banco", type="primary", use_container_width=True):
        if _converter_para_minutos(das_str) == -1 or _converter_para_minutos(as_str) == -1:
            st.error("Formato de hora inválido! Use HH:MM")
            return
            
        supa = banco.conectar()
        
        tipo_bd = "PRODUÇÃO"
        if tipo_reg != "PRODUÇÃO":
            tipo_bd = "PARADA"
            f_cod = df_codigos[df_codigos['codigo'].astype(str) == cod_ocorrencia]
            if not f_cod.empty and 'tipo' in f_cod.columns:
                tipo_bd = str(f_cod.iloc[0]['tipo']).strip().upper()
                
        dados_nuvem = {
            "data_registro": data_selecionada.strftime("%Y-%m-%d"),
            "setor": setor_selecionado, "maquina": maquina_selecionada, 
            "tipo": tipo_bd, "cod_ocorrencia": cod_ocorrencia,
            "cod_peca": cod_peca, "nome_peca": nome_peca, "quantidade": qtd_val,
            "das": das_str.strip(), "as_hora": as_str.strip(), 
            "origem": "Auditoria Admin", "modalidade_processo": mod_val,
            "operador": "Ajuste Admin"
        }
        
        supa.table("producao_diaria").insert(dados_nuvem).execute()
        st.cache_data.clear()
        st.rerun()

@st.dialog("✏️ Corrigir Peça / Parada")
def dialog_corrigir_auditoria(row_dict, df_produtos, df_codigos, df_caixas, is_embalagem):
    id_reg = row_dict['id']
    st.markdown(f"**Alterando ID:** {id_reg}")
    
    tipo_atual = "PRODUÇÃO" if row_dict['cod_ocorrencia'] == 'P' else "PARADA / PAUSA"
    tipo_reg = st.radio("Mudar o tipo de Apontamento para:", ["PRODUÇÃO", "PARADA / PAUSA"], index=0 if tipo_atual == "PRODUÇÃO" else 1, horizontal=True)
    
    cod_ocorrencia = "P"
    cod_peca = None
    nome_peca = None
    
    if tipo_reg == "PRODUÇÃO":
        lista_prods = sorted(df_produtos['produto_formula'].dropna().unique().tolist()) if not df_produtos.empty else []
        
        prod_atual = row_dict['nome_peca'].split(" ➔ ")[0] if row_dict['nome_peca'] and " ➔ " in str(row_dict['nome_peca']) else ""
        idx_prod = lista_prods.index(prod_atual) if prod_atual in lista_prods else 0
        prod_sel = st.selectbox("Novo Produto:", lista_prods, index=idx_prod)
        
        if is_embalagem:
            df_cx_filtro = df_caixas[df_caixas['produto_formula'] == prod_sel] if not df_caixas.empty else pd.DataFrame()
            lista_pecas = [f"Caixa {r['num_caixa']} (Cód: {r['cod_caixa']})" for _, r in df_cx_filtro.iterrows()] if not df_cx_filtro.empty else []
        else:
            df_pecas_filtro = df_produtos[df_produtos['produto_formula'] == prod_sel] if not df_produtos.empty else pd.DataFrame()
            lista_pecas = [f"{r['descricao']} (Cód: {r['cod']})" for _, r in df_pecas_filtro.iterrows()] if not df_pecas_filtro.empty else []
            
        idx_peca = 0
        for i, p in enumerate(lista_pecas):
            if str(row_dict['cod_peca']) in p:
                idx_peca = i; break
                
        peca_sel = st.selectbox("Nova Peça / Volume:", lista_pecas, index=idx_peca if lista_pecas else 0)
        if peca_sel:
            cod_peca = peca_sel.split("(Cód: ")[-1].replace(")", "").strip()
            nome_peca = f"{prod_sel} ➔ {peca_sel.split(' (Cód:')[0]}"
            
    else:
        df_codigos_parada = df_codigos[(df_codigos['tipo'].astype(str).str.upper() != 'PRODUÇÃO') & (df_codigos['codigo'].astype(str).str.upper() != 'P')] if not df_codigos.empty else pd.DataFrame()
        lista_paradas = [f"{r['descricao']} ({r['codigo']})" for _, r in df_codigos_parada.iterrows()]
        
        idx_parada = 0
        for i, p in enumerate(lista_paradas):
            if str(row_dict['cod_ocorrencia']) in p:
                idx_parada = i; break
                
        parada_sel = st.selectbox("Novo Motivo:", lista_paradas, index=idx_parada if lista_paradas else 0)
        if parada_sel:
            cod_ocorrencia = parada_sel.split("(")[-1].replace(")", "").strip()
            nome_peca = None
            
    if st.button("💾 Atualizar Classificação", type="primary", use_container_width=True):
        supa = banco.conectar()
        
        tipo_bd = "PRODUÇÃO"
        if tipo_reg != "PRODUÇÃO":
            tipo_bd = "PARADA"
            f_cod = df_codigos[df_codigos['codigo'].astype(str) == cod_ocorrencia]
            if not f_cod.empty and 'tipo' in f_cod.columns:
                tipo_bd = str(f_cod.iloc[0]['tipo']).strip().upper()
                
        supa.table("producao_diaria").update({
            "tipo": tipo_bd, "cod_ocorrencia": cod_ocorrencia,
            "cod_peca": cod_peca, "nome_peca": nome_peca,
            "origem": "Auditoria Admin"
        }).eq("id", id_reg).execute()
        
        st.cache_data.clear()
        st.rerun()

def renderizar_auditoria():
    st.markdown("### 🔎 Auditoria de Apontamentos")
    st.markdown("Ferramenta administrativa para conferência, correção e validação da linha do tempo operacional.")
    st.markdown("<hr style='opacity: 0.2;'>", unsafe_allow_html=True)
    
    # 1. Filtros Unificados
    c_f1, c_f2 = st.columns([1, 2])
    
    with c_f1: 
        data_sel = st.date_input("📅 Data do Apontamento", datetime.today())
    
    df_est = banco.obter_estrutura_completa()
    if not df_est.empty:
        df_est['status_txt'] = df_est['ativo'].apply(lambda x: "" if x is True or str(x).lower() == 'true' else " (DESATIVADA)")
        df_est['nome_exibicao'] = df_est['setor'] + " ➔ " + df_est['maquina'] + df_est['status_txt']
        df_est = df_est.sort_values(by=['setor', 'maquina'])
        opcoes = df_est['nome_exibicao'].tolist()
    else:
        opcoes = []
        
    with c_f2: 
        selecao_maq = st.selectbox("🏭 Setor ➔ Máquina", opcoes) if opcoes else None
    
    if not selecao_maq:
        st.info("Selecione os filtros acima para carregar o histórico.")
        return

    # Extrai o setor e máquina exatos da seleção
    linha_sel = df_est[df_est['nome_exibicao'] == selecao_maq].iloc[0]
    setor_sel = linha_sel['setor']
    maq_sel = linha_sel['maquina']

    # 2. Buscar Dados
    supa = banco.conectar()
    resp = supa.table("producao_diaria").select("*").eq("data_registro", str(data_sel)).eq("setor", setor_sel).eq("maquina", maq_sel).execute()
    df_dados = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()

    df_produtos = banco.obter_produtos_matriz()
    df_codigos = banco.obter_codigos()
    try: df_caixas = pd.DataFrame(supa.table("caixas_matriz").select("*").execute().data)
    except: df_caixas = pd.DataFrame()
    is_embalagem = str(setor_sel).strip().upper() == "EMBALAGEM"

    if df_dados.empty:
        st.warning("⚠️ Nenhum registro encontrado para esta data e máquina.")
        if st.button("➕ Inserir Primeiro Apontamento do Dia", type="primary"):
            dialog_inserir_auditoria(data_sel, setor_sel, maq_sel, df_produtos, df_codigos, df_caixas)
        return

    # 3. Preparar a Tabela
    df_dados['das_min'] = df_dados['das'].apply(_converter_para_minutos)
    df_dados = df_dados.sort_values('das_min').drop(columns=['das_min'])
    df_dados.insert(0, "Selecionar", False)
    
    cfg_colunas = {
        "Selecionar": st.column_config.CheckboxColumn("Sel.", default=False, width="small"),
        "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
        "tipo": st.column_config.TextColumn("Tipo", disabled=True, width="small"),
        "cod_ocorrencia": st.column_config.TextColumn("Cód.", disabled=True, width="small"),
        "das": st.column_config.TextColumn("Início", width="small", help="Formato HH:MM"),
        "as_hora": st.column_config.TextColumn("Fim", width="small", help="Formato HH:MM"),
        "cod_peca": st.column_config.TextColumn("Cód. Peça", disabled=True),
        "nome_peca": st.column_config.TextColumn("Nome do Registro", disabled=True),
        "quantidade": st.column_config.NumberColumn("Qtd.", min_value=0, width="small"),
        "modalidade_processo": st.column_config.SelectboxColumn("Modal.", options=["Simples", "Dupla"], width="small")
    }

    # Remove colunas indesejadas da view visual
    colunas_ocultas = ['created_at', 'data_registro', 'setor', 'maquina', 'operador', 'origem']
    df_view = df_dados.drop(columns=[c for c in colunas_ocultas if c in df_dados.columns])

    st.markdown("<br><div style='font-size:14px; font-weight:bold; color:#7f8c8d;'>*Dê dois cliques nas colunas Início, Fim, Qtd ou Modalidade para editar diretamente na tabela.*</div>", unsafe_allow_html=True)
    
    # CÁLCULO DE ALTURA DINÂMICA PARA REMOVER A ROLAGEM VERTICAL
    altura_tabela = max(100, int((len(df_view) * 35.5) + 40))
    
    # Renderiza a Planilha
    df_editado = st.data_editor(df_view, column_config=cfg_colunas, hide_index=True, use_container_width=True, height=altura_tabela)
    
    # 4. Painel de Ferramentas
    st.markdown("<hr style='opacity: 0.2;'>", unsafe_allow_html=True)
    c_b1, c_b2, c_b3, c_b4 = st.columns(4)
    
    linhas_selecionadas = df_editado[df_editado["Selecionar"] == True]
    
    with c_b1:
        if st.button("💾 Salvar Horários/Qtds", type="primary", use_container_width=True, help="Salva edições feitas direto na tabela"):
            valido, msg = _verificar_choque_horarios(df_editado)
            if not valido:
                st.error(msg)
            else:
                for _, row in df_editado.iterrows():
                    id_row = row['id']
                    linha_original = df_dados[df_dados['id'] == id_row].iloc[0]
                    
                    if (row['das'] != linha_original['das'] or 
                        row['as_hora'] != linha_original['as_hora'] or 
                        row['quantidade'] != linha_original['quantidade'] or 
                        row['modalidade_processo'] != linha_original['modalidade_processo']):
                        
                        try: qtd_nova = int(float(row['quantidade'])) if pd.notna(row['quantidade']) else 0
                        except: qtd_nova = 0
                            
                        supa.table("producao_diaria").update({
                            "das": row['das'].strip(),
                            "as_hora": row['as_hora'].strip(),
                            "quantidade": qtd_nova,
                            "modalidade_processo": row.get('modalidade_processo', 'Simples'),
                            "origem": "Auditoria Admin"
                        }).eq("id", id_row).execute()
                        
                st.success("✅ Tabela salva com sucesso!")
                st.cache_data.clear()
                st.rerun()

    with c_b2:
        if st.button("➕ Inserir Novo", use_container_width=True):
            dialog_inserir_auditoria(data_sel, setor_sel, maq_sel, df_produtos, df_codigos, df_caixas)

    with c_b3:
        if st.button("✏️ Corrigir Peça", use_container_width=True):
            if len(linhas_selecionadas) == 1:
                dialog_corrigir_auditoria(linhas_selecionadas.iloc[0].to_dict(), df_produtos, df_codigos, df_caixas, is_embalagem)
            else:
                st.warning("⚠️ Selecione exatamente UM item na tabela para corrigir.")

    with c_b4:
        if st.button("🗑️ Excluir", use_container_width=True):
            if len(linhas_selecionadas) > 0:
                ids_excluir = linhas_selecionadas['id'].tolist()
                for id_del in ids_excluir:
                    supa.table("producao_diaria").delete().eq("id", id_del).execute()
                st.success(f"🗑️ {len(ids_excluir)} registro(s) excluído(s).")
                st.cache_data.clear()
                st.rerun()
            else:
                st.warning("⚠️ Selecione ao menos um item na tabela para excluir.")