import streamlit as st
# 🔒 REGRA DE SEGURANÇA: Configuração da página DEVE ser a primeira linha do Streamlit!
st.set_page_config(page_title="PCP Avelan", page_icon="🏭", layout="wide")

import streamlit.components.v1 as components
from datetime import datetime, timedelta
import banco
import configuracoes
import filtros
import disponibilidade
import ocorrencias 
import importacao
import apontamentos
import backups 
import plano_acao 
import chao_de_fabrica
import ao_vivo 
import desempenho
import gerenciador
import usuarios
import produtos
import caixas
import painel_ops 
from streamlit_option_menu import option_menu
import base64

# ==========================================
# MOTOR DE HEARTBEAT (MONITORAMENTO SILENCIOSO)
# ==========================================
def registrar_heartbeat():
    """Registra a atividade do usuário a cada 5 minutos no banco de dados."""
    usuario_logado = st.session_state.get('usuario_logado')
    if not usuario_logado:
        return

    nome_usuario = usuario_logado.get('nome', 'Desconhecido')
    username = usuario_logado.get('username', '').strip().lower()

    if nome_usuario == "Admin Master" or username == "admin":
        return

    aba_atual = st.session_state.get('aba_atual', 'Desconhecida')
    agora = datetime.utcnow() - timedelta(hours=3)

    if 'sessao_db_id' not in st.session_state:
        st.session_state['sessao_db_id'] = None
    if 'ultimo_ping' not in st.session_state:
        st.session_state['ultimo_ping'] = None

    ultimo_ping = st.session_state['ultimo_ping']

    if ultimo_ping is None or (agora - ultimo_ping).total_seconds() > 300:
        agora_str = agora.strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            supa = banco.conectar()
            
            if st.session_state['sessao_db_id'] is None:
                dados = {
                    "usuario": nome_usuario,
                    "inicio": agora_str,
                    "ultima_atividade": agora_str,
                    "ultima_aba": aba_atual
                }
                resp = supa.table("registro_sessoes").insert([dados]).execute()
                if resp.data:
                    st.session_state['sessao_db_id'] = resp.data[0]['id']
                    st.session_state['ultimo_ping'] = agora
            else:
                dados = {
                    "ultima_atividade": agora_str,
                    "ultima_aba": aba_atual
                }
                supa.table("registro_sessoes").update(dados).eq("id", st.session_state['sessao_db_id']).execute()
                st.session_state['ultimo_ping'] = agora
                
        except Exception as e:
            pass 

# Carrega configurações visuais
try:
    cfg = banco.obter_configuracoes()
    titulo_app = cfg.get('titulo_programa', 'PCP Avelan')
    modo_manutencao = cfg.get('modo_manutencao', False)
    previsao_retorno = cfg.get('previsao_retorno', 'Em breve')
except:
    cfg = {}
    titulo_app = 'PCP Avelan'
    modo_manutencao = False
    previsao_retorno = ''

# ==========================================
# 1. SISTEMA DE LOGIN COM PERSISTÊNCIA E MANUTENÇÃO
# ==========================================
if 'usuario_logado' not in st.session_state:
    st.session_state['usuario_logado'] = None

if st.session_state['usuario_logado'] is None:
    try:
        if hasattr(st, 'query_params') and 'session' in st.query_params:
            decoded_user = base64.b64decode(st.query_params['session']).decode('utf-8')
            user_valido = banco.obter_usuario_por_login(decoded_user)
            if user_valido:
                st.session_state['usuario_logado'] = user_valido
        elif hasattr(st, 'experimental_get_query_params'):
            params = st.experimental_get_query_params()
            if 'session' in params:
                decoded_user = base64.b64decode(params['session'][0]).decode('utf-8')
                user_valido = banco.obter_usuario_por_login(decoded_user)
                if user_valido:
                    st.session_state['usuario_logado'] = user_valido
    except:
        pass

