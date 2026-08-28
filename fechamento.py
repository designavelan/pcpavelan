import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import banco
import json

def calcular_minutos_str(hora_str):
    try: 
        return int(hora_str.split(':')[0]) * 60 + int(hora_str.split(':')[1])
    except: 
        return 0

def rodar_fechamento(data_alvo_str):
    """Calcula os dados de produção e paradas de um dia e salva na tabela fechamento_diario"""
    supa = banco.conectar()
    
    # 1. Buscar Produção do dia
    resp_prod = supa.table("producao_diaria").select("*").eq("data_registro", data_alvo_str).execute()
    df_dia = pd.DataFrame(resp_prod.data) if resp_prod.data else pd.DataFrame()
    
    if df_dia.empty:
        return f"Não há registros para o dia {data_alvo_str}."

    # 2. Buscar tabela de Códigos para descobrir o que é Rotina e o que é Problema
    resp_cod = supa.table("codigos_parada").select("*").execute()
    df_codigos = pd.DataFrame(resp_cod.data) if resp_cod.data else pd.DataFrame()

    # --- VARIÁVEIS DO FECHAMENTO ---
    total_pecas = 0
    prod_setor = {}
    
    min_problema = 0
    min_rotina = 0
    
    dict_problemas = {}
    dict_rotinas = {}
    dict_maquinas_paradas = {} # Focado apenas em problemas reais

    # --- PROCESSANDO OS DADOS ---
    for _, row in df_dia.iterrows():
        tipo_registro = str(row.get('tipo', '')).strip().upper()
        
        # CÁLCULO DE PRODUÇÃO
        if tipo_registro == 'PRODUÇÃO':
            qtd = pd.to_numeric(row.get('quantidade', 0), errors='coerce')
            if pd.isna(qtd): qtd = 0
            qtd = int(qtd)
            setor = str(row.get('setor', 'Outros')).strip()
            
            total_pecas += qtd
            prod_setor[setor] = prod_setor.get(setor, 0) + qtd
            
        # CÁLCULO DE PARADAS (Cruzando com codigos_parada)
        elif tipo_registro == 'PARADA':
            cod = str(row.get('cod_ocorrencia', '')).strip()
            min_ini = calcular_minutos_str(row.get('das', '00:00'))
            min_fim = calcular_minutos_str(row.get('as_hora', '00:00'))
            duracao = max(0, min_fim - min_ini)
            maquina = str(row.get('maquina', '')).strip()
            
            desc_motivo = "Motivo Desconhecido"
            tipo_motivo = "PARADA" # Default
            
            # Descobrindo o tipo real do problema
            if not df_codigos.empty:
                f_cod = df_codigos[df_codigos['codigo'].astype(str) == cod]
                if not f_cod.empty:
                    desc_motivo = str(f_cod.iloc[0]['descricao'])
                    tipo_motivo = str(f_cod.iloc[0]['tipo']).strip().upper()
            
            # Distribuindo o tempo
            if tipo_motivo == 'ROTINA':
                min_rotina += duracao
                dict_rotinas[desc_motivo] = dict_rotinas.get(desc_motivo, 0) + duracao
            
            elif tipo_motivo == 'PARADA': # Problemas Reais
                min_problema += duracao
                dict_problemas[desc_motivo] = dict_problemas.get(desc_motivo, 0) + duracao
                dict_maquinas_paradas[maquina] = dict_maquinas_paradas.get(maquina, 0) + duracao

    # --- ACHANDO OS VILÕES (OFENSORES) ---
    ofensor_problema = max(dict_problemas, key=dict_problemas.get) if dict_problemas else "Nenhum"
    ofensor_rotina = max(dict_rotinas, key=dict_rotinas.get) if dict_rotinas else "Nenhum"
    maquina_pior = max(dict_maquinas_paradas, key=dict_maquinas_paradas.get) if dict_maquinas_paradas else "Nenhuma"
    min_total = min_problema + min_rotina

    # --- CRIANDO O TEXTO PARA A IA ---
    setores_texto = ", ".join([f"{s} ({q} pçs)" for s, q in prod_setor.items()])
    
    resumo_ia = f"No dia {data_alvo_str}, a fábrica produziu {total_pecas} peças. Divisão por setor: {setores_texto}. "
    resumo_ia += f"O tempo não produtivo total foi de {min_total} minutos. "
    resumo_ia += f"Desse total, {min_rotina} minutos foram gastos com ROTINAS, sendo o maior consumidor de tempo: '{ofensor_rotina}'. "
    resumo_ia += f"Os problemas reais (PARADA) consumiram {min_problema} minutos, e o principal ofensor foi: '{ofensor_problema}'. "
    resumo_ia += f"A máquina que perdeu mais tempo com problemas foi a {maquina_pior}."

    # --- SALVANDO NO BANCO DE DADOS ---
    dados_insercao = {
        "data_fechamento": data_alvo_str,
        "total_pecas_produzidas": total_pecas,
        "producao_por_setor": json.dumps(prod_setor, ensure_ascii=False),
        "min_perdidos_problema": min_problema,
        "min_perdidos_rotina": min_rotina,
        "min_perdidos_total": min_total,
        "principal_ofensor_problema": ofensor_problema,
        "principal_ofensor_rotina": ofensor_rotina,
        "maquina_mais_parada": maquina_pior,
        "resumo_para_ia": resumo_ia
    }

    try:
        # Tenta inserir; no mundo real, você faria um upsert (atualizar se já existir)
        supa.table("fechamento_diario").insert(dados_insercao).execute()
        return f"✅ Sucesso! O fechamento do dia {data_alvo_str} foi salvo. Resumo gerado para IA:\n{resumo_ia}"
    except Exception as e:
        return f"❌ Erro ao salvar no banco: {e}"

# ==== INTERFACE PARA TESTE NO STREAMLIT ====
def renderizar():
    st.title("🧪 Testador de Fechamento (Para a IA)")
    st.write("Isso calcula os dados de um dia passado e salva o resumo para a IA ler depois.")
    
    data_ontem = (datetime.utcnow() - timedelta(hours=3) - timedelta(days=1)).strftime("%Y-%m-%d")
    data_alvo = st.text_input("Qual data quer calcular/fechar? (AAAA-MM-DD)", value=data_ontem)
    
    if st.button("Executar Fechamento", type="primary"):
        with st.spinner("Calculando o dia inteiro..."):
            resultado = rodar_fechamento(data_alvo)
            st.success(resultado)