import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import banco
import streamlit.components.v1 as components
import json
import altair as alt
import time

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

    codigos_pausa = []
    if not df_codigos.empty and 'tipo' in df_codigos.columns:
        mask_pausa = df_codigos['tipo'].astype(str).str.strip().str.upper().isin(['NÃO CONTA', 'DESNCONSIDERAR', 'DESCONSIDERAR'])
        codigos_pausa = df_codigos[mask_pausa]['codigo'].astype(str).str.strip().tolist()

    total_min_turno = max(0, m_as_min - m_das_min) + max(0, t_as_min - t_das_min)
    if total_min_turno <= 0: total_min_turno = 1
    
    min_passados = 0
    for m in range(m_das_min, agora_min):
        if (m >= m_das_min and m < m_as_min) or (m >= t_das_min and m < t_as_min): min_passados += 1
            
    perc_turno = (min_passados / total_min_turno) * 100
    if perc_turno > 100: perc_turno = 100

    st.markdown(f"""<div style="width: 100%; background-color: #e0e0e0; height: 6px; overflow: hidden; margin-bottom: 15px; border-radius: 3px;">
<div style="width: {perc_turno:.1f}%; background-color: #2980b9; height: 100%;"></div>
</div>""", unsafe_allow_html=True)

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
    if not df_nuvem.empty and 'data_registro' in df_nuvem.columns and 'tipo' in df_nuvem.columns:
        df_nuvem_operacao = df_nuvem[df_nuvem['tipo'].astype(str).str.strip().str.upper() == 'PRODUÇÃO'].copy()
        if not df_nuvem_operacao.empty:
            df_nuvem_operacao['data_registro_dt'] = pd.to_datetime(df_nuvem_operacao['data_registro'], errors='coerce')
            df_nuvem_operacao['quantidade_num'] = pd.to_numeric(df_nuvem_operacao['quantidade'], errors='coerce').fillna(0)

    # --- INÍCIO DA PREPARAÇÃO DOS DADOS PARA O ETA E CORRIDA DAS OPS (LÓGICA CORRETA IMPORTADA) ---
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
            desc = str(df_codigos[df_codigos['codigo'].astype(str) == str(cod)].iloc[0]['descricao']) if cod and not df_codigos.empty and not df_codigos[df_codigos['codigo'].astype(str) == str(cod)].empty else "Desconhecido"
            info['descricao_completa'] = f"{desc} ({cod})"
            info['is_pausa'] = str(cod).strip() in codigos_pausa
            if info['is_pausa']:
                maquinas_pausas.append(info)
                classe_mapa, icone_mapa = "cd-pausa", "🟠"
            else:
                maquinas_paradas_criticas.append(info)
                classe_mapa, icone_mapa = "cd-parado", "🔴"
                try:
                    h_ini = datetime.strptime(info['hora_inicio'], "%Y-%m-%d %H:%M:%S")
                    if h_ini.date() == agora.date():
                        for m in range(h_ini.hour * 60 + h_ini.minute, agora_min + 1):
                            if (m >= m_das_min and m < m_as_min) or (m >= t_das_min and m < t_as_min): minutos_ativos_perdidos += 1
                except: pass
        elif status_maq == 'Produzindo':
            qtd_rodando += 1
            classe_mapa, icone_mapa = "cd-prod", "🟢"
            cod_peca = info.get('cod_peca_atual')
            nome_peca_completo, html_progresso = "Peça Desconhecida", ""
            if cod_peca and not df_produtos.empty:
                f_peca = df_produtos[df_produtos['cod'].astype(str) == str(cod_peca)]
                if not f_peca.empty:
                    prod_form = f_peca.iloc[0]['produto_formula']
                    nome_peca_completo = f"{prod_form} ➔ {f_peca.iloc[0]['descricao']}"
                    if prod_form in ops_dict:
                        op_data = ops_dict[prod_form]
                        meta_peca = int(op_data['quantidade_planejada']) * int(float(f_peca.iloc[0].get('qnt', 0)))
                        if meta_peca > 0:
                            prod_realizada = 0
                            if not df_nuvem_operacao.empty:
                                data_inicio_op_dt = pd.to_datetime(op_data['data_inicio'].split(" ")[0], errors='coerce')
                                mask_todas_op = (df_nuvem_operacao['cod_peca'].astype(str).str.strip() == str(cod_peca)) & (df_nuvem_operacao['setor'].astype(str).str.strip().str.upper() == setor.upper()) & (df_nuvem_operacao['data_registro_dt'] >= data_inicio_op_dt)
                                prod_realizada = int(df_nuvem_operacao[mask_todas_op]['quantidade_num'].sum())
                            
                            # Trava de segurança (min) para não deixar a barra individual passar de 100%
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
            qtd_livres += 1
            classe_mapa, icone_mapa = "cd-livre", "🔵"
            
        mapa_visual_dict[setor].append({"maquina": maq, "operadores": operadores_texto, "classe": classe_mapa, "icone": icone_mapa})

    cards_exibicao = maquinas_paradas_criticas + maquinas_pausas + maquinas_produzindo
    qtd_total = len(pares_maquinas)
    perc_rodando = (qtd_rodando / qtd_total) * 100 if qtd_total > 0 else 0

    df_hoje = df_nuvem[(df_nuvem['data_registro'] == hoje_str)].copy() if not df_nuvem.empty and 'maquina' in df_nuvem.columns else pd.DataFrame()
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

    # 2️⃣ COLUNA DO MEIO: MAPA VISUAL E CARDS CRONÔMETRO
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
                    cor_fundo = "#27ae60" if m['classe'] == "cd-prod" else ("#e74c3c" if m['classe'] == "cd-parado" else ("#f39c12" if m['classe'] == "cd-pausa" else "#3498db"))
                    html_mapa += f"<div style='background: {cor_fundo}; padding: 4px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; color: white; margin-bottom: 4px; display: flex; justify-content: space-between;'>"
                    html_mapa += f"<span>{m['icone']} {m['maquina']}</span><span style='opacity: 0.8; font-weight: normal; font-size: 10px;'>{m['operadores']}</span></div>"
                html_mapa += "</div>"
            html_mapa += "</div></div>"
            st.markdown(html_mapa, unsafe_allow_html=True)

        if cards_exibicao:
            st.markdown("""<style>
.grid-dash { display: flex; flex-wrap: wrap; gap: 10px; }
.card-dash { flex: 1 1 180px; padding: 12px; border-radius: 8px; color: white; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1); display: flex; flex-direction: column; justify-content: space-between; }
.cd-prod { background-color: #27ae60; } .cd-parado { background-color: #e74c3c; } .cd-pausa { background-color: #f39c12; } .cd-livre { background-color: #3498db; }
.cd-critico { background-color: #8b0000; animation: p-crit 1s infinite alternate; }
@keyframes p-crit { 0% { opacity: 1; } 100% { opacity: 0.8; } }
</style>""", unsafe_allow_html=True)
            
            html_cards = "<div class='grid-dash'>"
            for p in cards_exibicao:
                p_id = f"{p['setor']}_{p['maquina']}".replace(" ", "_").replace("/", "_").strip()
                lista_js_timers.append({"id": p_id, "inicio_iso": str(p['hora_inicio']).replace(" ", "T")})
                status_maq = p.get('status', 'Livre')
                classe_card = "cd-prod" if status_maq == 'Produzindo' else ("cd-pausa" if p.get('is_pausa') else "cd-parado")
                
                html_cards += f"<div id='card_{p_id}' class='card-dash {classe_card}'>"
                html_cards += "<div>" 
                html_cards += f"<div style='font-size:11px; font-weight:bold; opacity:0.9;'>{p.get('setor_exibicao', p['setor'])}</div>"
                html_cards += f"<div style='font-size:18px; font-weight:900; margin-bottom:5px;'>{p['maquina']}</div>"
                html_cards += f"<div style='font-size:11px; height:30px; overflow:hidden;'>{p['descricao_completa']}</div>"
                html_cards += p.get('html_progresso', '')
                html_cards += "</div>" 
                html_cards += f"<div id='timer_{p_id}' style='font-size:24px; font-weight:bold; font-family:monospace; background:rgba(0,0,0,0.2); border-radius:5px; margin-top:auto; padding: 4px 0;'>00:00:00</div>"
                html_cards += "</div>"
            html_cards += "</div>"
            st.markdown(html_cards, unsafe_allow_html=True)

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
                    
                    html_timelines += "<div style='flex-grow: 1; display: flex; height: 12px; border-radius: 3px; overflow: hidden;'>"
                    counts_minutos = {}
                    for stype, slen in segments:
                        html_timelines += f"<div style='width:{(slen/total_timeline_min)*100}%; background-color:{get_color(stype)};' title='{get_friendly_name(stype)}'></div>"
                        counts_minutos[stype] = counts_minutos.get(stype, 0) + slen
                    html_timelines += "</div>"
                    
                    min_nao_conta = sum(slen for stype, slen in counts_minutos.items() if stype == 'INTERVALO PREVISTO' or 'NÃO CONTA' in stype)
                    base_100 = max(1, total_timeline_min - min_nao_conta)
                    
                    itens_c = []
                    for stype, slen in counts_minutos.items():
                        if slen > 0 and stype != 'INTERVALO PREVISTO' and 'NÃO CONTA' not in stype:
                            itens_c.append(((slen/base_100)*100, stype))
                            
                    html_timelines += "<div style='display: flex; gap: 6px; font-size: 10px; font-weight: bold; color: #2c3e50; min-width: 90px; justify-content: flex-end;'>"
                    for pct_val, stype in sorted(itens_c, key=lambda x: x[0], reverse=True)[:3]: 
                        cor = get_color(stype)
                        brd = "border:1px solid #ccc;" if cor.upper() in ["#ECF0F1", "#FFFFFF", "#BDC3C7"] else ""
                        html_timelines += f"<div style='display: flex; align-items: center; gap: 3px;' title='{get_friendly_name(stype)}'><div style='width:8px;height:8px;background:{cor};border-radius:50%;{brd}'></div>{pct_val:.0f}%</div>"
                    html_timelines += "</div></div>"
                    
            st.markdown(html_timelines, unsafe_allow_html=True)
            
            # --- LEGENDA GLOBAL ÚNICA ---
            tipos_exibicao_legenda = set(['LIVRE', 'PRODUÇÃO', 'PARADA', 'NÃO CONTA', 'INTERVALO PREVISTO', 'A REALIZAR'])
            for k in mapa_cores.keys(): tipos_exibicao_legenda.add(k)
            html_legenda = "<div style='display: flex; justify-content: center; flex-wrap: wrap; gap: 15px; font-size: 10px; font-weight: bold; color: #555; padding-top: 5px; margin-bottom: 25px;'>"
            for stype in sorted(tipos_exibicao_legenda):
                c_hex = get_color(stype)
                border = "border: 1px solid #ccc;" if c_hex.upper() in ["#ECF0F1", "#FFFFFF", "#BDC3C7"] else ""
                html_legenda += f"<div style='display: flex; align-items: center; gap: 4px;'><div style='width:10px; height:10px; background:{c_hex}; border-radius:2px; {border}'></div> {get_friendly_name(stype)}</div>"
            html_legenda += "</div>"
            st.markdown(html_legenda, unsafe_allow_html=True)
            
        # --- A CORRIDA DAS OPS (AGORA COM A MATEMÁTICA CORRETA IMPORTADA DO PAINEL) ---
        if ops_ativas:
            st.markdown("<h3 style='text-align: center; color: #2c3e50; text-transform: uppercase; font-weight: 900; margin-bottom: 15px; font-size: 18px;'>🏁 A Corrida das OPs</h3>", unsafe_allow_html=True)
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
                
                # LOOP DAS PEÇAS (Com trava de proteção antimáscara)
                for _, row in df_filtrado.iterrows():
                    try: qnt_peca = int(float(row.get('qnt', 0)))
                    except: qnt_peca = 0
                    qtd_total = qnt_peca * qtd_plan
                    cod = str(row.get('cod', '')).strip()
                    
                    def get_p(s): return mapa_prod.get((s.upper(), cod), 0)
                    
                    # Corte
                    meta_global += qtd_total
                    prod_global += min(qtd_total, get_p('Corte'))
                    
                    # Coladeira
                    f_m = str(row.get('fita_mais', '')).replace('.0', '').strip()
                    f_mn = str(row.get('fita_menos', '')).replace('.0', '').strip()
                    if f_m in ['1', '2', '*'] or f_mn in ['1', '2', '*']:
                        meta_global += qtd_total
                        prod_global += min(qtd_total, get_p('Coladeira'))
                        
                    # Furadeira
                    if str(row.get('furadeira', '')).strip().upper() == 'SIM':
                        meta_global += qtd_total
                        prod_global += min(qtd_total, get_p('Furadeira'))
                        
                    # Pintura
                    lp = str(row.get('lp', '')).replace('.0', '').strip()
                    if lp in ['1', '2']:
                        meta_global += qtd_total
                        prod_global += min(qtd_total, get_p('Pintura'))

                # LOOP DAS CAIXAS
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
                        
                        const cel = window.parent.document.getElementById("card_" + p.id);
                        if (cel && distance >= tempoCriticoMs && !cel.classList.contains("cd-critico") && !cel.classList.contains("cd-pausa") && !cel.classList.contains("cd-prod")) {{
                            cel.classList.remove("cd-parado"); cel.classList.add("cd-critico"); playBeep();
                        }}
                    }}
                }});
            }}, 1000);
        }}
    </script>
    """
    components.html(js_engine, height=0)