if st.session_state['usuario_logado'] is None:
    st.markdown("""
        <style>
        header[data-testid="stHeader"] { display: none !important; }
        .block-container { max-width: 450px !important; padding-top: 5rem !important; }
        </style>
    """, unsafe_allow_html=True)
    
    logo_b64 = cfg.get('logo_base64', None)
    if logo_b64:
        st.markdown(f'<div style="text-align:center;"><img src="data:image/png;base64,{logo_b64}" style="max-height: 80px; margin-bottom: 20px;"></div>', unsafe_allow_html=True)
    
    st.markdown(f"<h2 style='text-align: center; color: #2c3e50;'>🏭 {titulo_app}</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #7f8c8d; margin-bottom: 30px;'>Acesso Restrito</p>", unsafe_allow_html=True)
    
    with st.form("form_login"):
        login = st.text_input("Usuário", placeholder="Digite seu login")
        senha = st.text_input("Senha", type="password", placeholder="Digite sua senha")
        submit = st.form_submit_button("Entrar no Sistema", use_container_width=True, type="primary")
        
        if submit:
            if not login.strip() and senha:
                login = "admin"
                
            if login and senha:
                if modo_manutencao and login.strip().lower() != "admin":
                    st.error("🚧 Acesso negado: O sistema encontra-se em manutenção.")
                else:
                    user_valido = banco.autenticar_usuario(login, senha)
                    if user_valido:
                        st.session_state['usuario_logado'] = user_valido
                        encoded_user = base64.b64encode(user_valido['username'].encode('utf-8')).decode('utf-8')
                        try: st.query_params['session'] = encoded_user
                        except: st.experimental_set_query_params(session=encoded_user)
                        st.rerun()
                    else:
                        st.error("❌ Usuário ou senha incorretos, ou conta desativada.")
            else:
                st.warning("⚠️ Preencha usuário e senha.")
                
    if modo_manutencao:
        st.markdown(f"""
        <div style="background-color: #fdf3f2; border-left: 5px solid #e74c3c; padding: 15px; margin-top: 25px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
            <h4 style="color: #c0392b; margin: 0 0 5px 0; font-size: 16px;">🚧 SISTEMA EM MANUTENÇÃO</h4>
            <p style="color: #e74c3c; margin: 0; font-size: 14px; line-height: 1.4;">Estou realizando algumas atualizações no sistema no momento. Por favor, aguarde a liberação!<br><br><b>⏳ Previsão de retorno:</b> {previsao_retorno}</p>
        </div>
        """, unsafe_allow_html=True)
        
    st.stop() 

# ==========================================
# 2. LÓGICA DE PERMISSÃO E IDENTIFICAÇÃO DE ABA 
# ==========================================
usuario_atual = st.session_state['usuario_logado']

if modo_manutencao and usuario_atual.get('username', '').lower() != "admin":
    st.session_state['usuario_logado'] = None
    try: st.query_params.clear()
    except: st.experimental_set_query_params()
    st.rerun()

perfil_atual = usuario_atual.get('perfis_acesso', {})
is_admin = perfil_atual.get('is_admin', False)
abas_permitidas_str = perfil_atual.get('abas_permitidas', '')

try:
    if hasattr(st, 'query_params') and 'codigo_alvo' in st.query_params:
        st.session_state['codigo_alvo'] = st.query_params['codigo_alvo']
        st.session_state['aba_atual'] = "🔎 Ocorrências"
        filtros.salvar_memoria() 
        st.query_params.clear()
        try: st.query_params['session'] = base64.b64encode(usuario_atual['username'].encode('utf-8')).decode('utf-8')
        except: pass
    elif hasattr(st, 'experimental_get_query_params') and 'codigo_alvo' in st.experimental_get_query_params():
        st.session_state['codigo_alvo'] = st.experimental_get_query_params()['codigo_alvo'][0]
        st.session_state['aba_atual'] = "🔎 Ocorrências"
        filtros.salvar_memoria()
        st.experimental_set_query_params(session=base64.b64encode(usuario_atual['username'].encode('utf-8')).decode('utf-8'))
except: pass

