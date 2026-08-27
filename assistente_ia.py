import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import banco
import google.generativeai as genai

# ==========================================
# 1. FUNÇÃO PARA EXTRAIR O CONTEXTO AO VIVO DA FÁBRICA
# ==========================================
def obter_contexto_fabrica():
    """Lê o banco de dados e cria um resumo em texto para a IA entender a fábrica."""
    supa = banco.conectar()
    agora = datetime.utcnow() - timedelta(hours=3)
    hoje_str = agora.strftime("%Y-%m-%d")
    
    contexto = f"DADOS ATUAIS DA FÁBRICA AVELAN MÓVEIS (Data/Hora atual: {agora.strftime('%d/%m/%Y %H:%M')}):\n\n"
    
    # 1. Status das Máquinas
    try:
        resp_maq = supa.table("status_maquinas").select("*").execute()
        if resp_maq.data:
            contexto += "[STATUS DAS MÁQUINAS NESTE EXATO MOMENTO]\n"
            for m in resp_maq.data:
                status = m.get('status', 'Desconhecido')
                contexto += f"- Setor: {m.get('setor', '')} | Máquina: {m.get('maquina', '')} | Status: {status}"
                if status == 'Produzindo':
                    contexto += f" | Peça/Caixa atual: {m.get('cod_peca_atual', 'N/A')}"
                elif status == 'Parado':
                    contexto += f" | Cód. Ocorrência: {m.get('cod_ocorrencia', 'N/A')}"
                contexto += "\n"
            contexto += "\n"
    except: pass

    # 2. OPs em Andamento
    try:
        resp_ops = supa.table("planejamento_ops").select("*").eq("status", "Em Andamento").order("ordem_prioridade").execute()
        if resp_ops.data:
            contexto += "[ORDENS DE PRODUÇÃO (OPs) ATIVAS NA FILA]\n"
            for op in resp_ops.data:
                contexto += f"- Prioridade {op.get('ordem_prioridade', 0)}: {op.get('produto_formula', '')} (Qtd: {op.get('quantidade_planejada', 0)})\n"
            contexto += "\n"
    except: pass

    # 3. Produção e Paradas de Hoje
    try:
        resp_prod = supa.table("producao_diaria").select("*").gte("data_registro", hoje_str).execute()
        if resp_prod.data:
            df_hoje = pd.DataFrame(resp_prod.data)
            df_hoje['quantidade'] = pd.to_numeric(df_hoje['quantidade'], errors='coerce').fillna(0)
            
            # Resumo de Peças Produzidas
            df_prod = df_hoje[df_hoje['tipo'].str.upper() == 'PRODUÇÃO']
            if not df_prod.empty:
                contexto += "[RESUMO DE PRODUÇÃO DE HOJE]\n"
                agrupado = df_prod.groupby('setor')['quantidade'].sum().reset_index()
                for _, row in agrupado.iterrows():
                    contexto += f"- Setor {row['setor']}: {int(row['quantidade'])} bips registrados.\n"
                contexto += "\n"
                
            # Resumo de Problemas/Paradas
            df_paradas = df_hoje[df_hoje['tipo'].str.upper() == 'PARADA']
            if not df_paradas.empty:
                contexto += "[PROBLEMAS REGISTRADOS HOJE]\n"
                agrup_paradas = df_paradas.groupby('cod_ocorrencia').size().reset_index(name='vezes')
                for _, row in agrup_paradas.iterrows():
                    contexto += f"- Código do problema {row['cod_ocorrencia']}: ocorreu {row['vezes']} vezes hoje.\n"
                contexto += "\n"
    except: pass

    return contexto

