import streamlit as st
import pandas as pd
from datetime import datetime
import banco
import configuracoes

def calcular_minutos_str(hora_str):
    try: return int(hora_str.split(':')[0]) * 60 + int(hora_str.split(':')[1])
    except: return 0

def salvar_parametro_db(coluna, valor):
    """Atualiza a configuração diretamente na linha id=1 da tabela configuracoes"""
    try:
        supa = banco.conectar()
        supa.table('configuracoes').update({coluna: valor}).eq('id', 1).execute()
    except Exception as e:
        pass

def obter_melhores_desempenhos(df_nuvem, tempo_minimo=5):
    if df_nuvem.empty: return pd.DataFrame()
    
    if 'tipo' not in df_nuvem.columns: return pd.DataFrame()
    df_prod = df_nuvem[(df_nuvem['setor'].astype(str).str.strip().str.upper() == 'CORTE') & 
                       (df_nuvem['tipo'].astype(str).str.strip().str.upper() == 'PRODUÇÃO')].copy()
    
    if df_prod.empty: return pd.DataFrame()
    
    df_prod['quantidade_num'] = pd.to_numeric(df_prod['quantidade'], errors='coerce').fillna(0)
    df_prod['das_min'] = df_prod['das'].astype(str).apply(calcular_minutos_str)
    df_prod['as_min'] = df_prod['as_hora'].astype(str).apply(calcular_minutos_str)
    
    df_prod['minutos'] = df_prod['as_min'] - df_prod['das_min']
    df_prod.loc[df_prod['minutos'] < 0, 'minutos'] += 1440 
    
    # ⚠️ TRAVA ANTI-OUTLIER: Só aceita apontamentos maiores ou iguais ao tempo mínimo
    df_prod = df_prod[(df_prod['minutos'] >= tempo_minimo) & (df_prod['quantidade_num'] > 0)]
    if df_prod.empty: return pd.DataFrame()
    
    df_prod['pecas_por_hora'] = (df_prod['quantidade_num'] / df_prod['minutos']) * 60
    
    df_prod['cod_peca'] = df_prod['cod_peca'].astype(str).str.strip()
    idx_recordes = df_prod.groupby('cod_peca')['pecas_por_hora'].idxmax()
    df_recordes = df_prod.loc[idx_recordes].copy()
    
    return df_recordes

