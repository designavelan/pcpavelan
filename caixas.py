import streamlit as st
import pandas as pd
import banco
import os
import json

def ler_caminho_matriz():
    if os.path.exists("matriz_config.json"):
        try:
            with open("matriz_config.json", "r") as f:
                return json.load(f).get("caminho", "")
        except: pass
    return ""

def processar_planilha_caixas(arquivo_ou_caminho):
    try:
        df_raw = pd.read_excel(arquivo_ou_caminho, sheet_name="Caixas", header=None)
    except Exception as e:
        return []

    header_row_idx = None
    for idx, row in df_raw.iterrows():
        linha_texto = [str(x).strip() for x in row.values]
        if "Quantidade de Caixas" in linha_texto and "Cod" in linha_texto:
            header_row_idx = idx
            break
            
    if header_row_idx is not None:
        df_raw.columns = df_raw.iloc[header_row_idx]
        df = df_raw.iloc[header_row_idx + 1:].reset_index(drop=True)
    else:
        df = df_raw.copy()
        
    df = df.loc[:, df.columns.notnull()]
    
    # --- NOVIDADE: Adicionada a busca pela coluna "Tipo" ---
    colunas_esperadas = ["Quantidade de Caixas", "Cod", "Comp.", "Larg.", "Alt.", "Tipo"]
    cols_presentes = [c for c in colunas_esperadas if c in df.columns]
    df = df[cols_presentes]
    
    mapa = {
        "Quantidade de Caixas": "produto_formula",
        "Cod": "cod_caixa",
        "Comp.": "comp",
        "Larg.": "larg",
        "Alt.": "alt",
        "Tipo": "tipo"
    }
    df = df.rename(columns=mapa)
    
    # ==========================================
    # 🪓 GUILHOTINA ANTI-FANTASMAS E OPCIONAIS
    # ==========================================
    df['produto_formula'] = df['produto_formula'].astype(str).str.strip()
    df = df[~df['produto_formula'].isin(["", "nan", "None", "NaN", "<NA>", "?"])]
    df = df[df['produto_formula'].str.len() >= 2]
    
    # ==========================================
    # 🔢 CÁLCULOS: NUMERAÇÃO (N) E CUBAGEM (m³)
    # ==========================================
    # 1. Numeração sequencial baseada na ordem do Excel (1/3, 2/3, etc)
    df['total'] = df.groupby('produto_formula')['produto_formula'].transform('count')
    df['indice'] = df.groupby('produto_formula').cumcount() + 1
    df['num_caixa'] = df['indice'].astype(str) + "/" + df['total'].astype(str)
    
    # 2. Cálculo do m³ com 4 casas decimais (Comp x Larg x Alt / 1 bilhão)
    df['c_num'] = pd.to_numeric(df['comp'], errors='coerce').fillna(0)
    df['l_num'] = pd.to_numeric(df['larg'], errors='coerce').fillna(0)
    df['a_num'] = pd.to_numeric(df['alt'], errors='coerce').fillna(0)
    
    df['m3'] = ((df['c_num'] * df['l_num'] * df['a_num']) / 1_000_000_000).round(4)
    
    # Limpeza final e exportação
    def limpar_texto(v):
        if pd.isna(v): return None
        t = str(v).strip()
        if t in ["", "nan", "None", "NaN", "<NA>", "?"]: return None
        if t.endswith(".0"): return t[:-2]
        return t
        
    registros_limpos = []
    for _, row in df.iterrows():
        linha = {
            'produto_formula': limpar_texto(row['produto_formula']),
            'cod_caixa': limpar_texto(row['cod_caixa']),
            'comp': limpar_texto(row['comp']),
            'larg': limpar_texto(row['larg']),
            'alt': limpar_texto(row['alt']),
            'num_caixa': row['num_caixa'],
            'm3': float(row['m3']),
            'tipo': limpar_texto(row.get('tipo'))
        }
        registros_limpos.append(linha)
        
    return registros_limpos

def sincronizar_caixas_bd(registros):
    supa = banco.conectar()
    # Apaga as caixas antigas para não gerar duplicidade nas atualizações
    resp = supa.table("caixas_matriz").select("id").execute()
    if resp.data:
        ids = [r['id'] for r in resp.data]
        for i in range(0, len(ids), 1000):
            supa.table("caixas_matriz").delete().in_("id", ids[i:i+1000]).execute()
            
    # Insere as novas em lotes
    for i in range(0, len(registros), 1000):
        supa.table("caixas_matriz").insert(registros[i:i+1000]).execute()