st.markdown("""
    <style>
    header[data-testid="stHeader"] { display: none !important; }
    .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; max-width: 100% !important; }
    .cabecalho-responsivo { display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px; }
    .logo-container { display: flex; align-items: center; gap: 20px; }
    .logo-responsiva { max-height: 60px; object-fit: contain; }
    .titulo-responsivo { margin: 0; padding: 0; font-size: 2.5rem; }
    ul.nav-pills { flex-wrap: nowrap !important; overflow-x: auto !important; overflow-y: hidden !important; scrollbar-width: none !important; }
    ul.nav-pills::-webkit-scrollbar { display: none !important; }
    li.nav-item { white-space: nowrap !important; }
    @media (max-width: 768px) {
        .cabecalho-responsivo { flex-direction: column; justify-content: center; text-align: center; gap: 10px; margin-top: 10px; }
        .logo-responsiva { max-height: 80px; } .titulo-responsivo { font-size: 2rem; }
    }
    </style>
""", unsafe_allow_html=True)

df_nuvem = banco.obter_dados_nuvem()
df_codigos = banco.obter_codigos()
meta, jornada, m_das, m_as, t_das, t_as = configuracoes.obter_parametros()

todas_abas_padrao = ["📱 Chão de Fábrica", "🔴 Ao Vivo", "🎯 Painel de OPs", "🏆 Desempenho", "💡 Plano de Ação", "📈 Disponibilidade", "📋 Apontamentos", "🔎 Ocorrências", "📦 Produtos", "📦 Caixas", "⚙️ Configurações", "👥 Controle de Acessos"]

if is_admin or abas_permitidas_str.upper() == 'TODAS': abas_usuario = todas_abas_padrao.copy()
else:
    abas_usuario = [aba for aba in todas_abas_padrao if aba in abas_permitidas_str]
    if not abas_usuario: abas_usuario = ["📱 Chão de Fábrica"]

ordem_str = cfg.get('ordem_abas', None)
if ordem_str:
    todas_abas = [a.strip() for a in ordem_str.split(',') if a.strip() in abas_usuario]
    for a in abas_usuario:
        if a not in todas_abas: todas_abas.append(a)
else: todas_abas = abas_usuario.copy()

aba_padrao_salva = cfg.get('aba_padrao', todas_abas[0])
if aba_padrao_salva not in todas_abas: aba_padrao_salva = todas_abas[0]

lembrar_aba_ligado = cfg.get('lembrar_aba', True)

if 'aba_atual' not in st.session_state:
    if lembrar_aba_ligado:
        memoria = filtros.carregar_memoria()
        aba_cache = memoria.get("aba_atual", "")
        st.session_state.aba_atual = aba_cache if aba_cache in todas_abas else aba_padrao_salva
    else: st.session_state.aba_atual = aba_padrao_salva

if st.session_state.aba_atual not in todas_abas: st.session_state.aba_atual = todas_abas[0]

