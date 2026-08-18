import streamlit as st
import pandas as pd
import banco
import datetime

def limpar_hora(valor):
    """Padroniza a hora e resolve o truque do Excel de digitar '1438' para '14:38'"""
    if pd.isna(valor) or str(valor).strip().lower() in ['nan', 'none', '']:
        return ''
        
    # Se o Pandas leu como um objeto de tempo nativo
    if isinstance(valor, (datetime.time, datetime.datetime)):
        return valor.strftime('%H:%M')
        
    s = str(valor).strip()
    
    # Resolve o truque do Excel: se for só número (ex: "1438" ou "930.0")
    s_numerico = s.replace('.0', '')
    if s_numerico.isdigit():
        s_numerico = s_numerico.zfill(4) # Garante que "930" vire "0930"
        return f"{s_numerico[:2]}:{s_numerico[2:4]}"
        
    # Corta os segundos se vier no padrão "14:30:00"
    if len(s) >= 5 and s[2] == ':':
        return s[:5]
        
    return s

def blindar_dados(valor):
    """Garante que nenhum tipo estranho do Excel chegue ao banco de dados"""
    if pd.isna(valor):
        return None
    if isinstance(valor, (datetime.time, datetime.date, datetime.datetime, pd.Timestamp)):
        return str(valor)
    return valor

def renderizar_producao():
    st.markdown("#### 📦 Importar Planilha de Produção")
    
    st.markdown("Escolha como o sistema deve tratar os dados desta planilha:")
    estrategia = st.radio(
        "",
        [
            "🟢 **Complementar:** Analisa as linhas, ignora repetidas e insere apenas os apontamentos novos. *(Recomendado pro dia a dia)*", 
            "🔴 **Substituir Tudo:** Apaga TODO o banco de dados atual e importa essa planilha do zero. *(Use para correções no histórico)*"
        ],
        label_visibility="collapsed"
    )
    st.markdown("<hr style='margin-top: 5px; margin-bottom: 20px;'>", unsafe_allow_html=True)
    
    arquivo = st.file_uploader("Selecione a planilha de Produção (Excel)", type=["xlsx", "xls"])
    
    if arquivo and st.button("🚀 Iniciar Importação", type="primary"):
        try:
            with st.spinner("Lendo a planilha selecionada..."):
                df_novo = pd.read_excel(arquivo)
            
            df_novo.columns = [str(c).strip().lower() for c in df_novo.columns]
            
            mapa_colunas = {
                'data': 'data_registro', 'data_registro': 'data_registro',
                'setor': 'setor',
                'máquina': 'maquina', 'maquina': 'maquina',
                'tipo': 'tipo',
                'das': 'das',
                'às': 'as_hora', 'as': 'as_hora', 'as_hora': 'as_hora',
                'cod': 'cod_ocorrencia', 'código': 'cod_ocorrencia', 'cod_ocorrencia': 'cod_ocorrencia',
                'cod ocorrencia': 'cod_ocorrencia' 
            }
            df_novo = df_novo.rename(columns=mapa_colunas)
            
            # --- FILTRO CORTA-CAMINHO (Remove colunas excedentes como "Cod Peça" e "Quantidade") ---
            colunas_permitidas = ['data_registro', 'setor', 'maquina', 'cod_ocorrencia', 'das', 'as_hora', 'tipo']
            colunas_finais = [c for c in df_novo.columns if c in colunas_permitidas]
            df_novo = df_novo[colunas_finais]
            # -------------------------------------------------------------------------------------

            colunas_necessarias = ['data_registro', 'maquina', 'das', 'as_hora']
            for col in colunas_necessarias:
                if col not in df_novo.columns:
                    st.error(f"Erro: A planilha precisa ter a coluna '{col}' (ou um nome similar mapeado) para funcionar.")
                    return

            df_novo['data_registro'] = pd.to_datetime(df_novo['data_registro'], errors='coerce').dt.strftime('%Y-%m-%d')
            df_novo['maquina'] = df_novo['maquina'].astype(str).str.strip()
            df_novo['das'] = df_novo['das'].apply(limpar_hora)
            df_novo['as_hora'] = df_novo['as_hora'].apply(limpar_hora)
            
            df_novo = df_novo.dropna(subset=['data_registro'])
            
            supa = banco.conectar()
            
            if "Substituir Tudo" in estrategia:
                with st.spinner("⚠️ Apagando dados antigos do banco (Substituição)..."):
                    supa.table("producao_diaria").delete().neq("id", 0).execute()
                
                df_inserir = df_novo
                st.info("Banco de dados limpo para receber a nova planilha completa.")
                
            else: 
                with st.spinner("🔍 Comparando planilha com os dados que já estão no banco..."):
                    df_banco = banco.obter_dados_nuvem()
                    
                    if not df_banco.empty:
                        df_banco['data_registro'] = pd.to_datetime(df_banco['data_registro']).dt.strftime('%Y-%m-%d')
                        df_banco['maquina'] = df_banco['maquina'].astype(str).str.strip()
                        df_banco['das'] = df_banco['das'].apply(limpar_hora)
                        df_banco['as_hora'] = df_banco['as_hora'].apply(limpar_hora)
                        
                        df_merged = df_novo.merge(
                            df_banco[['data_registro', 'maquina', 'das', 'as_hora']], 
                            on=['data_registro', 'maquina', 'das', 'as_hora'], 
                            how='left', 
                            indicator=True
                        )
                        df_inserir = df_merged[df_merged['_merge'] == 'left_only'].drop(columns=['_merge'])
                    else:
                        df_inserir = df_novo
            
            if df_inserir.empty:
                st.success("✅ O banco já está 100% atualizado! Nenhuma linha nova precisou ser importada.")
                return
            
            registros = df_inserir.to_dict(orient='records')
            registros_limpos = [{k: blindar_dados(v) for k, v in reg.items()} for reg in registros]
            
            with st.spinner(f"🚀 Enviando {len(registros_limpos)} novos registros para a nuvem..."):
                tamanho_lote = 500
                for i in range(0, len(registros_limpos), tamanho_lote):
                    lote = registros_limpos[i:i+tamanho_lote]
                    supa.table("producao_diaria").insert(lote).execute()
                    
            st.success(f"🎉 Importação concluída com sucesso! Foram adicionados **{len(registros_limpos)}** novos apontamentos ao sistema.")
            
        except Exception as e:
            st.error(f"Erro ao processar importação: {e}")

