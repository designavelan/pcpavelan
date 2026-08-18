import streamlit as st
import pandas as pd
import banco

def renderizar_producao():
    st.subheader("📥 Enviar Produção Diária (Tempos)")
    
    supabase = banco.conectar()
    
    # 1. Busca a tabela de códigos para fazer o "PROCV" automático na prévia
    resp_cod = supabase.table("codigos_parada").select("codigo, tipo").execute()
    # Cria um dicionário no formato { '16': 'Parado', 'D1': 'Desconsiderar' }
    dict_codigos = {str(row['codigo']).strip().upper(): str(row['tipo']).strip() for row in resp_cod.data} if resp_cod.data else {}

    arquivo = st.file_uploader("Arraste a planilha de Tempos aqui", type=["xlsx", "xls"], key="up_prod")
    
    if arquivo is None:
        # ==========================================
        # CENÁRIO A: Nenhum arquivo anexado (Mostra o Banco de Dados)
        # ==========================================
        st.markdown("### 📊 Dados Atuais no Banco de Dados (Últimos 50 registros)")
        
        # Puxa os dados ordenados do mais recente para o mais antigo
        resp_atuais = supabase.table("producao_diaria").select("*").order("data_registro", desc=True).limit(50).execute()
        
        if resp_atuais.data:
            df_atuais = pd.DataFrame(resp_atuais.data)
            
            # Formata a visualização para ficar mais bonita e adiciona a coluna Tipo cruzada
            if 'cod_ocorrencia' in df_atuais.columns:
                df_atuais['cod_ocorrencia'] = df_atuais['cod_ocorrencia'].fillna('')
                
                # Aplica a automação do Tipo para visualizar como o banco interpreta hoje
                df_atuais['tipo_identificado'] = df_atuais['cod_ocorrencia'].apply(
                    lambda x: 'Trabalhando' if str(x).strip() == '' else dict_codigos.get(str(x).strip().upper(), 'Desconhecido')
                )
                
                # Reorganiza a ordem das colunas para facilitar a leitura
                colunas_mostrar = ['data_registro', 'setor', 'maquina', 'cod_ocorrencia', 'tipo_identificado', 'das', 'as_hora', 'quantidade']
                # Filtra apenas as colunas que realmente existem no DF para evitar erros
                colunas_mostrar = [c for c in colunas_mostrar if c in df_atuais.columns]
                df_atuais = df_atuais[colunas_mostrar]
            
            st.dataframe(df_atuais, use_container_width=True)
        else:
            st.info("O banco de dados de produção está vazio no momento.")
            
    else:
        # ==========================================
        # CENÁRIO B: Arquivo anexado (Mostra a prévia do Excel com o Tipo Automático)
        # ==========================================
        try:
            df = pd.read_excel(arquivo)
            df.columns = df.columns.str.strip() 
            
            # Limpeza e formatação de horas
            if 'Data' in df.columns: df['Data'] = pd.to_datetime(df['Data'], errors='coerce').dt.strftime('%Y-%m-%d')
            if 'Das' in df.columns: df['Das'] = df['Das'].apply(banco.formatar_hora_excel)
            if 'As' in df.columns: df['As'] = df['As'].apply(banco.formatar_hora_excel)
            
            # --- A MÁGICA DO TIPO AUTOMÁTICO NA PRÉVIA ---
            if 'Cod Ocorrencia' in df.columns:
                df['Cod Ocorrencia'] = df['Cod Ocorrencia'].astype(str).str.strip().replace({'nan': '', 'None': ''})
                
                def preencher_tipo_auto(cod):
                    if not cod: return 'Trabalhando'
                    return dict_codigos.get(cod.upper(), '⚠️ Código Não Cadastrado')
                
                # Cria a coluna apenas para visualização do usuário
                df['Tipo (Automático)'] = df['Cod Ocorrencia'].apply(preencher_tipo_auto)
                
                # Joga a coluna de Tipo logo pro lado do Cod Ocorrencia para facilitar a leitura
                cols = df.columns.tolist()
                cols.insert(cols.index('Cod Ocorrencia') + 1, cols.pop(cols.index('Tipo (Automático)')))
                df = df[cols]
            
            st.markdown("### 👀 Prévia do Arquivo a Importar")
            st.dataframe(df.head(15), use_container_width=True)
            
            if st.button("🚀 Confirmar e Injetar Dados", type="primary", key="btn_prod"):
                with st.spinner("Injetando dados na nuvem..."):
                    df_bd = pd.DataFrame()
                    if 'Data' in df.columns: df_bd['data_registro'] = df['Data']
                    df_bd['setor'] = banco.ler_texto_seguro(df, 'Setor')
                    df_bd['maquina'] = banco.ler_texto_seguro(df, 'Maquina')
                    df_bd['cod_ocorrencia'] = banco.ler_texto_seguro(df, 'Cod Ocorrencia')
                    df_bd['das'] = banco.ler_texto_seguro(df, 'Das')
                    df_bd['as_hora'] = banco.ler_texto_seguro(df, 'As')
                    df_bd['cod_peca'] = banco.ler_texto_seguro(df, 'Cod Peça')
                    df_bd['quantidade'] = banco.ler_numero_seguro(df, 'Quantidade')
                    
                    df_bd = df_bd.replace({'nan': None, 'None': None, '': None}).astype(object).where(pd.notnull(df_bd), None)
                    
                    supabase.table("producao_diaria").insert(df_bd.to_dict(orient='records')).execute()
                    st.success("🎉 BINGO! Dados inseridos com sucesso!")
        except Exception as e: 
            st.error(f"Erro durante a leitura do Excel: {e}")


