import streamlit as st
import pandas as pd
import banco
import json
from datetime import datetime

def limpar_nans(lista):
    """Varredura de segurança: troca qualquer 'nan' vazio por 'None' (null)"""
    if not lista: return []
    return [{k: (None if pd.isna(v) else v) for k, v in reg.items()} for reg in lista]

def renderizar():
    st.markdown("### 💾 Backup e Restauração (JSON)")
    st.markdown("Gerencie a segurança dos seus dados. O formato JSON garante que as informações sejam salvas e restauradas exatamente como o banco de dados exige, sem perdas de formatação.")
    
    st.markdown("<hr style='margin-top: 5px; margin-bottom: 20px;'>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    # ==========================================
    # ÁREA DE DOWNLOAD (EXPORTAR BACKUP)
    # ==========================================
    with col1:
        st.markdown("#### ⬇️ Exportar Backup")
        st.markdown("Baixe todo o banco de dados atual.")
        
        if st.button("📦 Preparar Backup do Sistema", type="primary"):
            with st.spinner("Conectando ao banco e empacotando dados em JSON..."):
                try:
                    supa = banco.conectar()
                    
                    res_producao = supa.table("producao_diaria").select("*").execute()
                    res_codigos = supa.table("codigos_parada").select("*").execute()
                    res_config = supa.table("configuracoes").select("*").execute()
                    
                    backup_dados = {
                        "producao_diaria": limpar_nans(res_producao.data) if res_producao.data else [],
                        "codigos_parada": limpar_nans(res_codigos.data) if res_codigos.data else [],
                        "configuracoes": limpar_nans(res_config.data) if res_config.data else []
                    }
                    
                    json_string = json.dumps(backup_dados, indent=4, ensure_ascii=False)
                    
                    hoje = datetime.now().strftime("%d-%m-%Y_%H-%M")
                    nome_arquivo = f"Backup_PCP_{hoje}.json"
                    
                    st.success("✅ Backup preparado com sucesso!")
                    
                    st.download_button(
                        label="💾 Baixar Arquivo .JSON",
                        data=json_string,
                        file_name=nome_arquivo,
                        mime="application/json"
                    )
                    
                except Exception as e:
                    st.error(f"Erro ao gerar backup: {e}")

    # ==========================================
    # ÁREA DE UPLOAD (RESTAURAR BACKUP)
    # ==========================================
    with col2:
        st.markdown("#### ⬆️ Restaurar Backup")
        st.markdown("Faça upload de um backup anterior para restaurar o sistema.")
        
        arquivo_json = st.file_uploader("Selecione o arquivo de backup (.json)", type=["json"])
        
        if arquivo_json is not None:
            st.warning("⚠️ **ATENÇÃO:** Restaurar um backup irá APAGAR TODOS os dados atuais do sistema e substituí-los pelos dados deste arquivo. Essa ação não pode ser desfeita.")
            
            confirmacao = st.checkbox("Eu entendo os riscos e quero restaurar este backup.")
            
            if confirmacao and st.button("🚨 Iniciar Restauração", type="primary"):
                try:
                    with st.spinner("Lendo arquivo JSON..."):
                        dados_restauracao = json.load(arquivo_json)
                        
                    if "producao_diaria" not in dados_restauracao or "codigos_parada" not in dados_restauracao:
                        st.error("Erro: O arquivo JSON selecionado não é um backup válido deste sistema.")
                    else:
                        supa = banco.conectar()
                        
                        with st.spinner("Apagando banco de dados atual e injetando backup..."):
                            
                            if dados_restauracao.get("configuracoes"):
                                supa.table("configuracoes").delete().neq("id", 0).execute()
                                supa.table("configuracoes").insert(limpar_nans(dados_restauracao["configuracoes"])).execute()

                            # CORREÇÃO AQUI: Apagando usando a coluna 'codigo' que sabemos que existe
                            if dados_restauracao.get("codigos_parada"):
                                supa.table("codigos_parada").delete().neq("codigo", "LIXO").execute()
                                supa.table("codigos_parada").insert(limpar_nans(dados_restauracao["codigos_parada"])).execute()

                            # Restaura a Produção Diária
                            supa.table("producao_diaria").delete().neq("id", 0).execute()
                            registros_prod = limpar_nans(dados_restauracao.get("producao_diaria", []))
                            
                            tamanho_lote = 500
                            for i in range(0, len(registros_prod), tamanho_lote):
                                lote = registros_prod[i:i+tamanho_lote]
                                supa.table("producao_diaria").insert(lote).execute()
                                
                        st.success("🎉 Sistema restaurado com sucesso! Recarregue a página (F5) para ver os dados.")
                        
                except Exception as e:
                    st.error(f"Erro ao restaurar backup: {e}")