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

def processar_planilha(arquivo_ou_caminho):
    df_raw = pd.read_excel(arquivo_ou_caminho, sheet_name="Peças", header=None)
    
    header_row_idx = None
    for idx, row in df_raw.iterrows():
        linha_texto = [str(x).strip() for x in row.values]
        if "Produto Formula" in linha_texto and "Cod" in linha_texto:
            header_row_idx = idx
            break
            
    if header_row_idx is not None:
        df_raw.columns = df_raw.iloc[header_row_idx]
        df = df_raw.iloc[header_row_idx + 1:].reset_index(drop=True)
    else:
        df = df_raw.copy()
        
    df = df.loc[:, df.columns.notnull()]
    
    # --- ADICIONADO "Furadeira" AQUI ---
    colunas_esperadas = ["Produto Formula", "Cod", "Descrição", "Qnt", "Comp", "Larg", "Esp.", "LP", "Fita+", "Fita-", "Furadeira"]
    cols_presentes = [c for c in colunas_esperadas if c in df.columns]
    df = df[cols_presentes]
    
    # --- ADICIONADO MAPEAMENTO DA "Furadeira" AQUI ---
    mapa = {
        "Produto Formula": "produto_formula", "Cod": "cod", "Descrição": "descricao",
        "Qnt": "qnt", "Comp": "comp", "Larg": "larg", "Esp.": "esp",
        "LP": "lp", "Fita+": "fita_mais", "Fita-": "fita_menos", "Furadeira": "furadeira"
    }
    df = df.rename(columns=mapa)
    
    # --- REGRA DE OBRIGATORIEDADE ---
    # Apenas a Produto Formula é obrigatória. Descarta se estiver vazia.
    df['produto_formula'] = df['produto_formula'].astype(str).str.strip()
    df = df[~df['produto_formula'].isin(["", "nan", "None", "NaN", "<NA>"])]
    
    # Prepara os códigos (aceita vazios e permite DUPLICADOS normalmente)
    df['cod'] = df['cod'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    df['cod'] = df['cod'].replace(["", "nan", "None", "NaN", "<NA>"], None)
    
    registros_brutos = df.to_dict('records')
    
    registros_limpos = []
    for reg in registros_brutos:
        linha_limpa = {}
        for k, v in reg.items():
            if pd.isna(v):
                linha_limpa[k] = None
            else:
                texto = str(v).strip()
                if texto in ["", "nan", "None", "NaN", "<NA>"]:
                    linha_limpa[k] = None
                else:
                    if texto.endswith(".0"):
                        texto = texto[:-2]
                    linha_limpa[k] = texto
                    
        registros_limpos.append(linha_limpa)
        
    return registros_limpos

def renderizar():
    st.markdown("### 📦 Catálogo de Produtos e Peças")
    st.markdown("Consulte ou faça ajustes rápidos nas peças. A planilha **Matriz** permanece como a fonte oficial.")
    st.markdown("<hr style='opacity: 0.2;'>", unsafe_allow_html=True)
    
    caminho_local = ler_caminho_matriz()
    is_local = os.path.exists(caminho_local) if caminho_local else False
    
    c1, c2 = st.columns([7, 3])
    
    with c2:
        st.markdown("#### 🔄 Sincronizar Matriz")
        if is_local:
            st.success(f"🖥️ **Acesso Local Detectado**\n\nLendo diretamente de:\n`{caminho_local}`")
            if st.button("🚀 Iniciar Sincronização Automática", type="primary", use_container_width=True):
                with st.spinner("Lendo a planilha e atualizando banco de dados..."):
                    try:
                        registros = processar_planilha(caminho_local)
                        if registros:
                            banco.sincronizar_produtos(registros)
                            st.success(f"✅ {len(registros)} peças atualizadas com sucesso!")
                            st.rerun()
                        else:
                            st.error("A planilha foi lida, mas nenhuma peça válida foi encontrada.")
                    except Exception as e:
                        st.error(f"Erro ao ler a planilha: {e}")
        else:
            st.info("🌐 **Acesso Remoto Detectado**\n\nFaça o upload manual da Matriz.")
            arquivo = st.file_uploader("Selecione a planilha Matriz (.xlsx)", type=["xlsx"])
            if arquivo and st.button("🚀 Sincronizar Arquivo", type="primary", use_container_width=True):
                with st.spinner("Lendo a planilha e atualizando a nuvem..."):
                    try:
                        registros = processar_planilha(arquivo)
                        if registros:
                            banco.sincronizar_produtos(registros)
                            st.success(f"✅ {len(registros)} peças atualizadas com sucesso!")
                            st.rerun()
                        else:
                            st.error("A planilha foi lida, mas nenhuma peça válida foi encontrada.")
                    except Exception as e:
                        st.error(f"Erro ao ler a planilha: {e}")
                        
    with c1:
        st.markdown("#### 🔍 Consulta e Ajustes Manuais")
        df_produtos = banco.obter_produtos_matriz()
        
        if df_produtos.empty:
            st.warning("Nenhum produto cadastrado ainda. Realize a primeira sincronização ao lado.")
        else:
            lista_produtos = sorted(df_produtos['produto_formula'].dropna().unique().tolist())
            
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.info(f"🛋️ **Total de Produtos:** {len(lista_produtos)}")
            with col_m2:
                st.info(f"🧩 **Total de Peças:** {len(df_produtos)}")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            produto_selecionado = st.selectbox("Filtre pelo Produto:", [""] + lista_produtos)
            
            if produto_selecionado:
                df_filtrado = df_produtos[df_produtos['produto_formula'] == produto_selecionado].copy()
                
                # --- ADICIONADO 'furadeira' AQUI NA EXIBIÇÃO ---
                colunas_exibicao = ['id', 'cod', 'descricao', 'qnt', 'comp', 'larg', 'esp', 'lp', 'fita_mais', 'fita_menos', 'furadeira']
                df_filtrado = df_filtrado[colunas_exibicao]
                
                st.markdown(f"<p style='color: #2980b9; font-weight: bold;'>Exibindo {len(df_filtrado)} peças da fórmula: {produto_selecionado}</p>", unsafe_allow_html=True)
                
                df_editado = st.data_editor(
                    df_filtrado, 
                    use_container_width=True,
                    disabled=["cod", "id"], 
                    hide_index=True,
                    column_config={"id": None}, 
                    key="editor_pecas"
                )
                
                if st.button("💾 Salvar Ajuste Manual", type="primary"):
                    mudancas = []
                    for idx, row in df_editado.iterrows():
                        id_peca = row['id']
                        linha_original = df_filtrado[df_filtrado['id'] == id_peca].iloc[0]
                        if not row.equals(linha_original):
                            mudancas.append(row.to_dict())
                    
                    if mudancas:
                        with st.spinner("Salvando ajustes no banco..."):
                            for m in mudancas:
                                dados_salvar = {k: (None if pd.isna(v) else v) for k, v in m.items()}
                                banco.atualizar_peca_individual(dados_salvar['id'], dados_salvar)
                            st.success(f"✅ {len(mudancas)} peça(s) ajustada(s) no sistema!")
                            st.rerun()
                    else:
                        st.info("Você não alterou nenhuma medida.")