def renderizar_codigos():
    st.markdown("#### 📋 Importar Planilha de Códigos")
    arquivo = st.file_uploader("Selecione a planilha de Códigos (Excel)", type=["xlsx", "xls"])
    
    if arquivo and st.button("🚀 Atualizar Códigos", type="primary"):
        try:
            with st.spinner("Lendo planilha..."):
                df_novo = pd.read_excel(arquivo)
            
            df_novo.columns = [str(c).strip().lower() for c in df_novo.columns]
            
            mapa = {
                'cod': 'codigo', 'código': 'codigo', 
                'descrição': 'descricao', 'descricao': 'descricao',
                'tipo': 'tipo',
                'cronico': 'cronico', 'crônico': 'cronico'
            }
            df_novo = df_novo.rename(columns=mapa)
            
            supa = banco.conectar()
            with st.spinner("Apagando códigos antigos e subindo os novos..."):
                supa.table("codigos_parada").delete().neq("codigo", "LIXO").execute()
                
                registros = df_novo.to_dict(orient='records')
                registros_limpos = [{k: blindar_dados(v) for k, v in reg.items()} for reg in registros]
                
                supa.table("codigos_parada").insert(registros_limpos).execute()
                
            st.success(f"✅ Tabela de códigos atualizada com {len(registros_limpos)} registros!")
            
        except Exception as e:
            st.error(f"Erro ao atualizar códigos: {e}")