def renderizar_codigos():
    st.subheader("📋 Atualizar Tabela de Códigos")
    
    supabase = banco.conectar()
    arquivo = st.file_uploader("Arraste a planilha de Códigos aqui", type=["xlsx", "xls"], key="up_cod")
    
    if arquivo is None:
        # ==========================================
        # CENÁRIO A: Mostrar Códigos Atuais do Banco
        # ==========================================
        st.markdown("### 📊 Códigos Cadastrados Atualmente")
        resp_atuais = supabase.table("codigos_parada").select("*").order("codigo").execute()
        
        if resp_atuais.data:
            # Organiza as colunas principais na frente
            df_atuais = pd.DataFrame(resp_atuais.data)
            colunas_mostrar = ['codigo', 'descricao', 'tipo', 'cronico', 'produto', 'qnt']
            colunas_mostrar = [c for c in colunas_mostrar if c in df_atuais.columns]
            df_atuais = df_atuais[colunas_mostrar]
            
            st.dataframe(df_atuais, use_container_width=True)
        else:
            st.info("Nenhum código cadastrado no banco de dados.")
            
    else:
        # ==========================================
        # CENÁRIO B: Prévia de novos códigos a importar
        # ==========================================
        try:
            df = pd.read_excel(arquivo)
            df.columns = df.columns.str.strip()
            
            st.markdown("### 👀 Prévia dos Novos Códigos a Importar")
            st.dataframe(df.head(10), use_container_width=True)
            
            if st.button("🚀 Atualizar Códigos na Nuvem", type="primary", key="btn_cod"):
                with st.spinner("Sincronizando tabela de códigos..."):
                    df_bd = pd.DataFrame()
                    df_bd['codigo'] = banco.ler_texto_seguro(df, 'Cod')
                    df_bd['descricao'] = banco.ler_texto_seguro(df, 'Descrição')
                    df_bd['tipo'] = banco.ler_texto_seguro(df, 'Tipo')
                    df_bd['cronico'] = banco.ler_texto_seguro(df, 'Cronico')
                    df_bd['produto'] = banco.ler_texto_seguro(df, 'Produto')
                    df_bd['qnt'] = banco.ler_numero_seguro(df, 'Qnt')
                    
                    df_bd = df_bd.replace({'nan': None, 'None': None, '': None}).astype(object).where(pd.notnull(df_bd), None)
                    
                    # O UPSERT garante que códigos existentes sejam atualizados e novos sejam inseridos
                    supabase.table("codigos_parada").upsert(df_bd.to_dict(orient='records')).execute()
                    st.success("🎯 Códigos atualizados com sucesso no banco!")
        except Exception as e: 
            st.error(f"Erro durante a leitura do Excel: {e}")