def renderizar(df_nuvem, df_codigos, filtros_selecionados):
    st.markdown("""
        <style>
        .sim-box { background: #fdfefe; border: 1px solid #d5dbdb; border-radius: 10px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); margin-bottom: 25px; }
        .sim-title { color: #2c3e50; font-weight: 800; text-transform: uppercase; font-size: 15px; margin-bottom: 15px; display: flex; align-items: center; gap: 8px;}
        .card-tempo { background: #f4f6f6; border-radius: 8px; padding: 15px; text-align: center; border: 1px solid #eaeded; }
        .destaque-cap { font-size: 42px; font-weight: 900; color: #27ae60; line-height: 1.1; margin-top: 5px; margin-bottom: 5px; }
        ::-webkit-scrollbar { display: none; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<div style='text-align: center; margin-bottom: 20px;'><h2 style='color: #2c3e50; font-weight: 900;'>⚡ Engenharia de Capacidade (Corte)</h2><p style='color: #7f8c8d;'>Simule a capacidade máxima diária com base nos recordes históricos de produção.</p></div>", unsafe_allow_html=True)

    # ==========================================
    # ⚙️ MEMÓRIA DO SISTEMA E PARÂMETROS
    # ==========================================
    cfg = banco.obter_configuracoes()
    df_est = banco.obter_estrutura()
    
    maq_corte_total = 1
    if not df_est.empty:
        df_corte = df_est[df_est['setor'].astype(str).str.strip().str.upper() == 'CORTE']
        if not df_corte.empty:
            maq_corte_total = df_corte['maquina'].nunique()

    # Busca dados salvos (incluindo tempo mínimo e fonte)
    try: cfg_oee = int(cfg.get('cap_oee', 80))
    except: cfg_oee = 80
    
    try: cfg_maq = int(cfg.get('cap_maq', maq_corte_total))
    except: cfg_maq = maq_corte_total
    
    try: cfg_min_tempo = int(cfg.get('cap_min_tempo', 5))
    except: cfg_min_tempo = 5

    try: cfg_fonte = int(cfg.get('cap_fonte', 14))
    except: cfg_fonte = 14
    
    cfg_ignorar = bool(cfg.get('cap_ignorar', False))

    if 'cap_oee' not in st.session_state: st.session_state['cap_oee'] = cfg_oee
    if 'cap_maq' not in st.session_state: st.session_state['cap_maq'] = cfg_maq
    if 'cap_min_tempo' not in st.session_state: st.session_state['cap_min_tempo'] = cfg_min_tempo
    if 'cap_fonte' not in st.session_state: st.session_state['cap_fonte'] = cfg_fonte
    if 'cap_ignorar' not in st.session_state: st.session_state['cap_ignorar'] = cfg_ignorar
    
    def on_change_configs():
        salvar_parametro_db('cap_oee', st.session_state.cap_oee)
        salvar_parametro_db('cap_maq', st.session_state.cap_maq)
        salvar_parametro_db('cap_min_tempo', st.session_state.cap_min_tempo)
        salvar_parametro_db('cap_fonte', st.session_state.cap_fonte)
        salvar_parametro_db('cap_ignorar', st.session_state.cap_ignorar)

    # 🚀 PUXA A JORNADA DE TRABALHO DIRETO DO MOTOR CENTRAL (COM OS LANCHES DESCONTADOS)
    try:
        _, jornada_minutos, _, _, _, _ = configuracoes.obter_parametros()
        minutos_turno = int(jornada_minutos)
    except:
        minutos_turno = 510 # Fallback 08:30h
        
    if minutos_turno <= 0: 
        minutos_turno = 510

    # CARD DISCRETO DA JORNADA DE TRABALHO
    h_jornada = int(minutos_turno // 60)
    m_jornada = int(minutos_turno % 60)
    st.markdown(f"<div style='text-align: right; margin-top: -30px; margin-bottom: 15px; font-size: 13px; color: #7f8c8d;'><span style='background: #fdfefe; padding: 4px 10px; border-radius: 4px; border: 1px solid #eaeded; box-shadow: 0 1px 2px rgba(0,0,0,0.02);'>🕒 <b>Jornada de Trabalho:</b> {h_jornada:02d}h:{m_jornada:02d}m úteis/dia (Ajustável em Configurações)</span></div>", unsafe_allow_html=True)

    # CÁLCULOS DE TEMPO ÚTIL
    minutos_uteis_1maq = minutos_turno * (st.session_state.cap_oee / 100.0)
    minutos_uteis_total = minutos_uteis_1maq * st.session_state.cap_maq

    st.markdown("<div class='sim-box'>", unsafe_allow_html=True)
    st.markdown("<div class='sim-title'>⚙️ Ajustes de Cenário da Fábrica</div>", unsafe_allow_html=True)
    
    col_cfg1, col_cfg2, col_cfg3, col_cfg4 = st.columns([1.2, 1.2, 1, 1])
    with col_cfg1:
        st.number_input("Disponibilidade Alvo (OEE %)", min_value=1, max_value=100, key='cap_oee', on_change=on_change_configs)
        st.toggle("⚠️ Ignorar peças sem histórico", key='cap_ignorar', on_change=on_change_configs)
    with col_cfg2:
        st.number_input("Máquinas Ativas no Corte", min_value=1, max_value=20, key='cap_maq', on_change=on_change_configs)
        st.number_input("Tempo Mín. p/ Recorde (min)", min_value=1, max_value=120, key='cap_min_tempo', on_change=on_change_configs)
    with col_cfg3:
        st.number_input("Tamanho da Fonte (px)", min_value=10, max_value=30, key='cap_fonte', on_change=on_change_configs)
    with col_cfg4:
        ht, mt = int(minutos_uteis_total // 60), int(minutos_uteis_total % 60)
        st.markdown(f"<div class='card-tempo' style='border-color: #3498db; background: #ebf5fb; margin-top: 15px;'><div style='color:#2980b9; font-size:12px; font-weight:bold;'>Tempo Útil Total (Setor)</div><div style='font-size:22px; font-weight:900; color:#2980b9;'>{ht:02d}h:{mt:02d}m</div></div>", unsafe_allow_html=True)
        
    st.markdown("</div>", unsafe_allow_html=True)

    # PROCESSAMENTO DE DADOS MESTRES 
    df_recordes = obter_melhores_desempenhos(df_nuvem, st.session_state.cap_min_tempo)
    df_matriz = banco.obter_produtos_matriz()
    
    if df_matriz.empty:
        st.warning("Nenhuma matriz de produto encontrada no sistema.")
        return

    lista_produtos = sorted(df_matriz['produto_formula'].dropna().unique().tolist())
    
    if 'cap_produto' not in st.session_state:
        prod_salvo = cfg.get('cap_produto', '')
        st.session_state['cap_produto'] = prod_salvo if prod_salvo in lista_produtos else (lista_produtos[0] if lista_produtos else "")

    def on_change_produto():
        salvar_parametro_db('cap_produto', st.session_state.cap_produto)

    # ==========================================
    # 🔎 BLOCO 1: DETALHAMENTO DO PRODUTO 
    # ==========================================
    st.markdown("### 🔎 Auditoria de Peças por Produto")
    
    produto_selecionado = st.selectbox("Selecione um produto para auditar e calcular a capacidade:", lista_produtos, key='cap_produto', on_change=on_change_produto)
    
    if produto_selecionado:
        df_pecas_prod = df_matriz[df_matriz['produto_formula'] == produto_selecionado].copy()
        df_pecas_prod['cod'] = df_pecas_prod['cod'].astype(str).str.strip()
        
        pecas_brutas = []
        minutos_totais_produto = 0
        pecas_sem_dados = 0
        
        for _, peca in df_pecas_prod.iterrows():
            cod_p = str(peca.get('cod', '')).strip()
            desc_p = str(peca.get('descricao', ''))
            try: qtd_p = float(peca.get('qnt', 0))
            except: qtd_p = 0
            
            melhor_pch = 0
            maq_rec, operador_rec, data_rec, horario_rec, qtd_lote_rec = "-", "-", "-", "-", "-"
            
            if not df_recordes.empty and cod_p in df_recordes['cod_peca'].values:
                rec = df_recordes[df_recordes['cod_peca'] == cod_p].iloc[0]
                melhor_pch = rec['pecas_por_hora']
                maq_rec = rec['maquina']
                operador_rec = str(rec.get('operador', '-')).strip()
                data_rec = rec['data_registro']
                
                # Formatação Limpa do Horário
                das_str = str(rec.get('das', '')).strip()
                as_str = str(rec.get('as_hora', '')).strip()
                duracao_min = rec.get('minutos', 0)
                
                try: das_clean = f"{int(das_str.split(':')[0])}:{das_str.split(':')[1]}"
                except: das_clean = das_str
                
                try: as_clean = f"{int(as_str.split(':')[0])}:{as_str.split(':')[1]}"
                except: as_clean = as_str
                
                if duracao_min >= 60:
                    dur_str = f"{int(duracao_min // 60)}:{int(duracao_min % 60):02d}m"
                else:
                    dur_str = f"{int(duracao_min)}m"
                
                horario_rec = f"{das_clean} - {as_clean} / {dur_str}"
                
                qtd_lote_rec = int(rec['quantidade_num'])
                
                minutos_peca = (qtd_p / melhor_pch) * 60 if melhor_pch > 0 else 0
                minutos_totais_produto += minutos_peca
            else:
                pecas_sem_dados += 1
                
            pecas_brutas.append({
                "cod_p": cod_p, "desc_p": desc_p, "qtd_p": qtd_p,
                "melhor_pch": melhor_pch, "maq_rec": maq_rec, "operador_rec": operador_rec,
                "data_rec": data_rec, "horario_rec": horario_rec, "qtd_lote_rec": qtd_lote_rec
            })
            
        cap_diaria = 0
        pode_calcular = (pecas_sem_dados == 0) or (pecas_sem_dados > 0 and st.session_state.cap_ignorar)
        
        if pode_calcular and minutos_totais_produto > 0:
            cap_diaria = int(minutos_uteis_total / minutos_totais_produto)
            txt_tempo = f"{minutos_totais_produto:.1f} minutos"
            
            alerta_html = ""
            if pecas_sem_dados > 0:
                alerta_html = f"<div style='color: #e74c3c; font-size: 13px; font-weight: bold; margin-top: 8px;'>⚠️ Atenção: Cálculo ignorando {pecas_sem_dados} peça(s) sem histórico. A capacidade real será menor.</div>"

            st.markdown(f"""
            <div style='background: #e8f8f5; border: 1px solid #27ae60; box-shadow: 0 4px 10px rgba(39,174,96,0.15); padding: 25px; border-radius: 12px; margin-bottom: 25px; text-align: center;'>
                <div style='color: #2c3e50; font-size: 16px; font-weight: 600; text-transform: uppercase;'>Capacidade Diária Estimada no Corte</div>
                <div class='destaque-cap'>{cap_diaria} unidades</div>
                <div style='color: #7f8c8d; font-size: 14px;'>Velocidade de Processamento Global: <b>{txt_tempo}</b> de serra / unidade.</div>
                {alerta_html}
            </div>
            """, unsafe_allow_html=True)
        else:
            if not pode_calcular:
                st.warning(f"⚠️ Impossível calcular capacidade exata. Faltam apontamentos históricos para {pecas_sem_dados} peça(s) deste produto. Ative a opção 'Ignorar peças sem histórico' para forçar uma estimativa.")
            else:
                st.warning("Nenhum tempo histórico válido encontrado para as peças deste produto.")

        dados_tabela_1 = []
        total_qtd_prod = 0
        total_qtd_op = 0
        total_tempo_op_min = 0
        soma_pch = 0
        count_pch = 0
        
        for item in pecas_brutas:
            qtd_op = int(item['qtd_p'] * cap_diaria)
            tempo_op_min = (qtd_op / item['melhor_pch']) * 60 if item['melhor_pch'] > 0 else 0
            
            # Somatórios para a linha de totais
            total_qtd_prod += item['qtd_p']
            if cap_diaria > 0:
                total_qtd_op += qtd_op
            total_tempo_op_min += tempo_op_min
            
            if item['melhor_pch'] > 0:
                soma_pch += item['melhor_pch']
                count_pch += 1
            
            if tempo_op_min > 0:
                h_op = int(tempo_op_min // 60)
                m_op = int(tempo_op_min % 60)
                if h_op > 0:
                    tempo_op_str = f"{h_op}:{m_op:02d}m"
                else:
                    tempo_op_str = f"{m_op}m"
            else:
                tempo_op_str = "-"
                
            dados_tabela_1.append({
                "Código": item['cod_p'],
                "Peça": item['desc_p'],
                "Qtd/Prod": int(item['qtd_p']) if item['qtd_p'].is_integer() else item['qtd_p'],
                "Qtd/OP": qtd_op if cap_diaria > 0 else "-",
                "Tempo/OP": tempo_op_str,
                "⏱️ Melhor Peças/h": f"{item['melhor_pch']:.1f}" if item['melhor_pch'] > 0 else "Sem Dados",
                "Data": item['data_rec'],
                "Das / Às": item['horario_rec'],
                "Qtd. Lote": item['qtd_lote_rec'],
                "Máquina": item['maq_rec'],
                "Operador": item['operador_rec']
            })

        # Adiciona a linha de TOTAL / MÉDIA
        if dados_tabela_1:
            avg_pch = soma_pch / count_pch if count_pch > 0 else 0
            if total_tempo_op_min > 0:
                h_tot = int(total_tempo_op_min // 60)
                m_tot = int(total_tempo_op_min % 60)
                if h_tot > 0:
                    tempo_tot_str = f"{h_tot}:{m_tot:02d}m"
                else:
                    tempo_tot_str = f"{m_tot}m"
            else:
                tempo_tot_str = "-"

            dados_tabela_1.append({
                "Código": "",
                "Peça": "TOTAL / MÉDIA",
                "Qtd/Prod": int(total_qtd_prod) if total_qtd_prod.is_integer() else total_qtd_prod,
                "Qtd/OP": total_qtd_op if cap_diaria > 0 else "-",
                "Tempo/OP": tempo_tot_str,
                "⏱️ Melhor Peças/h": f"{avg_pch:.1f}" if avg_pch > 0 else "-",
                "Data": "",
                "Das / Às": "",
                "Qtd. Lote": "",
                "Máquina": "",
                "Operador": ""
            })

        df_tab1 = pd.DataFrame(dados_tabela_1)
        altura_dinamica = (len(df_tab1) + 1) * 36 + 10
        tamanho_fonte = st.session_state.cap_fonte
        
        # BLINDAGEM DUPLA DE ALINHAMENTO: column_config (Streamlit) + set_properties (Pandas)
        col_cfg_1 = {col: st.column_config.Column(alignment="center") for col in df_tab1.columns}
        col_cfg_1["Peça"] = st.column_config.Column(alignment="left")

        def estilizar_totais(row):
            if row.name == df_tab1.index[-1]:
                return ['font-weight: bold; background-color: #f8f9fa; color: #2c3e50'] * len(row)
            return [''] * len(row)

        df_tab1_styled = df_tab1.style.set_properties(**{
            'text-align': 'center',
            'font-size': f'{tamanho_fonte}px'
        }).set_properties(subset=['Peça'], **{
            'text-align': 'left'
        }).apply(estilizar_totais, axis=1).set_table_styles([{
            'selector': 'th',
            'props': [('text-align', 'center'), ('font-size', f'{tamanho_fonte}px')]
        }])

        st.dataframe(df_tab1_styled, use_container_width=True, hide_index=True, height=altura_dinamica, column_config=col_cfg_1)

    st.markdown("<hr style='opacity:0.2; margin: 40px 0;'>", unsafe_allow_html=True)

    # ==========================================
    # 🏆 BLOCO 2: RANKING GLOBAL DE PRODUTOS
    # ==========================================
    st.markdown("### 🏭 Visão Global de Capacidade")
    
    dados_tabela_2 = []
    
    for prod in lista_produtos:
        df_p = df_matriz[df_matriz['produto_formula'] == prod]
        total_pecas = len(df_p)
        pecas_ok = 0
        minutos_totais = 0
        
        for _, peca in df_p.iterrows():
            cod_p = str(peca.get('cod', '')).strip()
            qtd_p = 0
            try: qtd_p = float(peca.get('qnt', 0))
            except: pass
            
            if not df_recordes.empty and cod_p in df_recordes['cod_peca'].values:
                rec = df_recordes[df_recordes['cod_peca'] == cod_p].iloc[0]
                pch = rec['pecas_por_hora']
                if pch > 0:
                    minutos_totais += (qtd_p / pch) * 60
                    pecas_ok += 1
        
        # TEXTO MAPEAMENTO FORMATADO: Faltam X/Y peças (Z%)
        pct_concluido = int((pecas_ok / total_pecas) * 100) if total_pecas > 0 else 0
        if pecas_ok == total_pecas:
            status_txt = f"✅ Completo ({pct_concluido}%)"
        else:
            faltantes = total_pecas - pecas_ok
            status_txt = f"⚠️ Faltam {faltantes}/{total_pecas} peças ({pct_concluido}%)"
        
        cap_unid = None
        if pecas_ok == total_pecas or (st.session_state.cap_ignorar and pecas_ok > 0):
            if minutos_totais > 0:
                cap_unid = int(minutos_uteis_total / minutos_totais)
        
        dados_tabela_2.append({
            "Produto": prod,
            "Mapeamento": status_txt,
            "Peças (Matriz)": str(total_pecas), # Força string para não sumir da tela
            "Tempo Corte/Unid.": f"{minutos_totais:.1f} min" if minutos_totais > 0 else "-",
            "Capacidade Diária": cap_unid if cap_unid is not None else 0,
            "_ordenacao": cap_unid if cap_unid is not None else -1
        })
        
    df_visao_global = pd.DataFrame(dados_tabela_2)
    df_visao_global = df_visao_global.sort_values(by='_ordenacao', ascending=False).drop(columns=['_ordenacao'])
    
    texto_erro = "Parcial (Ative a projeção)" if not st.session_state.cap_ignorar else "Sem histórico útil"
    df_visao_global['Capacidade Diária'] = df_visao_global['Capacidade Diária'].apply(lambda x: f"{x} unid." if isinstance(x, int) and x > 0 else texto_erro)
    
    # ❌ OCULTAR PRODUTOS "SEM HISTÓRICO ÚTIL"
    df_visao_global = df_visao_global[df_visao_global['Capacidade Diária'] != "Sem histórico útil"]
    
    # BLINDAGEM DUPLA DE ALINHAMENTO PARA TABELA 2
    col_cfg_2 = {col: st.column_config.Column(alignment="center") for col in df_visao_global.columns}
    col_cfg_2["Produto"] = st.column_config.Column(alignment="left")
    
    df_visao_global_styled = df_visao_global.style.set_properties(**{
        'text-align': 'center',
        'font-size': f'{tamanho_fonte}px'
    }).set_properties(subset=['Produto'], **{
        'text-align': 'left'
    }).set_table_styles([{
        'selector': 'th',
        'props': [('text-align', 'center'), ('font-size', f'{tamanho_fonte}px')]
    }])
    
    st.dataframe(df_visao_global_styled, use_container_width=True, hide_index=True, column_config=col_cfg_2)