def renderizar():
    st.markdown("### 📦 Catálogo de Volumes (Caixas)")
    st.markdown("Consulte ou faça ajustes rápidos nas dimensões dos volumes. A planilha **Matriz** permanece como a fonte oficial.")
    st.markdown("<hr style='opacity: 0.2;'>", unsafe_allow_html=True)
    
    caminho_local = ler_caminho_matriz()
    is_local = os.path.exists(caminho_local) if caminho_local else False
    
    c1, c2 = st.columns([7, 3])
    
    with c2:
        st.markdown("#### 🔄 Sincronizar Caixas")
        if is_local:
            st.success(f"🖥️ **Acesso Local Detectado**\n\nLendo diretamente de:\n`{caminho_local}`")
            if st.button("🚀 Importar Aba 'Caixas'", type="primary", use_container_width=True):
                with st.spinner("Lendo a planilha e calculando numeração e m³..."):
                    try:
                        registros = processar_planilha_caixas(caminho_local)
                        if registros:
                            sincronizar_caixas_bd(registros)
                            st.success(f"✅ {len(registros)} caixas atualizadas com sucesso!")
                            st.rerun()
                        else:
                            st.error("A planilha foi lida, mas nenhuma caixa válida foi encontrada.")
                    except Exception as e:
                        st.error(f"Erro ao ler a planilha: {e}")
        else:
            st.info("🌐 **Acesso Remoto Detectado**\n\nFaça o upload manual da Matriz.")
            arquivo = st.file_uploader("Selecione a planilha Matriz (.xlsx)", type=["xlsx"])
            if arquivo and st.button("🚀 Sincronizar Arquivo", type="primary", use_container_width=True):
                with st.spinner("Lendo a planilha e calculando numeração e m³..."):
                    try:
                        registros = processar_planilha_caixas(arquivo)
                        if registros:
                            sincronizar_caixas_bd(registros)
                            st.success(f"✅ {len(registros)} caixas atualizadas com sucesso!")
                            st.rerun()
                        else:
                            st.error("A planilha foi lida, mas nenhuma caixa válida foi encontrada.")
                    except Exception as e:
                        st.error(f"Erro ao ler a planilha: {e}")
                        
    with c1:
        st.markdown("#### 🔍 Consulta e Ajustes Manuais")
        
        supa = banco.conectar()
        try:
            resp_caixas = supa.table("caixas_matriz").select("*").execute()
            df_caixas = pd.DataFrame(resp_caixas.data) if resp_caixas.data else pd.DataFrame()
        except Exception as e:
            df_caixas = pd.DataFrame()
            
        if df_caixas.empty:
            st.warning("Nenhuma caixa cadastrada ainda. Sincronize a matriz ao lado.")
        else:
            lista_prods_caixas = sorted(df_caixas['produto_formula'].dropna().unique().tolist())
            
            col_c1, col_c2 = st.columns(2)
            with col_c1: st.info(f"🛋️ **Total de Produtos:** {len(lista_prods_caixas)}")
            with col_c2: st.info(f"📦 **Total de Volumes Registrados:** {len(df_caixas)}")
            
            st.markdown("<br>", unsafe_allow_html=True)
            prod_sel_cx = st.selectbox("Filtre pelo Produto:", [""] + lista_prods_caixas)
            
            if prod_sel_cx:
                df_cx_filtro = df_caixas[df_caixas['produto_formula'] == prod_sel_cx].copy()
                
                if 'num_caixa' not in df_cx_filtro.columns: df_cx_filtro['num_caixa'] = ""
                if 'm3' not in df_cx_filtro.columns: df_cx_filtro['m3'] = 0.0
                if 'tipo' not in df_cx_filtro.columns: df_cx_filtro['tipo'] = None
                
                # Reordena para N ficar no começo, m³ e Tipo no final
                df_cx_filtro = df_cx_filtro[['id', 'num_caixa', 'cod_caixa', 'comp', 'larg', 'alt', 'm3', 'tipo']]
                
                st.markdown(f"<p style='color: #27ae60; font-weight: bold;'>Exibindo {len(df_cx_filtro)} volumes para: {prod_sel_cx}</p>", unsafe_allow_html=True)
                
                df_cx_edit = st.data_editor(
                    df_cx_filtro, 
                    use_container_width=True, 
                    disabled=["id", "num_caixa", "cod_caixa", "m3"], 
                    hide_index=True, 
                    column_config={
                        "id": None,
                        "num_caixa": "N",
                        "cod_caixa": "Cod.",
                        "comp": "Comp.",
                        "larg": "Larg.",
                        "alt": "Alt.",
                        "m3": st.column_config.NumberColumn("m³", format="%.4f"),
                        "tipo": "Tipo (Espelho/Vidro)"
                    }, 
                    key="editor_caixas_ind"
                )
                
                if st.button("💾 Salvar Ajuste Manual", type="primary"):
                    mudancas_cx = []
                    for idx, row in df_cx_edit.iterrows():
                        id_cx = row['id']
                        linha_orig = df_cx_filtro[df_cx_filtro['id'] == id_cx].iloc[0]
                        
                        if row['comp'] != linha_orig['comp'] or row['larg'] != linha_orig['larg'] or row['alt'] != linha_orig['alt'] or row['tipo'] != linha_orig['tipo']:
                            try:
                                c_n = float(row['comp']) if row['comp'] else 0
                                l_n = float(row['larg']) if row['larg'] else 0
                                a_n = float(row['alt']) if row['alt'] else 0
                                novo_m3 = round((c_n * l_n * a_n) / 1_000_000_000, 4)
                            except:
                                novo_m3 = 0.0
                                
                            mudancas_cx.append({
                                "id": id_cx,
                                "comp": str(row['comp']) if row['comp'] else None,
                                "larg": str(row['larg']) if row['larg'] else None,
                                "alt": str(row['alt']) if row['alt'] else None,
                                "m3": novo_m3,
                                "tipo": str(row['tipo']).strip() if row['tipo'] else None
                            })
                        
                    if mudancas_cx:
                        with st.spinner("Salvando ajustes e recalculando m³..."):
                            for m in mudancas_cx:
                                supa.table("caixas_matriz").update(m).eq("id", m['id']).execute()
                            st.success(f"✅ {len(mudancas_cx)} caixa(s) ajustada(s) no sistema!")
                            st.rerun()
                    else:
                        st.info("Você não alterou nenhuma medida ou tipo.")