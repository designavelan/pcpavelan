import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import banco
import streamlit.components.v1 as components
import json

# Importando os novos submódulos
import dashboard_coluna_1
import dashboard_coluna_2

def obter_hora_atual():
    return datetime.utcnow() - timedelta(hours=3)

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

def aplicar_abreviacoes(texto, df_abrev, todas_vazias=False):
    """Varre o dicionário e aplica as regras de encurtamento no texto."""
    if pd.isna(texto) or not str(texto).strip() or df_abrev.empty:
        return texto
    txt_final = str(texto)
    for _, row in df_abrev.iterrows():
        orig = str(row['texto_original']).strip()
        
        if todas_vazias:
            sub = ""
        else:
            sub = str(row['texto_substituto']).strip() if pd.notna(row['texto_substituto']) else ""
            
        if orig:
            txt_final = txt_final.replace(orig, sub)
    return " ".join(txt_final.split())

def renderizar(df_nuvem, df_codigos, filtros_selecionados):
    
    def calcular_minutos_str(hora_str):
        try: return int(hora_str.split(':')[0]) * 60 + int(hora_str.split(':')[1])
        except: return 0

    def formatar_minutos(minutos):
        h = int(minutos // 60)
        m = int(minutos % 60)
        if h > 0: return f"{h}:{m:02d}h"
        return f"{m}m"

    supa = banco.conectar()
    cfg = banco.obter_configuracoes()
    
    usuario_logado = st.session_state.get('usuario_logado', {})
    is_dark = bool(usuario_logado.get('modo_escuro', False))

    if is_dark:
        css_tema = """
        :root {
            --bg-main: #0e1117;
            --bg-card: #1e1e1e;
            --text-main: #ffffff;
            --text-muted: #aaaaaa;
            --border-color: #333333;
            --bg-sem-op: #2a2a2a;
            --text-sem-op: #7f8c8d;
            --bg-corte-prog: #333333;
        }
        .stApp, [data-testid="stAppViewContainer"] {
            background-color: var(--bg-main) !important;
        }
        """
    else:
        css_tema = """
        :root {
            --bg-main: #f0f2f6;
            --bg-card: #ffffff;
            --text-main: #2c3e50;
            --text-muted: #7f8c8d;
            --border-color: #eeeeee;
            --bg-sem-op: #f1f2f6;
            --text-sem-op: #7f8c8d;
            --bg-corte-prog: #ecf0f1;
        }
        .stApp, [data-testid="stAppViewContainer"] {
            background-color: var(--bg-main) !important;
        }
        """

    st.markdown(f"""
    <style>
    {css_tema}
    ::-webkit-scrollbar {{ display: none; }}
    .block-container {{ 
        max-width: 100% !important; 
        padding-top: 1rem !important; 
        padding-bottom: 5rem !important; 
        padding-left: 1rem !important; 
        padding-right: 1rem !important; 
    }}
    header[data-testid="stHeader"] {{ display: none !important; }}
    
    @media (min-width: 1024px) {{
        .pull-up {{ margin-top: -32px !important; }}
    }}
    @media (max-width: 1023px) {{
        .pull-up {{ margin-top: 0px !important; }}
    }}
    
    .grid-dash {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 25px; }}
    .card-dash {{ flex: 1 1 180px; padding: 12px; border-radius: 8px; color: white; text-align: left; box-shadow: 0 4px 6px rgba(0,0,0,0.1); display: flex; flex-direction: column; justify-content: space-between; transition: all 0.3s ease; position: relative; }}
    .cd-critico {{ animation: p-crit 0.8s infinite alternate !important; z-index: 10; }}
    @keyframes p-crit {{ 0% {{ transform: scale(1); box-shadow: 0 4px 6px rgba(0,0,0,0.1); }} 100% {{ transform: scale(1.04); box-shadow: 0 12px 24px rgba(0,0,0,0.4); }} }}
    </style>
    """, unsafe_allow_html=True)

    try:
        resp_mem = supa.table("memoria_sistema").select("*").execute()
        mem_dict = {r['chave']: r['valor'] for r in resp_mem.data} if resp_mem.data else {}
    except:
        mem_dict = {}

    ordem_c1_str = mem_dict.get('ordem_dash_col1', 'Status da Produção,Resumo de Indicadores,Evolução (Ao Vivo),Em Corte Agora,Status das OPs')
    ordem_c2_str = mem_dict.get('ordem_dash_col2', 'Chão de Fábrica,Cronômetros de Parada,Desempenho da Fábrica')
    todas_vazias = True if mem_dict.get('abrev_todas_vazias', 'False') == 'True' else False
    
    largura_col1 = int(mem_dict.get('dash_largura_col1', 33))
    max_cards_row = int(mem_dict.get('dash_max_cards_row', 7))

    refresh_segundos = int(cfg.get('ao_vivo_refresh', 60))
    tempo_critico = int(cfg.get('ao_vivo_critico', 15))
    vel_barra = int(cfg.get('ao_vivo_vel_barra', 8))
    
    m_das, m_as = cfg.get('manha_das', '07:30'), cfg.get('manha_as', '11:50')
    t_das, t_as = cfg.get('tarde_das', '13:30'), cfg.get('tarde_as', '17:30')
    lm_das, lm_as = cfg.get('lanche_m_das', ''), cfg.get('lanche_m_as', '')
    lt_das, lt_as = cfg.get('lanche_t_das', ''), cfg.get('lanche_t_as', '')
    
    m_das_min, m_as_min = calcular_minutos_str(m_das), calcular_minutos_str(m_as)
    t_das_min, t_as_min = calcular_minutos_str(t_das), calcular_minutos_str(t_as)
    lm_das_min = calcular_minutos_str(lm_das) if lm_das else -1
    lm_as_min = calcular_minutos_str(lm_as) if lm_as else -1
    lt_das_min = calcular_minutos_str(lt_das) if lt_das else -1
    lt_as_min = calcular_minutos_str(lt_as) if lt_as else -1

    agora = obter_hora_atual()
    hoje_str = agora.strftime("%Y-%m-%d")
    agora_min = agora.hour * 60 + agora.minute

    mapa_cores = banco.obter_mapa_cores()
    def get_color(tipo):
        t = str(tipo).strip().upper()
        if t in mapa_cores: return mapa_cores[t]
        if t == 'PRODUÇÃO': return '#27ae60'
        if t == 'PARADA': return '#e74c3c'
        if t == 'NÃO CONTA': return '#f39c12'
        if t == 'LIVRE': return '#3498db'
        return '#95a5a6'

    try:
        resp_img = supa.table("imagens_base64").select("nome, imagem_base64").eq("aplicacao", "Ícone de Setor").execute()
        icones_dict = {r['nome']: r['imagem_base64'] for r in resp_img.data} if resp_img.data else {}
    except:
        icones_dict = {}

    ordem_map = {}
    if not df_codigos.empty:
        col_ordem = None
        for col in df_codigos.columns:
            if 'ordem' in col.lower() and 'card' in col.lower():
                col_ordem = col
                break
                
        for _, r_cod in df_codigos.iterrows():
            c = str(r_cod.get('codigo', '')).strip()
            o_raw = r_cod[col_ordem] if col_ordem else pd.NA
            try:
                if pd.isna(o_raw) or str(o_raw).strip() == '': o_val = 99
                else: o_val = int(float(o_raw))
            except: o_val = 99
            if c: ordem_map[c] = o_val

    codigos_pausa = []
    if not df_codigos.empty and 'tipo' in df_codigos.columns:
        mask_pausa = df_codigos['tipo'].astype(str).str.strip().str.upper().isin(['NÃO CONTA', 'DESNCONSIDERAR', 'DESCONSIDERAR'])
        codigos_pausa = df_codigos[mask_pausa]['codigo'].astype(str).str.strip().tolist()
    
    try:
        resp_abrev = supa.table("config_abreviacoes").select("*").execute()
        df_abrev = pd.DataFrame(resp_abrev.data) if resp_abrev.data else pd.DataFrame()
    except: df_abrev = pd.DataFrame()

    df_est = banco.obter_estrutura()
    if 'ordem_maquina' not in df_est.columns: df_est['ordem_maquina'] = 99
    df_est_clean = df_est.dropna(subset=['setor', 'maquina']).drop_duplicates(subset=['setor', 'maquina'])
    total_maq_atual = len(df_est_clean)
    
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
    else: df_completo['percentual'] = pd.NA
        
    df_completo['percentual'] = df_completo['percentual'].ffill().fillna(0.0)
    agora_minuto = agora.replace(second=0, microsecond=0)
    df_completo.loc[df_completo.index > agora_minuto, 'percentual'] = pd.NA
    df_completo.reset_index(inplace=True)
    df_completo.rename(columns={'index': 'Hora', 'percentual': 'Em Operação (%)'}, inplace=True)
    df_plot = df_completo.dropna(subset=['Em Operação (%)']).copy()

    df_produtos = banco.obter_produtos_matriz() 
    try: df_caixas = pd.DataFrame(supa.table("caixas_matriz").select("*").execute().data)
    except: df_caixas = pd.DataFrame()
        
    usuarios_cadastrados = banco.obter_usuarios_completo() 
    ordem_setores = {}
    if not df_est.empty and 'ordem_fluxo' in df_est.columns:
        for _, row in df_est[['setor', 'ordem_fluxo']].dropna().drop_duplicates(subset=['setor']).iterrows():
            try: ordem_setores[str(row['setor']).strip()] = float(row['ordem_fluxo'])
            except: pass

    resp_status = supa.table("status_maquinas").select("*").execute()
    status_dict = {(str(d.get('setor', '')).strip(), str(d.get('maquina', '')).strip()): d for d in resp_status.data} if resp_status.data else {}

    resp_ops = supa.table("planejamento_ops").select("id, produto_formula, quantidade_planejada, data_inicio").eq("status", "Em Andamento").order("id").execute()
    ops_ativas = resp_ops.data if resp_ops.data else []
    ops_dict = {}
    ops_numeracao = {}
    
    for idx_op, op in enumerate(ops_ativas):
        nome_prod = op['produto_formula']
        ops_dict[nome_prod] = op
        ops_numeracao[nome_prod] = f"{idx_op + 1} - "
    
    df_hoje = pd.DataFrame()
    df_nuvem_operacao = pd.DataFrame()
    if not df_nuvem.empty and 'data_registro' in df_nuvem.columns and 'tipo' in df_nuvem.columns:
        df_hoje = df_nuvem[(df_nuvem['data_registro'] == hoje_str)].copy()
        df_nuvem_operacao = df_nuvem[df_nuvem['tipo'].astype(str).str.strip().str.upper() == 'PRODUÇÃO'].copy()
        if not df_nuvem_operacao.empty:
            df_nuvem_operacao['data_registro_dt'] = pd.to_datetime(df_nuvem_operacao['data_registro'], errors='coerce')
            df_nuvem_operacao['quantidade_num'] = pd.to_numeric(df_nuvem_operacao['quantidade'], errors='coerce').fillna(0)

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

    for _, r_est in df_est_clean.iterrows():
        setor = str(r_est['setor']).strip()
        maq = str(r_est['maquina']).strip()
        ordem_maq = int(r_est.get('ordem_maquina', 99))
        maq_formatada = f"{ordem_maq}: {maq}" if ordem_maq < 99 else maq
        
        if setor not in mapa_visual_dict: mapa_visual_dict[setor] = []
        info = status_dict.get((setor, maq), {})
        status_maq = info.get('status', 'Livre')
        info['maquina'] = maq
        info['maquina_fmt'] = maq_formatada
        info['ordem'] = ordem_maq
        info['setor'] = setor
        info['icone_b64'] = icones_dict.get(setor, None)
        
        operadores_maq = [u['nome'] for u in usuarios_cadastrados if str(u.get('maquina', '')).strip() == maq and str(u.get('setor', '')).strip() == setor and u.get('ativo') == True]
        info['setor_exibicao'] = f"{setor} / {' / '.join(operadores_maq)}" if operadores_maq else setor
        info['operadores'] = " / ".join(operadores_maq) if operadores_maq else "Sem Operador"
        
        if status_maq == 'Parado':
            cod = info.get('cod_ocorrencia')
            tipo_parada = 'PARADA'
            desc = "Desconhecido"
            if cod and not df_codigos.empty:
                f_cod = df_codigos[df_codigos['codigo'].astype(str) == str(cod)]
                if not f_cod.empty:
                    desc = str(f_cod.iloc[0]['descricao'])
                    if 'tipo' in f_cod.columns: tipo_parada = str(f_cod.iloc[0]['tipo']).strip().upper()
                        
            if 'DESCONSIDERAR' in tipo_parada: tipo_parada = 'NÃO CONTA'
            
            info['tipo_registro'] = tipo_parada
            info['descricao_completa'] = f"{desc} ({cod})"
            info['is_pausa'] = str(cod).strip() in codigos_pausa
            info['ordem_card'] = ordem_map.get(str(cod).strip(), 99) if cod else 99
            
            if info['is_pausa']:
                maquinas_pausas.append(info)
            else:
                maquinas_paradas_criticas.append(info)
                try:
                    h_ini = datetime.strptime(info['hora_inicio'], "%Y-%m-%d %H:%M:%S")
                    if h_ini.date() == agora.date():
                        for m in range(h_ini.hour * 60 + h_ini.minute, agora_min + 1):
                            if (m >= m_das_min and m < m_as_min) or (m >= t_das_min and m < t_as_min): minutos_ativos_perdidos += 1
                except: pass
                
        elif status_maq == 'Produzindo':
            info['tipo_registro'] = 'PRODUÇÃO'
            qtd_rodando += 1
            info['ordem_card'] = ordem_map.get('P', 99)
            
            cod_peca = info.get('cod_peca_atual')
            nome_peca_completo, html_progresso = "Peça Desconhecida", ""
            
            ultima_p = info.get('ultima_peca_sel', '')
            ultimo_prod = info.get('ultimo_produto_sel', '')
            
            if str(cod_peca).startswith("VIRTUAL-") and ultima_p and ultimo_prod:
                nome_cx = ultima_p.split(" (Cód:")[0].strip()
                p_abrev = aplicar_abreviacoes(ultimo_prod, df_abrev, todas_vazias)
                cx_abrev = aplicar_abreviacoes(nome_cx, df_abrev, todas_vazias)
                nome_peca_completo = f"<b style='font-size:12px;'>{p_abrev}</b><br><span style='font-size:10px; opacity:0.9;'>{cx_abrev}</span>"
                prod_form = ultimo_prod
            elif cod_peca and not df_produtos.empty:
                f_peca = df_produtos[df_produtos['cod'].astype(str) == str(cod_peca)]
                if not f_peca.empty:
                    prod_form = f_peca.iloc[0]['produto_formula']
                    p_abrev = aplicar_abreviacoes(prod_form, df_abrev, todas_vazias)
                    d_abrev = aplicar_abreviacoes(f_peca.iloc[0]['descricao'], df_abrev, todas_vazias)
                    nome_peca_completo = f"<b style='font-size:12px;'>{p_abrev}</b><br><span style='font-size:10px; opacity:0.9;'>{d_abrev}</span>"
                elif not df_caixas.empty:
                    f_cx = df_caixas[df_caixas['cod_caixa'].astype(str) == str(cod_peca)]
                    if not f_cx.empty:
                        prod_form = f_cx.iloc[0]['produto_formula']
                        p_abrev = aplicar_abreviacoes(prod_form, df_abrev, todas_vazias)
                        nome_peca_completo = f"<b style='font-size:12px;'>{p_abrev}</b><br><span style='font-size:10px; opacity:0.9;'>Caixa {f_cx.iloc[0]['num_caixa']}</span>"
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
                        
                        html_progresso = f"""
                        <div style='background: rgba(255,255,255,0.15); padding: 5px 10px; border-radius: 5px; margin-bottom: 5px;'>
                            <div style='display: flex; justify-content: space-between; font-size: 11px; font-weight: bold; margin-bottom: 4px;'>
                                <span>{prod_realizada}/{meta_peca}</span><span>{perc:.1f}%</span>
                            </div>
                            <div style='width: 100%; background: rgba(0,0,0,0.2); height: 6px; border-radius: 3px;'>
                                <div style='width: {perc}%; background: #ffffff; height: 100%;'></div>
                            </div>
                        </div>
                        """
            info['descricao_completa'] = nome_peca_completo
            info['html_progresso'] = html_progresso
            info['ultimo_produto_sel'] = ultimo_prod
            maquinas_produzindo.append(info)
        else:
            info['tipo_registro'] = 'LIVRE'
            qtd_livres += 1
            info['ordem_card'] = 99
            
            is_intervalo = False
            if m_as_min <= agora_min < t_das_min: is_intervalo = True
            elif lm_das_min >= 0 and lm_as_min >= 0 and lm_das_min <= agora_min < lm_as_min: is_intervalo = True
            elif lt_das_min >= 0 and lt_as_min >= 0 and lt_das_min <= agora_min < lt_as_min: is_intervalo = True
            elif agora_min >= t_as_min or agora_min < m_das_min: is_intervalo = True
            
            if is_intervalo:
                info['tipo_registro'] = 'NÃO CONTA'
            
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
                    for min_bd in range(m_i, m_f):
                        is_turno = (m_das_min <= min_bd < m_as_min) or (t_das_min <= min_bd < t_as_min)
                        is_lanche = (lm_das_min <= min_bd < lm_as_min) or (lt_das_min <= min_bd < lt_as_min)
                        if is_turno and not is_lanche: minutos_acumulados_bd += 1
                            
        info['minutos_acumulados_bd'] = minutos_acumulados_bd
        mapa_visual_dict[setor].append(info)

    cards_brutos = maquinas_paradas_criticas + maquinas_pausas + maquinas_produzindo
    cards_exibicao = []
    for p in cards_brutos:
        if p.get('ordem_card', 99) == 0:
            continue
        cards_exibicao.append(p)

    cards_exibicao = sorted(cards_exibicao, key=lambda x: (x.get('ordem_card', 99), x.get('setor', ''), x.get('ordem', 99)))
    perc_rodando = (qtd_rodando / total_maq_atual) * 100 if total_maq_atual > 0 else 0

    lista_js_timers = []
    for p in cards_exibicao:
        p_id = f"{p['setor']}_{p['maquina']}".replace(" ", "_").replace("/", "_").strip()
        tipo_reg = p.get('tipo_registro', 'LIVRE')
        hora_inicio = p.get('hora_inicio', '')
        if hora_inicio:
            lista_js_timers.append({
                "id": p_id, 
                "inicio_iso": str(hora_inicio).replace(" ", "T"),
                "past_ms": p.get('minutos_acumulados_bd', 0) * 60000,
                "min_passados": 1, 
                "tipo": tipo_reg
            })

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
    if not df_hoje.empty and not df_produtos.empty:
        df_corte_hoje = df_hoje[(df_hoje['setor'].astype(str).str.strip().str.upper() == 'CORTE') & (df_hoje['tipo'].astype(str).str.strip().str.upper() == 'PRODUÇÃO')]
        for _, r in df_corte_hoje.iterrows():
            qtd = pd.to_numeric(r.get('quantidade', 0), errors='coerce')
            if pd.isna(qtd): qtd = 0
            vol_corte_un += int(qtd)

    for p in maquinas_paradas_criticas: noticias.append(f"🔴 [{p['setor']}] {p['maquina']} parada: {p['descricao_completa']}")
    for p in maquinas_pausas: noticias.append(f"☕ [{p['setor']}] {p['maquina']}: {p['descricao_completa']}")
    for p in maquinas_produzindo: noticias.append(f"🟢 [{p['setor']}] {p['maquina']} produzindo: {str(p.get('cod_peca_atual',''))}")
    texto_letreiro = " &nbsp;&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;&nbsp; ".join(noticias) if noticias else "🟢 FÁBRICA OPERANDO COM 100% DE CAPACIDADE NESTE MOMENTO"

    html_ultimas_pecas_setor = {}
    setores_ordenados = sorted(mapa_visual_dict.keys(), key=lambda s: (ordem_setores.get(s, 999), s))
    
    if not df_nuvem_operacao.empty:
        for s_nome in setores_ordenados:
            df_sec = df_nuvem_operacao[df_nuvem_operacao['setor'].astype(str).str.strip().str.upper() == s_nome.upper()]
            if not df_sec.empty:
                if 'id' in df_sec.columns: df_sec = df_sec.sort_values('id', ascending=False).head(5)
                else: df_sec = df_sec.tail(5).iloc[::-1]
                
                html_pecas = ""
                for _, r_peca in df_sec.iterrows():
                    peca_raw = str(r_peca.get('nome_peca', 'Desconhecida')).strip()
                    produto_nome = "Produto"
                    if '➔' in peca_raw: produto_nome, peca_nome = peca_raw.split('➔')[0].strip(), peca_raw.split('➔')[1].strip()
                    elif '->' in peca_raw: produto_nome, peca_nome = peca_raw.split('->')[0].strip(), peca_raw.split('->')[1].strip()
                    else: peca_nome = peca_raw
                    
                    qtd_peca = int(pd.to_numeric(r_peca.get('quantidade', 0), errors='coerce'))
                    das = str(r_peca.get('das', '00:00')).strip()
                    as_hora = str(r_peca.get('as_hora', '00:00')).strip()
                    das_f, as_hora_f = das[:5] if len(das) >= 5 else das, as_hora[:5] if len(as_hora) >= 5 else as_hora
                    
                    cod_peca = str(r_peca.get('cod_peca', '')).strip()
                    if produto_nome == "Produto" and cod_peca:
                        if s_nome.upper() == 'EMBALAGEM' and not df_caixas.empty:
                            f_cx = df_caixas[df_caixas['cod_caixa'].astype(str) == cod_peca]
                            if not f_cx.empty: produto_nome = str(f_cx.iloc[0].get('produto_formula', 'Produto'))
                        elif not df_produtos.empty:
                            f_prod = df_produtos[df_produtos['cod'].astype(str) == cod_peca]
                            if not f_prod.empty: produto_nome = str(f_prod.iloc[0].get('produto_formula', 'Produto'))
                    
                    p_abrev = aplicar_abreviacoes(produto_nome, df_abrev, todas_vazias)
                    c_abrev = aplicar_abreviacoes(peca_nome, df_abrev, todas_vazias)
                    
                    html_pecas += f"""
                    <div style='display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding: 5px 0;'>
                        <div style='white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 11px; flex-grow: 1; margin-right: 5px;'>
                            <span style='font-weight: 800; color: var(--text-main);'>{p_abrev}</span> <span style='color: var(--text-muted);'>{c_abrev}</span>
                        </div>
                        <div style='font-size: 13px; font-weight: 900; color: #27ae60; white-space: nowrap; margin-right: 8px;'>+{qtd_peca} un</div>
                        <div style='font-size: 9px; color: var(--text-muted); white-space: nowrap;'>{das_f} ➔ {as_hora_f}</div>
                    </div>"""
                html_ultimas_pecas_setor[s_nome] = html_pecas

    def calc_corte_prog(nome_op):
        if nome_op not in ops_dict: return None
        op = ops_dict[nome_op]
        qtd_plan = int(op.get('quantidade_planejada', 0))
        data_op_dt = pd.to_datetime(op['data_inicio'].split(" ")[0].split("T")[0])
        df_filtrado = df_produtos[df_produtos['produto_formula'] == nome_op]
        mapa_prod_corte = {}
        if not df_todas_producoes.empty:
            df_op_prod = df_todas_producoes[(df_todas_producoes['data_registro_dt'] >= data_op_dt) & (df_todas_producoes['setor'] == 'CORTE')]
            agrup = df_op_prod.groupby('cod_peca')['quantidade'].sum().reset_index()
            for _, r in agrup.iterrows(): mapa_prod_corte[r['cod_peca']] = int(r['quantidade'])
        meta_corte, prod_corte = 0, 0
        for _, row in df_filtrado.iterrows():
            try: qnt_peca = int(float(row.get('qnt', 0)))
            except: qnt_peca = 0
            qtd_total = qnt_peca * qtd_plan
            cod = str(row.get('cod', '')).strip()
            meta_corte += qtd_total
            prod_corte += min(qtd_total, mapa_prod_corte.get(cod, 0))
        if meta_corte > 0:
            perc = min(100.0, (prod_corte / meta_corte) * 100)
            prefixo_op = ops_numeracao.get(nome_op, "")
            nome_abrev = aplicar_abreviacoes(nome_op, df_abrev, todas_vazias)
            return {'nome': f"{prefixo_op}{nome_abrev}", 'meta': meta_corte, 'prod': prod_corte, 'perc': perc}
        return None

    produto_em_corte = None
    for maq_info in maquinas_produzindo:
        if str(maq_info.get('setor', '')).strip().upper() == 'CORTE':
            prod_agora = maq_info.get('ultimo_produto_sel')
            if prod_agora and prod_agora in ops_dict:
                produto_em_corte = prod_agora
                break

    if not produto_em_corte and not df_nuvem_operacao.empty:
        df_corte_recentes = df_nuvem_operacao[df_nuvem_operacao['setor'].astype(str).str.strip().str.upper() == 'CORTE']
        if not df_corte_recentes.empty:
            if 'id' in df_corte_recentes.columns: df_corte_recentes = df_corte_recentes.sort_values('id', ascending=False)
            else: df_corte_recentes = df_corte_recentes.iloc[::-1]
            for _, row in df_corte_recentes.iterrows():
                cod_peca = str(row.get('cod_peca', '')).strip()
                prod_nome = None
                if not df_produtos.empty:
                    f_prod = df_produtos[df_produtos['cod'].astype(str) == cod_peca]
                    if not f_prod.empty: prod_nome = str(f_prod.iloc[0].get('produto_formula', ''))
                if prod_nome and prod_nome in ops_dict:
                    produto_em_corte = prod_nome
                    break

    produtos_para_exibir = []
    if produto_em_corte:
        prog = calc_corte_prog(produto_em_corte)
        if prog:
            produtos_para_exibir.append(prog)

    html_ops = ""
    if ops_ativas:
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
            meta_global, prod_global = 0, 0
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
            prefixo_op = ops_numeracao.get(nome_op, "")
            nome_abrev = aplicar_abreviacoes(nome_op, df_abrev, todas_vazias)
            nome_final = f"{prefixo_op}{nome_abrev}"
            
            html_ops += f"<div style='margin-bottom: 12px;'>"
            html_ops += f"<div style='display: flex; justify-content: space-between; font-size: 11px; font-weight: bold; color: var(--text-main); margin-bottom: 3px;'><span>📦 {nome_final}</span><span>{perc_op:.1f}% ({int(prod_global)}/{int(meta_global)})</span></div>"
            html_ops += f"<div style='width: 100%; background: var(--bg-corte-prog); height: 10px; border-radius: 5px; overflow: hidden; border: 1px solid var(--border-color);'><div style='width: {perc_op}%; background: #e74c3c; height: 100%; transition: width 0.5s ease;'></div></div>"
            html_ops += f"</div>"
        html_ops += "</div>"

    df_desemp = pd.DataFrame()
    ordem_maquinas_chart = []
    altura_dinamica_desemp = 150
    df_chart = df_hoje.copy()
    if not df_chart.empty:
        df_chart['das_min'] = df_chart['das'].astype(str).apply(calcular_minutos_str)
        df_chart['as_min'] = df_chart['as_hora'].astype(str).apply(calcular_minutos_str)
        def calc_uteis(row):
            total = 0
            for m in range(int(row['das_min']), int(row['as_min'])):
                is_t = (m_das_min <= m < m_as_min) or (t_das_min <= m < t_as_min)
                is_l = (lm_das_min <= m < lm_as_min) or (lt_das_min <= m < lt_as_min)
                if is_t and not is_l: total += 1
            return total
        df_chart['duracao'] = df_chart.apply(calc_uteis, axis=1)
        def map_class(row):
            t = str(row.get('tipo', 'PARADA')).strip().upper()
            if t == 'PRODUÇÃO': return 'PRODUÇÃO'
            if t == 'PARADA':
                cod = str(row.get('cod_ocorrencia', '')).strip()
                if cod and not df_codigos.empty:
                    f = df_codigos[df_codigos['codigo'].astype(str) == cod]
                    if not f.empty and 'tipo' in f.columns:
                        t_cod = str(f.iloc[0]['tipo']).strip().upper()
                        if 'DESCONSIDERAR' in t_cod: return 'NÃO CONTA'
                        return t_cod
            if 'DESCONSIDERAR' in t: return 'NÃO CONTA'
            return t
            
        df_chart['classificacao'] = df_chart.apply(map_class, axis=1)
        
        tipos_permitidos = ['PRODUÇÃO', 'PASSAGEM ADICIONAL', 'RETRABALHO', 'ROTINA', 'PARADA']
        df_desemp = df_chart[df_chart['classificacao'].isin(tipos_permitidos)].groupby(['setor', 'maquina', 'classificacao'])['duracao'].sum().reset_index()
        df_desemp = df_desemp[df_desemp['duracao'] > 0]
        
        if not df_desemp.empty:
            df_desemp['setor_fmt'] = df_desemp['setor'].astype(str).str.title()
            def maq_formatada_gr(maq_nome, setor_nome):
                maq_r = df_est_clean[(df_est_clean['setor'].str.upper() == str(setor_nome).upper()) & (df_est_clean['maquina'] == maq_nome)]
                ordem = int(maq_r.iloc[0].get('ordem_maquina', 99)) if not maq_r.empty else 99
                return f"{ordem}: {maq_nome}" if ordem < 99 else maq_nome
            df_desemp['maquina_fmt'] = df_desemp.apply(lambda x: maq_formatada_gr(x['maquina'], x['setor']), axis=1)
            df_desemp['maquina_exibicao'] = "[" + df_desemp['setor_fmt'] + "] " + df_desemp['maquina_fmt']
            df_desemp['total_maq'] = df_desemp.groupby('maquina_exibicao')['duracao'].transform('sum')
            df_desemp['pct'] = (df_desemp['duracao'] / df_desemp['total_maq'] * 100).fillna(0)
            df_desemp['tempo_str'] = df_desemp['duracao'].apply(formatar_minutos)
            def get_label_maq(row):
                if row['pct'] >= 10: return f"{row['tempo_str']} ({row['pct']:.1f}%)"
                elif row['pct'] >= 5: return f"{int(round(row['pct']))}%" 
                return ""
            df_desemp['label_exibicao'] = df_desemp.apply(get_label_maq, axis=1)
            
            mapa_ordem_barras = {'PRODUÇÃO': 1, 'PASSAGEM ADICIONAL': 2, 'RETRABALHO': 3, 'ROTINA': 4, 'PARADA': 5}
            df_desemp['ordem'] = df_desemp['classificacao'].map(mapa_ordem_barras)
            
            df_desemp = df_desemp.sort_values(by=['total_maq', 'maquina_exibicao', 'ordem'], ascending=[False, True, True])
            ordem_maquinas_chart = df_desemp[['maquina_exibicao', 'total_maq']].drop_duplicates().sort_values('total_maq', ascending=False)['maquina_exibicao'].tolist()
            df_desemp['cum_duracao'] = df_desemp.groupby('maquina_exibicao')['duracao'].cumsum()
            df_desemp['midpos'] = df_desemp['cum_duracao'] - (df_desemp['duracao'] / 2)
            altura_dinamica_desemp = max(150, len(ordem_maquinas_chart) * 60)

    ctx = {
        'perc_rodando': perc_rodando, 'qtd_rodando': qtd_rodando, 'total_maq_atual': total_maq_atual,
        'maquinas_paradas_criticas': maquinas_paradas_criticas, 'maquinas_pausas': maquinas_pausas, 'qtd_livres': qtd_livres,
        'h_perdido': h_perdido, 'm_perdido': m_perdido, 'top_ofensor': top_ofensor, 'mttr_str': mttr_str,
        'vol_corte_un': vol_corte_un, 'df_plot': df_plot,
        'hora_inicio_turno': hora_inicio_turno, 'hora_fim_turno': hora_fim_turno,
        'produtos_para_exibir': produtos_para_exibir, 'html_ops': html_ops,
        'setores_ordenados': setores_ordenados, 'mapa_visual_dict': mapa_visual_dict,
        'html_ultimas_pecas_setor': html_ultimas_pecas_setor, 'cards_exibicao': cards_exibicao,
        'df_desemp': df_desemp, 'ordem_maquinas_chart': ordem_maquinas_chart, 'altura_dinamica_desemp': altura_dinamica_desemp,
        'lista_js_timers': lista_js_timers, 'max_cards_row': max_cards_row,
        'get_color': get_color, 'is_dark': is_dark
    }

    col_esq, col_dir = st.columns([largura_col1, 100 - largura_col1], gap="small")
    with col_esq: dashboard_coluna_1.renderizar_coluna_1(ctx, ordem_c1_str.split(','))
    with col_dir: dashboard_coluna_2.renderizar_coluna_2(ctx, ordem_c2_str.split(','), get_color)

    st.markdown(f"""
    <div style="position: fixed; bottom: 0; left: 0; width: 100%; background-color: #34495e; color: white; padding: 10px 0; z-index: 9998; box-shadow: 0 -2px 10px rgba(0,0,0,0.2);">
        <marquee scrollamount="{vel_barra}" style="font-size: 16px; font-weight: 600; letter-spacing: 1px;">{texto_letreiro}</marquee>
    </div>
    <div style="height: 50px;"></div>
    """, unsafe_allow_html=True)

    with st.expander("🛠️ Organizar Layout do Dashboard"):
        st.markdown("<p style='font-size:13px; color:var(--text-muted); margin-top:-10px;'>Personalize as colunas e a distribuição visual da tela principal.</p>", unsafe_allow_html=True)
        opcoes_c1 = ["Status da Produção", "Resumo de Indicadores", "Evolução (Ao Vivo)", "Em Corte Agora", "Status das OPs"]
        opcoes_c2 = ["Chão de Fábrica", "Cronômetros de Parada", "Desempenho da Fábrica"]
        
        c_layout1, c_layout2, c_layout3 = st.columns([2, 2, 1])
        with c_layout1:
            st.markdown("#### 📐 Proporção das Colunas")
            nova_largura_col1 = st.slider("Largura da Coluna 1 (%)", min_value=20, max_value=50, value=largura_col1, step=1)
            st.markdown(f"<div style='margin-top:-10px; font-size:12px; color:var(--text-muted);'>A Coluna 2 preencherá os <b>{100 - nova_largura_col1}%</b> restantes.</div>", unsafe_allow_html=True)
        with c_layout2:
            st.markdown("#### ⏱️ Cronômetros de Parada")
            nova_max_cards = st.slider("Limite Máximo de Cards por Linha", min_value=4, max_value=10, value=max_cards_row, step=1)
            st.markdown(f"<div style='margin-top:-10px; font-size:12px; color:var(--text-muted);'>O sistema usará matemática para distribuir o excedente.</div>", unsafe_allow_html=True)
        with c_layout3:
            st.markdown("#### 🌗 Tema Visual")
            st.markdown(f"<div style='font-size:12px; color:var(--text-muted); margin-top:-10px; margin-bottom: 5px;'>Salvo para: <b>{usuario_logado.get('nome', 'Usuário')}</b></div>", unsafe_allow_html=True)
            novo_tema_escuro = st.toggle("Modo Escuro", value=is_dark)

        st.markdown("<br>", unsafe_allow_html=True)
        col_org_1, col_org_2 = st.columns(2)
        with col_org_1:
            n_ordem_c1 = st.multiselect("Ordem Coluna 1 (Esquerda)", opcoes_c1, default=[x for x in ordem_c1_str.split(',') if x in opcoes_c1])
        with col_org_2:
            n_ordem_c2 = st.multiselect("Ordem Coluna 2 (Direita)", opcoes_c2, default=[x for x in ordem_c2_str.split(',') if x in opcoes_c2])
            
        if st.button("💾 Salvar Novo Layout", type="primary"):
            if len(n_ordem_c1) == len(opcoes_c1) and len(n_ordem_c2) == len(opcoes_c2):
                def upsert_memoria(chave, valor):
                    res = supa.table("memoria_sistema").select("id").eq("aba", "Dashboard").eq("chave", chave).execute()
                    if res.data:
                        supa.table("memoria_sistema").update({"valor": valor}).eq("id", res.data[0]['id']).execute()
                    else:
                        supa.table("memoria_sistema").insert({"aba": "Dashboard", "local_aplicacao": "Geral", "chave": chave, "valor": valor}).execute()
                try:
                    upsert_memoria("ordem_dash_col1", ",".join(n_ordem_c1))
                    upsert_memoria("ordem_dash_col2", ",".join(n_ordem_c2))
                    upsert_memoria("dash_largura_col1", str(nova_largura_col1))
                    upsert_memoria("dash_max_cards_row", str(nova_max_cards))
                    
                    username_atual = usuario_logado.get('username')
                    if username_atual:
                        supa.table("usuarios").update({"modo_escuro": novo_tema_escuro}).eq("username", username_atual).execute()
                        st.session_state['usuario_logado']['modo_escuro'] = novo_tema_escuro
                        
                    st.success("✅ Layout salvo! Recarregue a página (F5) para aplicar as configurações.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
            else:
                st.warning("⚠️ Você precisa adicionar todos os elementos antes de salvar para não esconder nenhum indicador.")

    json_timers = json.dumps(ctx['lista_js_timers'])
    js_engine = f"""
    <script>
        if (window.parent.__dash_intervals) {{ window.parent.__dash_intervals.forEach(clearInterval); }}
        window.parent.__dash_intervals = [];
        
        const intRef = setInterval(function() {{
            const btns = window.parent.document.querySelectorAll('button');
            for (let i = 0; i < btns.length; i++) {{
                if (btns[i].innerText === '🔄 Atualizar' || btns[i].innerText.includes('Atualizar')) {{ btns[i].click(); break; }}
            }}
        }}, {refresh_segundos * 1000});
        window.parent.__dash_intervals.push(intRef);

        const timers = {json_timers};
        const tempoCriticoMs = {tempo_critico} * 60 * 1000;
        
        if (timers.length > 0) {{
            const intTimers = setInterval(() => {{
                const now = new Date().getTime();
                timers.forEach(p => {{
                    const distance = now - new Date(p.inicio_iso).getTime();
                    if (distance > 0) {{
                        const h = Math.floor(distance / 3600000); 
                        const m = Math.floor((distance % 3600000) / 60000); 
                        const s = Math.floor((distance % 60000) / 1000);
                        const tel = window.parent.document.getElementById("timer_" + p.id);
                        if (tel) tel.innerHTML = (h<10?"0":"")+h + ":" + (m<10?"0":"")+m + ":" + (s<10?"0":"")+s;
                        
                        const subTel = window.parent.document.getElementById("sub_timer_" + p.id);
                        if (subTel) {{
                            const totalMs = distance + p.past_ms;
                            const totalMin = Math.floor(totalMs / 60000);
                            let prefix = "";
                            if (p.tipo === "PRODUÇÃO") prefix = "Tempo trabalhado: ";
                            else if (p.tipo === "PARADA") prefix = "Total parado: ";
                            else if (p.tipo === "ROTINA") prefix = "Total rotina: ";
                            else if (p.tipo === "RETRABALHO") prefix = "Total retrabalho: ";
                            else if (p.tipo === "NÃO CONTA" || p.tipo === "INTERVALO PREVISTO") prefix = "Total em pausa: ";
                            else prefix = "Acumulado: ";
                            
                            let tempoStr = "";
                            const h_tot = Math.floor(totalMin / 60);
                            const m_tot = totalMin % 60;
                            if (h_tot > 0) tempoStr = h_tot + "h" + (m_tot < 10 ? "0":"") + m_tot + "m";
                            else tempoStr = m_tot + " min";
                            
                            subTel.innerHTML = prefix + tempoStr;
                        }}
                        
                        const cel = window.parent.document.getElementById("card_" + p.id);
                        if (cel) {{
                            const tipoReg = cel.getAttribute("data-tipo");
                            if (distance >= tempoCriticoMs && (tipoReg === "PARADA" || tipoReg === "ROTINA")) {{
                                if (!cel.classList.contains("cd-critico")) {{
                                    cel.classList.add("cd-critico"); 
                                }}
                            }} else {{
                                cel.classList.remove("cd-critico");
                            }}
                        }}
                    }}
                }});
            }}, 1000);
            window.parent.__dash_intervals.push(intTimers);
        }}
    </script>
    """
    components.html(js_engine, height=0)