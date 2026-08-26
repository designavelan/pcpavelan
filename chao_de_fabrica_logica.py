import pandas as pd
from datetime import datetime, timedelta

def obter_hora_atual():
    """Retorna a hora atual ajustada para o fuso horário correto."""
    return datetime.utcnow() - timedelta(hours=3)

def registrar_telemetria(supa, setor, maquina, acao, df_est):
    """Calcula a porcentagem global idêntica à aba Ao Vivo e salva com rastreabilidade."""
    try:
        agora_str = obter_hora_atual().strftime("%Y-%m-%d %H:%M:%S")
        
        # 1. Puxa a "Verdade Absoluta" (Estrutura da Fábrica) passada por parâmetro
        if not df_est.empty:
            df_limpo = df_est[['setor', 'maquina']].dropna().drop_duplicates()
            maquinas_validas = set(df_limpo['setor'].astype(str).str.strip() + "||" + df_limpo['maquina'].astype(str).str.strip())
            total_maquinas = len(maquinas_validas)
        else:
            maquinas_validas = set()
            total_maquinas = 1
            
        # 2. Puxa o status exclusivamente das máquinas validadas na estrutura
        ativas = 0
        if maquinas_validas:
            resp = supa.table("status_maquinas").select("status, setor, maquina").eq("status", "Produzindo").execute()
            if resp.data:
                for m in resp.data:
                    chave_m = str(m.get("setor")).strip() + "||" + str(m.get("maquina")).strip()
                    if chave_m in maquinas_validas:
                        ativas += 1
        
        # 3. Calcula o percentual cravado
        if total_maquinas > 0:
            percentual = round((ativas / total_maquinas) * 100.0, 2)
        else:
            percentual = 0.0
            
        texto_acao = f"[{setor}] {maquina}: {acao}"
        
        # 4. Envia as informações com a rastreabilidade matemática para o banco
        dados_telemetria = {
            "data_hora": agora_str,
            "percentual": float(percentual),
            "acao": str(texto_acao),
            "maquinas_ativas": int(ativas),
            "maquinas_totais": int(total_maquinas)
        }
        
        supa.table("historico_operacao").insert([dados_telemetria]).execute()
        return True, ""
    except Exception as e:
        return False, str(e)

def salvar_producao(supa, setor_selecionado, maquina_selecionada, nomes_operadores, hora_inicio_str, cod_peca_atual, nome_peca, qtd_informada, modalidade_escolhida, codigo_parada_novo, df_codigos, df_est):
    """
    Função centralizada para registrar o lote produzido e atualizar o status da máquina,
    calculando também o sistema de Recordes Globais.
    """
    hora_fim = obter_hora_atual()
    hora_inicio_obj = datetime.strptime(hora_inicio_str, "%Y-%m-%d %H:%M:%S")
    duracao_segundos = (hora_fim - hora_inicio_obj).total_seconds()
    
    if duracao_segundos >= 60:
        tipo_producao = "PRODUÇÃO"
        if not df_codigos.empty:
            f_prod = df_codigos[df_codigos['codigo'].astype(str).str.upper() == 'P']
            if not f_prod.empty and 'tipo' in f_prod.columns:
                tipo_producao = str(f_prod.iloc[0]['tipo']).strip().upper()
                
        dados_nuvem = {
            "data_registro": hora_inicio_obj.strftime("%Y-%m-%d"),
            "setor": setor_selecionado, "maquina": maquina_selecionada, 
            "tipo": tipo_producao,  
            "cod_peca": cod_peca_atual, "nome_peca": nome_peca, "quantidade": qtd_informada,
            "operador": nomes_operadores, "cod_ocorrencia": "P",
            "das": hora_inicio_obj.strftime("%H:%M"), "as_hora": hora_fim.strftime("%H:%M"), 
            "origem": "Chão de Fábrica",
            "modalidade_processo": modalidade_escolhida 
        }
        supa.table("producao_diaria").insert(dados_nuvem).execute()
        
        try:
            qtd_valida = int(qtd_informada)
            if qtd_valida > 0 and duracao_segundos >= 60:
                duracao_min = float(duracao_segundos / 60.0)
                p_hora_atual = float((qtd_valida / duracao_min) * 60.0)
                
                c_peca_str = str(cod_peca_atual).strip()
                c_maq_str = str(maquina_selecionada).strip()
                
                resp_rec = supa.table("producao_recordes").select("*").eq("cod_peca", c_peca_str).eq("maquina", c_maq_str).eq("is_recorde_atual", "true").execute()
                
                bater_recorde = False
                if not resp_rec.data:
                    bater_recorde = True
                else:
                    recorde_banco = float(resp_rec.data[0].get("pecas_por_hora", 0))
                    if p_hora_atual > recorde_banco:
                        bater_recorde = True
                        id_antigo = int(resp_rec.data[0]["id"])
                        supa.table("producao_recordes").update({"is_recorde_atual": False}).eq("id", id_antigo).execute()
                
                if bater_recorde:
                    dados_recorde = {
                        "cod_peca": c_peca_str, "nome_peca": str(nome_peca).strip(),
                        "setor": str(setor_selecionado).strip(), "maquina": c_maq_str,
                        "operador": str(nomes_operadores).strip(), "quantidade_produzida": qtd_valida,
                        "tempo_gasto_minutos": round(duracao_min, 2), "pecas_por_hora": round(p_hora_atual, 2),
                        "data_recorde": hora_fim.strftime("%Y-%m-%d %H:%M:%S"),
                        "is_recorde_atual": True, "modalidade_processo": str(modalidade_escolhida).strip()
                    }
                    supa.table("producao_recordes").insert(dados_recorde).execute()
        except Exception as e:
            pass # Silencia o erro de recorde para não atrapalhar a produção
    
    # Após salvar, atualiza a máquina para Parada ou Livre
    if codigo_parada_novo:
        supa.table("status_maquinas").update({
            "status": "Parado", "hora_inicio": hora_fim.strftime("%Y-%m-%d %H:%M:%S"),
            "cod_ocorrencia": codigo_parada_novo, "cod_peca_atual": None
        }).eq("maquina", maquina_selecionada).eq("setor", setor_selecionado).execute()
        
        return registrar_telemetria(supa, setor_selecionado, maquina_selecionada, f"Fim Lote -> Parada ({codigo_parada_novo})", df_est)
    else:
        supa.table("status_maquinas").update({
            "status": "Livre", "hora_inicio": None, "cod_ocorrencia": None, "cod_peca_atual": None
        }).eq("maquina", maquina_selecionada).eq("setor", setor_selecionado).execute()
        
        return registrar_telemetria(supa, setor_selecionado, maquina_selecionada, "Fim Lote -> Livre", df_est)