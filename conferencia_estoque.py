import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import altair as alt
import banco

# ==========================================
# 1. CACHE PARA ZERAR O DELAY (Memória Rápida)
# ==========================================
@st.cache_data(ttl=300)
def carregar_dados_estoque():
    """Baixa tudo do banco de uma vez só e guarda na memória RAM por 5 min."""
    df_produtos = banco.obter_produtos_matriz()
    df_cores = banco.obter_cores_produtos()
    supa = banco.conectar()
    try:
        resp_cx = supa.table("caixas_matriz").select("*").execute()
        df_caixas = pd.DataFrame(resp_cx.data) if resp_cx.data else pd.DataFrame()
    except:
        df_caixas = pd.DataFrame()
    return df_produtos, df_cores, df_caixas

def renderizar_app_conferente():
    st.markdown("""
        <style>
        .title-conf { font-size: 24px; font-weight: 900; color: #2c3e50; text-align: center; margin-bottom: 20px;}
        .passo-conf { font-size: 16px; font-weight: bold; color: #2980b9; margin-top: 15px; margin-bottom: 5px; }
        .pendentes-tit { font-size: 18px; font-weight: 900; color: #e67e22; margin-top: 40px; margin-bottom: 10px; border-bottom: 2px solid #e67e22; padding-bottom: 5px;}
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<div class='title-conf'>📦 App do Conferente</div>", unsafe_allow_html=True)
    
    # --- VARIÁVEIS DE SESSÃO (Para travar Produto/Cor e limpar o resto) ---
    if 'conf_prod' not in st.session_state: st.session_state['conf_prod'] = ""
    if 'conf_cor' not in st.session_state: st.session_state['conf_cor'] = ""
    if 'form_k' not in st.session_state: st.session_state['form_k'] = 0
    
    user_logado = st.session_state.get('usuario_logado', {}).get('nome', 'Operador Desconhecido')

    df_produtos, df_cores, df_caixas = carregar_dados_estoque()

    if df_caixas.empty:
        st.warning("⚠️ Nenhuma caixa/volume cadastrado na matriz de produtos. O estoque de caixas está vazio.")
        return
        
    cores_ativas = df_cores[df_cores['ativo'] == True] if not df_cores.empty else pd.DataFrame()
    
    # PASSO 1: PRODUTO
    st.markdown("<div class='passo-conf'>1. Qual produto você vai contar?</div>", unsafe_allow_html=True)
    produtos_disp = sorted(df_caixas['produto_formula'].dropna().unique().tolist())
    
    produto_sel = st.selectbox(
        "Selecione o Produto", 
        [""] + produtos_disp, 
        key="conf_prod", 
        label_visibility="collapsed"
    )

    if produto_sel:
        if cores_ativas.empty:
            st.warning("⚠️ Nenhuma cor cadastrada/ativa no sistema. Solicite ao gestor para cadastrar em Configurações > Cores.")
            return

        # PASSO 2: COR
        st.markdown("<div class='passo-conf'>2. Qual o acabamento (Cor)?</div>", unsafe_allow_html=True)
        
        opcoes_cores = []
        for _, c in cores_ativas.iterrows():
            nome_exibicao = f"[{c['cod_cor']}] {c['nome_cor']} ({c['sigla']})" if c['cod_cor'] else f"{c['nome_cor']} ({c['sigla']})"
            opcoes_cores.append({'nome_exibe': nome_exibicao, 'nome': c['nome_cor'], 'sigla': c['sigla'], 'cod': c['cod_cor']})
            
        cor_sel_nome = st.selectbox(
            "Selecione a Cor", 
            [""] + [c['nome_exibe'] for c in opcoes_cores], 
            key="conf_cor", 
            label_visibility="collapsed"
        )

        if cor_sel_nome:
            dados_cor_sel = next(c for c in opcoes_cores if c['nome_exibe'] == cor_sel_nome)
            
            # PASSO 3: VOLUMES DINÂMICOS (Com inteligência de Filtro de Tipos)
            k_dinamica = st.session_state['form_k']
            caixas_prod = df_caixas[df_caixas['produto_formula'] == produto_sel].sort_values('num_caixa')
            
            # Filtro Inteligente: Remove volumes onde a coluna 'tipo' não está vazia (Ex: Espelho, Vidro)
            if 'tipo' in caixas_prod.columns:
                caixas_prod = caixas_prod[
                    caixas_prod['tipo'].isna() | 
                    (caixas_prod['tipo'].astype(str).str.strip() == '') | 
                    (caixas_prod['tipo'].astype(str).str.lower() == 'nan') |
                    (caixas_prod['tipo'].astype(str).str.lower() == 'null') |
                    (caixas_prod['tipo'].astype(str).str.lower() == 'none')
                ]

            st.markdown("<hr style='opacity: 0.2; margin: 25px 0;'>", unsafe_allow_html=True)
            
            if caixas_prod.empty:
                st.info("ℹ️ Todos os volumes deste produto são classificados como itens especiais (ex: Espelho/Vidro) e não necessitam de contagem cega.")
            else:
                # Dicionário para guardar qtd e obs de cada caixa
                dados_informados = {}
                
                # Gerador de linhas para cada caixa (Sem os cabeçalhos)
                for _, r in caixas_prod.iterrows():
                    cod = str(r.get('cod_caixa', '')).strip()
                    num = str(r.get('num_caixa', '')).strip()
                    nome_exibicao = f"Caixa {num} (Cód: {cod})"
                    
                    c_vol, c_input = st.columns([7, 3], vertical_alignment="center")
                    with c_vol:
                        st.markdown(f"<div style='font-size: 16px; font-weight: bold; color: #2c3e50;'>📦 {nome_exibicao}</div>", unsafe_allow_html=True)
                    with c_input:
                        qtd = st.number_input("Qtd", min_value=0, step=1, value=0, key=f"qt_{cod}_{k_dinamica}", label_visibility="collapsed")
                    
                    # Campo de observação individual sutil
                    obs = st.text_input("Obs", placeholder=f"Anotação sobre a {nome_exibicao} (Opcional)", key=f"ob_{cod}_{k_dinamica}", label_visibility="collapsed")
                    
                    dados_informados[(cod, nome_exibicao)] = {'qtd': qtd, 'obs': obs}
                    
                    st.markdown("<hr style='margin: 15px 0; opacity: 0.1;'>", unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)
                
                if st.button("💾 ENVIAR CONTAGEM DE TODOS OS VOLUMES", type="primary", use_container_width=True):
                    sucessos = 0
                    erros = 0
                    
                    with st.spinner("Registrando volumes no banco de dados..."):
                        for (cod_cx, nome_cx), dados in dados_informados.items():
                            suc, msg = banco.salvar_contagem_estoque(
                                operador=user_logado, 
                                produto_formula=produto_sel, 
                                nome_cor=dados_cor_sel['nome'],
                                sigla_cor=dados_cor_sel['sigla'],
                                cod_cor=dados_cor_sel['cod'],
                                cod_caixa=cod_cx, 
                                caixa_nome=nome_cx, 
                                quantidade_fisica=dados['qtd'], 
                                observacao=dados['obs']
                            )
                            if suc:
                                sucessos += 1
                            else:
                                erros += 1
                    
                    if erros == 0:
                        st.success(f"✅ {sucessos} volumes registrados com sucesso!")
                        st.balloons()
                        # Incrementa o K para limpar as caixas de texto mantendo o Produto/Cor
                        st.session_state['form_k'] += 1 
                        st.rerun()
                    else:
                        st.error(f"⚠️ Ocorreram {erros} erros ao salvar. {sucessos} volumes foram salvos.")

    # ==========================================
    # MEUS REGISTROS PENDENTES (Com Edição e Exclusão)
    # ==========================================
    st.markdown("<div class='pendentes-tit'>📋 Minhas Contagens Pendentes de Hoje</div>", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 13px; color: #7f8c8d; margin-top: -10px;'>As contagens abaixo aguardam a auditoria do gestor. Você pode corrigi-las se errou algo.</p>", unsafe_allow_html=True)
    
    supa = banco.conectar()
    # Busca apenas os pendentes DESTE operador
    resp_pendentes = supa.table("conferencia_estoque").select("*").eq("status", "Pendente").eq("operador", user_logado).order("data_contagem", desc=True).execute()
    pendentes_op = resp_pendentes.data if resp_pendentes.data else []

    if not pendentes_op:
        st.info("Nenhuma contagem pendente. Você está em dia!")
    else:
        for p in pendentes_op:
            cor_str = f"{p.get('nome_cor','')} ({p.get('sigla_cor','')})"
            hora_str = datetime.fromisoformat(p['data_contagem'].replace('Z', '+00:00')).strftime('%H:%M')
            
            # Título do card compactado
            with st.expander(f"📦 {p['produto_formula']} 🎨 {cor_str} ➖ {p['caixa_nome']} ➡️ {p['quantidade_fisica']} cx ({hora_str})"):
                c1, c2, c3 = st.columns([4, 3, 3])
                
                with c1:
                    nova_qtd = st.number_input("Corrigir Quantidade:", min_value=0, step=1, value=p['quantidade_fisica'], key=f"edit_qt_{p['id']}")
                
                with c2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("✏️ Salvar Edição", key=f"btn_edit_{p['id']}", type="primary", use_container_width=True):
                        supa.table("conferencia_estoque").update({"quantidade_fisica": nova_qtd}).eq("id", p['id']).execute()
                        st.success("✅ Atualizado!")
                        st.rerun()
                
                with c3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🗑️ Excluir", key=f"btn_del_{p['id']}", use_container_width=True):
                        supa.table("conferencia_estoque").delete().eq("id", p['id']).execute()
                        st.warning("⚠️ Registro excluído!")
                        st.rerun()


def renderizar_auditoria_gestor():
    st.markdown("## ⚖️ Gestão e Auditoria de Estoque")
    aba_fila, aba_dash = st.tabs(["📋 Fila de Auditoria", "📈 Dashboard de Acuracidade"])

    with aba_fila:
        st.markdown("Confirme a quantidade física informada pelos operadores cruzando com o saldo atual do seu ERP (Sistema Principal).")
        st.markdown("<br>", unsafe_allow_html=True)
        
        pendentes = banco.obter_contagens_pendentes()

        if not pendentes:
            st.info("🎉 Estoque em dia! Nenhuma contagem pendente de auditoria no momento.")
        else:
            for p in pendentes:
                data_formatada = datetime.fromisoformat(p['data_contagem'].replace('Z', '+00:00')).strftime('%d/%m/%Y às %H:%M')
                
                cod_view = f"[{p['cod_cor']}] " if p.get('cod_cor') else ""
                cor_view = f"{cod_view}{p.get('nome_cor','')} ({p.get('sigla_cor','')})"
                
                with st.expander(f"📦 {p['produto_formula']} 🎨 {cor_view} ➖ {p['caixa_nome']} (Aguardando)", expanded=False):
                    c1, c2 = st.columns([1, 1])
                    
                    with c1:
                        st.markdown(f"<div style='background:#f8f9fa; padding:15px; border-radius:8px; border-left:4px solid #f39c12;'>", unsafe_allow_html=True)
                        st.markdown(f"<span style='font-size:12px; color:#7f8c8d; text-transform:uppercase; font-weight:bold;'>Informação da Fábrica</span>", unsafe_allow_html=True)
                        st.markdown(f"**Conferente:** {p['operador']}")
                        st.markdown(f"**Data da Coleta:** {data_formatada}")
                        st.markdown(f"**Acabamento:** {cor_view}")
                        st.markdown(f"**Quantidade Encontrada:** <span style='font-size:24px; font-weight:900; color:#2c3e50;'>{p['quantidade_fisica']}</span>", unsafe_allow_html=True)
                        if p['observacao']:
                            st.markdown(f"**Obs:** _{p['observacao']}_")
                        st.markdown("</div>", unsafe_allow_html=True)

                    with c2:
                        st.markdown(f"<div style='background:#fdfefe; padding:15px; border-radius:8px; border: 1px solid #eee;'>", unsafe_allow_html=True)
                        st.markdown(f"<span style='font-size:12px; color:#2980b9; text-transform:uppercase; font-weight:bold;'>O Momento da Verdade</span>", unsafe_allow_html=True)
                        
                        qtd_sistema = st.number_input("1. Qual o Saldo que está no ERP?", min_value=0, step=1, key=f"sys_{p['id']}", value=p['quantidade_fisica'])
                        
                        diferenca = p['quantidade_fisica'] - qtd_sistema
                        cor_dif = "#27ae60" 
                        texto_dif = "✅ Bateu exato!"
                        
                        if diferenca > 0: 
                            cor_dif = "#2980b9" 
                            texto_dif = f"Sobra Física (+{diferenca} caixas)"
                        elif diferenca < 0: 
                            cor_dif = "#c0392b" 
                            texto_dif = f"Falta Física ({diferenca} caixas)"

                        st.markdown(f"**Resultado:** <span style='font-size:18px; font-weight:900; color:{cor_dif};'>{texto_dif}</span>", unsafe_allow_html=True)

                        motivo = ""
                        if diferenca != 0:
                            motivos_lista = ["", "Erro de Expedição / Separação", "Avaria não reportada", "Erro de Produção / OP", "Desvio / Extravio", "Erro do Sistema ERP", "Contagem anterior errada", "Outros"]
                            motivo = st.selectbox("2. Motivo da Divergência", motivos_lista, key=f"mot_{p['id']}")

                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("✔️ Aprovar e Finalizar Auditoria", key=f"btn_{p['id']}", type="primary", use_container_width=True):
                            if diferenca != 0 and not motivo:
                                st.warning("⚠️ Uma divergência foi encontrada. É obrigatório selecionar o motivo para poder finalizar.")
                            else:
                                auditor = st.session_state.get('usuario_logado', {}).get('nome', 'Gestor')
                                motivo_final = motivo if diferenca != 0 else "OK - Contagem Exata"
                                suc, msg = banco.auditar_contagem_estoque(p['id'], auditor, qtd_sistema, diferenca, motivo_final)
                                if suc:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
                        st.markdown("</div>", unsafe_allow_html=True)

    with aba_dash:
        df_hist = banco.obter_historico_conferencia()
        
        if df_hist.empty:
            st.info("Nenhum histórico de auditoria finalizada para gerar gráficos.")
        else:
            total_auditorias = len(df_hist)
            exatas = len(df_hist[df_hist['diferenca'] == 0])
            divergentes = total_auditorias - exatas
            acuracidade = (exatas / total_auditorias) * 100 if total_auditorias > 0 else 0

            st.markdown("""
                <style>
                .kpi-dash { background:#fff; padding:15px; border-radius:10px; text-align:center; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px;}
                .kpi-dash-tit { font-size:12px; color:#7f8c8d; font-weight:bold; text-transform:uppercase; margin-bottom:5px; }
                .kpi-dash-val { font-size:32px; font-weight:900; line-height:1; }
                </style>
            """, unsafe_allow_html=True)

            k1, k2, k3, k4 = st.columns(4)
            k1.markdown(f"<div class='kpi-dash'><div class='kpi-dash-tit'>Total de Contagens</div><div class='kpi-dash-val' style='color:#2c3e50;'>{total_auditorias}</div></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='kpi-dash'><div class='kpi-dash-tit'>Contagens Exatas</div><div class='kpi-dash-val' style='color:#27ae60;'>{exatas}</div></div>", unsafe_allow_html=True)
            k3.markdown(f"<div class='kpi-dash'><div class='kpi-dash-tit'>Com Divergência</div><div class='kpi-dash-val' style='color:#c0392b;'>{divergentes}</div></div>", unsafe_allow_html=True)
            k4.markdown(f"<div class='kpi-dash'><div class='kpi-dash-tit'>Acuracidade (%)</div><div class='kpi-dash-val' style='color:#2980b9;'>{acuracidade:.1f}%</div></div>", unsafe_allow_html=True)

            st.markdown("<hr style='opacity: 0.2;'>", unsafe_allow_html=True)
            c_graf1, c_graf2 = st.columns(2)

            with c_graf1:
                st.markdown("#### 📉 Pareto de Motivos (Onde estamos errando?)")
                df_motivos = df_hist[df_hist['diferenca'] != 0]['motivo_divergencia'].value_counts().reset_index()
                df_motivos.columns = ['Motivo', 'Quantidade']
                if not df_motivos.empty:
                    chart_motivos = alt.Chart(df_motivos).mark_bar(color='#f39c12').encode(
                        x=alt.X('Quantidade:Q', title='Número de Ocorrências'),
                        y=alt.Y('Motivo:N', sort='-x', title=''),
                        tooltip=['Motivo', 'Quantidade']
                    ).properties(height=300)
                    st.altair_chart(chart_motivos, use_container_width=True)
                else:
                    st.info("Estoque perfeito! Nenhuma divergência registrada ainda.")

            with c_graf2:
                st.markdown("#### 📦 Produtos com Mais Divergências (Foco de Inventário)")
                df_prod_div = df_hist[df_hist['diferenca'] != 0]['produto_formula'].value_counts().reset_index()
                df_prod_div.columns = ['Produto', 'Quantidade de Erros']
                if not df_prod_div.empty:
                    chart_prods = alt.Chart(df_prod_div.head(10)).mark_bar(color='#c0392b').encode(
                        x=alt.X('Quantidade de Erros:Q', title='Nº de Contagens Erradas'),
                        y=alt.Y('Produto:N', sort='-x', title=''),
                        tooltip=['Produto', 'Quantidade de Erros']
                    ).properties(height=300)
                    st.altair_chart(chart_prods, use_container_width=True)
                else:
                    st.info("Estoque perfeito! Nenhuma divergência registrada ainda.")
                    
            st.markdown("<hr style='opacity: 0.2;'>", unsafe_allow_html=True)
            st.markdown("#### 📋 Histórico Completo de Auditorias")
            df_exibicao = df_hist[['data_auditoria', 'auditor', 'operador', 'produto_formula', 'nome_cor', 'sigla_cor', 'caixa_nome', 'quantidade_fisica', 'quantidade_sistema', 'diferenca', 'motivo_divergencia']].copy()
            df_exibicao['data_auditoria'] = pd.to_datetime(df_exibicao['data_auditoria']).dt.strftime('%d/%m/%Y %H:%M')
            
            df_exibicao['Cor'] = df_exibicao['nome_cor'] + " (" + df_exibicao['sigla_cor'] + ")"
            df_exibicao = df_exibicao[['data_auditoria', 'auditor', 'operador', 'produto_formula', 'Cor', 'caixa_nome', 'quantidade_fisica', 'quantidade_sistema', 'diferenca', 'motivo_divergencia']]
            
            df_exibicao.columns = ['Data', 'Gestor', 'Conferente', 'Produto', 'Cor', 'Volume', 'Qtd Física', 'Qtd ERP', 'Diferença', 'Motivo']
            
            st.dataframe(df_exibicao, use_container_width=True, hide_index=True)