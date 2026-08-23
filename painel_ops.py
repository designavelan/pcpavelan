import streamlit as st
import pandas as pd
import banco
from datetime import datetime, date
import time

# ==========================================
# FUNÇÕES DE TABELA E FORMATAÇÃO
# ==========================================
def formatar_valor(valor):
    return valor if valor > 0 else ""

def gerar_tabela_necessidades(df_produtos, df_apontamentos, produto, qtd_op):
    df_filtrado = df_produtos[df_produtos['produto_formula'] == produto].copy()
    linhas_tabela = []
    
    mapa_producao = {}
    if not df_apontamentos.empty:
        df_apontamentos['cod_peca'] = df_apontamentos['cod_peca'].astype(str).str.strip()
        df_apontamentos['setor'] = df_apontamentos['setor'].astype(str).str.strip().str.upper()
        df_apontamentos['quantidade'] = pd.to_numeric(df_apontamentos['quantidade'], errors='coerce').fillna(0)
        
        agrupado = df_apontamentos.groupby(['setor', 'cod_peca'])['quantidade'].sum().reset_index()
        for _, r in agrupado.iterrows():
            mapa_producao[(r['setor'], r['cod_peca'])] = int(r['quantidade'])
    
    for _, row in df_filtrado.iterrows():
        try: qnt_peca = int(float(row.get('qnt', 0)))
        except: qnt_peca = 0
            
        qtd_total = qnt_peca * qtd_op
        cod_peca_str = str(row.get('cod', '')).strip()
        
        def get_prod(setor_nome): return mapa_producao.get((setor_nome.upper(), cod_peca_str), 0)
        
        val_cor_nec = formatar_valor(qtd_total)
        val_cor_prod = formatar_valor(get_prod('Corte'))
        
        f_mais = str(row.get('fita_mais', '')).replace('.0', '').strip()
        f_menos = str(row.get('fita_menos', '')).replace('.0', '').strip()
        if f_mais in ['1', '2', '*'] or f_menos in ['1', '2', '*']:
            val_col_nec = formatar_valor(qtd_total)
            val_col_prod = formatar_valor(get_prod('Coladeira'))
        else:
            val_col_nec, val_col_prod = "", ""
            
        furadeira = str(row.get('furadeira', '')).strip().upper()
        if furadeira == 'SIM':
            val_fur_nec = formatar_valor(qtd_total)
            val_fur_prod = formatar_valor(get_prod('Furadeira'))
        else:
            val_fur_nec, val_fur_prod = "", ""
            
        lp = str(row.get('lp', '')).replace('.0', '').strip()
        if lp in ['1', '2']:
            val_pin_nec = formatar_valor(qtd_total)
            val_pin_prod = formatar_valor(get_prod('Pintura'))
        else:
            val_pin_nec, val_pin_prod = "", ""
            
        val_emb_nec = formatar_valor(qtd_total)
        val_emb_prod = formatar_valor(get_prod('Embalagem'))
        
        linhas_tabela.append({
            ("", "Código"): cod_peca_str,
            ("", "Peça"): str(row.get('descricao', '')),
            ("", "Qtd/Prod"): formatar_valor(qnt_peca),
            ("", "Total OP"): formatar_valor(qtd_total),
            ("CORTE", "Necess."): val_cor_nec,
            ("CORTE", "Prod."): val_cor_prod,
            ("COLADEIRA", "Necess."): val_col_nec,
            ("COLADEIRA", "Prod."): val_col_prod,
            ("FURADEIRA", "Necess."): val_fur_nec,
            ("FURADEIRA", "Prod."): val_fur_prod,
            ("PINTURA", "Necess."): val_pin_nec,
            ("PINTURA", "Prod."): val_pin_prod,
            ("EMBALAGEM", "Necess."): val_emb_nec,
            ("EMBALAGEM", "Prod."): val_emb_prod
        })
        
    df = pd.DataFrame(linhas_tabela)
    if not df.empty:
        df.columns = pd.MultiIndex.from_tuples(df.columns)
    return df

