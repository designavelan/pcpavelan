import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import banco
import google.generativeai as genai
import fechamento  # Importando o motor que calcula os dias

# ==========================================
# 1. FUNÇÃO PARA EXTRAIR O CONTEXTO AO VIVO E HISTÓRICO DA FÁBRICA
# ==========================================
def calcular_minutos_str(hora_str):
    try: return int(hora_str.split(':')[0]) * 60 + int(hora_str.split(':')[1])
    except: return 0

def obter_contexto_fabrica():
    """Lê o banco de dados e cria um resumo ao vivo + memória do passado para a IA."""
    supa = banco.conectar()
    agora = datetime.utcnow() - timedelta(hours=3)
    hoje_str = agora.strftime("%Y-%m-%d")
    
    contexto = f"DADOS DA FÁBRICA AVELAN MÓVEIS (Data/Hora atual: {agora.strftime('%d/%m/%Y %H:%M')}):\n\n"
    
    df_codigos = pd.DataFrame()
    try:
        resp_cod = supa.table("codigos_parada").select("*").execute()
        if resp_cod.data: df_codigos = pd.DataFrame(resp_cod.data)
    except: pass
    
    def obter_desc_codigo(cod):
        if df_codigos.empty or not cod: return "Desconhecido"
        f_cod = df_codigos[df_codigos['codigo'].astype(str) == str(cod)]
        if not f_cod.empty: return str(f_cod.iloc[0]['descricao'])
        return "Desconhecido"

    # 1. Status das Máquinas (AGORA)
    try:
        resp_maq = supa.table("status_maquinas").select("*").execute()
        if resp_maq.data:
            contexto += "[STATUS DAS MÁQUINAS NESTE EXATO MOMENTO]\n"
            for m in resp_maq.data:
                status = m.get('status', 'Desconhecido')
                contexto += f"- Setor: {m.get('setor', '')} | Máquina: {m.get('maquina', '')} | Status: {status}"
                if status == 'Produzindo': contexto += f" | Peça atual: {m.get('cod_peca_atual', 'N/A')}"
                elif status == 'Parado': contexto += f" | Parada por: {obter_desc_codigo(m.get('cod_ocorrencia', ''))}"
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

    # 3. Produção e Paradas de Hoje (AO VIVO)
    try:
        resp_prod = supa.table("producao_diaria").select("*").gte("data_registro", hoje_str).execute()
        if resp_prod.data:
            df_hoje = pd.DataFrame(resp_prod.data)
            
            df_prod = df_hoje[df_hoje['tipo'].astype(str).str.strip().str.upper() == 'PRODUÇÃO'].copy()
            if not df_prod.empty:
                df_prod['quantidade'] = pd.to_numeric(df_prod['quantidade'], errors='coerce').fillna(0)
                contexto += "[RESUMO DE PRODUÇÃO DE HOJE (ATÉ O MOMENTO)]\n"
                agrup = df_prod.groupby('setor')['quantidade'].sum().reset_index()
                for _, r in agrup.iterrows(): contexto += f"- Setor {r['setor']}: {int(r['quantidade'])} pçs.\n"
                contexto += "\n"
                
            df_paradas = df_hoje[df_hoje['tipo'].astype(str).str.strip().str.upper() == 'PARADA'].copy()
            if not df_paradas.empty:
                contexto += "[HISTÓRICO DE PARADAS E ROTINAS DE HOJE]\n"
                tempos_motivo = {}
                for _, r in df_paradas.iterrows():
                    desc = obter_desc_codigo(str(r.get('cod_ocorrencia', '')).strip())
                    min_ini = calcular_minutos_str(r.get('das', '00:00'))
                    min_fim = calcular_minutos_str(r.get('as_hora', '00:00'))
                    duracao = max(0, min_fim - min_ini)
                    tempos_motivo[desc] = tempos_motivo.get(desc, 0) + duracao
                
                for mot, mins in sorted(tempos_motivo.items(), key=lambda x: x[1], reverse=True):
                    contexto += f"- {mot}: {mins} minutos consumidos.\n"
                contexto += "\n"
    except: pass

    # --- NOVIDADE: 4. A MEMÓRIA DA IA (Histórico dos últimos dias) ---
    contexto += "[MEMÓRIA HISTÓRICA DE PRODUÇÃO (DIAS ANTERIORES)]\n"
    try:
        data_limite = (agora - timedelta(days=30)).strftime("%Y-%m-%d")
        resp_hist = supa.table("fechamento_diario").select("data_fechamento, resumo_para_ia").gte("data_fechamento", data_limite).order("data_fechamento", desc=True).execute()
        
        if resp_hist.data and len(resp_hist.data) > 0:
            for reg in resp_hist.data:
                contexto += f"- {reg.get('resumo_para_ia')}\n"
        else:
            contexto += "Nenhum histórico passado foi processado no banco de dados ainda.\n"
    except Exception as e: 
        contexto += f"(Erro ao puxar histórico: {e})\n"

    return contexto