# ==========================================
# 2. RENDERIZAÇÃO DA INTERFACE DE CHAT
# ==========================================
def renderizar():
    st.markdown("### 🤖 Copiloto PCP (Gemini AI)")
    st.markdown("Faça perguntas sobre a produção, ritmo das máquinas, gargalos ou OPs. A inteligência artificial está conectada aos dados em tempo real da fábrica.")
    st.markdown("<hr style='opacity: 0.2;'>", unsafe_allow_html=True)

    if "GEMINI_API_KEY" not in st.secrets:
        st.error("⚠️ Chave de API do Gemini não encontrada! Configure o arquivo `.streamlit/secrets.toml`.")
        return

    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

    if "mensagens_ia" not in st.session_state:
        st.session_state.mensagens_ia = []

    for msg in st.session_state.mensagens_ia:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt_usuario = st.chat_input("Ex: Qual máquina está parada no momento?")

    if prompt_usuario:
        with st.chat_message("user"):
            st.markdown(prompt_usuario)
        st.session_state.mensagens_ia.append({"role": "user", "content": prompt_usuario})

        with st.spinner("Conectando aos servidores do Google e analisando a fábrica..."):
            try:
                contexto_atual = obter_contexto_fabrica()
                
                instrucao_sistema = f"""Você é o Assistente Virtual de Planejamento e Controle de Produção (PCP) da fábrica de móveis Avelan.
Sua missão é responder perguntas dos gestores de forma clara, direta e analítica.
Use APENAS os dados fornecidos abaixo para embasar suas respostas. Se a resposta não estiver nos dados, informe que não tem essa informação.
Destaque nomes de máquinas e setores em negrito.

1. FOCO NO PROBLEMA: NUNCA exiba os códigos numéricos de parada/ocorrência. Mostre apenas a descrição clara do motivo da parada.
2. COMUNICAÇÃO EXECUTIVA: Seja extremamente direto ao ponto. Evite introduções longas ou textos robóticos. Use tópicos (bullet points) para listar informações.
3. ORGANIZAÇÃO VISUAL: Sempre que o usuário pedir um resumo de muitas máquinas, um comparativo de produção ou listas de OPs, estruture a resposta usando Tabelas (Markdown) para facilitar a leitura.
4. LEITURA DINÂMICA: Destaque obrigatoriamente os nomes de **máquinas**, **setores**, **peças** e **quantidades** em negrito.
5. PROATIVIDADE DE GARGALO: Se o usuário pedir um resumo do dia e você notar que um setor ou máquina específica tem muitos registros de parada, adicione um pequeno alerta no final apontando o possível gargalo.
6. JORNADA DE TRABALHO: Tenha sempre em mente que a fábrica opera das 07:30 às 11:50 e das 13:30 às 17:30. Use essa informação para entender o momento do turno (ex: se está no início da manhã, perto do almoço, ou no final do expediente).

{contexto_atual}
"""
                # ==========================================
                # LÓGICA ATUALIZADA COM OS MODELOS RECENTES
                # ==========================================
                modelos_suportados = []
                for m in genai.list_models():
                    if 'generateContent' in m.supported_generation_methods:
                        modelos_suportados.append(m.name)
                        
                if not modelos_suportados:
                    st.error("⚠️ O Google ainda não liberou nenhum modelo de texto para o seu projeto. Aguarde alguns minutos ou crie uma nova chave.")
                    return
                    
                # Forçando a prioridade para o modelo novo que a própria API recomendou
                modelo_escolhido = modelos_suportados[0]
                preferencias = ['models/gemini-3.6-flash', 'models/gemini-3.6-pro']
                
                for pref in preferencias:
                    if pref in modelos_suportados:
                        modelo_escolhido = pref
                        break
                
                nome_limpo = modelo_escolhido.replace("models/", "")

                # ==========================================
                # EXECUÇÃO DA IA
                # ==========================================
                try:
                    modelo = genai.GenerativeModel(
                        model_name=nome_limpo,
                        system_instruction=instrucao_sistema
                    )
                    resposta_ia = modelo.generate_content(prompt_usuario)
                    
                except TypeError:
                    modelo = genai.GenerativeModel(model_name=nome_limpo)
                    prompt_completo = instrucao_sistema + "\n\nPergunta do gestor:\n" + prompt_usuario
                    resposta_ia = modelo.generate_content(prompt_completo)

                texto_resposta = resposta_ia.text

                with st.chat_message("assistant"):
                    st.markdown(texto_resposta)
                st.session_state.mensagens_ia.append({"role": "assistant", "content": texto_resposta})
                
            except Exception as e:
                st.error(f"Ocorreu um erro ao processar a inteligência artificial. Detalhes: {e}")