def estilizar_tabela(df):
    if df.empty: return df
    
    # Motor cravado célula por célula via HTML
    def aplicar_estilos(row):
        styles = []
        for col in row.index:
            # Tudo centralizado no meio por padrão
            estilo = "text-align: center; vertical-align: middle;"
            
            # Exceção forçada para a Peça (Esquerda)
            if col == ("", "Peça"):
                estilo = "text-align: left; vertical-align: middle;"
                
            # Dinâmica de Cores
            if col[1] == "Prod.":
                estilo += " color: #27ae60; font-weight: bold;"
            elif col[1] == "Necess.":
                setor = col[0]
                val_nec = row[col]
                val_prod = row.get((setor, "Prod."), "")
                
                try: nec_num = float(val_nec) if val_nec != "" else 0
                except: nec_num = 0
                    
                try: prod_num = float(val_prod) if val_prod != "" else 0
                except: prod_num = 0
                
                if nec_num > 0:
                    if prod_num >= nec_num:
                        estilo += " color: #27ae60; font-weight: bold;" # Atingiu meta (Verde)
                    else:
                        estilo += " color: #e74c3c; font-weight: bold;" # Abaixo da meta (Vermelho)
                        
            styles.append(estilo)
        return styles
        
    return df.style.apply(aplicar_estilos, axis=1)