# ==========================================
# 3. CABEÇALHO GLOBAL CONDICIONAL E POP-UP ADMIN
# ==========================================
@st.dialog("⚖️ Central de Correções", width="large")
def abrir_central_correcoes(admin_nome):
    st.markdown("### ⚖️ Gestão de Correções de Produção")
    tab_pend, tab_manual = st.tabs(["Fila de Aprovações", "Correção Direta por ID"])
    
    with tab_pend:
        pendentes = banco.obter_solicitacoes_pendentes()
        if not pendentes:
            st.success("🎉 Nenhuma solicitação pendente no momento.")
        else:
            for p in pendentes:
                prod_info = p.get('producao_diaria', {})
                if isinstance(prod_info, list) and len(prod_info) > 0: prod_info = prod_info[0]
                nome_peca = prod_info.get('nome_peca', 'Desconhecida')
                setor = prod_info.get('setor', '')
                maq = prod_info.get('maquina', '')
                
                try: data_f = datetime.strptime(p['data_solicitacao'], "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M")
                except: data_f = p['data_solicitacao']
                
                st.markdown(f"**Registro #ID:** {p['id_producao']} | **Peça:** {nome_peca} ({setor} - {maq})")
                st.markdown(f"**Operador:** {p['operador_solicitante']} | **Data do Pedido:** {data_f}")
                st.markdown(f"<h4 style='color:#e74c3c; margin:0; font-size:16px;'>Quantidade Atual: {p['qtd_antiga']}</h4>", unsafe_allow_html=True)
                st.markdown(f"<h4 style='color:#27ae60; margin:0 0 10px 0; font-size:16px;'>Quantidade Solicitada: {p['qtd_nova']}</h4>", unsafe_allow_html=True)
                
                if p.get('motivo'):
                    st.info(f"**Motivo:** {p['motivo']}")
                
                c1, c2 = st.columns(2)
                if c1.button("✅ Aprovar e Corrigir", key=f"apr_{p['id']}", type="primary", use_container_width=True):
                    banco.aprovar_solicitacao(p['id'], p['id_producao'], p['qtd_nova'], admin_nome)
                    st.rerun()
                if c2.button("❌ Recusar Pedido", key=f"rec_{p['id']}", use_container_width=True):
                    banco.recusar_solicitacao(p['id'], admin_nome)
                    st.rerun()
                st.markdown("<hr style='opacity: 0.2;'>", unsafe_allow_html=True)
                
    with tab_manual:
        st.markdown("Busque um ID de produção para conferir os dados antes de fazer a alteração.")
        
        # Variável de estado para guardar o registro encontrado na busca
        if "registro_busca_manual" not in st.session_state:
            st.session_state.registro_busca_manual = None

        col_busca1, col_busca2 = st.columns([7, 3])
        with col_busca1:
            id_busca_str = st.text_input("Digite o ID do Registro:", value="", placeholder="Ex: 15482", key="input_id_busca")
        with col_busca2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔍 Buscar Registro", use_container_width=True):
                if id_busca_str.strip().isdigit():
                    id_busca = int(id_busca_str.strip())
                    reg_encontrado = banco.obter_registro_por_id(id_busca)
                    if reg_encontrado:
                        st.session_state.registro_busca_manual = reg_encontrado
                    else:
                        st.session_state.registro_busca_manual = None
                        st.error("❌ Registro não encontrado. Verifique o ID.")
                else:
                    st.error("⚠️ Por favor, digite um ID numérico válido.")

        # Se encontrou o registro, exibe a "Ficha Cadastral" e libera os campos de alteração
        if st.session_state.registro_busca_manual:
            reg = st.session_state.registro_busca_manual
            
            # Converte a data para padrão brasileiro, se possível
            data_reg = reg.get('data_registro', '')
            try: data_reg_br = datetime.strptime(data_reg, "%Y-%m-%d").strftime("%d/%m/%Y")
            except: data_reg_br = data_reg

            st.markdown("<hr style='opacity: 0.2; margin: 15px 0;'>", unsafe_allow_html=True)
            st.markdown("<h4 style='color: #2980b9; margin-bottom: 10px;'>📄 Dados do Registro Encontrado</h4>", unsafe_allow_html=True)
            
            # Caixa de informações com quebra de linha para cada informação (Mais legível)
            html_info = f"""
            <div style="background-color: #eaf2f8; padding: 15px; border-radius: 8px; border: 1px solid #bce0fd; color: #2c3e50; font-size: 15px; line-height: 1.8; margin-bottom: 15px;">
                <b>ID:</b> {reg.get('id')}<br>
                <b>Setor:</b> {reg.get('setor')}<br>
                <b>Máquina:</b> {reg.get('maquina')}<br>
                <b>Peça:</b> {reg.get('nome_peca')}<br>
                <b>Código da Peça:</b> {reg.get('cod_peca')}<br>
                <b>Operador:</b> {reg.get('operador')}<br>
                <b>Data:</b> {data_reg_br}<br>
                <b>Horário:</b> {reg.get('das')} às {reg.get('as_hora')}<br>
                <b>Quantidade Registrada:</b> <span style="color: #e74c3c; font-weight: bold;">{reg.get('quantidade')}</span>
            </div>
            """
            st.markdown(html_info, unsafe_allow_html=True)
            
            st.markdown("#### ✏️ Alteração e Auditoria")
            
            # Puxa a quantidade atual e a coloca em um campo de texto limpo
            qtd_atual = ""
            try: qtd_atual = str(int(float(reg.get('quantidade', 0))))
            except: pass

            nova_qtd_m_str = st.text_input("Nova Quantidade Correta:", value=qtd_atual)
            motivo_m = st.text_input("Motivo da Alteração:")
            
            if st.button("✅ Corrigir Imediatamente", type="primary", use_container_width=True):
                if nova_qtd_m_str.strip().isdigit():
                    nova_qtd_m = int(nova_qtd_m_str.strip())
                    if motivo_m:
                        sucesso, msg = banco.corrigir_registro_manual(reg['id'], nova_qtd_m, motivo_m, admin_nome)
                        if sucesso:
                            st.success("✅ Registro corrigido com sucesso!")
                            st.session_state.registro_busca_manual = None  # Limpa a tela após o sucesso
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.warning("⚠️ Informe um motivo para a auditoria antes de confirmar.")
                else:
                    st.error("⚠️ A quantidade precisa ser um número inteiro válido.")

