import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import banco
import streamlit.components.v1 as components
import json
import altair as alt
import time
import google.generativeai as genai

def obter_hora_atual():
    return datetime.utcnow() - timedelta(hours=3)

def calcular_minutos_str(hora_str):
    try: return int(hora_str.split(':')[0]) * 60 + int(hora_str.split(':')[1])
    except: return 0

def calcular_eta(min_restantes, agora_dt, m_das_min, m_as_min, t_das_min, t_as_min):
    if min_restantes <= 0: return agora_dt
    if min_restantes > 14400: return None 
    curr = agora_dt
    min_left = int(min_restantes)
    while min_left > 0:
        c_min = curr.hour * 60 + curr.minute
        if (m_das_min <= c_min < m_as_min) or (t_das_min <= c_min < t_as_min):
            min_left -= 1
        curr += timedelta(minutes=1)
        if curr.hour * 60 + curr.minute >= t_as_min:
            curr += timedelta(days=1)
            curr = curr.replace(hour=m_das_min//60, minute=m_das_min%60, second=0)
    return curr

def renderizar(df_nuvem, df_codigos, filtros_selecionados):
    st.markdown("""
<style>
::-webkit-scrollbar { display: none; }
.block-container { max-width: 99% !important; padding-top: 0.5rem !important; padding-bottom: 5rem !important; }
header[data-testid="stHeader"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

    cfg = banco.obter_configuracoes()
    refresh_segundos = int(cfg.get('ao_vivo_refresh', 60))
    tempo_critico = int(cfg.get('ao_vivo_critico', 15))
    vel_barra = int(cfg.get('ao_vivo_vel_barra', 8))
    
    m_das = cfg.get('manha_das', '07:30')
    m_as = cfg.get('manha_as', '11:50')
    t_das = cfg.get('tarde_das', '13:30')
    t_as = cfg.get('tarde_as', '17:30')
    
    lm_das = cfg.get('lanche_m_das', '')
    lm_as = cfg.get('lanche_m_as', '')
    lt_das = cfg.get('lanche_t_das', '')
    lt_as = cfg.get('lanche_t_as', '')
    
    m_das_min = calcular_minutos_str(m_das)
    m_as_min = calcular_minutos_str(m_as)
    t_das_min = calcular_minutos_str(t_das)
    t_as_min = calcular_minutos_str(t_as)
    
    lm_das_min = calcular_minutos_str(lm_das) if lm_das else -1
    lm_as_min = calcular_minutos_str(lm_as) if lm_as else -1
    lt_das_min = calcular_minutos_str(lt_das) if lt_das else -1
    lt_as_min = calcular_minutos_str(lt_as) if lt_as else -1

    agora = obter_hora_atual()
    hoje_str = agora.strftime("%Y-%m-%d")
    agora_min = agora.hour * 60 + agora.minute

    # ==========================================
    # LÓGICA DO TEMPO ÚTIL TRANSCORRIDO (A RÉGUA UNIVERSAL)
    # ==========================================
    minutos_uteis_passados = 0
    total_min_uteis_dia = 0
    
    for m in range(m_das_min, t_as_min):
        is_turno = (m_das_min <= m < m_as_min) or (t_das_min <= m < t_as_min)
        is_lanche = (lm_das_min <= m < lm_as_min) or (lt_das_min <= m < lt_as_min)
        if is_turno and not is_lanche:
            total_min_uteis_dia += 1
            if m < agora_min:
                minutos_uteis_passados += 1
                
    if minutos_uteis_passados <= 0: minutos_uteis_passados = 1 # Evita erro divisão por zero no início do dia
    if total_min_uteis_dia <= 0: total_min_uteis_dia = 1

    perc_turno = (minutos_uteis_passados / total_min_uteis_dia) * 100
    if perc_turno > 100: perc_turno = 100

    st.markdown(f"""<div style="width: 100%; background-color: #e0e0e0; height: 6px; overflow: hidden; margin-bottom: 15px; border-radius: 3px;">
<div style="width: {perc_turno:.1f}%; background-color: #2980b9; height: 100%;"></div>
</div>""", unsafe_allow_html=True)

    # ==========================================
    # MOTOR DE CORES DINÂMICAS 
    # ==========================================
    mapa_cores = banco.obter_mapa_cores()
    def get_color(tipo):
        t = str(tipo).strip().upper()
        if t in mapa_cores: return mapa_cores[t]
        if t == 'PRODUÇÃO': return '#27ae60'
        if t == 'PARADA': return '#e74c3c'
        if t == 'NÃO CONTA': return '#f39c12'
        if t == 'LIVRE': return '#3498db'
        if t == 'A REALIZAR': return '#ecf0f1'
        if t == 'INTERVALO PREVISTO': return '#bdc3c7'
        return '#95a5a6'

    def get_friendly_name(tipo):
        t = str(tipo).strip().upper()
        if t == 'NÃO CONTA': return 'Pausa Regist.'
        if t == 'PRODUÇÃO': return 'Produzindo'
        if t == 'PARADA': return 'Indisponível'
        if t == 'LIVRE': return 'Livre'
        if t == 'A REALIZAR': return 'A Realizar'
        if t == 'INTERVALO PREVISTO': return 'Interv. Prev.'
        return t.title()

    codigos_pausa = []
    if not df_codigos.empty and 'tipo' in df_codigos.columns:
        mask_pausa = df_codigos['tipo'].astype(str).str.strip().str.upper().isin(['NÃO CONTA', 'DESNCONSIDERAR', 'DESCONSIDERAR'])
        codigos_pausa = df_codigos[mask_pausa]['codigo'].astype(str).str.strip().tolist()

    supa = banco.conectar()
    df_est = banco.obter_estrutura()
    
    total_maq_atual = len(df_est[['setor', 'maquina']].dropna().drop_duplicates()) if not df_est.empty else 0
    
    resp_hist = supa.table("historico_operacao").select("data_hora, percentual, maquinas_ativas, maquinas_totais").gte("data_hora", f"{hoje_str} 00:00:00").order("data_hora").execute()
    hora_inicio_turno = datetime.strptime(f"{hoje_str} {m_das}", "%Y-%m-%d %H:%M")
    hora_fim_turno = datetime.strptime(f"{hoje_str} {t_as}", "%Y-%m-%d %H:%M")
    df_h = pd.DataFrame(resp_hist.data) if resp_hist.data else pd.DataFrame()
    
    if not df_h.empty:
        df_h['data_hora'] = pd.to_datetime(df_h['data_hora']).dt.tz_localize(None)
        df_h['minuto_exato'] = df_h['data_hora'].dt.floor('min')
        df_agrupado = df_h.groupby('minuto_exato')[['percentual', 'maquinas_ativas', 'maquinas_totais']].last().reset_index()
        df_agrupado.set_index('minuto_exato', inplace=True)
    else:
        df_agrupado = pd.DataFrame(columns=['percentual', 'maquinas_ativas', 'maquinas_totais'])
        
    idx_todos_minutos = pd.date_range(start=hora_inicio_turno, end=hora_fim_turno, freq='min')
    df_completo = pd.DataFrame(index=idx_todos_minutos)
    if not df_agrupado.empty: df_completo = df_completo.join(df_agrupado)
    else:
        df_completo['percentual'] = pd.NA
        df_completo['maquinas_ativas'] = pd.NA
        df_completo['maquinas_totais'] = pd.NA
        
    df_completo['percentual'] = df_completo['percentual'].ffill().fillna(0.0)
    df_completo['maquinas_ativas'] = df_completo['maquinas_ativas'].ffill().fillna(0)
    df_completo['maquinas_totais'] = df_completo['maquinas_totais'].ffill().fillna(total_maq_atual)
    agora_minuto = agora.replace(second=0, microsecond=0)
    df_completo.loc[df_completo.index > agora_minuto, 'percentual'] = pd.NA
    df_completo.reset_index(inplace=True)
    df_completo.rename(columns={'index': 'Hora', 'percentual': 'Em Operação (%)'}, inplace=True)
    df_plot = df_completo.dropna(subset=['Em Operação (%)']).copy()

    df_produtos = banco.obter_produtos_matriz() 
    usuarios_cadastrados = banco.obter_usuarios_completo() 
    ordem_setores = {}
    if not df_est.empty and 'ordem_fluxo' in df_est.columns:
        for _, row in df_est[['setor', 'ordem_fluxo']].dropna().drop_duplicates(subset=['setor']).iterrows():
            try: ordem_setores[str(row['setor']).strip()] = float(row['ordem_fluxo'])
            except: pass

    pares_maquinas = df_est[['setor', 'maquina']].dropna().drop_duplicates().values.tolist() if filtros_selecionados['setor'] == "[ Todos ]" else df_est[df_est['setor'] == filtros_selecionados['setor']][['setor', 'maquina']].dropna().drop_duplicates().values.tolist()
    resp_status = supa.table("status_maquinas").select("*").execute()
    status_dict = {(str(d.get('setor', '')).strip(), str(d.get('maquina', '')).strip()): d for d in resp_status.data} if resp_status.data else {}

    resp_ops = supa.table("planejamento_ops").select("id, produto_formula, quantidade_planejada, data_inicio").eq("status", "Em Andamento").execute()
    ops_ativas = resp_ops.data if resp_ops.data else []
    ops_dict = {op['produto_formula']: op for op in ops_ativas}
    
    df_nuvem_operacao = pd.DataFrame()
    df_hoje = pd.DataFrame()
    if not df_nuvem.empty and 'data_registro' in df_nuvem.columns and 'tipo' in df_nuvem.columns:
        df_hoje = df_nuvem[(df_nuvem['data_registro'] == hoje_str)].copy()
        df_nuvem_operacao = df_nuvem[df_nuvem['tipo'].astype(str).str.strip().str.upper() == 'PRODUÇÃO'].copy()
        if not df_nuvem_operacao.empty:
            df_nuvem_operacao['data_registro_dt'] = pd.to_datetime(df_nuvem_operacao['data_registro'], errors='coerce')
            df_nuvem_operacao['quantidade_num'] = pd.to_numeric(df_nuvem_operacao['quantidade'], errors='coerce').fillna(0)

    try:
        resp_cx = supa.table("caixas_matriz").select("*").execute()
        df_caixas = pd.DataFrame(resp_cx.data) if resp_cx.data else pd.DataFrame()
    except:
        df_caixas = pd.DataFrame()

    df_todas_producoes = pd.DataFrame()
    if ops_ativas:
        datas_brutas = [op['data_inicio'] for op in ops_ativas]
        menor_data_str = min(datas_brutas).split(" ")[0].split("T")[0]
        resp_prod = supa.table("producao_diaria").select("setor, cod_peca, quantidade, data_registro").eq("tipo", "PRODUÇÃO").gte("data_registro", menor_data_str).execute()
        if resp_prod.data:
            df_todas_producoes = pd.DataFrame(resp_prod.data)
            df_todas_producoes['data_registro_dt'] = pd.to_datetime(df_todas_producoes['data_registro'])
            df_todas_producoes['cod_peca'] = df_todas_producoes['cod_peca'].astype(str).str.strip()
            df_todas_producoes['setor'] = df_todas_producoes['setor'].astype(str).str.strip().str.upper()
            df_todas_producoes['quantidade'] = pd.to_numeric(df_todas_producoes['quantidade'], errors='coerce').fillna(0)

    maquinas_paradas_criticas = []
    maquinas_pausas = []
    maquinas_produzindo = []
    qtd_rodando = qtd_livres = minutos_ativos_perdidos = 0
    mapa_visual_dict = {}

    for setor_raw, maq_raw in pares_maquinas:
        setor = str(setor_raw).strip()
        maq = str(maq_raw).strip()
        if setor not in mapa_visual_dict: mapa_visual_dict[setor] = []
        info = status_dict.get((setor, maq), {})
        status_maq = info.get('status', 'Livre')
        info['maquina'] = maq
        info['setor'] = setor
        
        operadores_maq = [u['nome'] for u in usuarios_cadastrados if str(u.get('maquina', '')).strip() == maq and str(u.get('setor', '')).strip() == setor and u.get('ativo') == True]
        info['setor_exibicao'] = f"{setor} / {' / '.join(operadores_maq)}" if operadores_maq else setor
        operadores_texto = " / ".join(operadores_maq) if operadores_maq else "Sem Operador"
        
        if status_maq == 'Parado':
            cod = info.get('cod_ocorrencia')
            tipo_parada = 'PARADA'
            desc = "Desconhecido"
            
            if cod and not df_codigos.empty:
                f_cod = df_codigos[df_codigos['codigo'].astype(str) == str(cod)]
                if not f_cod.empty:
                    desc = str(f_cod.iloc[0]['descricao'])
                    if 'tipo' in f_cod.columns:
                        tipo_parada = str(f_cod.iloc[0]['tipo']).strip().upper()
                        
            if 'DESCONSIDERAR' in tipo_parada: tipo_parada = 'NÃO CONTA'
            
            info['tipo_registro'] = tipo_parada
            info['descricao_completa'] = f"{desc} ({cod})"
            info['is_pausa'] = str(cod).strip() in codigos_pausa
            
            if info['is_pausa']:
                maquinas_pausas.append(info)
                icone_mapa = "☕"
            else:
                maquinas_paradas_criticas.append(info)
                icone_mapa = "🟠" if tipo_parada == 'ROTINA' else "🔴"
                
                try:
                    h_ini = datetime.strptime(info['hora_inicio'], "%Y-%m-%d %H:%M:%S")
                    if h_ini.date() == agora.date():
                        for m in range(h_ini.hour * 60 + h_ini.minute, agora_min + 1):
                            if (m >= m_das_min and m < m_as_min) or (m >= t_das_min and m < t_as_min): minutos_ativos_perdidos += 1
                except: pass
                
        elif status_maq == 'Produzindo':
            info['tipo_registro'] = 'PRODUÇÃO'
            qtd_rodando += 1
            icone_mapa = "🟢"
            cod_peca = info.get('cod_peca_atual')
            nome_peca_completo, html_progresso = "Peça Desconhecida", ""
            
            ultima_p = info.get('ultima_peca_sel', '')
            ultimo_prod = info.get('ultimo_produto_sel', '')
            if str(cod_peca).startswith("VIRTUAL-") and ultima_p and ultimo_prod:
                nome_cx = ultima_p.split(" (Cód:")[0].strip()
                nome_peca_completo = f"{ultimo_prod} ➔ {nome_cx}"
                prod_form = ultimo_prod
            elif cod_peca and not df_produtos.empty:
                f_peca = df_produtos[df_produtos['cod'].astype(str) == str(cod_peca)]
                if not f_peca.empty:
                    prod_form = f_peca.iloc[0]['produto_formula']
                    nome_peca_completo = f"{prod_form} ➔ {f_peca.iloc[0]['descricao']}"
                elif not df_caixas.empty:
                    f_cx = df_caixas[df_caixas['cod_caixa'].astype(str) == str(cod_peca)]
                    if not f_cx.empty:
                        prod_form = f_cx.iloc[0]['produto_formula']
                        nome_peca_completo = f"{prod_form} ➔ Caixa {f_cx.iloc[0]['num_caixa']}"
            else:
                prod_form = None

            if cod_peca and prod_form:
                if prod_form in ops_dict:
                    op_data = ops_dict[prod_form]
                    
                    qnt_peca_matriz = 1
                    if not df_produtos.empty:
                        f_peca_aux = df_produtos[df_produtos['cod'].astype(str) == str(cod_peca)]
                        if not f_peca_aux.empty:
                            try: qnt_peca_matriz = int(float(f_peca_aux.iloc[0].get('qnt', 1)))
                            except: qnt_peca_matriz = 1
                            
                    meta_peca = int(op_data['quantidade_planejada']) * qnt_peca_matriz
                    
                    if meta_peca > 0:
                        prod_realizada = 0
                        if not df_nuvem_operacao.empty:
                            data_inicio_op_dt = pd.to_datetime(op_data['data_inicio'].split(" ")[0], errors='coerce')
                            mask_todas_op = (df_nuvem_operacao['cod_peca'].astype(str).str.strip() == str(cod_peca)) & (df_nuvem_operacao['setor'].astype(str).str.strip().str.upper() == setor.upper()) & (df_nuvem_operacao['data_registro_dt'] >= data_inicio_op_dt)
                            prod_realizada = int(df_nuvem_operacao[mask_todas_op]['quantidade_num'].sum())
                        
                        prod_realizada = min(meta_peca, prod_realizada)
                        perc = (prod_realizada / meta_peca * 100)
                        
                        eta_str = "ETA: Calculando..."
                        if not df_nuvem_operacao.empty:
                            mask_maq_hoje = mask_todas_op & (df_nuvem_operacao['maquina'] == maq) & (df_nuvem_operacao['data_registro'] == hoje_str)
                            df_maq_hoje = df_nuvem_operacao[mask_maq_hoje]
                            prod_realizada_hoje = int(df_maq_hoje['quantidade_num'].sum())
                            minutos_prod_hoje = 0
                            for _, r in df_maq_hoje.iterrows():
                                min_i = calcular_minutos_str(r.get('das', '00:00'))
                                min_f = calcular_minutos_str(r.get('as_hora', '00:00'))
                                minutos_prod_hoje += max(0, min_f - min_i)
                            
                            if minutos_prod_hoje >= 20 or perc >= 5.0:
                                if minutos_prod_hoje > 0:
                                    vel_minuto = prod_realizada_hoje / minutos_prod_hoje
                                    if vel_minuto > 0:
                                        faltam = max(0, meta_peca - prod_realizada)
                                        min_restantes = faltam / vel_minuto
                                        eta_dt = calcular_eta(min_restantes, agora, m_das_min, m_as_min, t_das_min, t_as_min)
                                        if eta_dt:
                                            if eta_dt.date() == agora.date(): eta_str = f"ETA: Hoje às {eta_dt.strftime('%H:%M')}"
                                            elif eta_dt.date() == (agora + timedelta(days=1)).date(): eta_str = f"ETA: Amanhã às {eta_dt.strftime('%H:%M')}"
                                            else: eta_str = f"ETA: {eta_dt.strftime('%d/%m %H:%M')}"

                        html_progresso = f"""
                        <div style='background: rgba(255,255,255,0.15); padding: 5px 10px; border-radius: 5px; margin-bottom: 5px;'>
                            <div style='display: flex; justify-content: space-between; font-size: 11px; font-weight: bold; margin-bottom: 4px;'>
                                <span>{prod_realizada}/{meta_peca}</span><span>{perc:.1f}%</span>
                            </div>
                            <div style='width: 100%; background: rgba(0,0,0,0.2); height: 6px; border-radius: 3px;'>
                                <div style='width: {perc}%; background: #ffffff; height: 100%;'></div>
                            </div>
                            <div style='font-size: 10px; color: #e1f5fe; text-align: right; margin-top: 3px; font-style: italic;'>{eta_str}</div>
                        </div>
                        """
            info['descricao_completa'] = nome_peca_completo
            info['html_progresso'] = html_progresso
            maquinas_produzindo.append(info)
        else:
            info['tipo_registro'] = 'LIVRE'
            qtd_livres += 1
            icone_mapa = "🔵"
            
        # ==========================================
        # ACUMULADO COM FILTRO DE TEMPO ÚTIL
        # ==========================================
        minutos_acumulados_bd = 0
        if not df_hoje.empty and info.get('tipo_registro') not in ['LIVRE', 'A REALIZAR']:
            df_maq_hoje = df_hoje[(df_hoje['maquina'] == maq) & (df_hoje['setor'] == setor)]
            for _, r in df_maq_hoje.iterrows():
                tipo_hist = str(r.get('tipo', '')).strip().upper()
                if 'DESCONSIDERAR' in tipo_hist: tipo_hist = 'NÃO CONTA'
                if not tipo_hist or tipo_hist == 'NAN': tipo_hist = 'PARADA'
                
                if tipo_hist == info['tipo_registro']:
                    m_i = calcular_minutos_str(r.get('das', '00:00'))
                    m_f = calcular_minutos_str(r.get('as_hora', '00:00'))
                    
                    # Filtra matematicamente para somar apenas os minutos que caem dentro do horário útil
                    for min_bd in range(m_i, m_f):
                        is_turno = (m_das_min <= min_bd < m_as_min) or (t_das_min <= min_bd < t_as_min)
                        is_lanche = (lm_das_min <= min_bd < lm_as_min) or (lt_das_min <= min_bd < lt_as_min)
                        if is_turno and not is_lanche:
                            minutos_acumulados_bd += 1
                            
        info['minutos_acumulados_bd'] = minutos_acumulados_bd
            
        mapa_visual_dict[setor].append({"maquina": maq, "operadores": operadores_texto, "tipo": info['tipo_registro'], "icone": icone_mapa})

    cards_exibicao = maquinas_paradas_criticas + maquinas_pausas + maquinas_produzindo
    qtd_total = len(pares_maquinas)
    perc_rodando = (qtd_rodando / qtd_total) * 100 if qtd_total > 0 else 0

    minutos_finalizados = 0
    top_ofensor = "Nenhum"
    mttr_str = "0m"
    noticias = []
    
    if not df_hoje.empty:
        df_paradas_hoje = df_hoje[df_hoje['tipo'].astype(str).str.strip().str.upper() == 'PARADA'] if 'tipo' in df_hoje.columns else df_hoje
        for _, row in df_paradas_hoje.iterrows():
            if str(row['cod_ocorrencia']).strip() not in codigos_pausa:
                for m in range(calcular_minutos_str(row['das']), calcular_minutos_str(row['as_hora'])):
                    if (m >= m_das_min and m < m_as_min) or (m >= t_das_min and m < t_as_min): minutos_finalizados += 1
        df_problemas = df_paradas_hoje[~df_paradas_hoje['cod_ocorrencia'].astype(str).str.strip().isin(codigos_pausa)]
        if not df_problemas.empty:
            mttr_str = f"{int(minutos_finalizados / len(df_problemas))}m"
            vilao_cod = df_problemas['cod_ocorrencia'].value_counts().idxmax()
            desc_vilao = str(df_codigos[df_codigos['codigo'].astype(str) == str(vilao_cod)].iloc[0]['descricao']) if not df_codigos.empty and not df_codigos[df_codigos['codigo'].astype(str) == str(vilao_cod)].empty else "Problema"
            top_ofensor = f"{desc_vilao}"
        for _, rr in df_paradas_hoje.sort_values(by='as_hora', ascending=False).head(5).iterrows():
            noticias.append(f"🟢 [{rr.get('setor', '')}] {rr['maquina']} solucionou problema às {rr['as_hora']}")

    total_perdido_hoje = minutos_finalizados + minutos_ativos_perdidos
    h_perdido, m_perdido = int(total_perdido_hoje // 60), int(total_perdido_hoje % 60)
    
    vol_corte_un = 0
    vol_corte_m2 = 0.0
    if not df_hoje.empty and not df_produtos.empty:
        df_corte_hoje = df_hoje[(df_hoje['setor'].astype(str).str.strip().str.upper() == 'CORTE') & (df_hoje['tipo'].astype(str).str.strip().str.upper() == 'PRODUÇÃO')]
        for _, r in df_corte_hoje.iterrows():
            qtd = pd.to_numeric(r.get('quantidade', 0), errors='coerce')
            if pd.isna(qtd): qtd = 0
            vol_corte_un += int(qtd)
            f_prod = df_produtos[df_produtos['cod'].astype(str) == str(r.get('cod_peca', '')).strip()]
            if not f_prod.empty:
                comp = pd.to_numeric(f_prod.iloc[0].get('comp', 0), errors='coerce')
                larg = pd.to_numeric(f_prod.iloc[0].get('larg', 0), errors='coerce')
                if pd.notna(comp) and pd.notna(larg):
                    vol_corte_m2 += (comp / 1000.0) * (larg / 1000.0) * qtd

    for p in maquinas_paradas_criticas: noticias.append(f"🔴 [{p['setor']}] {p['maquina']} parada: {p['descricao_completa']}")
    for p in maquinas_pausas: noticias.append(f"☕ [{p['setor']}] {p['maquina']}: {p['descricao_completa']}")
    for p in maquinas_produzindo: noticias.append(f"🟢 [{p['setor']}] {p['maquina']} produzindo: {str(p.get('cod_peca_atual',''))}")
    texto_letreiro = " &nbsp;&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;&nbsp; ".join(noticias) if noticias else "🟢 FÁBRICA OPERANDO COM 100% DE CAPACIDADE NESTE MOMENTO"

    if "ia_dash_msg" not in st.session_state:
        st.session_state.ia_dash_msg = "⏳ Aguardando primeira análise da IA..."
        st.session_state.ia_dash_time = datetime.min
    
    if "GEMINI_API_KEY" in st.secrets:
        if (agora - st.session_state.ia_dash_time).total_seconds() > 900:
            try:
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                dados_rapidos = f"""
                Hora atual: {agora.strftime('%H:%M')}
                Capacidade rodando: {perc_rodando:.0f}% ({qtd_rodando} de {qtd_total} máquinas).
                Máquinas Paradas: {len(maquinas_paradas_criticas)}. Livres: {qtd_livres}.
                Ofensor/Gargalo do dia: {top_ofensor}.
                """
                
                prompt_ia = f"""Você é o analista do PCP. Leia estes dados muito rápido: {dados_rapidos}
                Escreva UMA ÚNICA FRASE CURTA, encorajadora ou de alerta, para ser exibida num letreiro de TV na fábrica.
                Sem introduções, sem aspas, seja direto. Foque no que é mais crítico ou parabenize se o % estiver alto (acima de 80%)."""
                
                modelo = genai.GenerativeModel(model_name="gemini-3.6-flash")
                resp = modelo.generate_content(prompt_ia)
                st.session_state.ia_dash_msg = resp.text.strip()
                st.session_state.ia_dash_time = agora
            except:
                pass 

    # ==========================================
    # DESENHO DA TELA (LAYOUT 3 COLUNAS)
    # ==========================================
    col_esq, col_meio, col_dir = st.columns([30, 35, 35], gap="medium")

    # 1️⃣ COLUNA ESQUERDA: SAÚDE DA PRODUÇÃO E MÉTRICAS
    with col_esq:
        html_hero = f"""<div style="background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%); color: white; border-radius: 10px; padding: 20px 10px; text-align: center; box-shadow: 0 4px 10px rgba(0,0,0,0.2); margin-bottom: 15px;">
<div style="font-size: 16px; text-transform: uppercase; letter-spacing: 2px; color: #bdc3c7; font-weight: 700; margin-bottom: 5px;">Status da Produção</div>
<div style="font-size: 65px; font-weight: 900; line-height: 1; margin-bottom: 5px; color: #2ecc71;">{perc_rodando:.0f}%</div>
<div style="background: rgba(0,0,0,0.2); border-radius: 8px; padding: 10px; margin-top: 15px;">
<div style="font-size: 14px; font-weight: bold; margin-bottom: 5px;">{qtd_rodando} de {qtd_total} máqs ativas</div>
<div style="display: flex; justify-content: space-around; flex-wrap: wrap; font-size: 12px; font-weight: bold; color: #ecf0f1;">
<span title="Produzindo">🟢 {qtd_rodando} Prod.</span>
<span title="Paradas">🔴 {len(maquinas_paradas_criticas)} Par.</span>
<span title="Pausas">🟠 {len(maquinas_pausas)} Paus.</span>
<span title="Aguardando">🔵 {qtd_livres} Liv.</span>
</div>
</div>
</div>"""
        st.markdown(html_hero, unsafe_allow_html=True)

        if "GEMINI_API_KEY" in st.secrets:
            st.markdown(f"""
            <div style="background-color: #f0f7fb; border-left: 4px solid #2980b9; padding: 12px; border-radius: 5px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                <div style="font-size: 11px; font-weight: 900; color: #2980b9; text-transform: uppercase; margin-bottom: 5px;">🧠 Insight da Inteligência Artificial</div>
                <div style="font-size: 14px; font-weight: 600; color: #2c3e50; line-height: 1.4;">"{st.session_state.ia_dash_msg}"</div>
                <div style="font-size: 9px; color: #bdc3c7; text-align: right; margin-top: 4px;">Atualiza a cada 15 min</div>
            </div>
            """, unsafe_allow_html=True)

        mc1, mc2 = st.columns(2)
        with mc1:
            st.markdown(f"""<div style='background:#fff; padding:10px 5px; border-radius:8px; text-align:center; border: 1px solid #eee; margin-bottom: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); height: 75px;'>
<div style='color:#7f8c8d; font-size: 9px; font-weight: bold; text-transform: uppercase;'>Perdido Hoje</div>
<div style='font-size:18px; font-weight:900; color:#c0392b; margin-top: 5px;'>{h_perdido:02d}h{m_perdido:02d}</div>
</div>""", unsafe_allow_html=True)
            st.markdown(f"""<div style='background:#fff; padding:10px 5px; border-radius:8px; text-align:center; border: 1px solid #eee; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); height: 75px; display: flex; flex-direction: column; justify-content: center;'>
<div style='color:#7f8c8d; font-size: 9px; font-weight: bold; text-transform: uppercase;'>Ofensor Atual</div>
<div style='font-size:13px; font-weight:900; color:#e67e22; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;' title='{top_ofensor}'>{top_ofensor}</div>
</div>""", unsafe_allow_html=True)
        with mc2:
            st.markdown(f"""<div style='background:#fff; padding:10px 5px; border-radius:8px; text-align:center; border: 1px solid #eee; margin-bottom: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); height: 75px;'>
<div style='color:#7f8c8d; font-size: 9px; font-weight: bold; text-transform: uppercase;'>Médio/Sol.</div>
<div style='font-size:18px; font-weight:900; color:#2980b9; margin-top: 5px;'>{mttr_str}</div>
</div>""", unsafe_allow_html=True)
            st.markdown(f"""<div style='background:#fff; padding:8px 5px; border-radius:8px; text-align:center; border: 1px solid #eee; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); height: 75px;'>
<div style='color:#7f8c8d; font-size: 9px; font-weight: bold; text-transform: uppercase;'>Vol. Corte (Hoje)</div>
<div style='font-size:16px; font-weight:900; color:#27ae60; line-height: 1.1; margin-top: 3px;'>{vol_corte_un} un.</div>
<div style='font-size:11px; font-weight:bold; color:#95a5a6;'>{vol_corte_m2:,.1f} m²</div>
</div>""", unsafe_allow_html=True)

        st.markdown("<div style='font-size: 12px; font-weight: bold; color: #7f8c8d; text-transform: uppercase; text-align: center; margin-bottom: 5px;'>Evolução (Ao Vivo)</div>", unsafe_allow_html=True)
        
        ticks_x = []
        curr_tick = hora_inicio_turno.replace(minute=0, second=0, microsecond=0)
        fim_arredondado = hora_fim_turno.replace(minute=0, second=0, microsecond=0)
        if hora_fim_turno.minute > 0: fim_arredondado += timedelta(hours=1)
            
        while curr_tick <= fim_arredondado:
            ticks_x.append(curr_tick.isoformat())
            curr_tick += timedelta(hours=1)

        chart = alt.Chart(df_plot).mark_area(line={'color': '#2980b9'}, color='#2980b9', opacity=0.4).encode(
            x=alt.X('Hora:T', title='', scale=alt.Scale(domain=[hora_inicio_turno.isoformat(), hora_fim_turno.isoformat()]),
                    axis=alt.Axis(values=ticks_x, format='%H', labelExpr="parseInt(datum.label) + 'H'", grid=True)),
            y=alt.Y('Em Operação (%):Q', title='', scale=alt.Scale(domain=[0, 100]), 
                    axis=alt.Axis(values=[0, 25, 50, 75, 100], format='.0f', grid=True)),
            tooltip=['Hora:T', 'Em Operação (%):Q']
        ).properties(height=180)
        st.altair_chart(chart, use_container_width=True)

    # 2️⃣ COLUNA DO MEIO: MAPA VISUAL, CARDS CRONÔMETRO E FEED DE ATIVIDADES
    with col_meio:
        st.markdown("<h3 style='text-align: center; color: #2c3e50; text-transform: uppercase; font-weight: 900; margin-bottom: 15px; font-size: 18px;'>🗺️ Chão de Fábrica</h3>", unsafe_allow_html=True)
        
        lista_js_timers = []
        
        if mapa_visual_dict:
            setores_ordenados = sorted(mapa_visual_dict.keys(), key=lambda s: (ordem_setores.get(s, 999), s))
            html_mapa = "<div style='background: #fff; border-radius: 8px; padding: 12px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); border: 1px solid #eaeaea; margin-bottom: 20px;'>"
            html_mapa += "<div style='display: flex; flex-wrap: wrap; gap: 10px;'>"
            
            for setor in setores_ordenados:
                maquinas_lista = mapa_visual_dict[setor]
                html_mapa += "<div style='flex: 1; min-width: 140px;'>"
                html_mapa += f"<div style='background: #34495e; color: white; padding: 6px; border-radius: 5px; text-align: center; font-weight: bold; font-size: 12px; margin-bottom: 6px;'>{setor}</div>"
                for m in sorted(maquinas_lista, key=lambda x: x['maquina']):
                    cor_fundo = get_color(m['tipo'])
                    html_mapa += f"<div style='background: {cor_fundo}; padding: 4px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; color: white; margin-bottom: 4px; display: flex; justify-content: space-between;'>"
                    html_mapa += f"<span>{m['icone']} {m['maquina']}</span><span style='opacity: 0.8; font-weight: normal; font-size: 10px;'>{m['operadores']}</span></div>"
                html_mapa += "</div>"
            html_mapa += "</div></div>"
            st.markdown(html_mapa, unsafe_allow_html=True)

        if cards_exibicao:
            st.markdown("""<style>
.grid-dash { display: flex; flex-wrap: wrap; gap: 10px; }
.card-dash { flex: 1 1 180px; padding: 12px; border-radius: 8px; color: white; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1); display: flex; flex-direction: column; justify-content: space-between; transition: background-color 0.3s ease; }
.cd-critico { background-color: #8b0000 !important; animation: p-crit 1s infinite alternate; }
@keyframes p-crit { 0% { opacity: 1; } 100% { opacity: 0.8; } }
</style>""", unsafe_allow_html=True)
            
            html_cards = "<div class='grid-dash'>"
            for p in cards_exibicao:
                p_id = f"{p['setor']}_{p['maquina']}".replace(" ", "_").replace("/", "_").strip()
                
                lista_js_timers.append({
                    "id": p_id, 
                    "inicio_iso": str(p['hora_inicio']).replace(" ", "T"),
                    "past_ms": p.get('minutos_acumulados_bd', 0) * 60000,
                    "min_passados": minutos_uteis_passados, # A Régua Universal Aplicada
                    "tipo": p.get('tipo_registro', 'LIVRE')
                })
                
                tipo_reg = p.get('tipo_registro', 'LIVRE')
                cor_card = get_color(tipo_reg)
                
                html_cards += f"<div id='card_{p_id}' class='card-dash' style='background-color: {cor_card};' data-tipo='{tipo_reg}'>"
                html_cards += "<div>" 
                html_cards += f"<div style='font-size:11px; font-weight:bold; opacity:0.9;'>{p.get('setor_exibicao', p['setor'])}</div>"
                html_cards += f"<div style='font-size:18px; font-weight:900; margin-bottom:5px;'>{p['maquina']}</div>"
                html_cards += f"<div style='font-size:11px; height:30px; overflow:hidden;'>{p['descricao_completa']}</div>"
                html_cards += p.get('html_progresso', '')
                html_cards += "</div>" 
                html_cards += f"<div id='timer_{p_id}' style='font-size:24px; font-weight:bold; font-family:monospace; background:rgba(0,0,0,0.2); border-radius:5px 5px 0 0; margin-top:auto; padding: 6px 0 2px 0;'>00:00:00</div>"
                html_cards += f"<div id='sub_timer_{p_id}' style='font-size:11px; font-style:italic; opacity:0.85; background:rgba(0,0,0,0.2); border-radius:0 0 5px 5px; padding: 0 0 6px 0; margin-top:0px;'>Calculando...</div>"
                html_cards += "</div>"
            html_cards += "</div>"
            st.markdown(html_cards, unsafe_allow_html=True)

        if not df_nuvem_operacao.empty:
            df_feed = df_nuvem_operacao.copy()
            if 'id' in df_feed.columns:
                df_feed = df_feed.sort_values('id', ascending=False).head(10)
            else:
                df_feed = df_feed.tail(10).iloc[::-1]
                
            if not df_feed.empty:
                html_feed = "<h4 style='color: #2c3e50; font-size: 14px; text-transform: uppercase; font-weight: 900; margin-top: 25px; margin-bottom: 12px; text-align: center;'>⚡ Últimas Produções</h4>"
                
                html_feed += "<div style='display: grid; grid-template-columns: 1fr 1fr; gap: 10px;'>"
                
                for _, row in df_feed.iterrows():
                    peca_raw = str(row.get('nome_peca', 'Desconhecida')).strip()
                    produto_nome = "Produto Desconhecido"
                    
                    if '➔' in peca_raw: 
                        produto_nome = peca_raw.split('➔')[0].strip()
                        peca_nome = peca_raw.split('➔')[1].strip()
                    elif '->' in peca_raw: 
                        produto_nome = peca_raw.split('->')[0].strip()
                        peca_nome = peca_raw.split('->')[1].strip()
                    else: 
                        peca_nome = peca_raw
                        
                    cod_peca = str(row.get('cod_peca', '')).strip()
                    qtd = int(pd.to_numeric(row.get('quantidade', 0), errors='coerce'))
                    das = str(row.get('das', '00:00')).strip()
                    as_hora = str(row.get('as_hora', '00:00')).strip()
                    maquina_nome = str(row.get('maquina', 'Máquina')).strip()
                    operador_nome = str(row.get('operador', 'Sem Operador')).strip()
                    setor_feed = str(row.get('setor', '')).strip().upper()
                    
                    das_f = das[:5] if len(das) >= 5 else das
                    as_hora_f = as_hora[:5] if len(as_hora) >= 5 else as_hora
                    
                    if produto_nome == "Produto Desconhecido" and cod_peca:
                        if setor_feed == 'EMBALAGEM':
                            if not df_caixas.empty:
                                f_cx = df_caixas[df_caixas['cod_caixa'].astype(str) == cod_peca]
                                if not f_cx.empty:
                                    produto_nome = str(f_cx.iloc[0].get('produto_formula', 'Produto Desconhecido'))
                        else:
                            if not df_produtos.empty:
                                f_prod = df_produtos[df_produtos['cod'].astype(str) == cod_peca]
                                if not f_prod.empty:
                                    produto_nome = str(f_prod.iloc[0].get('produto_formula', 'Produto Desconhecido'))
                            
                    html_feed += f"""<div style='background: #fff; padding: 8px 10px; border-radius: 6px; border-left: 4px solid #27ae60; box-shadow: 0 1px 2px rgba(0,0,0,0.05); border: 1px solid #f1f2f6; display: flex; flex-direction: column;'>
<div style='display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px; gap: 5px;'>
<div style='overflow: hidden;'>
<div style='white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 12px; color: #2c3e50;'><b>{produto_nome}</b></div>
<div style='white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 11px; color: #7f8c8d; margin-top: 1px;'>{peca_nome}</div>
</div>
<div style='font-size: 12px; font-weight: 900; color: #27ae60; white-space: nowrap; background: #eafaf1; padding: 3px 6px; border-radius: 4px; flex-shrink: 0;'>
+{qtd} pçs
</div>
</div>
<div style='font-size: 10px; color: #95a5a6; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; border-top: 1px dashed #eee; padding-top: 4px;'>
{das_f} ➔ {as_hora_f} &nbsp;•&nbsp; 🛠️ {maquina_nome} / {operador_nome}
</div>
</div>"""
                html_feed += "</div>"
                st.markdown(html_feed, unsafe_allow_html=True)

    # 3️⃣ COLUNA DA DIREITA: HISTÓRICO INDIVIDUAL & CORRIDA DAS OPS
    with col_dir:
        st.markdown("<h3 style='text-align: center; color: #2c3e50; text-transform: uppercase; font-weight: 900; margin-bottom: 15px; font-size: 18px;'>📊 Histórico Individual</h3>", unsafe_allow_html=True)
        
        total_timeline_min = max(1, t_as_min - m_das_min)
        pares_ativos_hoje = set()
        if not df_hoje.empty:
            for _, r in df_hoje.iterrows(): pares_ativos_hoje.add((str(r.get('setor', '')).strip(), str(r.get('maquina', '')).strip()))
        for (setor, maq), info_maq in status_dict.items():
            if info_maq.get('status') in ['Produzindo', 'Parado']: pares_ativos_hoje.add((setor, maq))
                
        setores_dict_timeline = {}
        for setor, maq in pares_maquinas:
            if (setor, maq) in pares_ativos_hoje:
                if setor not in setores_dict_timeline: setores_dict_timeline[setor] = []
                setores_dict_timeline[setor].append(maq)
        for s in setores_dict_timeline: setores_dict_timeline[s] = sorted(setores_dict_timeline[s])

        if setores_dict_timeline:
            html_timelines = ""
            for setor in sorted(setores_dict_timeline.keys(), key=lambda s: (ordem_setores.get(s, 999), s)):
                html_timelines += f"<div style='font-size: 13px; color: #7f8c8d; font-weight: 900; text-transform: uppercase; border-bottom: 2px solid #ecf0f1; margin-bottom: 5px; padding-bottom: 4px;'>🏭 {setor}</div>"
                
                html_timelines += "<div style='display: flex; align-items: center; gap: 8px; margin-bottom: 4px;'>"
                html_timelines += "<div style='width: 80px;'></div>" 
                html_timelines += "<div style='flex-grow: 1; position: relative; height: 15px; font-size: 10px; color: #95a5a6; font-weight: bold;'>"
                html_timelines += f"<div style='position: absolute; left: 0%; transform: translateX(0%); top: 0px;'>{m_das}</div>"
                for m in range(total_timeline_min):
                    curr = m_das_min + m
                    pct = (m / total_timeline_min) * 100
                    if abs(curr - m_das_min) < 15 or abs(curr - m_as_min) < 15 or abs(curr - t_das_min) < 15 or abs(curr - t_as_min) < 15: continue
                    if curr % 60 == 0: html_timelines += f"<div style='position: absolute; left: {pct}%; transform: translateX(-50%); top: 0px;'>{curr//60}h</div>"
                    elif curr % 60 == 30: html_timelines += f"<div style='position: absolute; left: {pct}%; top: 4px; width: 1px; height: 4px; background-color: #bdc3c7;'></div>"
                pct_as_m = ((m_as_min - m_das_min) / total_timeline_min) * 100
                pct_das_t = ((t_das_min - m_das_min) / total_timeline_min) * 100
                html_timelines += f"<div style='position: absolute; left: {pct_as_m}%; transform: translateX(-50%); top: 0px;'>{m_as}</div>"
                html_timelines += f"<div style='position: absolute; left: {pct_das_t}%; transform: translateX(-50%); top: 0px;'>{t_das}</div>"
                html_timelines += f"<div style='position: absolute; left: 100%; transform: translateX(-100%); top: 0px;'>{t_as}</div>"
                html_timelines += "</div>"
                html_timelines += "<div style='min-width: 90px;'></div>" 
                html_timelines += "</div>"

                for maq in setores_dict_timeline[setor]:
                    timeline = ['A REALIZAR'] * total_timeline_min
                    for i in range(total_timeline_min):
                        curr = m_das_min + i
                        if curr >= m_as_min and curr < t_das_min: timeline[i] = 'INTERVALO PREVISTO'
                        elif lm_das_min != -1 and curr >= lm_das_min and curr < lm_as_min: timeline[i] = 'INTERVALO PREVISTO'
                        elif lt_das_min != -1 and curr >= lt_das_min and curr < lt_as_min: timeline[i] = 'INTERVALO PREVISTO'
                        elif curr > agora_min: timeline[i] = 'A REALIZAR' 
                        elif (curr >= m_das_min and curr < m_as_min) or (curr >= t_das_min and curr < t_as_min): timeline[i] = 'LIVRE'
                            
                    if not df_hoje.empty:
                        for _, row in df_hoje[(df_hoje['maquina'] == maq) & (df_hoje['setor'] == setor)].iterrows():
                            if pd.notna(row.get('das')) and pd.notna(row.get('as_hora')):
                                for m in range(calcular_minutos_str(row['das']), calcular_minutos_str(row['as_hora'])):
                                    idx = m - m_das_min
                                    tipo_reg = str(row.get('tipo', 'PARADA')).strip().upper()
                                    if 'DESCONSIDERAR' in tipo_reg: tipo_reg = 'NÃO CONTA'
                                    if 0 <= idx < total_timeline_min: timeline[idx] = tipo_reg
                                    
                    info_maq = status_dict.get((setor, maq), {})
                    if info_maq.get('status') in ['Produzindo', 'Parado']:
                        try:
                            if datetime.strptime(info_maq['hora_inicio'], "%Y-%m-%d %H:%M:%S").date() == agora.date():
                                h_i = datetime.strptime(info_maq['hora_inicio'], "%Y-%m-%d %H:%M:%S")
                                tipo_linha = 'PRODUÇÃO' if info_maq.get('status') == 'Produzindo' else 'PARADA'
                                if tipo_linha == 'PARADA' and info_maq.get('cod_ocorrencia') and not df_codigos.empty:
                                    f_cod = df_codigos[df_codigos['codigo'].astype(str) == str(info_maq.get('cod_ocorrencia')).strip()]
                                    if not f_cod.empty and 'tipo' in f_cod.columns:
                                        tipo_linha = str(f_cod.iloc[0]['tipo']).strip().upper()
                                        if 'DESCONSIDERAR' in tipo_linha: tipo_linha = 'NÃO CONTA'
                                for m in range(h_i.hour * 60 + h_i.minute, agora_min + 1):
                                    if 0 <= m - m_das_min < total_timeline_min: timeline[m - m_das_min] = tipo_linha
                        except: pass

                    segments = []
                    curr_type, curr_len = timeline[0], 1
                    for i in range(1, total_timeline_min):
                        if timeline[i] == curr_type: curr_len += 1
                        else:
                            segments.append((curr_type, curr_len))
                            curr_type, curr_len = timeline[i], 1
                    segments.append((curr_type, curr_len))
                    
                    html_timelines += "<div style='display: flex; align-items: center; margin-bottom: 6px; gap: 8px; background: #fff; padding: 4px 8px; border-radius: 4px; border: 1px solid #eaeaea; box-shadow: 0 1px 3px rgba(0,0,0,0.02);'>"
                    html_timelines += f"<div style='width: 80px; font-size: 11px; font-weight: 800; color: #34495e; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;' title='{maq}'>{maq}</div>"
                    
                    # LINHA DE PROGRESSO DO GRÁFICO (Mantém o visual esticado do dia todo)
                    html_timelines += "<div style='flex-grow: 1; display: flex; height: 12px; border-radius: 3px; overflow: hidden;'>"
                    for stype, slen in segments:
                        html_timelines += f"<div style='width:{(slen/total_timeline_min)*100}%; background-color:{get_color(stype)};' title='{get_friendly_name(stype)}'></div>"
                    html_timelines += "</div>"
                    
                    # CÁLCULO CIRÚRGICO DA % (USANDO A RÉGUA UNIVERSAL DE TEMPO ÚTIL PASSADO)
                    counts_passados = {}
                    base_matematica = 0
                    
                    for i in range(total_timeline_min):
                        curr = m_das_min + i
                        if curr >= agora_min: break # Ignora completamente o futuro
                        
                        stype = timeline[i]
                        # Ignora os lanches/pausas para o cálculo da base de 100% útil
                        if stype != 'INTERVALO PREVISTO' and 'NÃO CONTA' not in stype:
                            counts_passados[stype] = counts_passados.get(stype, 0) + 1
                            base_matematica += 1
                            
                    if base_matematica <= 0: base_matematica = 1 # Proteção
                    
                    itens_c = []
                    for stype, slen in counts_passados.items():
                        if slen > 0:
                            itens_c.append(((slen/base_matematica)*100, stype))
                            
                    # REMOVIDO O LIMITE DE 3 ITENS (Para fechar 100% exato e bater com o Card)
                    html_timelines += "<div style='display: flex; gap: 6px; font-size: 10px; font-weight: bold; color: #2c3e50; min-width: 90px; justify-content: flex-end; flex-wrap: wrap;'>"
                    for pct_val, stype in sorted(itens_c, key=lambda x: x[0], reverse=True): 
                        cor = get_color(stype)
                        brd = "border:1px solid #ccc;" if cor.upper() in ["#ECF0F1", "#FFFFFF", "#BDC3C7"] else ""
                        html_timelines += f"<div style='display: flex; align-items: center; gap: 3px;' title='{get_friendly_name(stype)}'><div style='width:8px;height:8px;background:{cor};border-radius:50%;{brd}'></div>{pct_val:.0f}%</div>"
                    html_timelines += "</div></div>"
                    
            st.markdown(html_timelines, unsafe_allow_html=True)
            
            tipos_exibicao_legenda = set(['LIVRE', 'PRODUÇÃO', 'PARADA', 'NÃO CONTA', 'INTERVALO PREVISTO', 'A REALIZAR'])
            for k in mapa_cores.keys(): tipos_exibicao_legenda.add(k)
            html_legenda = "<div style='display: flex; justify-content: center; flex-wrap: wrap; gap: 15px; font-size: 10px; font-weight: bold; color: #555; padding-top: 5px; margin-bottom: 25px;'>"
            for stype in sorted(tipos_exibicao_legenda):
                c_hex = get_color(stype)
                border = "border: 1px solid #ccc;" if c_hex.upper() in ["#ECF0F1", "#FFFFFF", "#BDC3C7"] else ""
                html_legenda += f"<div style='display: flex; align-items: center; gap: 4px;'><div style='width:10px; height:10px; background:{c_hex}; border-radius:2px; {border}'></div> {get_friendly_name(stype)}</div>"
            html_legenda += "</div>"
            st.markdown(html_legenda, unsafe_allow_html=True)
            
        if ops_ativas:
            st.markdown("<h3 style='text-align: center; color: #2c3e50; text-transform: uppercase; font-weight: 900; margin-bottom: 15px; font-size: 18px;'>🏁 A Corrida DAS OPS</h3>", unsafe_allow_html=True)
            html_ops = "<div>"
            
            for op in ops_ativas:
                nome_op = op['produto_formula']
                qtd_plan = int(op.get('quantidade_planejada', 0))
                data_op_dt = pd.to_datetime(op['data_inicio'].split(" ")[0].split("T")[0])
                
                df_filtrado = df_produtos[df_produtos['produto_formula'] == nome_op]
                
                mapa_prod = {}
                if not df_todas_producoes.empty:
                    df_op_prod = df_todas_producoes[df_todas_producoes['data_registro_dt'] >= data_op_dt]
                    agrup = df_op_prod.groupby(['setor', 'cod_peca'])['quantidade'].sum().reset_index()
                    for _, r in agrup.iterrows(): mapa_prod[(r['setor'], r['cod_peca'])] = int(r['quantidade'])
                
                meta_global = 0
                prod_global = 0
                
                for _, row in df_filtrado.iterrows():
                    try: qnt_peca = int(float(row.get('qnt', 0)))
                    except: qnt_peca = 0
                    qtd_total = qnt_peca * qtd_plan
                    cod = str(row.get('cod', '')).strip()
                    
                    def get_p(s): return mapa_prod.get((s.upper(), cod), 0)
                    
                    meta_global += qtd_total
                    prod_global += min(qtd_total, get_p('Corte'))
                    
                    f_m = str(row.get('fita_mais', '')).replace('.0', '').strip()
                    f_mn = str(row.get('fita_menos', '')).replace('.0', '').strip()
                    if f_m in ['1', '2', '*'] or f_mn in ['1', '2', '*']:
                        meta_global += qtd_total
                        prod_global += min(qtd_total, get_p('Coladeira'))
                        
                    if str(row.get('furadeira', '')).strip().upper() == 'SIM':
                        meta_global += qtd_total
                        prod_global += min(qtd_total, get_p('Furadeira'))
                        
                    lp = str(row.get('lp', '')).replace('.0', '').strip()
                    if lp in ['1', '2']:
                        meta_global += qtd_total
                        prod_global += min(qtd_total, get_p('Pintura'))

                if not df_caixas.empty:
                    df_cx_filtrado = df_caixas[df_caixas['produto_formula'] == nome_op]
                    for _, row_cx in df_cx_filtrado.iterrows():
                        cod_cx = str(row_cx.get('cod_caixa', '')).strip()
                        if cod_cx and cod_cx not in ["", "None", "nan"]:
                            meta_global += qtd_plan
                            prod_cx_real = mapa_prod.get(('EMBALAGEM', cod_cx), 0)
                            prod_global += min(qtd_plan, prod_cx_real)

                perc_op = min(100, (prod_global / meta_global * 100)) if meta_global > 0 else 0
                
                html_ops += f"""
                <div style='margin-bottom: 12px;'>
                    <div style='display: flex; justify-content: space-between; font-size: 11px; font-weight: bold; color: #34495e; margin-bottom: 3px;'>
                        <span>📦 {nome_op}</span><span>{perc_op:.1f}% ({int(prod_global)}/{int(meta_global)})</span>
                    </div>
                    <div style='width: 100%; background: #ecf0f1; height: 12px; border-radius: 6px; overflow: hidden; border: 1px solid #bdc3c7;'>
                        <div style='width: {perc_op}%; background: #e74c3c; height: 100%; transition: width 0.5s ease;'></div>
                    </div>
                </div>"""
            html_ops += "</div>"
            st.markdown(html_ops, unsafe_allow_html=True)

    # ==========================================
    # RODAPÉ E JAVASCRIPT FIXOS
    # ==========================================
    st.markdown(f"""
    <div style="position: fixed; bottom: 0; left: 0; width: 100%; background-color: #34495e; color: white; padding: 10px 0; z-index: 9998; box-shadow: 0 -2px 10px rgba(0,0,0,0.2);">
        <marquee scrollamount="{vel_barra}" style="font-size: 16px; font-weight: 600; letter-spacing: 1px;">{texto_letreiro}</marquee>
    </div>
    <div style="height: 50px;"></div>
    """, unsafe_allow_html=True)

    json_timers = json.dumps(lista_js_timers)
    stamp_agora = time.time()
    
    js_engine = f"""
    <script>
        // Stamp: {stamp_agora}
        setInterval(function() {{
            const btns = window.parent.document.querySelectorAll('button');
            for (let i = 0; i < btns.length; i++) {{
                if (btns[i].innerText === '🔄 Atualizar' || btns[i].innerText.includes('Atualizar')) {{ 
                    btns[i].click(); 
                    break; 
                }}
            }}
        }}, {refresh_segundos * 1000});

        function playBeep() {{
            try {{
                const ctx = new (window.AudioContext || window.webkitAudioContext)(); 
                const osc = ctx.createOscillator(); const gain = ctx.createGain();
                osc.connect(gain); gain.connect(ctx.destination);
                osc.type = 'sine'; osc.frequency.value = 750; 
                gain.gain.setValueAtTime(0, ctx.currentTime); gain.gain.linearRampToValueAtTime(0.3, ctx.currentTime + 0.1); gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.6);
                osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.6);
            }} catch(e) {{}}
        }}

        const timers = {json_timers};
        const tempoCriticoMs = {tempo_critico} * 60 * 1000;
        
        if (timers.length > 0) {{
            setInterval(() => {{
                const now = new Date().getTime();
                timers.forEach(p => {{
                    const distance = now - new Date(p.inicio_iso).getTime();
                    if (distance > 0) {{
                        const h = Math.floor(distance / 3600000); const m = Math.floor((distance % 3600000) / 60000); const s = Math.floor((distance % 60000) / 1000);
                        const tel = window.parent.document.getElementById("timer_" + p.id);
                        if (tel) tel.innerHTML = (h<10?"0":"")+h + ":" + (m<10?"0":"")+m + ":" + (s<10?"0":"")+s;
                        
                        // LÓGICA DO SUBTOTAL ACUMULADO AO VIVO
                        const subTel = window.parent.document.getElementById("sub_timer_" + p.id);
                        if (subTel) {{
                            const totalMs = distance + p.past_ms;
                            const totalMin = Math.floor(totalMs / 60000);
                            let perc = 0;
                            if (p.min_passados > 0) {{
                                perc = (totalMin / p.min_passados) * 100;
                            }}
                            if (perc > 100) perc = 100;
                            
                            let prefix = "";
                            if (p.tipo === "PRODUÇÃO") prefix = "Tempo trabalhado hoje: ";
                            else if (p.tipo === "PARADA") prefix = "Total parado hoje: ";
                            else if (p.tipo === "ROTINA") prefix = "Total rotina hoje: ";
                            else if (p.tipo === "RETRABALHO") prefix = "Total retrabalho hoje: ";
                            else if (p.tipo === "NÃO CONTA" || p.tipo === "INTERVALO PREVISTO") prefix = "Total em pausa hoje: ";
                            else prefix = "Acumulado hoje: ";
                            
                            let tempoStr = "";
                            const h_tot = Math.floor(totalMin / 60);
                            const m_tot = totalMin % 60;
                            if (h_tot > 0) tempoStr = h_tot + "h" + (m_tot < 10 ? "0":"") + m_tot + "m";
                            else tempoStr = m_tot + " min";
                            
                            subTel.innerHTML = prefix + tempoStr + " (" + perc.toFixed(1) + "%)";
                        }}
                        
                        const cel = window.parent.document.getElementById("card_" + p.id);
                        if (cel && distance >= tempoCriticoMs && !cel.classList.contains("cd-critico")) {{
                            const tipoReg = cel.getAttribute("data-tipo");
                            if (tipoReg !== "NÃO CONTA" && tipoReg !== "PRODUÇÃO" && tipoReg !== "LIVRE") {{
                                cel.classList.add("cd-critico"); 
                                playBeep();
                            }}
                        }}
                    }}
                }});
            }}, 1000);
        }}
    </script>
    """
    components.html(js_engine, height=0)