# ==========================================
# COMPONENTES VISUAIS (DASHBOARD)
# ==========================================
def renderizar_card(titulo, valor, subtitulo, icone, cor):
    html = f"""
    <div style="background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #f0f0f0; border-top: 4px solid {cor}; text-align: center; height: 100%;">
        <div style="font-size: 13px; color: #7f8c8d; text-transform: uppercase; font-weight: bold; margin-bottom: 5px; letter-spacing: 0.5px;">{icone} {titulo}</div>
        <div style="font-size: 28px; font-weight: 900; color: #2c3e50; margin-bottom: 5px;">{valor}</div>
        <div style="font-size: 13px; color: #95a5a6; font-weight: 500;">{subtitulo}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def renderizar_barra_progresso(label, meta, prod, altura_fina=False):
    perc = (prod / meta * 100) if meta > 0 else 0
    perc_disp = min(100, perc)
    
    if perc_disp < 40: cor = "#e74c3c"
    elif perc_disp < 80: cor = "#f1c40f"
    else: cor = "#27ae60"
        
    altura_barra = "8px" if altura_fina else "14px"
    margem = "10px" if altura_fina else "18px"
        
    html = f"""
    <div style="margin-bottom: {margem};">
        <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span style="font-weight: bold; color: #2c3e50; font-size: 13px;">{label}</span>
            <span style="font-size: 12px; color: #7f8c8d;"><b>{perc:.1f}%</b> <span style="font-size:11px;">({prod}/{meta})</span></span>
        </div>
        <div style="background-color: #ecf0f1; border-radius: 6px; width: 100%; height: {altura_barra}; overflow: hidden; box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);">
            <div style="background-color: {cor}; width: {perc_disp}%; height: 100%; transition: width 0.5s ease;"></div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def renderizar_barra_inline(label, meta, prod):
    """Nova barra de progresso horizontal com tamanho flexível cravado e sem buracos em branco."""
    perc = (prod / meta * 100) if meta > 0 else 0
    perc_disp = min(100, perc)
    
    if perc_disp < 40: cor = "#e74c3c"
    elif perc_disp < 80: cor = "#f1c40f"
    else: cor = "#27ae60"
    
    html = f"""
    <div style="display: flex; align-items: center; margin-bottom: 18px;">
        <div style="flex: 0 0 320px; font-weight: bold; color: #2c3e50; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding-right: 15px;">📦 {label}</div>
        <div style="flex-grow: 1; background-color: #ecf0f1; border-radius: 8px; height: 22px; overflow: hidden; box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);">
            <div style="background-color: {cor}; width: {perc_disp}%; height: 100%; transition: width 0.5s ease;"></div>
        </div>
        <div style="flex: 0 0 140px; font-size: 13px; color: #7f8c8d; text-align: right; padding-left: 15px;"><b>{perc:.1f}%</b> <span style="font-size:11px;">({prod}/{meta})</span></div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# ==========================================
# RENDERIZAÇÃO PRINCIPAL
# ==========================================
def renderizar():
    container_cabecalho = st.container()
    container_cards = st.container()
    container_graficos = st.container()
    container_admin = st.container()
    container_tabelas = st.container()

    with container_cabecalho:
        st.markdown("### 🎯 Painel de OPs (Gestão e Acompanhamento)")
        st.markdown("Acompanhe os indicadores em tempo real. Gerencie prioridades e OPs na área administrativa (abaixo).")
        st.markdown("<br>", unsafe_allow_html=True)

    supa = banco.conectar()
    df_produtos = banco.obter_produtos_matriz()
    
    if df_produtos.empty:
        with container_cabecalho: st.warning("⚠️ Nenhum produto encontrado na matriz. Sincronize a planilha primeiro na tela de Configurações.")
        return
        
    lista_produtos = sorted(df_produtos['produto_formula'].dropna().unique().tolist())
    
    resp_ops = supa.table("planejamento_ops").select("*").eq("status", "Em Andamento").order('ordem_prioridade', desc=False).order('id', desc=True).execute()
    ops_ativas = resp_ops.data if resp_ops.data else []
    produtos_em_op = [op['produto_formula'] for op in ops_ativas]

    if not ops_ativas:
        with container_cabecalho: st.info("Nenhuma ordem de produção ativa no momento para gerar os gráficos.")
        
    # ==========================================
    # CÁLCULO GERAL E MOTOR DE DADOS
    # ==========================================
    lista_dados_ops = []
    df_todas_producoes = pd.DataFrame()
    
    if ops_ativas:
        datas_brutas = [op['data_inicio'] for op in ops_ativas]
        menor_data_str = min(datas_brutas).split(" ")[0].split("T")[0]
        
        resp_prod = supa.table("producao_diaria").select("setor, cod_peca, quantidade, data_registro").eq("tipo", "PRODUÇÃO").gte("data_registro", menor_data_str).execute()
        if resp_prod.data:
            df_todas_producoes = pd.DataFrame(resp_prod.data)
            df_todas_producoes['data_registro_dt'] = pd.to_datetime(df_todas_producoes['data_registro'])
            df_todas_producoes['cod_peca'] = df_todas_producoes['cod_peca'].astype(str).str.strip()
            df_todas_producoes['setor'] = df_todas_producoes['setor'].astype(str).str.strip().str.upper()
            df_todas_producoes['quantidade'] = pd.to_numeric(df_todas_producoes['quantidade'], errors='coerce').fillna(0)

        for idx_op, op in enumerate(ops_ativas):
            num_prioridade = idx_op + 1
            nome_op = op['produto_formula']
            qtd_plan = op['quantidade_planejada']
            
            data_bruta_limpa = op['data_inicio'].split(" ")[0].split("T")[0]
            data_op_dt = pd.to_datetime(data_bruta_limpa)
            try: data_formatada = datetime.strptime(data_bruta_limpa, "%Y-%m-%d").strftime("%d/%m/%Y")
            except: data_formatada = data_bruta_limpa
                
            df_filtrado = df_produtos[df_produtos['produto_formula'] == nome_op]
            
            mapa_prod = {}
            if not df_todas_producoes.empty:
                df_op_prod = df_todas_producoes[df_todas_producoes['data_registro_dt'] >= data_op_dt]
                agrup = df_op_prod.groupby(['setor', 'cod_peca'])['quantidade'].sum().reset_index()
                for _, r in agrup.iterrows(): mapa_prod[(r['setor'], r['cod_peca'])] = int(r['quantidade'])
            
            meta_setor = {'Corte': 0, 'Coladeira': 0, 'Furadeira': 0, 'Pintura': 0, 'Embalagem': 0}
            prod_setor = {'Corte': 0, 'Coladeira': 0, 'Furadeira': 0, 'Pintura': 0, 'Embalagem': 0}
            
            codigos_desta_op = []
            
            for _, row in df_filtrado.iterrows():
                try: qnt_peca = int(float(row.get('qnt', 0)))
                except: qnt_peca = 0
                qtd_total = qnt_peca * qtd_plan
                cod = str(row.get('cod', '')).strip()
                codigos_desta_op.append(cod)
                
                def get_p(s): return mapa_prod.get((s.upper(), cod), 0)
                
                meta_setor['Corte'] += qtd_total
                prod_setor['Corte'] += get_p('Corte')
                
                f_m = str(row.get('fita_mais', '')).replace('.0', '').strip()
                f_mn = str(row.get('fita_menos', '')).replace('.0', '').strip()
                if f_m in ['1', '2', '*'] or f_mn in ['1', '2', '*']:
                    meta_setor['Coladeira'] += qtd_total
                    prod_setor['Coladeira'] += get_p('Coladeira')
                    
                if str(row.get('furadeira', '')).strip().upper() == 'SIM':
                    meta_setor['Furadeira'] += qtd_total
                    prod_setor['Furadeira'] += get_p('Furadeira')
                    
                lp = str(row.get('lp', '')).replace('.0', '').strip()
                if lp in ['1', '2']:
                    meta_setor['Pintura'] += qtd_total
                    prod_setor['Pintura'] += get_p('Pintura')
                    
                meta_setor['Embalagem'] += qtd_total
                prod_setor['Embalagem'] += get_p('Embalagem')

            meta_global = sum(meta_setor.values())
            prod_global = sum(prod_setor.values())
            
            rotulo_com_prioridade = f"{num_prioridade} — {nome_op}"
            
            lista_dados_ops.append({
                'op_dict': op,
                'id': op['id'],
                'nome': nome_op,
                'label': rotulo_com_prioridade,
                'qtd_plan': qtd_plan,
                'inicio': data_formatada, 
                'inicio_dt_original': data_op_dt,
                'meta_global': meta_global,
                'prod_global': prod_global,
                'setores': meta_setor,
                'produzidos': prod_setor,
                'codigos': codigos_desta_op
            })

    # ==========================================
    # ÁREA ADMINISTRATIVA
    # ==========================================
    with container_admin:
        if ops_ativas:
            st.markdown("<hr style='opacity: 0.1; margin-top: 35px; margin-bottom: 25px;'>", unsafe_allow_html=True)
            st.markdown("<h4 style='color:#7f8c8d; font-size: 16px; margin-bottom: 15px;'>⚙️ Ferramentas Administrativas</h4>", unsafe_allow_html=True)
            
            ca1, ca2, ca3 = st.columns([1, 1, 1])
            
            with ca1:
                with st.expander("➕ NOVA ORDEM DE PRODUÇÃO", expanded=False):
                    with st.form("form_nova_op"):
                        produto_sel = st.selectbox("Produto:", [""] + lista_produtos)
                        qtd_op = st.number_input("Qtd (Unid.):", min_value=1, value=500, step=1)
                        data_inicio = st.date_input("Início:", value=date.today())
                        st.markdown("<br>", unsafe_allow_html=True)
                        btn_abrir = st.form_submit_button("🚀 Iniciar Produção", type="primary", use_container_width=True)
                        
                    if btn_abrir:
                        if not produto_sel: st.warning("⚠️ Selecione um produto.")
                        elif produto_sel in produtos_em_op: st.error("❌ Já existe uma OP 'Em Andamento' para este produto.")
                        else:
                            data_inicio_str = f"{data_inicio.strftime('%Y-%m-%d')} 00:00:00"
                            supa.table("planejamento_ops").insert({"produto_formula": produto_sel, "quantidade_planejada": qtd_op, "data_inicio": data_inicio_str, "status": "Em Andamento"}).execute()
                            st.success("✅ OP aberta com sucesso!")
                            time.sleep(1)
                            st.rerun()

            with ca2:
                with st.expander("↕️ ORGANIZAR PRIORIDADES", expanded=False):
                    st.markdown("<p style='font-size: 12px; color: #7f8c8d; margin-top:-10px;'>Arraste para definir a ordem.</p>", unsafe_allow_html=True)
                    nomes_ops_ativas = [op['produto_formula'] for op in ops_ativas]
                    nova_ordem_ops = st.multiselect("Ordem (Cascata):", options=nomes_ops_ativas, default=nomes_ops_ativas)
                    if st.button("💾 Salvar Fila", type="primary"):
                        if len(nova_ordem_ops) == len(nomes_ops_ativas):
                            with st.spinner("Atualizando..."):
                                for idx, nome_op in enumerate(nova_ordem_ops):
                                    supa.table("planejamento_ops").update({"ordem_prioridade": int(idx + 1)}).eq("produto_formula", nome_op).eq("status", "Em Andamento").execute()
                                st.success("✅ Fila organizada!")
                                time.sleep(1)
                                st.rerun()
                        else: st.warning("⚠️ Selecione todos os produtos.")
                        
            with ca3:
                opcoes_filtro = ["TODOS"] + sorted(produtos_em_op)
                filtro_sel = st.selectbox("🔍 Filtrar Painel por Produto:", opcoes_filtro)
                
    if ops_ativas:
        if filtro_sel != "TODOS": lista_filtrada = [d for d in lista_dados_ops if d['nome'] == filtro_sel]
        else: lista_filtrada = lista_dados_ops
        
        if not lista_filtrada:
            with container_cards: st.warning("Nenhuma informação encontrada para o filtro selecionado.")
            return

        # ==========================================
        # CONSTRUÇÃO DOS INDICADORES E CARDS
        # ==========================================
        vol_filtrado = sum([d['qtd_plan'] for d in lista_filtrada])
        meta_g_filtrada = sum([d['meta_global'] for d in lista_filtrada])
        prod_g_filtrada = sum([d['prod_global'] for d in lista_filtrada])
        perc_g_filtrada = (prod_g_filtrada / meta_g_filtrada * 100) if meta_g_filtrada > 0 else 0
        
        hoje_str = date.today().strftime('%Y-%m-%d')
        codigos_validos = set()
        for d in lista_filtrada: 
            for cod in d['codigos']: codigos_validos.add(cod)
            
        pecas_hoje = 0
        if not df_todas_producoes.empty:
            df_hoje = df_todas_producoes[df_todas_producoes['data_registro'].str.startswith(hoje_str)]
            df_hoje_filtrado = df_hoje[df_hoje['cod_peca'].isin(codigos_validos)]
            pecas_hoje = int(df_hoje_filtrado['quantidade'].sum())

        meta_setor_total = {'Corte': 0, 'Coladeira': 0, 'Furadeira': 0, 'Pintura': 0, 'Embalagem': 0}
        prod_setor_total = {'Corte': 0, 'Coladeira': 0, 'Furadeira': 0, 'Pintura': 0, 'Embalagem': 0}
        
        for d in lista_filtrada:
            for s in meta_setor_total.keys():
                meta_setor_total[s] += d['setores'][s]
                prod_setor_total[s] += d['produzidos'][s]
                
        gargalos = {s: max(0, meta_setor_total[s] - prod_setor_total[s]) for s in meta_setor_total.keys()}
        setor_critico = max(gargalos, key=gargalos.get) if sum(gargalos.values()) > 0 else "Nenhum"
        qtd_critica = gargalos.get(setor_critico, 0)

        with container_cards:
            cd1, cd2, cd3, cd4 = st.columns(4)
            with cd1: renderizar_card("Planejamento", f"{vol_filtrado}", f"{len(lista_filtrada)} OPs Ativas", "🛋️", "#9b59b6")
            with cd2: renderizar_card("Progresso Global", f"{min(100, perc_g_filtrada):.1f}%", f"{prod_g_filtrada}/{meta_g_filtrada} peças", "🎯", "#27ae60")
            with cd3: renderizar_card("Ritmo do Dia", f"{pecas_hoje}", "Peças movimentadas hoje", "🔥", "#e67e22")
            with cd4: renderizar_card("Fila Crítica", f"{setor_critico}", f"Faltam {qtd_critica} peças", "🚧", "#e74c3c")
            st.markdown("<br>", unsafe_allow_html=True)

        # ==========================================
        # DASHBOARDS GRÁFICOS OTIMIZADOS
        # ==========================================
        with container_graficos:
            st.markdown("<h4 style='color:#2c3e50; font-size: 18px; margin-bottom: 25px;'>🏁 A Corrida das OPs (Produtos)</h4>", unsafe_allow_html=True)
            for d in lista_filtrada:
                label_completo = f"{d['label']} — {d['qtd_plan']} unidades"
                renderizar_barra_inline(label_completo, d['meta_global'], d['prod_global'])

            st.markdown("<br>", unsafe_allow_html=True)

            st.markdown("<h4 style='color:#2c3e50; font-size: 18px; margin-bottom: 20px;'>🏭 Funil da Fábrica (Evolução por Setor)</h4>", unsafe_allow_html=True)
            cols_funil = st.columns(2)
            ordem_setores = ['Corte', 'Coladeira', 'Furadeira', 'Pintura', 'Embalagem']
            
            for i, d in enumerate(lista_filtrada):
                col_idx = i % 2
                with cols_funil[col_idx]:
                    st.markdown(f"""
                    <div style='background-color: #ffffff; border: 1px solid #e1e8ed; padding: 15px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.02);'>
                        <div style='font-size: 14px; font-weight: bold; color: #34495e; margin-bottom: 12px; border-bottom: 1px solid #eee; padding-bottom: 5px;'>📦 {d['label']}</div>
                    """, unsafe_allow_html=True)
                    
                    for setor in ordem_setores:
                        m = d['setores'][setor]
                        p = d['produzidos'][setor]
                        if m > 0: renderizar_barra_progresso(setor.upper(), m, p, altura_fina=True)
                    st.markdown("</div>", unsafe_allow_html=True)

        # ==========================================
        # TABELAS DETALHADAS (HTML CUSTOMIZADO)
        # ==========================================
        with container_tabelas:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("<h4 style='color:#2c3e50; font-size: 18px; margin-bottom: 15px;'>📋 Consultas Detalhadas por OP</h4>", unsafe_allow_html=True)
            
            for d in lista_filtrada:
                id_op = d['id']
                nome_prod = d['nome']
                qtd_plan = d['qtd_plan']
                data_op_dt = d['inicio_dt_original']
                
                with st.expander(f"📦 {d['label']} — {qtd_plan} unidades | Início: {d['inicio']}", expanded=False):
                    if not df_todas_producoes.empty: df_op_prod = df_todas_producoes[df_todas_producoes['data_registro_dt'] >= data_op_dt].copy()
                    else: df_op_prod = pd.DataFrame()
                    
                    df_op = gerar_tabela_necessidades(df_produtos, df_op_prod, nome_prod, qtd_plan)
                    df_estilizado = estilizar_tabela(df_op)
                    
                    if not df_op.empty:
                        # Extrai a tabela nativa em HTML forçando o desaparecimento da coluna de Index inútil
                        try: html_out = df_estilizado.hide(axis="index").to_html(escape=False)
                        except AttributeError: html_out = df_estilizado.hide_index().to_html(escape=False)
                        
                        # Injeção de CSS Mestre para forçar o alinhamento central e expansão total da tabela
                        html_tabela = f"""
                        <div style="width: 100%; overflow-x: auto; border: 1px solid #e1e8ed; border-radius: 8px; margin-bottom: 15px;">
                            <style>
                                .tabela-ops-html table {{ width: 100%; border-collapse: collapse; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; font-size: 13px; background-color: white; }}
                                .tabela-ops-html th, .tabela-ops-html td {{ padding: 8px 12px; border: 1px solid #f1f2f6; white-space: nowrap; }}
                                .tabela-ops-html thead th {{ background-color: #f8f9fa; color: #34495e; font-weight: 700; border-bottom: 1px solid #bdc3c7; }}
                                .tabela-ops-html tbody tr:hover {{ background-color: #fdfdfe; }}
                                /* FORÇA TUDO PARA O CENTRO */
                                .tabela-ops-html th {{ text-align: center !important; }}
                                /* ABRE UMA EXCEÇÃO APENAS PARA A COLUNA 'PEÇA' (Que é a coluna de índice 1) */
                                .tabela-ops-html th.col_heading.level0.col1, .tabela-ops-html th.col_heading.level1.col1 {{ text-align: left !important; }}
                            </style>
                            <div class="tabela-ops-html">
                                {html_out}
                            </div>
                        </div>
                        """
                        st.markdown(html_tabela, unsafe_allow_html=True)
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    col_vazia, col_btn = st.columns([7, 3])
                    with col_btn:
                        if st.button("✅ Concluir OP (Remover da Lista)", key=f"btn_concluir_{id_op}", use_container_width=True):
                            data_fim_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            supa.table("planejamento_ops").update({"status": "Concluída", "data_fim": data_fim_str}).eq("id", id_op).execute()
                            st.success(f"OP {nome_prod} concluída com sucesso!")
                            st.rerun()