if st.session_state.aba_atual != "📱 Chão de Fábrica":
    c1, c2 = st.columns([8, 2])
    with c1:
        logo_b64 = cfg.get('logo_base64', None)
        if logo_b64:
            st.markdown(f'<div class="logo-container"><img src="data:image/png;base64,{logo_b64}" class="logo-responsiva"><h1 class="titulo-responsivo">{titulo_app}</h1></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="logo-container"><h1 class="titulo-responsivo">🏭 {titulo_app}</h1></div>', unsafe_allow_html=True)
    with c2:
        col_ola, col_sino = st.columns([7, 3])
        with col_ola:
            st.markdown(f"<div style='text-align: right; color: #7f8c8d; font-size: 14px; margin-top: 5px;'>👤 Olá, <b>{usuario_atual['nome']}</b></div>", unsafe_allow_html=True)
        with col_sino:
            tem_acesso_correcoes = is_admin or "🔔 Central de Correções" in abas_permitidas_str
            
            if tem_acesso_correcoes:
                pendentes = banco.obter_solicitacoes_pendentes()
                qtd_pendentes = len(pendentes) if pendentes else 0
                
                tipo_botao = "primary" if qtd_pendentes > 0 else "secondary"
                
                if st.button(f"🔔 {qtd_pendentes}", key="btn_sino_correcoes", help="Central de Correções", type=tipo_botao):
                    abrir_central_correcoes(usuario_atual['nome'])

        if st.button("🚪 Sair do Sistema", use_container_width=True):
            st.session_state['usuario_logado'] = None
            try: st.query_params.clear()
            except: st.experimental_set_query_params()
            st.rerun()

    if modo_manutencao:
        st.markdown("""<div style='background-color:#e74c3c; color:white; padding:8px 15px; border-radius:5px; text-align:center; font-weight:bold; margin-top:10px; margin-bottom:10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>⚠️ ATENÇÃO: O MODO MANUTENÇÃO ESTÁ ATIVADO. OPERADORES ESTÃO BLOQUEADOS.</div>""", unsafe_allow_html=True)

    st.markdown("<hr style='margin-top: 5px; margin-bottom: 10px; opacity: 0.2;'>", unsafe_allow_html=True)

# ==========================================
# 4. APLICAÇÃO E ROTEAMENTO
# ==========================================
if st.session_state.aba_atual not in ["📱 Chão de Fábrica", "🔴 Ao Vivo", "🎯 Painel de OPs", "🏆 Desempenho", "⚙️ Configurações", "👥 Controle de Acessos", "📦 Produtos", "📦 Caixas"]:
    filtros.renderizar_barra_superior(df_nuvem)
    filtros_selecionados = filtros.obter_filtros_atuais()
    st.markdown("<hr style='margin-top: 10px; margin-bottom: 20px; opacity: 0.2;'>", unsafe_allow_html=True)
else:
    filtros_selecionados = filtros.obter_filtros_atuais()
    if st.session_state.aba_atual == "🔴 Ao Vivo":
        st.markdown(f"<div style='text-align:right; margin-bottom:15px;'><span style='background:#f1f1f1; padding:5px 15px; border-radius:5px;'>Filtro Atual: <b>{filtros_selecionados['setor']}</b></span></div>", unsafe_allow_html=True)