# ==========================================
# 2. RENDERIZAÇÃO DA INTERFACE DE CHAT
# ==========================================
def renderizar():
    st.markdown("### 🤖 Pergunte para a IA")
    st.markdown("Faça perguntas sobre a produção atual, histórico de paradas de ontem, ritmo das máquinas, gargalos ou OPs.")
    
    # --- NOVO PAINEL DE ALIMENTAÇÃO DA MEMÓRIA ---
    with st.expander("⚙️ Gerenciar Memória da IA (Fechamentos Históricos)"):
        st.write("A IA lê os resumos diários para responder sobre dias anteriores. Use as opções abaixo para gerar o histórico.")
        
        col1, col2 = st.columns(2)
        with col1:
            data_alvo = st.date_input("Processar um dia específico:", value=datetime.utcnow() - timedelta(hours=3) - timedelta(days=1))
            if st.button("Executar Fechamento Único", type="secondary"):
                with st.spinner("Calculando o dia..."):
                    # Remove o registro anterior se existir para não dar erro
                    try: banco.conectar().table("fechamento_diario").delete().eq("data_fechamento", data_alvo.strftime("%Y-%m-%d")).execute()
                    except: pass
                    res = fechamento.rodar_fechamento(data_alvo.strftime("%Y-%m-%d"))
                    st.success(res)
                    
        with col2:
            st.write("Processamento em Lote:")
            if st.button("Gerar Histórico dos Últimos 30 Dias", type="primary"):
                with st.status("Viagem no tempo iniciada! Calculando dados antigos...", expanded=True) as status:
                    agora = datetime.utcnow() - timedelta(hours=3)
                    dias_processados = 0
                    for i in range(1, 31):
                        d_str = (agora - timedelta(days=i)).strftime("%Y-%m-%d")
                        st.write(f"⏳ Processando dia {d_str}...")
                        try:
                            # Limpa o dia caso já exista
                            banco.conectar().table("fechamento_diario").delete().eq("data_fechamento", d_str).execute()
                            fechamento.rodar_fechamento(d_str)
                            dias_processados += 1
                        except: pass
                    status.update(label=f"✅ Memória atualizada! {dias_processados} dias processados.", state="complete", expanded=False)

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

    prompt_usuario = st.chat_input("Ex: Como foi a produção de ontem? Qual foi a pior rotina?")

    if prompt_usuario:
        with st.chat_message("user"):
            st.markdown(prompt_usuario)
        st.session_state.mensagens_ia.append({"role": "user", "content": prompt_usuario})

        with st.spinner("Analisando dados da fábrica..."):
            try:
                contexto_atual = obter_contexto_fabrica()
                
                instrucao_sistema = f"""Você é o Assistente Virtual de PCP da fábrica Avelan.
Responda de forma clara e focada em resultados.
REGRAS:
1. Use APENAS os dados fornecidos no contexto.
2. Evite exibir códigos numéricos, exiba as descrições (nomes dos problemas/peças).
3. Seja direto. Use tabelas (Markdown) para comparar dias ou setores.
4. Destaque máquinas, setores e quantidades em negrito.
5. MEMÓRIA HISTÓRICA: Quando o usuário perguntar sobre a produção de ontem, semana passada, ou comparar dias, você DEVE basear sua resposta nos textos encontrados na seção [MEMÓRIA HISTÓRICA DE PRODUÇÃO]. 
Os dados da "Memória Histórica" são resumos exatos e auditados da fábrica, trate-os como fatos absolutos.

CONTEXTO DE DADOS DA FÁBRICA:
{contexto_atual}
"""
                modelos_suportados = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                modelo_escolhido = "models/gemini-3.6-flash" if "models/gemini-3.6-flash" in modelos_suportados else modelos_suportados[0]
                nome_limpo = modelo_escolhido.replace("models/", "")

                try:
                    modelo = genai.GenerativeModel(model_name=nome_limpo, system_instruction=instrucao_sistema)
                    resposta_ia = modelo.generate_content(prompt_usuario)
                except TypeError:
                    modelo = genai.GenerativeModel(model_name=nome_limpo)
                    prompt_completo = instrucao_sistema + "\n\nPergunta:\n" + prompt_usuario
                    resposta_ia = modelo.generate_content(prompt_completo)

                texto_resposta = resposta_ia.text
                with st.chat_message("assistant"):
                    st.markdown(texto_resposta)
                st.session_state.mensagens_ia.append({"role": "assistant", "content": texto_resposta})
                
            except Exception as e:
                st.error(f"Erro na IA: {e}")