idx_atual = todas_abas.index(st.session_state.aba_atual)

if len(todas_abas) > 1:
    escolha = option_menu(
        menu_title=None,
        options=todas_abas,
        default_index=idx_atual,
        orientation="horizontal",
        icons=[''] * len(todas_abas), 
        styles={
            "container": {"padding": "0!important", "background-color": "#f8f9fa", "border-radius": "5px", "margin-bottom": "25px"},
            "icon": {"display": "none"},
            "nav-link": {"font-size": "15px", "text-align": "center", "margin": "0px 5px", "white-space": "nowrap", "--hover-color": "#eee"},
            "nav-link-selected": {"background-color": "#2980b9"},
        }
    )
else:
    escolha = todas_abas[0]

if escolha != st.session_state.aba_atual:
    st.session_state.aba_atual = escolha
    filtros.salvar_memoria() 
    st.rerun()

registrar_heartbeat()

# ROTEADOR DE ABAS
if st.session_state.aba_atual == "📱 Chão de Fábrica": chao_de_fabrica.renderizar(df_nuvem, df_codigos)
elif st.session_state.aba_atual == "🔴 Ao Vivo": ao_vivo.renderizar(df_nuvem, df_codigos, filtros_selecionados)
elif st.session_state.aba_atual == "🎯 Painel de OPs": painel_ops.renderizar()
elif st.session_state.aba_atual == "🏆 Desempenho": desempenho.renderizar()
elif st.session_state.aba_atual == "💡 Plano de Ação": 
    if not df_nuvem.empty: plano_acao.renderizar(df_nuvem, df_codigos, filtros_selecionados, jornada)
    else: st.info("O banco de dados está vazio.")
elif st.session_state.aba_atual == "📈 Disponibilidade":
    if not df_nuvem.empty: disponibilidade.renderizar(df_nuvem, df_codigos, filtros_selecionados, jornada, meta)
    else: st.info("O banco de dados está vazio.")
elif st.session_state.aba_atual == "🔎 Ocorrências":
    if not df_nuvem.empty: ocorrencias.renderizar(df_nuvem, df_codigos, filtros_selecionados)
    else: st.info("O banco de dados está vazio.")
elif st.session_state.aba_atual == "📋 Apontamentos":
    if not df_nuvem.empty: apontamentos.renderizar(df_nuvem, df_codigos, filtros_selecionados)
    else: st.info("O banco de dados está vazio.")
elif st.session_state.aba_atual == "👥 Controle de Acessos":
    usuarios.renderizar(df_nuvem)
elif st.session_state.aba_atual == "📦 Produtos":
    produtos.renderizar()
elif st.session_state.aba_atual == "📦 Caixas": 
    caixas.renderizar()
elif st.session_state.aba_atual == "⚙️ Configurações":
    aba_interna, aba_config_abas, aba_estrutura, aba_produtos_linha, aba_importacoes, aba_cores, aba_backup, aba_gerenciador, aba_acessos = st.tabs(["⚙️ Ajustes Gerais", "📑 Config. de Abas", "🏭 Estrutura", "🟢 Produtos em Linha", "📥 Importação", "🎨 Cores", "💾 Backup", "🛠️ Gerenciador de Dados", "📡 Registro de Acessos"])
    
    with aba_interna: configuracoes.renderizar()
    with aba_config_abas: configuracoes.renderizar_config_abas()
    with aba_estrutura: configuracoes.renderizar_estrutura()
    with aba_produtos_linha: configuracoes.renderizar_produtos_linha()
    with aba_importacoes:
        importacao.renderizar_producao()
        st.markdown("<br>", unsafe_allow_html=True)
        importacao.renderizar_codigos()
    with aba_cores: configuracoes.renderizar_cores()
    with aba_backup: backups.renderizar()
    with aba_gerenciador: gerenciador.renderizar(df_nuvem)
    with aba_acessos: configuracoes.renderizar_registro_acessos()